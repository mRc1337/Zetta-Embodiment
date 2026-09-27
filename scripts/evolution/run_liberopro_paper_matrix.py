#!/usr/bin/env python3
"""Round-robin supervisor for the frozen 40-task LIBERO-Pro paper matrix.

All task campaigns retain independent append-only state and gate decisions;
only their host queue is shared. Run one queue worker separately per available
execution lane. This controller never consumes held-out seeds on its own.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from scripts.evolution.prepare_liberopro_paper_campaigns import PAPER_SETTINGS
from zetta.evolution.jsonio import read_json
from zetta.evolution.models import CampaignManifest, CampaignPhase
from zetta.evolution.store import CampaignStore
from zetta.evolution.supervisor import EvolutionSupervisor


def _campaigns(matrix_root: Path) -> list[tuple[dict[str, Any], Path]]:
    plan = read_json(matrix_root / "campaign-plan.json")
    rows = plan.get("campaigns")
    if not isinstance(rows, list) or len(rows) != 40:
        raise ValueError("paper matrix must contain 40 campaigns")
    expected = {
        (setting, task_id)
        for setting, _, _ in PAPER_SETTINGS
        for task_id in range(10)
    }
    if {(row.get("setting"), row.get("task_id")) for row in rows} != expected:
        raise ValueError("paper matrix setting/task coverage differs")
    result = []
    for row in rows:
        campaign = (matrix_root / row["campaign_root"]).resolve()
        if not campaign.is_relative_to(matrix_root):
            raise ValueError("campaign root escapes matrix")
        manifest = CampaignManifest.from_dict(read_json(campaign / "manifest.json"))
        if (
            manifest.code_commit != plan["code_commit"]
            or manifest.task != row["task"]
            or manifest.expected_rollouts != 50
            or manifest.expected_heldout != 20
        ):
            raise ValueError(f"frozen campaign contract differs: {row['task']}")
        result.append((row, campaign))
    return result


def sweep(matrix_root: Path, queue_root: Path, *, worker_host: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    errors: list[dict[str, str]] = []
    actions: dict[str, int] = {}
    for row, campaign in _campaigns(matrix_root):
        state_root = campaign / "state"
        store = CampaignStore(state_root)
        if not (state_root / "state.json").is_file():
            raise ValueError(f"campaign not initialized: {row['task']}")
        phase = CampaignPhase(store.state()["phase"])
        if phase == CampaignPhase.COMPLETE:
            counts["complete"] = counts.get("complete", 0) + 1
            continue
        supervisor = EvolutionSupervisor(
            campaign_root=state_root,
            queue_root=queue_root,
            worker_hosts=(worker_host,),
            tool_catalog=read_json(campaign / "tool-catalog.json"),
        )
        try:
            report = supervisor.step()
        except Exception as exc:
            # One campaign's provider/infrastructure error must not prevent
            # valid evidence from the other 39 campaigns being ingested.
            errors.append({"task": row["task"], "error": f"{type(exc).__name__}: {exc}"})
            continue
        action = str(report.get("action"))
        actions[action] = actions.get(action, 0) + 1
        if action == "rollout_blocked_on_infrastructure":
            errors.append({"task": row["task"], "error": action})
        next_phase = CampaignPhase(store.state()["phase"])
        counts[next_phase.value] = counts.get(next_phase.value, 0) + 1
    return {"campaigns": 40, "phases": counts, "actions": actions, "errors": errors}


def resume_paused_task2(queue_root: Path, replay_state_root: Path, *, worker_host: str) -> int:
    """Release task2 jobs only after the competing replay campaign is terminal."""

    paused = queue_root / "pending/paused_task2"
    jobs = sorted(paused.glob("job-*.json")) if paused.is_dir() else []
    if not jobs:
        return 0
    replay = CampaignStore(replay_state_root)
    if CampaignPhase(replay.state()["phase"]) != CampaignPhase.COMPLETE:
        return 0
    active = queue_root / "pending" / worker_host
    active.mkdir(parents=True, exist_ok=True)
    for path in jobs:
        payload = read_json(path)
        if payload.get("job", {}).get("task") != "libero_10_swap/task2":
            raise ValueError(f"paused queue contains a non-task2 job: {path.name}")
        if (active / path.name).exists():
            raise ValueError(f"paused task2 job already active: {path.name}")
    for path in jobs:
        path.rename(active / path.name)
    return len(jobs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--queue-root", type=Path)
    parser.add_argument("--worker-host", default="gpu3")
    parser.add_argument(
        "--resume-paused-task2-after",
        type=Path,
        help="replay campaign state root; release paused matrix task2 jobs only after it completes",
    )
    parser.add_argument("--poll-s", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_s < 0 or not args.worker_host:
        parser.error("poll interval and worker host must be valid")
    root = args.matrix_root.resolve()
    queue = (args.queue_root or root / "queue").resolve()
    while True:
        released = (
            resume_paused_task2(
                queue, args.resume_paused_task2_after.resolve(), worker_host=args.worker_host
            )
            if args.resume_paused_task2_after is not None
            else 0
        )
        report = sweep(root, queue, worker_host=args.worker_host)
        report["resumed_task2_jobs"] = released
        print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        if report["phases"].get("complete", 0) == 40:
            return 0
        if args.once:
            return 0
        time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
