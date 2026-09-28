# Copyright (c) 2026 Zetta Contributors
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.experiments.audit_liberopro_baseline import _flag, audit


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _matrix(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "matrix"
    rows = []
    horizon = {"policy_action_horizon": 300, "wait_steps": 10}
    for index in range(40):
        task = f"suite/task{index}"
        campaign_root = f"campaigns/task-{index:02d}"
        row = {
            "task": task,
            "campaign_root": campaign_root,
            "development_seeds": [100 + index],
            "heldout_seeds": list(range(1, 21)),
            "policy_rng_by_seed": {str(100 + index): 200 + index},
            "evaluation_horizon": horizon,
        }
        rows.append(row)
        _write(
            root / campaign_root / "manifest.json",
            {
                "code_commit": "a" * 40,
                "task": task,
                "rollout_seeds": row["development_seeds"],
                "heldout_seeds": row["heldout_seeds"],
                "runtime": {"rollout_command": ["python", "runner.py"]},
            },
        )
    _write(
        root / "campaign-plan.json",
        {
            "code_commit": "a" * 40,
            "development": {"seeds_per_task": 50},
            "campaigns": rows,
        },
    )
    output = root / "campaigns/task-00/state/attempts/g0000-rollout-000/attempt-000"
    _write(output / "episode_record.json", {"status": "valid", "success": True, "seed": 100, "policy_rng": 200})
    _write(output / "evaluation-horizon.json", horizon)
    _write(output / "latency/summary.json", {"episode_end_to_end": 1.0})
    for name in (
        "episode_agentview.mp4",
        "episode_agentview_wrist.mp4",
        "episode_agentview_multiview.mp4",
    ):
        path = output / "videos" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
    envelope = root / "queue/completed/gpu3/job-1.json"
    _write(
        envelope,
        {
            "kind": "rollout_terminal",
            "success": True,
            "job": {
                "logical_id": "g0000-rollout-000",
                "task": "suite/task0",
                "seed": 100,
                "policy_rng": 200,
                "output_dir": str(output),
                "result_file": str(output / "episode_record.json"),
                "command": [
                    "python", "runner.py", "--task", "suite/task0", "--seed", "100",
                    "--policy-rng", "200", "--baseline-mode", "strict_pure_vla",
                    "--bundle", "none", "--max-actions", "300", "--wait-steps", "10",
                ],
            },
        },
    )
    return root, envelope


def test_audit_baseline_validates_one_development_episode(tmp_path: Path) -> None:
    root, _ = _matrix(tmp_path)

    report = audit(root)

    assert report["scanned_completed_baseline_envelopes"] == 1
    assert report["verified_episodes"] == 1
    assert report["official_successes_in_verified_episodes"] == 1
    assert report["issue_count"] == 0
    assert report["complete"] is False


def test_audit_baseline_rejects_rng_mismatch(tmp_path: Path) -> None:
    root, envelope = _matrix(tmp_path)
    payload = json.loads(envelope.read_text(encoding="utf-8"))
    payload["job"]["policy_rng"] = 999
    _write(envelope, payload)

    report = audit(root)

    assert report["verified_episodes"] == 0
    assert report["issue_count"] == 1
    assert "frozen_policy_rng" in report["issues"][0]


def test_audit_flag_rejects_ambiguous_values() -> None:
    with pytest.raises(ValueError, match="expected one"):
        _flag(["--seed", "1", "--seed", "2"], "--seed")
