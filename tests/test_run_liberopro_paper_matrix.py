"""The matrix controller preserves frozen jobs while a task2 replay runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evolution import run_liberopro_paper_matrix as runner


def test_sweep_skips_only_explicitly_paused_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paused_root = tmp_path / "paused"
    active_root = tmp_path / "active"
    for root in (paused_root, active_root):
        (root / "state").mkdir(parents=True)
        (root / "state/state.json").write_text(
            json.dumps({"phase": "rollout"}), encoding="utf-8"
        )
        (root / "tool-catalog.json").write_text("{}", encoding="utf-8")
    rows = [
        ({"task": "libero_10_swap/task5"}, paused_root),
        ({"task": "libero_goal_swap/task0"}, active_root),
    ]
    monkeypatch.setattr(runner, "_campaigns", lambda _root: rows)

    class FakeStore:
        def __init__(self, _root: Path) -> None:
            pass

        def state(self) -> dict[str, str]:
            return {"phase": "rollout"}

    calls: list[Path] = []

    class FakeSupervisor:
        def __init__(self, *, campaign_root: Path, **_kwargs: object) -> None:
            calls.append(campaign_root)

        def step(self) -> dict[str, str]:
            return {"action": "waiting_for_rollouts"}

    monkeypatch.setattr(runner, "CampaignStore", FakeStore)
    monkeypatch.setattr(runner, "EvolutionSupervisor", FakeSupervisor)
    report = runner.sweep(
        tmp_path,
        tmp_path / "queue",
        worker_host="gpu3",
        paused_tasks=frozenset({"libero_10_swap/task5"}),
    )
    assert calls == [active_root / "state"]
    assert report["actions"] == {"paused_task": 1, "waiting_for_rollouts": 1}
    assert report["phases"] == {"rollout": 2}


def test_resume_paused_task2_only_after_replay_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paused = tmp_path / "pending/paused_task2"
    paused.mkdir(parents=True)
    job = paused / "job-one.json"
    job.write_text(json.dumps({"job": {"task": "libero_10_swap/task2"}}), encoding="utf-8")
    state = {"phase": "rollout"}

    class FakeStore:
        def __init__(self, _root: Path) -> None:
            pass

        def state(self) -> dict[str, str]:
            return state

    monkeypatch.setattr(runner, "CampaignStore", FakeStore)
    assert runner.resume_paused_task2(tmp_path, tmp_path, worker_host="gpu3") == 0
    assert job.exists()
    state["phase"] = "complete"
    assert runner.resume_paused_task2(tmp_path, tmp_path, worker_host="gpu3") == 1
    assert not job.exists()
    assert (tmp_path / "pending/gpu3/job-one.json").is_file()
    assert runner.resume_paused_task2(tmp_path, tmp_path, worker_host="gpu3") == 0


def test_resume_paused_task2_rejects_other_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paused = tmp_path / "pending/paused_task2"
    paused.mkdir(parents=True)
    job = paused / "job-other.json"
    job.write_text(json.dumps({"job": {"task": "libero_10_swap/task3"}}), encoding="utf-8")

    class CompleteStore:
        def __init__(self, _root: Path) -> None:
            pass

        def state(self) -> dict[str, str]:
            return {"phase": "complete"}

    monkeypatch.setattr(runner, "CampaignStore", CompleteStore)
    with pytest.raises(ValueError, match="non-task2"):
        runner.resume_paused_task2(tmp_path, tmp_path, worker_host="gpu3")
    assert job.exists()
