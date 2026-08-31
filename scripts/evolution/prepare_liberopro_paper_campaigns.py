#!/usr/bin/env python3
# Copyright (c) 2026 Zetta Contributors
"""Freeze the paper-faithful 4x10 LIBERO-Pro evaluation campaign matrix.

The matrix keeps development and final-test evidence separate: every task gets
50 deterministic-random development seeds outside 1--20, while seeds 1--20
are report-only held-out tests.  Each task is an independent, resumable Zetta
campaign with the official OpenPI horizon and per-episode latency recording.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from robots.libero.evolution_defaults import libero_horizon_contract  # noqa: E402
from robots.libero.latency import (  # noqa: E402
    DEFAULT_LATENCY_COMPONENTS,
    parse_latency_components,
)
from scripts.evolution.prepare_libero_campaign import (  # noqa: E402
    _parser as single_campaign_parser,
)
from scripts.evolution.prepare_libero_campaign import (  # noqa: E402
    prepare as prepare_campaign,
)
from zetta.evolution.jsonio import (  # noqa: E402
    atomic_write_json,
    canonical_sha256,
    file_sha256,
    read_json,
)
from zetta.evolution.schedule import preregister_seed_schedule  # noqa: E402


PAPER_SETTINGS = (
    ("Goal-T", "goal-t", "libero_goal_task"),
    ("Goal-S", "goal-s", "libero_goal_swap"),
    ("LIBERO-10-T", "libero-10-t", "libero_10_task"),
    ("LIBERO-10-S", "libero-10-s", "libero_10_swap"),
)
HELDOUT_SEEDS = tuple(range(1, 21))
DEVELOPMENT_SEED_COUNT = 50
TASKS_PER_SETTING = 10


def _case_master_seed(master_seed: int, suite: str, task_id: int) -> int:
    payload = f"{int(master_seed)}\0{suite}\0{int(task_id)}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & 0x7FFFFFFF


def probe_benchmark(runtime_python: Path) -> dict[str, Any]:
    """Read the installed benchmark once and return public task contracts."""

    suites = [suite for _, _, suite in PAPER_SETTINGS]
    program = f"""
import json
import re
from pathlib import Path
from liberopro.liberopro.benchmark import get_benchmark

rows = []
for suite_name in {suites!r}:
    suite = get_benchmark(suite_name)()
    tasks = []
    for task_id in range(suite.get_num_tasks()):
        task = suite.get_task(task_id)
        bddl = Path(suite.get_task_bddl_file_path(task_id)).read_text(encoding="utf-8")
        match = re.search(r"\\(:language\\s+([^)]+)\\)", bddl)
        language = match.group(1).strip() if match else task.language
        tasks.append({{
            "task_id": task_id,
            "task_name": task.name,
            "language": language,
            "init_state_count": len(suite.get_task_init_states(task_id)),
        }})
    rows.append({{
        "suite": suite_name,
        "task_count": suite.get_num_tasks(),
        "tasks": tasks,
    }})
