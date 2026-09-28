#!/usr/bin/env python3
"""Fail-closed, read-only Table 3 report from frozen LIBERO-Pro held-out gates.

Score the pure-VLA control from generation 0 and the final promoted harness
from its own held-out gate. Development rollouts and intermediate harnesses
never contribute to the reported success rate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.evolution.prepare_liberopro_paper_campaigns import PAPER_SETTINGS
from scripts.evolution.run_liberopro_final_harness import (
    EVALUATION_SCOPE as FINAL_HARNESS_SCOPE,
    evaluation_root as final_harness_root,
)
from scripts.evolution.run_liberopro_final_pure_vla import EVALUATION_SCOPE, evaluation_root
from zetta.evolution.gating import evaluate_paired_gate
from zetta.evolution.jsonio import canonical_sha256, file_sha256, read_json
from zetta.evolution.models import EpisodeRecord


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing ledger: {path}")
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"non-object ledger row at {path}:{number}")
        rows.append(row)
    return rows


def _artifact(path_value: Any, *, campaign_root: Path) -> None:
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("held-out evidence path is missing")
    path = Path(path_value).resolve()
    if not path.is_relative_to(campaign_root.resolve()):
        raise ValueError("held-out evidence escapes its campaign")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("held-out evidence is missing or empty")


def _verify_trajectory_artifacts(record: EpisodeRecord, *, campaign_root: Path) -> None:
    index = record.artifact_index.get("trajectory_index")
    if not isinstance(index, dict):
        raise ValueError("final-test episode has no trajectory index")
    paths = index.get("artifact_paths")
    hashes = index.get("artifact_sha256")
    if (
        not isinstance(paths, dict)
        or not isinstance(hashes, dict)
        or not paths
        or set(paths) != set(hashes)
    ):
        raise ValueError("final-test artifact path/hash manifest is incomplete")
    for name, path_value in paths.items():
        if not isinstance(path_value, str) or not path_value:
            raise ValueError(f"final-test artifact path is missing: {name}")
        path = Path(path_value).resolve()
        if not path.is_relative_to(campaign_root.resolve()) or not path.is_file():
            raise ValueError(f"final-test artifact is missing or escapes campaign: {name}")
        if file_sha256(path) != hashes[name]:
            raise ValueError(f"final-test artifact hash differs: {name}")


def _lineage(
    campaign_root: Path, row: dict[str, Any], code_commit: str
) -> list[tuple[Path, dict[str, Any]]]:
    """Follow immutable promotion handoffs to the terminal harness generation."""

    original = read_json(campaign_root / "manifest.json")
    if original.get("code_commit") != code_commit:
        raise ValueError("campaign code commit differs")
    current = (campaign_root / "state").resolve()
    visited: set[Path] = set()
    nodes: list[tuple[Path, dict[str, Any]]] = []
    while True:
        if current in visited or not current.is_relative_to(campaign_root.resolve()):
            raise ValueError("generation continuation escapes campaign or cycles")
        visited.add(current)
        stored = current / "manifest.json"
        manifest = read_json(stored) if stored.is_file() else original
        state = read_json(current / "state.json")
        if (
            manifest.get("code_commit") != code_commit
            or manifest.get("task") != row["task"]
            or manifest.get("generation") != len(nodes)
        ):
            raise ValueError("generation code, task, or index differs")
        if manifest.get("heldout_seeds") != list(range(1, 21)):
            raise ValueError("generation lacks the fixed 1--20 held-out seeds")
        if any(
            manifest.get("policy_rng_by_seed", {}).get(str(seed))
            != original.get("policy_rng_by_seed", {}).get(str(seed))
            for seed in range(1, 21)
        ):
            raise ValueError("generation changed held-out policy RNG")
        if not nodes and canonical_sha256(manifest) != canonical_sha256(original):
            raise ValueError("initial stored manifest differs from preregistration")
        if state.get("phase") != "complete":
            raise ValueError("final harness generation is not complete")
        nodes.append((current, manifest))
        handoff_path = current / "analysis/generation-continuation.json"
        if not handoff_path.is_file():
            return nodes
        handoff = read_json(handoff_path)
        if handoff.get("parent_manifest_sha256") != canonical_sha256(manifest):
            raise ValueError("generation continuation parent digest differs")
        child_value = handoff.get("child_campaign_root")
        if not isinstance(child_value, str) or not child_value:
            raise ValueError("generation continuation has no child root")
        child = Path(child_value).resolve()
        if not child.is_relative_to(campaign_root.resolve()):
            raise ValueError("generation continuation escapes campaign")
        child_manifest = read_json(child / "manifest.json")
        promoted = handoff.get("promoted_bundle_sha256")
        if (
            handoff.get("child_manifest_sha256") != canonical_sha256(child_manifest)
            or handoff.get("child_generation") != len(nodes)
            or child_manifest.get("active_bundle_sha256") != promoted
            or child_manifest.get("parent_bundle_sha256") != promoted
            or child_manifest.get("baseline_mode") != "active_bundle"
        ):
            raise ValueError("generation continuation child binding differs")
        current = child


def _score_gate(
    campaign_root: Path,
    state_root: Path,
    manifest: dict[str, Any],
    candidate_sha: str,
    parent_sha: str | None,
) -> dict[str, int]:
    """Validate one complete 20-pair gate against its frozen generation."""

    gate_root = state_root / "candidates" / candidate_sha / "gates/heldout_20"
    if not (gate_root / "plan.json").is_file():
        raise ValueError("selected promoted candidate has no held-out gate")
    plan = read_json(gate_root / "plan.json")
    if plan.get("kind") != "heldout_20" or plan.get("candidate_sha256") != candidate_sha:
        raise ValueError("held-out plan candidate identity differs")
    if plan.get("manifest_sha256") != canonical_sha256(manifest):
        raise ValueError("held-out plan manifest digest differs")
    if plan.get("parent_sha256") != parent_sha:
        raise ValueError(
            "held-out parent is not the pure-VLA baseline"
            if parent_sha is None
            else "held-out parent bundle differs from generation harness"
        )
    pairs = plan.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != 20:
        raise ValueError("held-out plan does not contain exactly 20 pairs")
    expected: dict[str, tuple[int, int, str]] = {}
    for index, pair in enumerate(pairs):
        seed = index + 1
        if pair.get("pair_index") != index or pair.get("seed") != seed:
            raise ValueError("held-out pair order or seed differs")
        policy_rng = manifest["policy_rng_by_seed"][str(seed)]
        if pair.get("policy_rng") != policy_rng:
            raise ValueError("held-out policy RNG differs")
        for arm in ("parent", "candidate"):
            logical_id = pair.get("logical_ids", {}).get(arm)
            if not isinstance(logical_id, str) or logical_id in expected:
                raise ValueError("held-out logical arm is missing or duplicate")
            expected[logical_id] = (seed, policy_rng, arm)

    records = _jsonl(gate_root / "ledgers/valid.jsonl")
    if len(records) != 40:
        raise ValueError(f"held-out valid ledger has {len(records)} arms, expected 40")
    observed: set[str] = set()
    successes = {"parent": 0, "candidate": 0}
    for payload in records:
        record = EpisodeRecord.from_dict(payload)
        if record.logical_id in observed or record.logical_id not in expected:
            raise ValueError("held-out ledger contains a duplicate or unknown arm")
        observed.add(record.logical_id)
        seed, policy_rng, arm = expected[record.logical_id]
        bundle_sha = candidate_sha if arm == "candidate" else parent_sha
        if (
            record.status != "valid"
            or record.generation != manifest["generation"]
            or record.seed != seed
            or record.policy_rng != policy_rng
            or record.bundle_sha256 != bundle_sha
        ):
            raise ValueError("held-out arm violates its frozen plan")
        videos = record.artifact_index.get("videos")
        if not isinstance(videos, dict) or not videos:
            raise ValueError("held-out episode has no video evidence")
        for path in videos.values():
            _artifact(path, campaign_root=campaign_root)
        _artifact(record.artifact_index.get("latency_summary"), campaign_root=campaign_root)
        successes[arm] += int(record.success is True)

    decisions = [
        decision
        for decision in _jsonl(state_root / "ledgers/gates.jsonl")
        if decision.get("kind") == "heldout_20"
        and decision.get("candidate_sha256") == candidate_sha
    ]
    if len(decisions) != 1:
        raise ValueError("held-out decision is missing or ambiguous")
    decision = decisions[0]
    if (
        decision.get("paired_count") != 20
        or decision.get("parent_successes") != successes["parent"]
        or decision.get("candidate_successes") != successes["candidate"]
    ):
        raise ValueError("held-out decision contradicts valid episode evidence")
    return successes


def _verify_promotion_gates(
    state_root: Path,
    manifest: dict[str, Any],
    candidate_sha: str,
    parent_sha: str | None,
    *,
    require_heldout: bool = True,
) -> None:
    """Bind a promotion to passed development gates and the fixed final test."""

    promotions = _jsonl(state_root / "ledgers/promotions.jsonl")
    if len(promotions) != 1:
        raise ValueError("generation lacks a unique promotion record")
    promotion = promotions[0]
    if (
        promotion.get("candidate_sha256") != candidate_sha
        or promotion.get("parent_sha256") != parent_sha
        or promotion.get("generation") != manifest["generation"]
    ):
        raise ValueError("promotion candidate, parent, or generation differs")
    decisions = [
        row
        for row in _jsonl(state_root / "ledgers/gates.jsonl")
        if row.get("candidate_sha256") == candidate_sha
    ]
    by_kind = {row.get("kind"): row for row in decisions}
    expected_kinds = {"same_seed", "regression"}
    if require_heldout:
        expected_kinds.add("heldout_20")
    if len(by_kind) != len(decisions) or set(by_kind) != expected_kinds:
        raise ValueError("promotion lacks its unique required development/test gates")
    ids = [row.get("decision_id") for row in decisions]
    if (
        any(not isinstance(value, str) or not value for value in ids)
        or promotion.get("gate_decision_ids") != sorted(ids)
    ):
        raise ValueError("promotion does not bind its gate decisions")
    development = set(manifest["rollout_seeds"])
    same_seed_schedule: list[int] | None = None
    for kind in ("same_seed", "regression"):
        decision = by_kind[kind]
        plan = read_json(state_root / "candidates" / candidate_sha / "gates" / kind / "plan.json")
        pairs = plan.get("pairs")
        if (
            plan.get("kind") != kind
            or plan.get("candidate_sha256") != candidate_sha
            or plan.get("parent_sha256") != parent_sha
            or plan.get("manifest_sha256") != canonical_sha256(manifest)
            or not isinstance(pairs, list)
            or not pairs
            or decision.get("paired_count") != len(pairs)
            or decision.get("passed") is not True
            or decision.get("parent_sha256") != parent_sha
            or decision.get("candidate_safety_events") != 0
        ):
            raise ValueError(f"promotion {kind} gate is missing or inconsistent")
        seen_seeds: set[int] = set()
        expected: dict[str, tuple[int, int, str]] = {}
        for pair in pairs:
            seed = pair.get("seed")
            if (
                not isinstance(seed, int)
                or seed not in development
                or seed in seen_seeds
                or pair.get("policy_rng") != manifest["policy_rng_by_seed"][str(seed)]
            ):
                raise ValueError(f"promotion {kind} gate changed development seeds")
            seen_seeds.add(seed)
            for arm in ("parent", "candidate"):
                logical_id = pair.get("logical_ids", {}).get(arm)
                if not isinstance(logical_id, str) or not logical_id or logical_id in expected:
                    raise ValueError(f"promotion {kind} gate has duplicate or missing arms")
                expected[logical_id] = (seed, pair["policy_rng"], arm)
        ordered_seeds = [pair["seed"] for pair in pairs]
        if kind == "same_seed":
            same_seed_schedule = ordered_seeds
        elif ordered_seeds != same_seed_schedule:
            raise ValueError("regression gate changed the originating failure cluster")
        successes = decision.get("candidate_successes")
        if (
            not isinstance(successes, int)
            or successes < 0
            or successes > len(pairs)
            or (kind == "same_seed" and successes * 2 < len(pairs))
            or (kind == "regression" and successes != len(pairs))
        ):
            raise ValueError(f"promotion {kind} gate missed the paper threshold")
        records = _jsonl(
            state_root / "candidates" / candidate_sha / "gates" / kind / "ledgers/valid.jsonl"
        )
        if len(records) != len(expected):
            raise ValueError(f"promotion {kind} gate lacks complete valid episode evidence")
        observed: set[str] = set()
        measured = {"parent": 0, "candidate": 0}
        arms: dict[str, list[EpisodeRecord]] = {"parent": [], "candidate": []}
        for payload in records:
            record = EpisodeRecord.from_dict(payload)
            if record.logical_id in observed or record.logical_id not in expected:
                raise ValueError(f"promotion {kind} gate has duplicate or unknown episodes")
            observed.add(record.logical_id)
            seed, policy_rng, arm = expected[record.logical_id]
            if (
                record.status != "valid"
                or type(record.success) is not bool
                or record.generation != manifest["generation"]
                or record.seed != seed
                or record.policy_rng != policy_rng
                or record.bundle_sha256 != (candidate_sha if arm == "candidate" else parent_sha)
                or (kind == "same_seed" and arm == "parent" and record.success)
            ):
                raise ValueError(f"promotion {kind} episode violates its frozen pair")
            videos = record.artifact_index.get("videos")
            if not isinstance(videos, dict) or set(videos) != {"agentview", "wrist", "multiview"}:
                raise ValueError(f"promotion {kind} episode lacks three-camera video evidence")
            for path in videos.values():
                _artifact(path, campaign_root=state_root)
            _artifact(record.artifact_index.get("latency_summary"), campaign_root=state_root)
            measured[arm] += int(record.success)
            arms[arm].append(record)
        if (
            decision.get("parent_successes") != measured["parent"]
            or decision.get("candidate_successes") != measured["candidate"]
        ):
            raise ValueError(f"promotion {kind} decision contradicts valid episodes")
        recomputed = evaluate_paired_gate(
            kind=kind,
            candidate_sha256=candidate_sha,
            parent_sha256=parent_sha,
            candidate_records=arms["candidate"],
            parent_records=arms["parent"],
            expected_seeds=tuple(ordered_seeds),
            same_seed_pass_rate=(0.5 if kind == "same_seed" else 1.0),
        )
        if not recomputed.passed or decision != recomputed.as_dict():
            raise ValueError(f"promotion {kind} decision fails causal recomputation")


def _score_final_pure_vla(
    campaign_root: Path,
    row: dict[str, Any],
    source_manifest: dict[str, Any],
    *,
    require_no_promotion: bool = True,
    verify_artifact_hashes: bool = False,
) -> int:
    """Score a terminal no-promotion task from its separate final-test lane."""

    source_state = read_json(campaign_root / "state/state.json")
    if (
        (require_no_promotion and source_state.get("current_bundle_sha256") is not None)
        or (require_no_promotion and source_state.get("candidate_sha256") is not None)
        or source_manifest.get("generation") != 0
        or source_manifest.get("baseline_mode") != "strict_pure_vla"
        or source_manifest.get("active_bundle_sha256") is not None
    ):
        raise ValueError("no-promotion task is not a pure-VLA harness")
    promotion_path = campaign_root / "state/ledgers/promotions.jsonl"
    if require_no_promotion and promotion_path.is_file() and _jsonl(promotion_path):
        raise ValueError("no-promotion task has promotion evidence")
    root = evaluation_root(campaign_root.parents[2], row)
    manifest = read_json(root / "manifest.json")
    state = read_json(root / "state.json")
    seeds = list(range(1, 21))
    if (
        manifest.get("runtime", {}).get("evaluation_scope") != EVALUATION_SCOPE
        or manifest["runtime"].get("evaluation_source_manifest_sha256")
        != canonical_sha256(source_manifest)
        or manifest.get("code_commit") != source_manifest.get("code_commit")
        or manifest.get("task") != row["task"]
        or manifest.get("generation") != 0
        or manifest.get("baseline_mode") != "strict_pure_vla"
        or manifest.get("active_bundle_sha256") is not None
        or manifest.get("rollout_seeds") != seeds
        or manifest.get("heldout_seeds") != source_manifest["rollout_seeds"][:20]
        or manifest.get("expected_rollouts") != 20
        or manifest.get("expected_heldout") != 20
        or manifest.get("policy_rng_by_seed")
        != {
            str(seed): source_manifest["policy_rng_by_seed"][str(seed)]
            for seed in (*seeds, *source_manifest["rollout_seeds"][:20])
        }
        or state.get("manifest_sha256") != canonical_sha256(manifest)
        or state.get("phase") != "rollout"
        or state.get("current_bundle_sha256") is not None
    ):
        raise ValueError("final pure-VLA test manifest or state differs")
    records = _jsonl(root / "ledgers/episodes.jsonl")
    if len(records) != 20:
        raise ValueError(f"final pure-VLA test has {len(records)} valid episodes, expected 20")
    observed: set[str] = set()
    successes = 0
    for payload in records:
        record = EpisodeRecord.from_dict(payload)
        if record.logical_id in observed:
            raise ValueError("final pure-VLA test has a duplicate episode")
        observed.add(record.logical_id)
        suffix = record.logical_id.removeprefix("g0000-rollout-")
        index = (
            int(suffix)
            if record.logical_id.startswith("g0000-rollout-") and suffix.isdigit()
            else -1
        )
        if (
            not 0 <= index < 20
            or record.status != "valid"
            or record.generation != 0
            or record.seed != index + 1
            or record.policy_rng
            != source_manifest["policy_rng_by_seed"][str(index + 1)]
            or record.bundle_sha256 is not None
        ):
            raise ValueError("final pure-VLA episode violates frozen test schedule")
        videos = record.artifact_index.get("videos")
        if not isinstance(videos, dict) or not videos:
            raise ValueError("final pure-VLA episode has no video evidence")
        for path in videos.values():
            _artifact(path, campaign_root=root)
        _artifact(record.artifact_index.get("latency_summary"), campaign_root=root)
        if verify_artifact_hashes:
            _verify_trajectory_artifacts(record, campaign_root=root)
        successes += int(record.success is True)
    return successes


def _score_final_harness(
    campaign_root: Path,
    row: dict[str, Any],
    source_manifest: dict[str, Any],
    *,
    verify_artifact_hashes: bool = False,
) -> int:
    """Score the terminal promoted bundle only from its final-test lane."""

    bundle_sha = source_manifest.get("active_bundle_sha256")
    if not isinstance(bundle_sha, str) or len(bundle_sha) != 64:
        raise ValueError("final harness has no promoted bundle digest")
    root = final_harness_root(campaign_root.parents[2], row)
    manifest = read_json(root / "manifest.json")
    state = read_json(root / "state.json")
    seeds = list(range(1, 21))
    controls = list(source_manifest["rollout_seeds"][:20])
    expected_rng = {
        str(seed): source_manifest["policy_rng_by_seed"][str(seed)]
        for seed in (*seeds, *controls)
    }
    if (
        manifest.get("runtime", {}).get("evaluation_scope") != FINAL_HARNESS_SCOPE
        or manifest["runtime"].get("evaluation_source_manifest_sha256")
        != canonical_sha256(source_manifest)
        or manifest["runtime"].get("evaluation_source_bundle_sha256") != bundle_sha
        or manifest.get("code_commit") != source_manifest.get("code_commit")
        or manifest.get("task") != row["task"]
        or manifest.get("generation") != source_manifest["generation"]
        or manifest.get("baseline_mode") != "active_bundle"
        or manifest.get("active_bundle_sha256") != bundle_sha
        or manifest.get("rollout_seeds") != seeds
        or manifest.get("heldout_seeds") != controls
        or manifest.get("expected_rollouts") != 20
        or manifest.get("expected_heldout") != 20
        or manifest.get("policy_rng_by_seed") != expected_rng
        or state.get("manifest_sha256") != canonical_sha256(manifest)
        or state.get("phase") != "rollout"
        or state.get("current_bundle_sha256") != bundle_sha
    ):
        raise ValueError("final harness test manifest or state differs")
    records = _jsonl(root / "ledgers/episodes.jsonl")
    if len(records) != 20:
        raise ValueError(f"final harness test has {len(records)} episodes, expected 20")
    seen: set[str] = set()
    successes = 0
    for payload in records:
        record = EpisodeRecord.from_dict(payload)
        if record.logical_id in seen:
            raise ValueError("final harness test has a duplicate episode")
        seen.add(record.logical_id)
        suffix = record.logical_id.removeprefix(
            f"g{source_manifest['generation']:04d}-rollout-"
        )
        index = int(suffix) if suffix.isdigit() else -1
        if (
            not 0 <= index < 20
            or record.logical_id
            != f"g{source_manifest['generation']:04d}-rollout-{index:03d}"
            or record.status != "valid"
            or type(record.success) is not bool
            or record.generation != source_manifest["generation"]
            or record.seed != index + 1
            or record.policy_rng != expected_rng[str(index + 1)]
            or record.bundle_sha256 != bundle_sha
        ):
            raise ValueError("final harness episode violates frozen test schedule")
        videos = record.artifact_index.get("videos")
        if not isinstance(videos, dict) or set(videos) != {
            "agentview", "wrist", "multiview"
        }:
            raise ValueError("final harness episode lacks three-camera video evidence")
        for path in videos.values():
            _artifact(path, campaign_root=root)
        _artifact(record.artifact_index.get("latency_summary"), campaign_root=root)
        if verify_artifact_hashes:
            _verify_trajectory_artifacts(record, campaign_root=root)
        successes += int(record.success)
    return successes


def _verify_development_baseline(
    campaign_root: Path, manifest: dict[str, Any], development: list[int]
) -> int:
    """Require the complete, frozen pure-VLA corpus before scoring a task."""

    records = _jsonl(campaign_root / "state/ledgers/episodes.jsonl")
    if len(records) != len(development):
        raise ValueError(
            f"development baseline has {len(records)} valid episodes, "
            f"expected {len(development)}"
        )
    seen: set[str] = set()
    failures = 0
    for payload in records:
        record = EpisodeRecord.from_dict(payload)
        logical_id = record.logical_id
        if logical_id in seen:
            raise ValueError("development baseline has a duplicate episode")
        seen.add(logical_id)
        suffix = logical_id.removeprefix("g0000-rollout-")
        index = (
            int(suffix)
            if logical_id.startswith("g0000-rollout-") and suffix.isdigit()
            else -1
        )
        if (
            not 0 <= index < len(development)
            or record.status != "valid"
            or type(record.success) is not bool
            or record.generation != 0
            or record.seed != development[index]
            or record.policy_rng
            != manifest["policy_rng_by_seed"][str(development[index])]
            or record.bundle_sha256 is not None
        ):
            raise ValueError("development baseline violates frozen pure-VLA schedule")
        videos = record.artifact_index.get("videos")
        if not isinstance(videos, dict) or set(videos) != {"agentview", "wrist", "multiview"}:
            raise ValueError("development baseline lacks three-camera video evidence")
        for path in videos.values():
            _artifact(path, campaign_root=campaign_root)
        _artifact(record.artifact_index.get("latency_summary"), campaign_root=campaign_root)
        failures += int(record.success is False)
    return failures


def _score_task(campaign_root: Path, row: dict[str, Any], code_commit: str) -> dict[str, Any]:
    nodes = _lineage(campaign_root, row, code_commit)
    manifest = nodes[0][1]
    development = manifest.get("rollout_seeds")
    if (
        not isinstance(development, list)
        or len(development) != 50
        or len(set(development)) != 50
        or set(development) & set(range(1, 21))
        or development != row.get("development_seeds")
    ):
        raise ValueError("campaign development schedule is missing or changed")
    if set(manifest.get("policy_rng_by_seed", {})) != {
        str(seed) for seed in (*development, *range(1, 21))
    }:
        raise ValueError("campaign policy RNG schedule is incomplete")
    development_failures = _verify_development_baseline(campaign_root, manifest, development)
    policy = manifest.get("runtime", {}).get("evolution_policy", {})
    if policy.get("heldout_mode") != "test" or policy.get("regression_scope") != "target_cluster":
        raise ValueError("campaign held-out or regression policy differs")

    if len(nodes) == 1:
        gates = list((nodes[0][0] / "candidates").glob("*/gates/heldout_20/plan.json"))
        state = read_json(nodes[0][0] / "state.json")
        if state.get("current_bundle_sha256") is None:
            if development_failures:
                raise ValueError(
                    f"unresolved development failures ({development_failures}/50) "
                    "with no validated recovery bundle"
                )
            baseline_successes = _score_final_pure_vla(campaign_root, row, manifest)
            zetta_successes = baseline_successes
            candidate_sha = None
        elif (
            len(gates) == 1
            and state.get("current_bundle_sha256") == gates[0].parents[2].name
        ):
            candidate_sha = state["current_bundle_sha256"]
            _verify_promotion_gates(nodes[0][0], manifest, candidate_sha, None)
            measured = _score_gate(campaign_root, nodes[0][0], manifest, candidate_sha, None)
            baseline_successes = measured["parent"]
            zetta_successes = measured["candidate"]
        else:
            raise ValueError("terminal promoted harness lacks a unique held-out gate")
        final_generation = 0
    else:
        first_handoff = read_json(nodes[0][0] / "analysis/generation-continuation.json")
        for source_root, source_manifest in nodes[:-1]:
            handoff = read_json(source_root / "analysis/generation-continuation.json")
            _verify_promotion_gates(
                source_root,
                source_manifest,
                handoff["promoted_bundle_sha256"],
                source_manifest.get("active_bundle_sha256"),
            )
        baseline = _score_gate(
            campaign_root,
            nodes[0][0],
            manifest,
            first_handoff["promoted_bundle_sha256"],
            None,
        )
        source_root, source_manifest = nodes[-2]
        last_handoff = read_json(source_root / "analysis/generation-continuation.json")
        candidate_sha = last_handoff["promoted_bundle_sha256"]
        final = _score_gate(
            campaign_root,
            source_root,
            source_manifest,
            candidate_sha,
            source_manifest.get("active_bundle_sha256"),
        )
        baseline_successes = baseline["parent"]
        zetta_successes = final["candidate"]
        final_generation = nodes[-1][1]["generation"]
    return {
        "task_id": row["task_id"],
        "baseline_successes": baseline_successes,
        "zetta_successes": zetta_successes,
        "episodes_per_method": 20,
        "baseline_rate_pct": 5.0 * baseline_successes,
        "zetta_rate_pct": 5.0 * zetta_successes,
        "candidate_sha256": candidate_sha,
        "final_generation": final_generation,
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
        "schema_version": "zetta-liberopro-table3-report-v1",
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
