"""Final harness measurement starts only after evolution terminates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts.evolution import run_liberopro_final_harness as runner
from zetta.evolution.jsonio import atomic_write_json, canonical_sha256
from zetta.evolution.models import CampaignManifest


def _source(tmp_path: Path) -> CampaignManifest:
    bundle = {"candidate_id": "frozen-final-harness"}
    bundle_sha = canonical_sha256(bundle)
    bundle_path = tmp_path / "bundle.json"
    atomic_write_json(bundle_path, bundle, overwrite=False)
    seeds = tuple(range(21, 71))
    heldout = tuple(range(1, 21))
    return CampaignManifest(
        campaign_id="task-g0001",
        environment="libero_pro",
        task="libero_goal_task/task0",
        generation=1,
        code_commit="a" * 40,
        prompt_sha256="b" * 64,
        model="test-model",
        tool_catalog_sha256="c" * 64,
        rollout_seeds=seeds,
        heldout_seeds=heldout,
        policy_rng_by_seed={str(seed): seed + 100 for seed in (*seeds, *heldout)},
        expected_rollouts=50,
        expected_heldout=20,
        parent_bundle_sha256=bundle_sha,
        active_bundle_sha256=bundle_sha,
        baseline_mode="active_bundle",
        runtime={
            "rollout_command": ["example", "{seed}"],
            "rollout_requires_api": True,
            "bundle_files_by_sha": {bundle_sha: str(bundle_path)},
        },
    )


def test_final_harness_reuses_frozen_test_rng_after_promotion(tmp_path: Path) -> None:
    source = _source(tmp_path)
    final = runner._evaluation_manifest(source)
    assert final.rollout_seeds == tuple(range(1, 21))
    assert final.heldout_seeds == source.rollout_seeds[:20]
    assert final.policy_rng_by_seed["1"] == source.policy_rng_by_seed["1"]
    assert final.active_bundle_sha256 == source.active_bundle_sha256
    assert final.runtime["evaluation_source_manifest_sha256"] == source.sha256
    assert final.runtime["evaluation_source_bundle_sha256"] == source.active_bundle_sha256


def test_final_harness_rejects_changed_bundle(tmp_path: Path) -> None:
    source = _source(tmp_path)
    bundle_path = Path(source.runtime["bundle_files_by_sha"][source.active_bundle_sha256])
    bundle_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing or changed"):
        runner._evaluation_manifest(source)


def test_final_harness_rejects_unpromoted_source(tmp_path: Path) -> None:
    source = _source(tmp_path)
    with pytest.raises(ValueError, match="promoted harness"):
        runner._evaluation_manifest(
            replace(
                source,
                generation=0,
                baseline_mode="strict_pure_vla",
                parent_bundle_sha256=None,
                active_bundle_sha256=None,
            )
        )
