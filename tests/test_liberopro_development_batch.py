from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.evolution.run_liberopro_development_batch import (
    _aggregate,
    _pending_jobs,
    _resolve_summary_output,
    _terminal_row,
    _write_summary,
)


def _write_pending(path: Path, *, logical_id: str, seed: int, mtime_ns: int) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "kind": "rollout_pending",
                "job_id": f"job-{logical_id}",
                "job": {
                    "logical_id": logical_id,
                    "seed": seed,
                    "attempt_index": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    os.utime(path, ns=(mtime_ns, mtime_ns))


def test_pending_jobs_follow_queue_claim_mtime_order(tmp_path: Path) -> None:
    pending = tmp_path / "pending" / "local"
    pending.mkdir(parents=True)
    _write_pending(pending / "job-z.json", logical_id="rollout-1", seed=11, mtime_ns=1)
    _write_pending(pending / "job-a.json", logical_id="rollout-2", seed=12, mtime_ns=2)

    jobs = _pending_jobs(tmp_path, 2)

    assert [job.seed for job in jobs] == [11, 12]


def test_terminal_row_records_valid_failure_and_latency() -> None:
    running = {
        "status": "running",
        "metrics": {},
        "countability": {
            "integrity_qualified": False,
            "official_result_present": False,
            "score_countable": False,
        },
        "effort": {},
        "insight": {"status": "pending"},
    }
    row = _terminal_row(
        running,
        record={
            "status": "valid",
            "success": False,
            "elapsed_s": 12.5,
            "attempt_index": 0,
        },
        latency={
            "event_count": 3,
            "components": {
                "model_inference": {
                    "count": 2,
                    "mean_s": 0.2,
                    "p95_s": 0.3,
                }
            },
        },
        integrity={
            "integrity_qualified": False,
            "classification": "runtime_isolation_not_attested",
        },
        observed_at="2026-09-01T00:00:00+00:00",
    )

    assert row["status"] == "completed"
    assert row["metrics"]["success_rate"]["value"] == 0
    assert row["metrics"]["success_rate"]["total"] == 1
    assert row["metrics"]["model_inference_mean_ms"]["value"] == 200.0
    assert row["countability"]["official_result_present"] is True
    assert row["countability"]["score_countable"] is False
    assert row["effort"]["duration_ms"] == 12500


def test_aggregate_weights_component_means_by_event_count() -> None:
    aggregate = _aggregate(
        [
            {
                "status": "valid",
                "success": False,
                "latency_event_count": 2,
                "latency": {"model_inference": {"count": 1, "mean_ms": 100.0}},
            },
            {
                "status": "valid",
                "success": True,
                "latency_event_count": 4,
                "latency": {"model_inference": {"count": 3, "mean_ms": 300.0}},
            },
        ]
    )

    assert aggregate["episode_count"] == 2
    assert aggregate["valid_episode_count"] == 2
    assert aggregate["success_count"] == 1
    assert aggregate["latency_event_count"] == 6
    assert aggregate["components"]["model_inference"] == {
        "count": 4,
        "weighted_mean_ms": 250.0,
    }


def test_summary_output_must_stay_inside_matrix_root(tmp_path: Path) -> None:
    matrix_root = tmp_path / "matrix"
    matrix_root.mkdir()

    assert _resolve_summary_output(matrix_root, Path("summaries/batch.json")) == (
        matrix_root / "summaries" / "batch.json"
    )
    with pytest.raises(ValueError, match="must stay inside"):
        _resolve_summary_output(matrix_root, Path("../outside.json"))


def test_write_summary_is_create_only(tmp_path: Path) -> None:
    output = tmp_path / "summaries" / "batch.json"
    payload = {"status": "completed", "episodes": []}

    _write_summary(output, payload)

    assert json.loads(output.read_text(encoding="utf-8")) == payload
    with pytest.raises(FileExistsError):
        _write_summary(output, payload)
