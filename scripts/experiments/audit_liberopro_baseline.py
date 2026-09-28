#!/usr/bin/env python3
# Copyright (c) 2026 Zetta Contributors
"""Read-only audit of generation-0 LIBERO-Pro pure-VLA development rollouts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


VIDEOS = (
    "episode_agentview.mp4",
    "episode_agentview_wrist.mp4",
    "episode_agentview_multiview.mp4",
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _flag(command: list[str], name: str) -> str:
    positions = [i for i, item in enumerate(command) if item == name]
    if len(positions) != 1 or positions[0] + 1 >= len(command):
        raise ValueError(f"expected one {name} flag")
    return command[positions[0] + 1]


def _inside(root: Path, value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"evidence path escapes matrix: {path}")
    return path


def audit(matrix_root: Path) -> dict[str, Any]:
    root = matrix_root.resolve()
    plan_path = root / "campaign-plan.json"
    plan = _read(plan_path)
    rows = {row["task"]: row for row in plan["campaigns"]}
    if len(rows) != 40 or len(plan["campaigns"]) != 40:
        raise ValueError("paper baseline requires 40 unique tasks")
    expected_count = int(plan["development"]["seeds_per_task"])
    if expected_count != 50:
        raise ValueError("paper baseline requires 50 development seeds per task")
    manifests: dict[str, dict[str, Any]] = {}
    for row in rows.values():
        manifest = _read(root / row["campaign_root"] / "manifest.json")
        if (
            manifest.get("code_commit") != plan["code_commit"]
            or manifest.get("task") != row["task"]
            or manifest.get("rollout_seeds") != row["development_seeds"]
            or manifest.get("heldout_seeds") != row["heldout_seeds"]
        ):
            raise ValueError(f"frozen manifest differs for {row['task']}")
        manifests[row["task"]] = manifest

    completed_root = root / "queue" / "completed"
    counts: Counter[str] = Counter()
    successes: Counter[str] = Counter()
    seen: set[tuple[str, int]] = set()
    issues: list[str] = []
    scanned = 0
    for envelope_path in sorted(completed_root.glob("*/job-*.json")):
        envelope = _read(envelope_path)
        job = envelope.get("job")
        if not isinstance(job, dict) or not str(job.get("logical_id", "")).startswith(
            "g0000-rollout-"
        ):
            continue
        scanned += 1
        try:
            task = str(job["task"])
            row = rows[task]
            seed = int(job["seed"])
            rng = int(job["policy_rng"])
            command = [str(value) for value in job["command"]]
            output = _inside(root, str(job["output_dir"]))
            record = _inside(root, str(job["result_file"]))
            episode = _read(record)
            horizon = _read(output / "evaluation-horizon.json")
            errors: list[str] = []
            if envelope.get("kind") != "rollout_terminal" or envelope.get("success") is not True:
                errors.append("queue_terminal")
            if episode.get("status") != "valid":
                errors.append("episode_invalid")
            if type(episode.get("success")) is not bool:
                errors.append("official_success_missing")
            if int(job.get("generation", 0)) != 0:
                errors.append("not_generation_zero")
            if episode.get("seed") != seed or episode.get("policy_rng") != rng:
                errors.append("episode_seed_rng")
            if seed not in row["development_seeds"] or seed in row["heldout_seeds"]:
                errors.append("seed_partition")
            if row["policy_rng_by_seed"].get(str(seed)) != rng:
                errors.append("frozen_policy_rng")
            if (task, seed) in seen:
                errors.append("duplicate_task_seed")
            seen.add((task, seed))
            if (
                _flag(command, "--task") != task
                or int(_flag(command, "--seed")) != seed
                or int(_flag(command, "--policy-rng")) != rng
                or _flag(command, "--baseline-mode") != "strict_pure_vla"
                or _flag(command, "--bundle") != "none"
            ):
                errors.append("command_identity_or_mode")
            frozen_command = manifests[task].get("runtime", {}).get("rollout_command", [])
            if len(frozen_command) < 2 or command[:2] != frozen_command[:2]:
                errors.append("rollout_runner_lineage")
            expected_horizon = row["evaluation_horizon"]
            if (
                horizon != expected_horizon
                or int(_flag(command, "--max-actions"))
                != expected_horizon["policy_action_horizon"]
                or int(_flag(command, "--wait-steps"))
                != expected_horizon["wait_steps"]
            ):
                errors.append("official_horizon")
            if any(
                not (output / "videos" / name).is_file()
                or (output / "videos" / name).stat().st_size == 0
                for name in VIDEOS
            ):
                errors.append("video_evidence")
            if not (output / "latency" / "summary.json").is_file():
                errors.append("latency_evidence")
            if errors:
                issues.append(f"{envelope_path.name}: {','.join(errors)}")
            else:
                counts[task] += 1
                successes[task] += int(episode.get("success") is True)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            issues.append(f"{envelope_path.name}: {type(exc).__name__}: {exc}")

    missing = {
        task: expected_count - counts[task]
        for task in sorted(rows)
        if counts[task] != expected_count
    }
    return {
        "schema_version": 1,
        "matrix_root": str(root),
        "code_commit": plan["code_commit"],
        "plan_file_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "expected_tasks": 40,
        "expected_development_episodes": 40 * expected_count,
        "scanned_completed_baseline_envelopes": scanned,
        "verified_episodes": sum(counts.values()),
        "verified_tasks_with_evidence": sum(count > 0 for count in counts.values()),
        "official_successes_in_verified_episodes": sum(successes.values()),
        "per_task_verified_count": dict(sorted(counts.items())),
        "per_task_official_success_count": dict(sorted(successes.items())),
        "remaining_by_task": missing,
        "issue_count": len(issues),
        "issues": issues[:50],
        "complete": not issues and not missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="exit 3 while any of the 2000 development baseline episodes is missing",
    )
    args = parser.parse_args()
    report = audit(args.matrix_root)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if report["issue_count"]:
        return 2
    return 3 if args.require_complete and not report["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
