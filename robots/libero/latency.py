"""Low-overhead, opt-in latency event recording for LIBERO rollouts."""

from __future__ import annotations

import json
import math
import os
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_LATENCY_COMPONENTS = frozenset(
    {
        "observation_preprocess",
        "policy_queue_wait",
        "model_inference",
        "action_decode_postprocess",
        "policy_request_end_to_end",
        "environment_execution",
        "critic_evaluation",
        "role1_llm_request",
        "recovery_execution",
        "chunk_end_to_end",
        "episode_end_to_end",
    }
)


def parse_latency_components(value: str | Iterable[str] | None) -> frozenset[str]:
    """Normalize a comma-separated component allowlist."""

    if value is None:
        return DEFAULT_LATENCY_COMPONENTS
    values = value.split(",") if isinstance(value, str) else value
    result = frozenset(str(item).strip() for item in values if str(item).strip())
    unknown = result - DEFAULT_LATENCY_COMPONENTS
    if unknown:
        raise ValueError(f"unknown latency components: {sorted(unknown)}")
    return result


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


class LatencyRecorder:
    """Append selected latency events and atomically materialize a summary."""

    def __init__(
        self,
        *,
        enabled: bool,
        events_path: str | Path,
        summary_path: str | Path,
        components: str | Iterable[str] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.events_path = Path(events_path)
        self.summary_path = Path(summary_path)
        self.components = parse_latency_components(components)
        self.context = dict(context or {})
        self._values: dict[str, list[float]] = defaultdict(list)
        self._finalized = False
        if self.enabled:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            self.summary_path.parent.mkdir(parents=True, exist_ok=True)
            self.events_path.touch(exist_ok=True)

    def wants(self, component: str) -> bool:
        return self.enabled and component in self.components

    def record(
        self,
        component: str,
        elapsed_s: float,
        **metadata: Any,
    ) -> None:
        """Record one finite non-negative duration if its component is enabled."""

        if not self.wants(component):
            return
        elapsed = float(elapsed_s)
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError(f"invalid latency for {component}: {elapsed_s!r}")
        event = {
            "schema_version": "zetta-libero-latency-event-v1",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "elapsed_s": elapsed,
            **self.context,
            **metadata,
        }
        with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._values[component].append(elapsed)

    @contextmanager
    def measure(self, component: str, **metadata: Any) -> Iterator[None]:
        """Measure a synchronous block, including failed calls."""

        started = time.perf_counter()
        try:
            yield
        except BaseException as exc:
            self.record(
                component,
                time.perf_counter() - started,
                status="error",
                error_type=type(exc).__name__,
                **metadata,
            )
            raise
        else:
            self.record(
                component,
                time.perf_counter() - started,
                status="ok",
                **metadata,
            )

    def summary(self) -> dict[str, Any]:
        components: dict[str, Any] = {}
        for name in sorted(self._values):
            values = self._values[name]
            components[name] = {
                "count": len(values),
                "mean_s": sum(values) / len(values),
                "p50_s": _percentile(values, 0.50),
                "p95_s": _percentile(values, 0.95),
                "max_s": max(values),
            }
        return {
            "schema_version": "zetta-libero-latency-summary-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "enabled_components": sorted(self.components),
            "event_count": sum(len(values) for values in self._values.values()),
            "components": components,
            **self.context,
        }

    def finalize(self) -> dict[str, Any] | None:
        """Write the current summary once; disabled recorders are no-ops."""

        if not self.enabled:
            return None
        payload = self.summary()
        temporary = self.summary_path.with_name(f".{self.summary_path.name}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.summary_path)
        self._finalized = True
        return payload

    @property
    def finalized(self) -> bool:
        return self._finalized


__all__ = ["DEFAULT_LATENCY_COMPONENTS", "LatencyRecorder", "parse_latency_components"]
