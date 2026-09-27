"""The no-promotion final test keeps evaluation separate from evolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evolution import run_liberopro_final_pure_vla as final_runner
from scripts.evolution.run_liberopro_final_pure_vla import (
    _evaluation_manifest,
    _needs_final_baseline,
)
from zetta.evolution.models import CampaignManifest


def _source(tmp_path: Path) -> tuple[Path, CampaignManifest]:
    campaign = tmp_path / "campaigns/goal-t/task-00"
    campaign.mkdir(parents=True)
    development = tuple(range(21, 71))
    heldout = tuple(range(1, 21))
    manifest = CampaignManifest(
        campaign_id="paper-goal-t-task-00",
        environment="liberopro",
        task="libero_goal_task/task0",
        generation=0,
        code_commit="b" * 40,
        prompt_sha256="a" * 64,
        model="gpt-5.4",
        tool_catalog_sha256="c" * 64,
        rollout_seeds=development,
        heldout_seeds=heldout,
        policy_rng_by_seed={str(seed): seed + 1000 for seed in (*development, *heldout)},
        expected_rollouts=50,
        expected_heldout=20,
        runtime={"rollout_command": ["example", "{seed}"], "rollout_requires_api": True},
    )
    (campaign / "manifest.json").write_text(json.dumps(manifest.as_dict()), encoding="utf-8")
    state = campaign / "state/state.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"phase": "complete", "current_bundle_sha256": None}), encoding="utf-8")
    return campaign, manifest


def test_final_test_manifest_reuses_frozen_seeds_and_rng(tmp_path: Path) -> None:
    campaign, source = _source(tmp_path)
    assert _needs_final_baseline(campaign)
    final = _evaluation_manifest(campaign)
    assert final.rollout_seeds == tuple(range(1, 21))
    assert final.heldout_seeds == source.rollout_seeds[:20]
    assert final.policy_rng_by_seed["1"] == source.policy_rng_by_seed["1"]
    assert final.runtime["evaluation_source_manifest_sha256"] == source.sha256
    assert final.runtime["rollout_requires_api"] is False
    assert final.active_bundle_sha256 is None


def test_final_test_excludes_promoted_or_nonterminal_source(tmp_path: Path) -> None:
    campaign, _ = _source(tmp_path)
    handoff = campaign / "state/analysis/generation-continuation.json"
    handoff.parent.mkdir()
    handoff.write_text("{}", encoding="utf-8")
    assert not _needs_final_baseline(campaign)
    handoff.unlink()
    state = campaign / "state/state.json"
    state.write_text(json.dumps({"phase": "rollout", "current_bundle_sha256": None}), encoding="utf-8")
    with pytest.raises(ValueError, match="not terminal"):
        _needs_final_baseline(campaign)


def test_failed_candidate_gate_does_not_turn_into_final_harness(tmp_path: Path) -> None:
    campaign, _ = _source(tmp_path)
    gate = campaign / "state/candidates" / ("d" * 64) / "gates/heldout_20/plan.json"
    gate.parent.mkdir(parents=True)
    gate.write_text("{}", encoding="utf-8")
    assert _needs_final_baseline(campaign)


def test_final_test_waits_for_all_evolution_tasks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, _ = _source(tmp_path)
    row = {"task": "libero_goal_task/task0", "setting_slug": "goal-t", "task_id": 0}
    monkeypatch.setattr(final_runner, "_campaigns", lambda root: [(row, campaign)])
    monkeypatch.setattr(final_runner, "_effective_phase", lambda state, root: final_runner.CampaignPhase.ROLLOUT)
    result = final_runner.step(tmp_path, tmp_path / "queue", worker_host="gpu3")
    assert result["status"] == "waiting_for_evolution"
    assert not (tmp_path / "final-pure-vla").exists()
