#!/usr/bin/env python3
"""Report Table 3 only from post-evolution seeds 1--20 on all 40 tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.evolution.prepare_liberopro_paper_campaigns import PAPER_SETTINGS
from scripts.evolution.report_liberopro_table3 import (
    _jsonl,
    _lineage,
    _score_final_harness,
    _score_final_pure_vla,
    _verify_development_baseline,
    _verify_promotion_gates,
)
from zetta.evolution.jsonio import read_json


def _score_task(campaign_root: Path, row: dict[str, Any], code_commit: str) -> dict[str, Any]:
    nodes = _lineage(campaign_root, row, code_commit)
    initial = nodes[0][1]
    development = initial.get("rollout_seeds")
    if (
        not isinstance(development, list)
        or len(development) != 50
        or len(set(development)) != 50
        or set(development) & set(range(1, 21))
        or development != row.get("development_seeds")
    ):
        raise ValueError("campaign development schedule is missing or changed")
    if set(initial.get("policy_rng_by_seed", {})) != {
        str(seed) for seed in (*development, *range(1, 21))
    }:
        raise ValueError("campaign policy RNG schedule is incomplete")
    failures = _verify_development_baseline(campaign_root, initial, development)
    policy = initial.get("runtime", {}).get("evolution_policy", {})
    if policy.get("heldout_mode") != "test" or policy.get("regression_scope") != "target_cluster":
        raise ValueError("campaign held-out or regression policy differs")
    for node_root, _ in nodes:
        if list((node_root / "candidates").glob("*/gates/heldout*/plan.json")):
            raise ValueError("final test seeds were scheduled during evolution")
        gate_ledger = node_root / "ledgers/gates.jsonl"
        if gate_ledger.is_file() and any(
            row.get("kind") in {"heldout_10", "heldout_20", "heldout_50"}
            for row in _jsonl(gate_ledger)
        ):
            raise ValueError("final test seeds were measured during evolution")
    for source_root, source_manifest in nodes[:-1]:
        handoff = read_json(source_root / "analysis/generation-continuation.json")
        _verify_promotion_gates(
            source_root,
            source_manifest,
            handoff["promoted_bundle_sha256"],
            source_manifest.get("active_bundle_sha256"),
            require_heldout=False,
        )
    terminal_root, terminal_manifest = nodes[-1]
    terminal_state = read_json(terminal_root / "state.json")
    bundle_sha = terminal_manifest.get("active_bundle_sha256")
    if (
        terminal_state.get("candidate_sha256") is not None
        or terminal_state.get("current_bundle_sha256") != bundle_sha
    ):
        raise ValueError("terminal harness state differs from frozen manifest")
    baseline_successes = _score_final_pure_vla(
        campaign_root, row, initial, require_no_promotion=False
    )
    if bundle_sha is None:
        if len(nodes) != 1 or failures:
            raise ValueError(
                f"unresolved development failures ({failures}/50) "
                "with no validated recovery bundle"
            )
        zetta_successes = baseline_successes
    else:
        if len(nodes) == 1:
            raise ValueError("promoted harness has no generation continuation")
        zetta_successes = _score_final_harness(campaign_root, row, terminal_manifest)
    return {
        "task_id": row["task_id"],
        "baseline_successes": baseline_successes,
        "zetta_successes": zetta_successes,
        "episodes_per_method": 20,
        "baseline_rate_pct": 5.0 * baseline_successes,
        "zetta_rate_pct": 5.0 * zetta_successes,
        "candidate_sha256": bundle_sha,
        "final_generation": terminal_manifest["generation"],
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
        "schema_version": "zetta-liberopro-table3-final-report-v2",
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
