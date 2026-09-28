#!/usr/bin/env python3
"""Read-only timing audit for a same-seed recovery gate.

This is a diagnostic, not a replacement for the frozen gate decision. An
unchanged action prefix through activation is necessary for a clean paired
intervention claim, but is not by itself proof that the intervention caused
the final success.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from zetta.evolution.jsonio import read_json
from zetta.evolution.models import EpisodeRecord


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing evidence: {path}")
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"non-object evidence at {path}:{number}")
        rows.append(value)
    return rows


def _path(value: Any, state_root: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("gate evidence path is missing")
    path = Path(value).resolve()
    if not path.is_relative_to(state_root.resolve()) or not path.is_file():
        raise ValueError(f"gate evidence is missing or outside campaign: {path}")
    return path


def _action_hashes(record: EpisodeRecord, state_root: Path) -> list[str]:
    rows = _jsonl(_path(record.artifact_index.get("actions"), state_root))
    result = []
    for index, row in enumerate(rows, 1):
        digest = row.get("action_sha256")
        if row.get("step_index") != index or not isinstance(digest, str) or not digest:
            raise ValueError("action evidence is not a sequential hashed trajectory")
        result.append(digest)
    if not result:
        raise ValueError("action evidence is empty")
    return result


def _first_action_divergence(candidate: list[str], parent: list[str]) -> int | None:
    return next(
        (index for index, (left, right) in enumerate(zip(candidate, parent), 1)
         if left != right),
        None,
    )


def _first_activation(record: EpisodeRecord, state_root: Path) -> int | None:
    value = record.artifact_index.get("role1:recovery-events.jsonl")
    if value is None:
        return None
    steps = []
    for row in _jsonl(_path(value, state_root)):
        if row.get("event") != "activated":
            continue
        step = row.get("state", {}).get("started_at_environment_step")
        if not isinstance(step, int) or isinstance(step, bool) or step < 1:
            raise ValueError("recovery activation has no physical step")
        steps.append(step)
    return min(steps) if steps else None


def audit(state_root: Path, candidate_sha256: str) -> dict[str, Any]:
    state_root = state_root.resolve()
    gate = state_root / "candidates" / candidate_sha256 / "gates/same_seed"
    plan = read_json(gate / "plan.json")
    if plan.get("candidate_sha256") != candidate_sha256 or plan.get("kind") != "same_seed":
        raise ValueError("same-seed plan does not bind candidate")
    records = [EpisodeRecord.from_dict(row) for row in _jsonl(gate / "ledgers/valid.jsonl")]
    by_id = {record.logical_id: record for record in records}
    pairs = plan.get("pairs")
    if not isinstance(pairs, list) or len(by_id) != len(records) or len(records) != 2 * len(pairs):
        raise ValueError("same-seed gate has incomplete or duplicate valid arms")
    details = []
    for pair in pairs:
        ids = pair.get("logical_ids", {})
        try:
            candidate = by_id[ids["candidate"]]
            parent = by_id[ids["parent"]]
        except (KeyError, TypeError) as exc:
            raise ValueError("same-seed gate is missing a paired arm") from exc
        if (
            candidate.seed != pair.get("seed") or parent.seed != pair.get("seed")
            or candidate.policy_rng != pair.get("policy_rng")
            or parent.policy_rng != pair.get("policy_rng")
            or candidate.status != "valid" or parent.status != "valid"
            or candidate.bundle_sha256 != candidate_sha256
            or parent.bundle_sha256 != plan.get("parent_sha256")
        ):
            raise ValueError("same-seed pair violates frozen seed, RNG, or bundle")
        candidate_identity = candidate.artifact_index.get("initial_observation_identity", {})
        parent_identity = parent.artifact_index.get("initial_observation_identity", {})
        if not isinstance(candidate_identity, dict) or not isinstance(parent_identity, dict):
            raise ValueError("same-seed pair lacks reset identity evidence")
        same_reset = (
            candidate_identity.get("state_sha256") is not None
            and candidate_identity.get("state_sha256") == parent_identity.get("state_sha256")
        )
        first_divergence = _first_action_divergence(
            _action_hashes(candidate, state_root), _action_hashes(parent, state_root)
        )
        first_activation = _first_activation(candidate, state_root)
        win = candidate.success is True and parent.success is False
        attested = candidate.artifact_index.get("candidate_intervention") is True
        prefix_consistent = bool(
            win and same_reset and attested and first_activation is not None
            and first_divergence is not None and first_divergence >= first_activation
        )
        details.append({
            "seed": candidate.seed,
            "candidate_win": win,
            "candidate_intervention": attested,
            "same_physical_reset": same_reset,
            "camera_hashes_match": candidate_identity.get("camera_sha256")
            == parent_identity.get("camera_sha256"),
            "first_activation_step": first_activation,
            "first_action_divergence_step": first_divergence,
            "prefix_consistent_win": prefix_consistent,
        })
    return {
        "candidate_sha256": candidate_sha256,
        "paired_count": len(details),
        "candidate_wins": sum(row["candidate_win"] for row in details),
        "prefix_consistent_wins": sum(row["prefix_consistent_win"] for row in details),
        "pre_activation_drift_wins": sum(
            row["candidate_win"] and row["first_activation_step"] is not None
            and row["first_action_divergence_step"] is not None
            and row["first_action_divergence_step"] < row["first_activation_step"]
            for row in details
        ),
        "details": details,
        "interpretation": "Prefix consistency is necessary, not sufficient, for causal attribution.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.state_root, args.candidate_sha256), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
