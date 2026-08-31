#!/usr/bin/env python3
# Copyright (c) 2026 Zetta Contributors
"""Run a bounded, recoverable LIBERO-Pro development batch.

This orchestrator deliberately keeps the evaluated runner revision separate
from the repository revision that contains experiment notes and orchestration
code.  It reads already-materialized campaign queues, preregisters every
selected episode on the LoopX experiment board, runs one serial worker lane per
campaign, ingests terminal queue envelopes, and replaces the running rows with
compact terminal metrics.

The command is a dry run unless ``--execute`` is supplied.  Raw trajectories,
videos, episode records, and local artifact paths are never printed.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SETTINGS = ("goal-t", "goal-s", "libero-10-t", "libero-10-s")
LATENCY_BOARD_COMPONENTS = (
    "chunk_end_to_end",
    "critic_evaluation",
    "environment_execution",
    "model_inference",
    "policy_request_end_to_end",
)


@dataclass(frozen=True)
class PendingJob:
    path: Path
    payload: dict[str, Any]

    @property
    def logical_id(self) -> str:
        return str(self.payload["logical_id"])

    @property
    def seed(self) -> int:
        return int(self.payload["seed"])

    @property
    def attempt_index(self) -> int:
        return int(self.payload["attempt_index"])


@dataclass(frozen=True)
class CampaignBatch:
    setting: str
    task_id: int
    campaign_root: Path
    state_root: Path
    queue_root: Path
    manifest: dict[str, Any]
    jobs: tuple[PendingJob, ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _json_from_stdout(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-4000:]
        raise RuntimeError(f"command failed ({completed.returncode}): {detail}")
    output = completed.stdout.strip()
    start = output.find("{")
    if start < 0:
        raise RuntimeError("command returned no JSON object")
    value = json.loads(output[start:])
    if not isinstance(value, dict):
        raise RuntimeError("command returned non-object JSON")
    return value


def _run_json(
    command: list[str],
    *,
    cwd: Path,
    input_value: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        input=(json.dumps(input_value, ensure_ascii=False) if input_value else None),
        capture_output=True,
        text=True,
        check=False,
    )
    return _json_from_stdout(completed)


def _read_board(*, loopx_bin: str, goal_id: str, project: Path) -> dict[str, Any]:
    return _run_json(
        [
            loopx_bin,
            "benchmark",
            "experiment-board-show",
            "--goal-id",
            goal_id,
            "--format",
            "json",
        ],
        cwd=project,
    )


def _source_fence(
    *,
    loopx_bin: str,
    project: Path,
    source_checkout: Path,
    expected_revision: str,
) -> dict[str, Any]:
    report = _run_json(
        [
            loopx_bin,
            "benchmark",
            "source-revision-fence",
            "--source-checkout",
            str(source_checkout),
            "--expected-revision",
            expected_revision,
            "--observed-reference-revision",
            expected_revision,
            "--require-admitted",
            "--format",
            "json",
        ],
        cwd=project,
    )
    if not report.get("admitted"):
        raise RuntimeError(f"source revision fence rejected: {report.get('reason_code')}")
    return report


def _runtime_health(runtime_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{runtime_url.rstrip('/')}/healthz", timeout=10) as reply:
        value = json.loads(reply.read().decode("utf-8"))
    if value.get("status") != "ok":
        raise RuntimeError(f"runtime health check failed: {value.get('status')}")
    if int(value.get("env_ranks_healthy", 0)) != int(value.get("env_ranks", -1)):
        raise RuntimeError("not every runtime environment rank is healthy")
    return value


def _queue_counts(queue_root: Path) -> dict[str, int]:
    return {
        bucket: len(tuple((queue_root / bucket / "local").glob("*.json")))
        for bucket in ("pending", "running", "completed", "failed")
    }


def _pending_jobs(queue_root: Path, count: int) -> tuple[PendingJob, ...]:
    candidates: list[PendingJob] = []
    for path in (queue_root / "pending" / "local").glob("*.json"):
        envelope = _read_json(path)
        job = envelope.get("job")
        if not isinstance(job, dict):
            raise ValueError(f"pending envelope has no job object: {path}")
        candidates.append(PendingJob(path=path, payload=job))
    candidates.sort(key=lambda item: (item.path.stat().st_mtime_ns, item.path.name))
    if len(candidates) < count:
        raise ValueError(f"requested {count} jobs but only {len(candidates)} are pending")
    return tuple(candidates[:count])


def _load_batch(
    *,
    matrix_root: Path,
    setting: str,
    task_id: int,
    count: int,
    expected_revision: str,
    runtime_url: str,
) -> CampaignBatch:
    campaign_root = matrix_root / "campaigns" / setting / f"task-{task_id:02d}"
    manifest = _read_json(campaign_root / "manifest.json")
    if manifest.get("code_commit") != expected_revision:
        raise RuntimeError(f"{setting}/task-{task_id:02d} manifest revision mismatch")
    rollout_command = (manifest.get("runtime") or {}).get("rollout_command", [])
    if runtime_url not in rollout_command:
        raise RuntimeError(f"{setting}/task-{task_id:02d} runtime URL mismatch")
    queue_root = campaign_root / "queue"
    counts = _queue_counts(queue_root)
    if counts["running"]:
        raise RuntimeError(f"{setting}/task-{task_id:02d} already has running jobs")
    jobs = _pending_jobs(queue_root, count)
    heldout = {int(seed) for seed in manifest["heldout_seeds"]}
    leaked = sorted({job.seed for job in jobs} & heldout)
    if leaked:
        raise RuntimeError(f"development batch intersects held-out seeds: {leaked}")
    return CampaignBatch(
        setting=setting,
        task_id=task_id,
        campaign_root=campaign_root,
        state_root=campaign_root / "state",
        queue_root=queue_root,
        manifest=manifest,
        jobs=jobs,
    )


def _case_id(batch: CampaignBatch, job: PendingJob) -> str:
    return f"{batch.setting}-task{batch.task_id}-seed{job.seed}"


def _run_id(batch: CampaignBatch, job: PendingJob, revision: str) -> str:
    return (
        f"paper-v1-{batch.setting}-t{batch.task_id:02d}-dev-seed{job.seed}-"
        f"{revision[:7]}-a{job.attempt_index}"
    )


def _running_row(
    batch: CampaignBatch,
    job: PendingJob,
    *,
    runner_revision: str,
    observed_at: str,
    model_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_experiment_board_row_v0",
        "benchmark_id": "liberopro",
        "study_id": "zetta_pi05_liberopro_paper_v1_development",
        "case_id": _case_id(batch, job),
        "run_id": _run_id(batch, job, runner_revision),
        "arm_id": "pi05_strict_pure_vla",
        "arm_role": "baseline",
        "attempt": job.attempt_index,
        "status": "running",
        "observed_at": observed_at,
        "model_id": model_id,
        "protocol_id": "liberopro_paper_s4_1_development_v1",
        "comparison_protocol_id": "liberopro_paper_s4_1_pure_vla_v1",
        "claim_scope": "inventory_only",
        "primary_metric": "success_rate",
        "guardrail_metrics": [
            "valid_episode_count",
            "infra_invalid_episode_count",
        ],
        "metrics": {},
        "countability": {
            "integrity_qualified": False,
            "official_result_present": False,
            "score_countable": False,
        },
        "treatment_fidelity": "not_applicable",
        "effort": {},
        "insight": {"status": "pending"},
        "runner_revision": runner_revision,
    }


def _upsert_row(
    row: dict[str, Any],
    *,
    loopx_bin: str,
    goal_id: str,
    project: Path,
    execute: bool,
) -> dict[str, Any]:
    command = [
        loopx_bin,
        "benchmark",
        "experiment-board-upsert",
        "--goal-id",
        goal_id,
        "--project",
        str(project),
        "--row-json",
        "-",
        "--format",
        "json",
    ]
    if execute:
        command.append("--execute")
    return _run_json(command, cwd=project, input_value=row)


def _worker_environment(source_checkout: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{source_checkout}{os.pathsep}{existing}" if existing else str(source_checkout)
    )
    return env


def _run_lane(
    batch: CampaignBatch,
    *,
    runtime_python: Path,
    source_checkout: Path,
) -> dict[str, Any]:
    env = _worker_environment(source_checkout)
    worker_runs = 0
    for _job in batch.jobs:
        completed = subprocess.run(
            [
                str(runtime_python),
                "-m",
                "zetta.evolution.cli",
                "worker",
                "--queue-root",
                str(batch.queue_root),
                "--host",
                "local",
                "--once",
            ],
            cwd=str(source_checkout),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[-4000:]
            raise RuntimeError(f"{batch.setting} worker failed: {detail}")
        worker_runs += 1
    ingestion = _run_json(
        [
            str(runtime_python),
            "-m",
            "zetta.evolution.cli",
            "resume",
            "--root",
            str(batch.state_root),
            "--queue-root",
            str(batch.queue_root),
            "--workers",
            "local",
        ],
        cwd=source_checkout,
        env=env,
    )
    return {"worker_runs": worker_runs, "ingestion": ingestion}


def _integrity_report(
    *, loopx_bin: str, project: Path, output_dir: Path
) -> dict[str, Any]:
    trajectory = output_dir / "episode_record.json"
    attestation = output_dir / "runtime-device-assignment.json"
    if not trajectory.is_file() or not attestation.is_file():
        return {
            "integrity_qualified": False,
            "classification": "integrity_artifact_missing",
        }
    return _run_json(
        [
            loopx_bin,
            "benchmark",
            "integrity-qualification",
            "--trajectory-json",
            str(trajectory),
            "--runtime-attestation-json",
            str(attestation),
            "--format",
            "json",
        ],
        cwd=project,
    )


def _latency_metrics(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    components = summary.get("components", {})
    for component in LATENCY_BOARD_COMPONENTS:
        values = components.get(component)
        if not isinstance(values, dict) or int(values.get("count", 0)) <= 0:
            continue
        metrics[f"{component}_mean_ms"] = {
            "value": round(float(values["mean_s"]) * 1000.0, 3),
            "unit": "milliseconds",
            "higher_is_better": False,
        }
    metrics["latency_event_count"] = {
        "value": int(summary.get("event_count", 0)),
        "unit": "events",
        "higher_is_better": True,
    }
    return metrics


def _terminal_row(
    running: dict[str, Any],
    *,
    record: dict[str, Any],
    latency: dict[str, Any] | None,
    integrity: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    status = str(record.get("status", "infra_invalid"))
    valid = status == "valid"
    success = bool(record.get("success")) if valid else False
    metrics: dict[str, dict[str, Any]] = {
        "success_rate": {
            "value": 100 if success else 0,
            "total": 1 if valid else 0,
            "unit": "percent",
            "higher_is_better": True,
        },
        "valid_episode_count": {
            "value": 1 if valid else 0,
            "unit": "episodes",
            "higher_is_better": True,
        },
        "infra_invalid_episode_count": {
            "value": 0 if valid else 1,
            "unit": "episodes",
            "higher_is_better": False,
        },
        "infrastructure_attempt_count": {
            "value": int(record.get("attempt_index", 0)) + 1,
            "unit": "attempts",
            "higher_is_better": False,
        },
    }
    if latency:
        metrics.update(_latency_metrics(latency))
    elapsed_ms = round(float(record.get("elapsed_s", 0.0)) * 1000.0)
    row = dict(running)
    row.update(
        {
            "status": "completed",
            "observed_at": observed_at,
            "metrics": metrics,
            "countability": {
                "integrity_qualified": bool(integrity.get("integrity_qualified")),
                "official_result_present": valid,
                "score_countable": bool(integrity.get("integrity_qualified")) and valid,
            },
            "effort": {"duration_ms": elapsed_ms},
            "insight": {
                "status": "complete",
                "classification": (
                    f"valid_full_horizon_{'success' if success else 'failure'}_batch"
                    if valid
                    else "infra_invalid"
                ),
                "artifact_ref": "liberopro-evaluation-log.md",
            },
        }
    )
    return row


def _compact_episode(
    batch: CampaignBatch,
    job: PendingJob,
    record: dict[str, Any],
    latency: dict[str, Any] | None,
    integrity: dict[str, Any],
) -> dict[str, Any]:
    components = (latency or {}).get("components", {})
    compact_latency: dict[str, Any] = {}
    for component in LATENCY_BOARD_COMPONENTS:
        values = components.get(component)
        if isinstance(values, dict) and int(values.get("count", 0)) > 0:
            compact_latency[component] = {
                "count": int(values["count"]),
                "mean_ms": round(float(values["mean_s"]) * 1000.0, 3),
                "p95_ms": round(float(values["p95_s"]) * 1000.0, 3),
            }
    return {
        "setting": batch.setting,
        "task_id": batch.task_id,
        "logical_id": job.logical_id,
        "seed": job.seed,
        "status": record.get("status"),
        "success": bool(record.get("success")),
        "elapsed_ms": round(float(record.get("elapsed_s", 0.0)) * 1000.0, 3),
        "latency_event_count": int((latency or {}).get("event_count", 0)),
        "latency": compact_latency,
        "integrity_classification": integrity.get("classification"),
    }


def _aggregate(episodes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(episodes)
    components: dict[str, dict[str, float | int]] = {}
    for component in LATENCY_BOARD_COMPONENTS:
        count = 0
        weighted_ms = 0.0
        for row in rows:
            values = row["latency"].get(component)
            if not values:
                continue
            count += int(values["count"])
            weighted_ms += int(values["count"]) * float(values["mean_ms"])
        if count:
            components[component] = {
                "count": count,
                "weighted_mean_ms": round(weighted_ms / count, 3),
            }
    valid = [row for row in rows if row["status"] == "valid"]
    return {
        "episode_count": len(rows),
        "valid_episode_count": len(valid),
        "infra_invalid_episode_count": len(rows) - len(valid),
        "success_count": sum(bool(row["success"]) for row in valid),
        "latency_event_count": sum(int(row["latency_event_count"]) for row in rows),
        "components": components,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", required=True, type=Path)
    parser.add_argument("--source-checkout", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--runtime-python", required=True, type=Path)
    parser.add_argument("--runtime-url", default="http://127.0.0.1:18730")
    parser.add_argument("--goal-id", default="zetta-embodiment-goal")
    parser.add_argument("--loopx-bin", default="loopx")
    parser.add_argument("--setting", action="append", dest="settings")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--episodes-per-campaign", type=int, default=1)
    parser.add_argument("--model-id", default="RLinf-Pi05-LIBERO-SFT")
    parser.add_argument("--execute", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.episodes_per_campaign < 1:
        raise ValueError("--episodes-per-campaign must be positive")
    project = Path(__file__).resolve().parents[2]
    matrix_root = args.matrix_root.resolve()
    source_checkout = args.source_checkout.resolve()
    runtime_python = args.runtime_python.resolve()
    settings = tuple(args.settings or DEFAULT_SETTINGS)

    board = _read_board(loopx_bin=args.loopx_bin, goal_id=args.goal_id, project=project)
    fence = _source_fence(
        loopx_bin=args.loopx_bin,
        project=project,
        source_checkout=source_checkout,
        expected_revision=args.expected_revision,
    )
    health = _runtime_health(args.runtime_url)
    batches = tuple(
        _load_batch(
            matrix_root=matrix_root,
            setting=setting,
            task_id=args.task_id,
            count=args.episodes_per_campaign,
            expected_revision=args.expected_revision,
            runtime_url=args.runtime_url,
        )
        for setting in settings
    )
    observed_at = _utc_now()
    running_rows = {
        (batch.setting, job.logical_id): _running_row(
            batch,
            job,
            runner_revision=args.expected_revision,
            observed_at=observed_at,
            model_id=args.model_id,
        )
        for batch in batches
        for job in batch.jobs
    }

    for row in running_rows.values():
        _upsert_row(
            row,
            loopx_bin=args.loopx_bin,
            goal_id=args.goal_id,
            project=project,
            execute=False,
        )

    selection = [
        {
            "setting": batch.setting,
            "task_id": batch.task_id,
            "logical_id": job.logical_id,
            "seed": job.seed,
            "run_id": running_rows[(batch.setting, job.logical_id)]["run_id"],
        }
        for batch in batches
        for job in batch.jobs
    ]
    if not args.execute:
        print(
            json.dumps(
                {
                    "schema_version": "zetta-liberopro-development-batch-v1",
                    "status": "dry_run",
                    "board_run_count_before": (board.get("summary") or {}).get(
                        "run_count"
                    ),
                    "source_admitted": fence.get("admitted"),
                    "runtime_env_ranks_healthy": health.get("env_ranks_healthy"),
                    "selection": selection,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    for row in running_rows.values():
        _upsert_row(
            row,
            loopx_bin=args.loopx_bin,
            goal_id=args.goal_id,
            project=project,
            execute=True,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(batches)) as pool:
        futures = {
            pool.submit(
                _run_lane,
                batch,
                runtime_python=runtime_python,
                source_checkout=source_checkout,
            ): batch.setting
            for batch in batches
        }
        lane_reports = {
            futures[future]: future.result()
            for future in concurrent.futures.as_completed(futures)
        }

    episodes: list[dict[str, Any]] = []
    for batch in batches:
        for job in batch.jobs:
            output_dir = Path(str(job.payload["output_dir"]))
            record_path = Path(str(job.payload["result_file"]))
            if not record_path.is_file():
                raise RuntimeError(f"worker produced no terminal record for {job.logical_id}")
            record = _read_json(record_path)
            latency_path = output_dir / "latency" / "summary.json"
            latency = _read_json(latency_path) if latency_path.is_file() else None
            integrity = _integrity_report(
                loopx_bin=args.loopx_bin,
                project=project,
                output_dir=output_dir,
            )
            running = running_rows[(batch.setting, job.logical_id)]
            terminal = _terminal_row(
                running,
                record=record,
                latency=latency,
                integrity=integrity,
                observed_at=_utc_now(),
            )
            _upsert_row(
                terminal,
                loopx_bin=args.loopx_bin,
                goal_id=args.goal_id,
                project=project,
                execute=False,
            )
            _upsert_row(
                terminal,
                loopx_bin=args.loopx_bin,
                goal_id=args.goal_id,
                project=project,
                execute=True,
            )
            episodes.append(_compact_episode(batch, job, record, latency, integrity))

    print(
        json.dumps(
            {
                "schema_version": "zetta-liberopro-development-batch-v1",
                "status": "completed",
                "board_run_count_before": (board.get("summary") or {}).get("run_count"),
                "source_admitted": fence.get("admitted"),
                "runtime_env_ranks_healthy": health.get("env_ranks_healthy"),
                "lane_reports": lane_reports,
                "episodes": episodes,
                "aggregate": _aggregate(episodes),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
