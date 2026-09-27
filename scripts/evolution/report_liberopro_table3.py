#!/usr/bin/env python3
"""Fail-closed, read-only Table 3 report from frozen LIBERO-Pro held-out gates.

Only the 20 paired test seeds of a completed generation-0 campaign are scored.
Development rollouts, incomplete gates, and non-pure-VLA parent arms never
contribute to a reported success rate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.evolution.prepare_liberopro_paper_campaigns import PAPER_SETTINGS
from zetta.evolution.jsonio import canonical_sha256, read_json
from zetta.evolution.models import EpisodeRecord


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing ledger: {path}")
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"non-object ledger row at {path}:{number}")
        rows.append(row)
    return rows


def _artifact(path_value: Any, *, campaign_root: Path) -> None:
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("held-out evidence path is missing")
    path = Path(path_value).resolve()
    if not path.is_relative_to(campaign_root.resolve()):
        raise ValueError("held-out evidence escapes its campaign")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("held-out evidence is missing or empty")


def _score_task(campaign_root: Path, row: dict[str, Any], code_commit: str) -> dict[str, Any]:
    manifest = read_json(campaign_root / "manifest.json")
    state = read_json(campaign_root / "state/state.json")
    if manifest.get("code_commit") != code_commit or state.get("phase") != "complete":
        raise ValueError("campaign code commit or terminal phase differs")
    if manifest.get("task") != row["task"] or manifest.get("generation") != 0:
        raise ValueError("campaign task or generation differs")
    if manifest.get("heldout_seeds") != list(range(1, 21)):
        raise ValueError("campaign lacks the fixed 1--20 held-out seeds")
    development = manifest.get("rollout_seeds")
    if (
        not isinstance(development, list)
        or len(development) != 50
        or len(set(development)) != 50
        or set(development) & set(range(1, 21))
        or development != row.get("development_seeds")
    ):
        raise ValueError("campaign development schedule is missing or changed")
    if set(manifest.get("policy_rng_by_seed", {})) != {
        str(seed) for seed in (*development, *range(1, 21))
    }:
        raise ValueError("campaign policy RNG schedule is incomplete")
    policy = manifest.get("runtime", {}).get("evolution_policy", {})
    if policy.get("heldout_mode") != "test" or policy.get("regression_scope") != "target_cluster":
        raise ValueError("campaign held-out or regression policy differs")

    gates = list((campaign_root / "state/candidates").glob("*/gates/heldout_20/plan.json"))
    if len(gates) != 1:
        raise ValueError(f"expected one completed held-out gate; found {len(gates)}")
    gate_root = gates[0].parent
    plan = read_json(gates[0])
    candidate_sha = gate_root.parent.parent.name
    if plan.get("kind") != "heldout_20" or plan.get("candidate_sha256") != candidate_sha:
        raise ValueError("held-out plan candidate identity differs")
    if plan.get("manifest_sha256") != canonical_sha256(manifest):
        raise ValueError("held-out plan manifest digest differs")
    if plan.get("parent_sha256") is not None:
        raise ValueError("held-out parent is not the pure-VLA baseline")
    pairs = plan.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != 20:
        raise ValueError("held-out plan does not contain exactly 20 pairs")
    expected: dict[str, tuple[int, int, str]] = {}
    for index, pair in enumerate(pairs):
        seed = index + 1
        if pair.get("pair_index") != index or pair.get("seed") != seed:
            raise ValueError("held-out pair order or seed differs")
        policy_rng = manifest["policy_rng_by_seed"][str(seed)]
        if pair.get("policy_rng") != policy_rng:
            raise ValueError("held-out policy RNG differs")
        for arm in ("parent", "candidate"):
            logical_id = pair.get("logical_ids", {}).get(arm)
            if not isinstance(logical_id, str) or logical_id in expected:
                raise ValueError("held-out logical arm is missing or duplicate")
            expected[logical_id] = (seed, policy_rng, arm)

    records = _jsonl(gate_root / "ledgers/valid.jsonl")
    if len(records) != 40:
        raise ValueError(f"held-out valid ledger has {len(records)} arms, expected 40")
    observed: set[str] = set()
    successes = {"parent": 0, "candidate": 0}
    for payload in records:
        record = EpisodeRecord.from_dict(payload)
        if record.logical_id in observed or record.logical_id not in expected:
            raise ValueError("held-out ledger contains a duplicate or unknown arm")
        observed.add(record.logical_id)
        seed, policy_rng, arm = expected[record.logical_id]
        bundle_sha = candidate_sha if arm == "candidate" else None
        if (
            record.status != "valid"
            or record.seed != seed
            or record.policy_rng != policy_rng
            or record.bundle_sha256 != bundle_sha
        ):
            raise ValueError("held-out arm violates its frozen plan")
        videos = record.artifact_index.get("videos")
        if not isinstance(videos, dict) or not videos:
            raise ValueError("held-out episode has no video evidence")
        for path in videos.values():
            _artifact(path, campaign_root=campaign_root)
        _artifact(record.artifact_index.get("latency_summary"), campaign_root=campaign_root)
        successes[arm] += int(record.success is True)

    decisions = [
        decision
        for decision in _jsonl(campaign_root / "state/ledgers/gates.jsonl")
        if decision.get("kind") == "heldout_20"
        and decision.get("candidate_sha256") == candidate_sha
    ]
    if len(decisions) != 1:
        raise ValueError("held-out decision is missing or ambiguous")
    decision = decisions[0]
    if (
        decision.get("paired_count") != 20
        or decision.get("parent_successes") != successes["parent"]
        or decision.get("candidate_successes") != successes["candidate"]
    ):
        raise ValueError("held-out decision contradicts valid episode evidence")
    return {
        "task_id": row["task_id"],
        "baseline_successes": successes["parent"],
        "zetta_successes": successes["candidate"],
        "episodes_per_method": 20,
        "baseline_rate_pct": 5.0 * successes["parent"],
        "zetta_rate_pct": 5.0 * successes["candidate"],
        "candidate_sha256": candidate_sha,
    }


def summarize(matrix_root: Path) -> dict[str, Any]:
    matrix_root = matrix_root.resolve()
    plan = read_json(matrix_root / "campaign-plan.json")
    rows = plan.get("campaigns")
    if not isinstance(rows, list) or len(rows) != 40:
        raise ValueError("matrix must contain exactly 40 task campaigns")
    expected = {
        (setting, task_id)
        for setting, _, _ in PAPER_SETTINGS
        for task_id in range(10)
    }
    if {(row.get("setting"), row.get("task_id")) for row in rows} != expected:
        raise ValueError("matrix setting/task coverage differs from Table 3")
    by_setting: dict[str, list[dict[str, Any]]] = {setting: [] for setting, _, _ in PAPER_SETTINGS}
    incomplete: list[dict[str, Any]] = []
    for row in rows:
        root = matrix_root / row["campaign_root"]
        try:
            by_setting[row["setting"]].append(_score_task(root, row, plan["code_commit"]))
        except (KeyError, TypeError, ValueError, FileNotFoundError) as exc:
            incomplete.append({"setting": row["setting"], "task_id": row["task_id"], "reason": str(exc)})
    if incomplete:
        return {
            "status": "incomplete",
            "completed_tasks": 40 - len(incomplete),
            "required_tasks": 40,
            "incomplete": incomplete,
        }
    settings = []
    for setting, _, _ in PAPER_SETTINGS:
        tasks = sorted(by_setting[setting], key=lambda task: task["task_id"])
        settings.append({
            "setting": setting,
            "tasks": tasks,
            "baseline_average_pct": sum(task["baseline_rate_pct"] for task in tasks) / 10,
            "zetta_average_pct": sum(task["zetta_rate_pct"] for task in tasks) / 10,
        })
    return {
        "status": "complete",
        "schema_version": "zetta-liberopro-table3-report-v1",
        "code_commit": plan["code_commit"],
        "episodes_per_task_method": 20,
        "settings": settings,
        "baseline_overall_macro_pct": sum(row["baseline_average_pct"] for row in settings) / 4,
        "zetta_overall_macro_pct": sum(row["zetta_average_pct"] for row in settings) / 4,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.matrix_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "complete" else 3


if __name__ == "__main__":
    raise SystemExit(main())
