"""A recovery cannot be credited when paired actions drift before activation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.experiments.audit_paired_causal_prefix import audit


CANDIDATE = "c" * 64


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _gate(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    gate = state / "candidates" / CANDIDATE / "gates/same_seed"
    pairs = []
    records = []
    for seed in (21, 22):
        ids = {arm: f"pair-{seed}-{arm}" for arm in ("parent", "candidate")}
        pairs.append({"seed": seed, "policy_rng": seed + 1000, "logical_ids": ids})
        for arm, logical_id in ids.items():
            candidate = arm == "candidate"
            trace = state / f"{logical_id}-actions.jsonl"
            # Seed 21 first differs exactly when recovery activates at step 3.
            # Seed 22 has already drifted at step 2 before activation at 4.
            first_difference = 3 if seed == 21 else 2
            _write_jsonl(trace, [
                {
                    "step_index": step,
                    "action_sha256": ("b" if candidate and step >= first_difference else "a") * 64,
                }
                for step in range(1, 6)
            ])
            artifacts = {
                "actions": str(trace),
                "trajectory_index": {
                    "artifact_sha256": {
                        "actions": hashlib.sha256(trace.read_bytes()).hexdigest(),
                    },
                },
                "candidate_intervention": candidate,
                "initial_observation_identity": {
                    "state_sha256": f"{seed:064x}", "camera_sha256": {}
                },
            }
            if candidate:
                events = state / f"{logical_id}-recovery-events.jsonl"
                _write_jsonl(events, [{
                    "event": "activated",
                    "state": {"started_at_environment_step": 3 if seed == 21 else 4},
                }])
                artifacts["role1:recovery-events.jsonl"] = str(events)
            records.append({
                "episode_id": logical_id,
                "logical_id": logical_id,
                "generation": 0,
                "seed": seed,
                "policy_rng": seed + 1000,
                "bundle_sha256": CANDIDATE if candidate else None,
                "status": "valid",
                "success": candidate,
                "started_at": "2026-09-28T00:00:00Z",
                "finished_at": "2026-09-28T00:01:00Z",
                "elapsed_s": 60.0,
                "artifact_index": artifacts,
            })
    _write_json(gate / "plan.json", {
        "kind": "same_seed", "candidate_sha256": CANDIDATE,
        "parent_sha256": None, "pairs": pairs,
    })
    _write_jsonl(gate / "ledgers/valid.jsonl", records)
    return state


def test_audit_separates_aligned_rescue_from_pre_activation_drift(tmp_path: Path) -> None:
    result = audit(_gate(tmp_path), CANDIDATE)
    assert result["paired_count"] == 2
    assert result["candidate_wins"] == 2
    assert result["prefix_consistent_wins"] == 1
    assert result["pre_activation_drift_wins"] == 1
    assert result["details"][0]["first_action_divergence_step"] == 3
    assert result["details"][1]["first_action_divergence_step"] == 2


def test_audit_rejects_missing_paired_evidence(tmp_path: Path) -> None:
    state = _gate(tmp_path)
    valid = state / "candidates" / CANDIDATE / "gates/same_seed/ledgers/valid.jsonl"
    valid.write_text("\n".join(valid.read_text().splitlines()[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete or duplicate valid arms"):
        audit(state, CANDIDATE)


def test_audit_rejects_action_artifact_drift(tmp_path: Path) -> None:
    state = _gate(tmp_path)
    trace = state / "pair-21-candidate-actions.jsonl"
    trace.write_text(trace.read_text() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="immutable trajectory digest"):
        audit(state, CANDIDATE)
