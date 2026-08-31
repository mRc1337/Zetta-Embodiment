from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from robots.libero.latency import LatencyRecorder, parse_latency_components
from robots.libero.tools import LiberoPrimitives


def test_latency_recorder_filters_events_and_summarizes(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    summary = tmp_path / "summary.json"
    recorder = LatencyRecorder(
        enabled=True,
        events_path=events,
        summary_path=summary,
        components="model_inference,chunk_end_to_end",
        context={"suite": "libero_goal_task", "task_id": 0},
    )
    recorder.record("model_inference", 1.0)
    recorder.record("model_inference", 3.0)
    recorder.record("policy_queue_wait", 99.0)
    recorder.record("chunk_end_to_end", 5.0)
    payload = recorder.finalize()

    assert payload is not None
    assert payload["event_count"] == 3
    assert payload["components"]["model_inference"] == pytest.approx(
        {"count": 2, "mean_s": 2.0, "p50_s": 2.0, "p95_s": 2.9, "max_s": 3.0}
    )
    assert len(events.read_text(encoding="utf-8").splitlines()) == 3
    assert json.loads(summary.read_text(encoding="utf-8"))["task_id"] == 0


def test_disabled_latency_recorder_creates_no_artifacts(tmp_path: Path) -> None:
    recorder = LatencyRecorder(
        enabled=False,
        events_path=tmp_path / "events.jsonl",
        summary_path=tmp_path / "summary.json",
    )
    recorder.record("model_inference", 1.0)
    assert recorder.finalize() is None
    assert not (tmp_path / "events.jsonl").exists()
    assert not (tmp_path / "summary.json").exists()


def test_unknown_latency_component_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown latency components"):
        parse_latency_components("model_inference,not-a-component")


class _Model:
    def predict_action_batch(
        self, env_obs: dict[str, Any], mode: str, **kwargs: Any
    ) -> tuple[np.ndarray, dict[str, Any]]:
        assert mode == "eval"
        assert kwargs["inference_parameters"]["record_latency"] is True
        return np.zeros((3, 7), dtype=np.float32), {
            "auxiliary_outputs": {
                "batch_size": 1,
                "latency_s": {
                    "observation_preprocess": 0.01,
                    "policy_queue_wait": 0.02,
                    "model_inference": 0.03,
                    "action_decode": 0.004,
                    "action_postprocess": 0.005,
                },
            }
        }


class _Env:
    return_all_frames = True
    episode_terminated = False
    episode_truncated = False

    def chunk_step(self, actions: Any, **kwargs: Any) -> tuple[Any, ...]:
        del kwargs
        horizon = int(np.asarray(actions).shape[0])
        frames = [
            {
                "states": np.zeros(8, dtype=np.float32),
                "task_descriptions": "open the drawer",
            }
            for _ in range(horizon)
        ]
        info = {
            "executed_horizon": horizon,
            "latency_s": {
                "action_preprocess": 0.001,
                "environment_execution": 0.04,
                "critic_evaluation": 0.0,
                "environment_chunk_total": 0.05,
            },
        }
        return frames, 0.0, np.zeros(horizon), np.zeros(horizon), info


def test_libero_chunk_records_server_and_client_boundaries(tmp_path: Path) -> None:
    recorder = LatencyRecorder(
        enabled=True,
        events_path=tmp_path / "events.jsonl",
        summary_path=tmp_path / "summary.json",
    )
    primitives = LiberoPrimitives(
        env=_Env(),  # type: ignore[arg-type]
        model=_Model(),  # type: ignore[arg-type]
        sam3_client=None,  # type: ignore[arg-type]
        latency_recorder=recorder,
    )
    primitives.set_obs(
        {
            "states": np.zeros(8, dtype=np.float32),
            "task_descriptions": "open the drawer",
        }
    )
    primitives._vlm_chunk("open the drawer", actions_per_chunk=2)
    payload = recorder.finalize()

    assert payload is not None
    components = payload["components"]
    assert components["observation_preprocess"]["mean_s"] == pytest.approx(0.01)
    assert components["policy_queue_wait"]["mean_s"] == pytest.approx(0.02)
    assert components["model_inference"]["mean_s"] == pytest.approx(0.03)
    assert components["action_decode_postprocess"]["mean_s"] >= 0.009
    assert components["environment_execution"]["mean_s"] == pytest.approx(0.04)
    assert components["critic_evaluation"]["mean_s"] == 0.0
    assert components["chunk_end_to_end"]["count"] == 1