print("ZETTA_LIBEROPRO_MATRIX=" + json.dumps({{"suites": rows}}, ensure_ascii=False))
"""
    completed = subprocess.run(
        [str(Path(os.path.abspath(runtime_python))), "-c", program],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise ValueError(f"LIBERO-Pro benchmark probe failed{suffix}")
    prefix = "ZETTA_LIBEROPRO_MATRIX="
    payload_line = next(
        (
            line
            for line in reversed(completed.stdout.splitlines())
            if line.startswith(prefix)
        ),
        None,
    )
    if payload_line is None:
        raise ValueError("LIBERO-Pro benchmark probe returned no matrix payload")
    payload = json.loads(payload_line[len(prefix) :])
    _validate_catalog(payload)
    return payload


def _validate_catalog(catalog: dict[str, Any]) -> None:
    expected_suites = {suite for _, _, suite in PAPER_SETTINGS}
    rows = catalog.get("suites")
    if not isinstance(rows, list):
        raise ValueError("benchmark catalog suites must be a list")
    by_suite = {row.get("suite"): row for row in rows if isinstance(row, dict)}
    if set(by_suite) != expected_suites:
        raise ValueError("benchmark catalog does not contain the four paper settings")
    for suite in sorted(expected_suites):
        row = by_suite[suite]
        tasks = row.get("tasks")
        if row.get("task_count") != TASKS_PER_SETTING or not isinstance(tasks, list):
            raise ValueError(f"{suite} must contain exactly 10 tasks")
        if [task.get("task_id") for task in tasks] != list(range(TASKS_PER_SETTING)):
            raise ValueError(f"{suite} task ids must be contiguous 0--9")
        for task in tasks:
            if int(task.get("init_state_count", 0)) < 1:
                raise ValueError(
                    f"{suite}/task{task.get('task_id')} has no init states"
                )
            if (
                not isinstance(task.get("language"), str)
                or not task["language"].strip()
            ):
                raise ValueError(f"{suite}/task{task.get('task_id')} has no language")


def build_matrix_plan(
    *,
    catalog: dict[str, Any],
    code_commit: str,
    master_seed: int,
    runtime_url: str,
    runtime_policy_id: str,
    latency_components: str | None = None,
) -> dict[str, Any]:
    """Build the deterministic, secret-free matrix contract."""

    _validate_catalog(catalog)
    if re.fullmatch(r"[0-9a-f]{40}", code_commit) is None:
        raise ValueError("code_commit must be a full lowercase Git SHA")
    components = sorted(parse_latency_components(latency_components))
    by_suite = {row["suite"]: row for row in catalog["suites"]}
    campaigns: list[dict[str, Any]] = []
    for setting, setting_slug, suite in PAPER_SETTINGS:
        task_rows = by_suite[suite]["tasks"]
        for task in task_rows:
            task_id = int(task["task_id"])
            task_key = f"{suite}/task{task_id}"
            case_seed = _case_master_seed(master_seed, suite, task_id)
            development, heldout, policy_rng = preregister_seed_schedule(
                master_seed=case_seed,
                task=task_key,
                rollout_count=DEVELOPMENT_SEED_COUNT,
                heldout_count=len(HELDOUT_SEEDS),
                heldout_seeds=HELDOUT_SEEDS,
            )
            horizon = libero_horizon_contract(suite)
            campaigns.append(
                {
                    "setting": setting,
                    "setting_slug": setting_slug,
                    "suite": suite,
                    "task_id": task_id,
                    "task": task_key,
                    "task_name": task["task_name"],
                    "task_language": task["language"],
                    "init_state_count": int(task["init_state_count"]),
                    "campaign_id": f"liberopro-paper-v1-{setting_slug}-t{task_id:02d}",
                    "campaign_root": f"campaigns/{setting_slug}/task-{task_id:02d}",
                    "case_master_seed": case_seed,
                    "development_seeds": list(development),
                    "heldout_seeds": list(heldout),
                    "policy_rng_by_seed": policy_rng,
                    "schedule_sha256": canonical_sha256(
                        {
                            "development_seeds": development,
                            "heldout_seeds": heldout,
                            "policy_rng_by_seed": policy_rng,
                        }
                    ),
                    "evaluation_horizon": horizon,
                }
            )
    return {
        "schema_version": "zetta-liberopro-paper-campaign-matrix-v1",
        "paper": "arXiv:2608.16590",
        "protocol_section": "4.1",
        "code_commit": code_commit,
        "master_seed": int(master_seed),
        "runtime": {
            "url": runtime_url,
            "policy_id": runtime_policy_id,
            "record_latency": True,
            "latency_components": components,
        },
        "development": {
            "seeds_per_task": DEVELOPMENT_SEED_COUNT,
            "excluded_seeds": list(HELDOUT_SEEDS),
            "target_cluster_count": 1,
            "representative": "deterministic_medoid",
            "minimum_success_rate": 0.5,
            "historical_cluster_regression_rate": 1.0,
        },
        "heldout": {
            "seeds": list(HELDOUT_SEEDS),
            "mode": "test",
            "used_for_promotion": False,
        },
        "summary": {
            "setting_count": len(PAPER_SETTINGS),
            "tasks_per_setting": TASKS_PER_SETTING,
            "campaign_count": len(campaigns),
            "development_rollout_slots_per_round": len(campaigns)
            * DEVELOPMENT_SEED_COUNT,
            "heldout_episodes_per_method": len(campaigns) * len(HELDOUT_SEEDS),
            "all_init_states_nonempty": all(
                campaign["init_state_count"] > 0 for campaign in campaigns
            ),
            "seed_partitions_disjoint": all(
                set(campaign["development_seeds"]).isdisjoint(
                    campaign["heldout_seeds"]
                )
                for campaign in campaigns
            ),
            "official_horizons": all(
                campaign["evaluation_horizon"]["is_standard"]
                for campaign in campaigns
            ),
        },
        "campaigns": campaigns,
    }


def _single_campaign_argv(args: argparse.Namespace, row: dict[str, Any]) -> list[str]:
    return [
        "--output-root",
        str(Path(args.output_root) / row["campaign_root"]),
        "--campaign-id",
        row["campaign_id"],
        "--repository-root",
        str(Path(args.repository_root).resolve()),
        "--runtime-python",
        str(Path(os.path.abspath(args.runtime_python))),
        "--code-commit",
        args.code_commit,
        "--suite",
        row["suite"],
        "--task-id",
        str(row["task_id"]),
        "--task-language",
        row["task_language"],
        "--master-seed",
        str(row["case_master_seed"]),
        "--rollout-count",
        str(DEVELOPMENT_SEED_COUNT),
        "--heldout-count",
        str(len(HELDOUT_SEEDS)),
        "--fixed-heldout-seeds",
        "1-20",
        "--runtime-url",
        args.runtime_url,
        "--runtime-policy-id",
        args.runtime_policy_id,
        "--heldout-mode",
        "test",
        "--same-seed-pass-rate",
        "0.5",
        "--maximum-target-clusters",
        "1",
        "--no-skip-regression-gate",
        "--record-latency",
        "--latency-components",
        args.latency_components,
        "--initial-logical-slots",
        str(args.initial_logical_slots),
        "--continuous-logical-slots",
        str(args.continuous_logical_slots),
        "--maximum-logical-slots",
        str(args.maximum_logical_slots),
        "--maximum-api-concurrency",
        str(args.maximum_api_concurrency),
    ]


def _audit_campaign(
    path: Path, row: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    manifest = read_json(manifest_path)
    runtime = manifest.get("runtime", {})
    policy = runtime.get("evolution_policy", {})
    expected = {
        "campaign_id": row["campaign_id"],
        "code_commit": plan["code_commit"],
        "task": row["task"],
        "rollout_seeds": row["development_seeds"],
        "heldout_seeds": row["heldout_seeds"],
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"{path}: manifest {key} differs from matrix plan")
    if runtime.get("evaluation_horizon") != row["evaluation_horizon"]:
        raise ValueError(f"{path}: non-official or changed horizon")
    if (
        policy.get("heldout_mode") != "test"
        or policy.get("skip_regression_gate") is not False
    ):
        raise ValueError(f"{path}: held-out isolation or regression gate differs")
    if float(policy.get("same_seed_pass_rate", 0.0)) != 0.5:
        raise ValueError(f"{path}: development success gate differs")
    if int(policy.get("maximum_target_clusters", 0)) != 1:
        raise ValueError(f"{path}: largest-cluster-only diagnosis differs")
    latency = runtime.get("latency", {})
    if latency.get("enabled") is not True:
        raise ValueError(f"{path}: latency recording is not enabled")
    if latency.get("components") != plan["runtime"]["latency_components"]:
        raise ValueError(f"{path}: latency component set differs")
    command = runtime.get("rollout_command", [])
    if "--record-latency" not in command:
        raise ValueError(f"{path}: rollout command does not record latency")
    return {
        "campaign_id": row["campaign_id"],
        "manifest": f"{row['campaign_root']}/manifest.json",
        "manifest_file_sha256": file_sha256(manifest_path),
        "manifest_sha256": canonical_sha256(manifest),
        "status": "prepared",
    }


def materialize_matrix(
    args: argparse.Namespace,
    *,
    catalog: dict[str, Any] | None = None,
    campaign_preparer: Callable[
        [argparse.Namespace], dict[str, Any]
    ] = prepare_campaign,
) -> dict[str, Any]:
    catalog = catalog or probe_benchmark(Path(args.runtime_python))
    plan = build_matrix_plan(
        catalog=catalog,
        code_commit=args.code_commit,
        master_seed=args.master_seed,
        runtime_url=args.runtime_url,
        runtime_policy_id=args.runtime_policy_id,
        latency_components=args.latency_components,
    )
    if args.dry_run:
        return {**plan, "status": "dry_run", "materialized": False}

    output = Path(args.output_root).resolve()
    if output.exists() and not args.resume:
        raise ValueError(
            f"output root already exists: {output}; pass --resume to audit/continue"
        )
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "campaign-plan.json"
    if plan_path.is_file():
        if read_json(plan_path) != plan:
            raise ValueError(
                "existing campaign plan differs; refusing mixed protocol state"
            )
    else:
        atomic_write_json(plan_path, plan, overwrite=False)

    prepared: list[dict[str, Any]] = []
    for row in plan["campaigns"]:
        campaign_root = output / row["campaign_root"]
        if (campaign_root / "manifest.json").is_file():
            prepared.append(_audit_campaign(campaign_root, row, plan))
            continue
        if campaign_root.exists():
            raise ValueError(
                f"partial campaign directory requires manual audit: {campaign_root}"
            )
        single_args = single_campaign_parser().parse_args(
            _single_campaign_argv(args, row)
        )
        campaign_preparer(single_args)
        prepared.append(_audit_campaign(campaign_root, row, plan))

    result = {
        "schema_version": "zetta-liberopro-paper-campaign-matrix-result-v1",
        "status": "prepared",
        "materialized": True,
        "plan_file": "campaign-plan.json",
        "plan_file_sha256": file_sha256(plan_path),
        "summary": plan["summary"],
        "campaigns": prepared,
        "run_command_template": (
            "python scripts/evolution/run_campaign.py "
            "--manifest <campaign>/manifest.json "
            "--root <campaign>/state --queue-root <queue> "
            "--tool-catalog <campaign>/tool-catalog.json --workers <worker-list>"
        ),
    }
    atomic_write_json(
        output / "campaign-matrix.json", result, overwrite=bool(args.resume)
    )
    return result


def _git_head(repository_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--runtime-python", type=Path, required=True)
    parser.add_argument("--code-commit")
    parser.add_argument("--master-seed", type=int, default=260816590)
    parser.add_argument("--runtime-url", default="http://127.0.0.1:18730")
    parser.add_argument("--runtime-policy-id", default="pi05")
    parser.add_argument(
        "--latency-components",
        default=",".join(sorted(DEFAULT_LATENCY_COMPONENTS)),
    )
    parser.add_argument("--initial-logical-slots", type=int, default=4)
    parser.add_argument("--continuous-logical-slots", type=int, default=4)
    parser.add_argument("--maximum-logical-slots", type=int, default=4)
    parser.add_argument("--maximum-api-concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    args.repository_root = args.repository_root.resolve()
    args.runtime_python = Path(os.path.abspath(args.runtime_python))
    args.code_commit = args.code_commit or _git_head(args.repository_root)
    args.latency_components = ",".join(
        sorted(parse_latency_components(args.latency_components))
    )
    if args.dry_run and args.resume:
        raise ValueError("--dry-run and --resume are mutually exclusive")
    report = materialize_matrix(args)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
