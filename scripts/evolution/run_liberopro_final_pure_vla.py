#!/usr/bin/env python3
"""Run the final pure-VLA control on all 40 tasks after evolution ends.

This evaluation-only lane is opened only after all 40 task evolutions are
terminal. It never invokes clustering, diagnosis, proposal, or promotion.
Re-running the command ingests terminal queue envelopes and enqueues only
missing infrastructure attempts under the original 1--20 seed/RNG schedule.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from scripts.evolution.run_liberopro_paper_matrix import _campaigns, _effective_phase
from zetta.evolution.campaign import enqueue_missing_rollouts, ingest_queue_results
from zetta.evolution.jsonio import read_json
from zetta.evolution.models import CampaignManifest, CampaignPhase
from zetta.evolution.store import CampaignStore

EVALUATION_SCOPE = "final_pure_vla_test"


def evaluation_root(matrix_root: Path, row: dict[str, Any]) -> Path:
    return matrix_root / "final-pure-vla" / row["setting_slug"] / f"task-{row['task_id']:02d}"


def _needs_final_baseline(campaign: Path) -> bool:
    state_root = campaign / "state"
    state = read_json(state_root / "state.json")
    if state.get("phase") != CampaignPhase.COMPLETE.value:
        raise ValueError("source task is not terminal")
    continuation = state_root / "analysis/generation-continuation.json"
    if continuation.is_file():
        handoff = read_json(continuation)
        if (
            state.get("current_bundle_sha256")
            != handoff.get("promoted_bundle_sha256")
            or state.get("candidate_sha256") is not None
        ):
            raise ValueError("promoted source task has an inconsistent handoff")
        return True
    if state.get("current_bundle_sha256") is not None:
        raise ValueError("uncontinued source task has an active bundle")
    if state.get("candidate_sha256") is not None:
        raise ValueError("uncontinued source task has an unresolved candidate")
    if (state_root / "ledgers/promotions.jsonl").is_file():
        if (state_root / "ledgers/promotions.jsonl").read_text(encoding="utf-8").strip():
            raise ValueError("uncontinued source task has a promotion ledger")
    return True


def _evaluation_manifest(campaign: Path) -> CampaignManifest:
    source = CampaignManifest.from_dict(read_json(campaign / "manifest.json"))
    if (
        source.generation != 0
        or source.baseline_mode != "strict_pure_vla"
        or source.active_bundle_sha256 is not None
        or source.heldout_seeds != tuple(range(1, 21))
    ):
        raise ValueError("final pure-VLA source is not the frozen generation-0 baseline")
    controls = source.rollout_seeds[:20]
    policy_rng = {
        str(seed): source.policy_rng_by_seed[str(seed)]
        for seed in (*source.heldout_seeds, *controls)
    }
    runtime = {
        **source.runtime,
        "evaluation_scope": EVALUATION_SCOPE,
        "evaluation_source_manifest_sha256": source.sha256,
        "rollout_requires_api": False,
    }
    return replace(
        source,
        campaign_id=f"{source.campaign_id}-final-pure-vla-test",
        rollout_seeds=source.heldout_seeds,
        heldout_seeds=controls,
        policy_rng_by_seed=policy_rng,
        expected_rollouts=20,
        expected_heldout=20,
        initial_logical_slots=1,
        continuous_logical_slots=1,
        maximum_logical_slots=1,
        maximum_api_concurrency=1,
        runtime=runtime,
    )


def step(matrix_root: Path, queue_root: Path, *, worker_host: str) -> dict[str, Any]:
    """Idempotently advance only final pure-VLA test episodes."""

    matrix_root = matrix_root.resolve()
    queue_root = queue_root.resolve()
    campaigns = _campaigns(matrix_root)
    unfinished = [
        row["task"]
        for row, campaign in campaigns
        if _effective_phase(campaign / "state", matrix_root) != CampaignPhase.COMPLETE
    ]
    if unfinished:
        return {
            "status": "waiting_for_evolution",
            "unfinished_tasks": len(unfinished),
            "prepared_tasks": 0,
        }
    prepared = 0
    complete = 0
    blocked: list[str] = []
    for row, campaign in campaigns:
        if not _needs_final_baseline(campaign):
            continue
        manifest = _evaluation_manifest(campaign)
        root = evaluation_root(matrix_root, row)
        store = CampaignStore(root)
        store.initialize(manifest)
        ingest_queue_results(campaign_root=root, queue_root=queue_root)
        valid = int(store.status()["episodes"]["valid"])
        if valid == 20:
            complete += 1
            continue
        enqueue = enqueue_missing_rollouts(
            campaign_root=root,
            queue_root=queue_root,
            worker_hosts=(worker_host,),
        )
        prepared += 1
        if enqueue["blocked"]:
            blocked.append(row["task"])
    return {
        "status": "blocked_on_infrastructure" if blocked else "running" if prepared else "complete",
        "prepared_tasks": prepared,
        "complete_tasks": complete,
        "blocked_tasks": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--queue-root", type=Path)
    parser.add_argument("--worker-host", default="gpu3")
    parser.add_argument("--watch", action="store_true", help="wait for all evolutions, then run final tests")
    parser.add_argument("--poll-s", type=float, default=300.0)
    args = parser.parse_args()
    if args.poll_s <= 0:
        parser.error("poll interval must be positive")
    root = args.matrix_root.resolve()
    queue = (args.queue_root or root / "queue").resolve()
    while True:
        report = step(root, queue, worker_host=args.worker_host)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        if report["status"] == "blocked_on_infrastructure":
            return 4
        if report["status"] == "complete" or not args.watch:
            return 0
        time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
