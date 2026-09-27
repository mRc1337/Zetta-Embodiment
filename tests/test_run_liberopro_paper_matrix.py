"""The matrix controller preserves frozen jobs while a task2 replay runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evolution import run_liberopro_paper_matrix as runner


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
