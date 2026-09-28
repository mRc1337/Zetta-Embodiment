#!/usr/bin/env python3
"""Evaluate each terminal promoted harness on seeds 1--20, after evolution.

The pure-VLA controls run in a separate final-test lane. Tasks without a
promotion reuse their pure-VLA result; this runner never proposes or promotes.
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
from zetta.evolution.jsonio import canonical_sha256, read_json
from zetta.evolution.models import CampaignManifest, CampaignPhase
from zetta.evolution.store import CampaignStore

EVALUATION_SCOPE = "final_harness_test"
TEST_SEEDS = tuple(range(1, 21))


def evaluation_root(matrix_root: Path, row: dict[str, Any]) -> Path:
    return matrix_root / "final-harness" / row["setting_slug"] / f"task-{row['task_id']:02d}"


def _terminal_manifest(campaign: Path, matrix_root: Path) -> CampaignManifest:
    current = (campaign / "state").resolve()
    seen: set[Path] = set()
    while True:
        if current in seen or not current.is_relative_to(campaign.resolve()):
            raise ValueError("harness lineage escapes task campaign or cycles")
        seen.add(current)
        store = CampaignStore(current)
        manifest = store.manifest()
        state = store.state()
        if state["phase"] != CampaignPhase.COMPLETE.value:
            raise ValueError("harness evolution has not terminated")
        continuation = current / "analysis/generation-continuation.json"
        if not continuation.is_file():
            return manifest
        handoff = read_json(continuation)
        child = Path(handoff["child_campaign_root"]).resolve()
        if (
            not child.is_relative_to(matrix_root.resolve())
            or not child.is_relative_to(campaign.resolve())
            or handoff.get("parent_manifest_sha256") != manifest.sha256
            or handoff.get("promoted_bundle_sha256") != state.get("current_bundle_sha256")
        ):
            raise ValueError("harness generation handoff changed")
        child_manifest = CampaignStore(child).manifest()
        if (
            handoff.get("child_manifest_sha256") != child_manifest.sha256
            or child_manifest.generation != manifest.generation + 1
            or child_manifest.active_bundle_sha256
            != handoff.get("promoted_bundle_sha256")
        ):
            raise ValueError("harness child manifest binding changed")
        current = child


def _evaluation_manifest(source: CampaignManifest) -> CampaignManifest:
    if (
        source.baseline_mode != "active_bundle"
        or source.active_bundle_sha256 is None
        or source.heldout_seeds != TEST_SEEDS
        or set(source.rollout_seeds) & set(TEST_SEEDS)
    ):
        raise ValueError("terminal source is not a frozen promoted harness")
    bundle_files = source.runtime.get("bundle_files_by_sha", {})
    bundle_path = bundle_files.get(source.active_bundle_sha256)
    if (
        not isinstance(bundle_path, str)
        or not Path(bundle_path).is_file()
        or canonical_sha256(read_json(Path(bundle_path)))
        != source.active_bundle_sha256
    ):
        raise ValueError("terminal harness bundle artifact is missing or changed")
    controls = source.rollout_seeds[:20]
    policy_rng = {
        str(seed): source.policy_rng_by_seed[str(seed)]
        for seed in (*TEST_SEEDS, *controls)
    }
    return replace(
        source,
        campaign_id=f"{source.campaign_id}-final-harness-test",
        rollout_seeds=TEST_SEEDS,
        heldout_seeds=controls,
        policy_rng_by_seed=policy_rng,
        expected_rollouts=20,
        expected_heldout=20,
        initial_logical_slots=1,
        continuous_logical_slots=1,
        maximum_logical_slots=1,
        maximum_api_concurrency=1,
        runtime={
            **source.runtime,
            "evaluation_scope": EVALUATION_SCOPE,
            "evaluation_source_manifest_sha256": source.sha256,
            "evaluation_source_bundle_sha256": source.active_bundle_sha256,
            "rollout_requires_api": True,
        },
    )


def step(matrix_root: Path, queue_root: Path, *, worker_host: str) -> dict[str, Any]:
    matrix_root = matrix_root.resolve()
    queue_root = queue_root.resolve()
    campaigns = _campaigns(matrix_root)
    unfinished = [
        row["task"]
        for row, campaign in campaigns
        if _effective_phase(campaign / "state", matrix_root) != CampaignPhase.COMPLETE
    ]
    if unfinished:
        return {"status": "waiting_for_evolution", "unfinished_tasks": len(unfinished)}
    prepared = 0
    complete = 0
    unpromoted = 0
    blocked: list[str] = []
    for row, campaign in campaigns:
        source = _terminal_manifest(campaign, matrix_root)
        if source.active_bundle_sha256 is None:
            if source.generation != 0:
                raise ValueError("unpromoted task has a nonzero generation")
            unpromoted += 1
            continue
        manifest = _evaluation_manifest(source)
        root = evaluation_root(matrix_root, row)
        store = CampaignStore(root)
        store.initialize(manifest)
        ingest_queue_results(campaign_root=root, queue_root=queue_root)
        if int(store.status()["episodes"]["valid"]) == 20:
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
        "unpromoted_tasks": unpromoted,
        "blocked_tasks": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--queue-root", type=Path)
    parser.add_argument("--worker-host", default="gpu3")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-s", type=float, default=300.0)
    args = parser.parse_args()
    if args.poll_s <= 0:
        parser.error("poll interval must be positive")
    root = args.matrix_root.resolve()
    queue = (args.queue_root or root / "queue").resolve()
    while True:
        result = step(root, queue, worker_host=args.worker_host)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        if result["status"] == "blocked_on_infrastructure":
            return 4
        if result["status"] == "complete" or not args.watch:
            return 0
        time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
