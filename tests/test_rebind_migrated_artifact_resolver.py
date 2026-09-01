# Copyright (c) 2026 Zetta Contributors
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.evolution.rebind_migrated_artifact_resolver import repair_campaign
from zetta.evolution.lifecycle import _observed_critic_features
from zetta.evolution.models import CampaignManifest, EpisodeRecord
from zetta.evolution.store import CampaignStore


def _manifest() -> CampaignManifest:
    return CampaignManifest(
        campaign_id="migrated-artifact-resolver",
        environment="libero",
        task="goal-t-task2",
        generation=0,
        code_commit="1" * 40,
        prompt_sha256="2" * 64,
        model="test",
        tool_catalog_sha256="3" * 64,
        rollout_seeds=(7,),
        heldout_seeds=(19,),
        policy_rng_by_seed={"7": 11, "19": 23},
        expected_rollouts=1,
        expected_heldout=1,
        protocol_explicit=False,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _campaign_with_migrated_locators(
    tmp_path: Path, *, tamper_target: bool = False
) -> tuple[CampaignStore, Path]:
    source_root = tmp_path / "old" / "state-a4"
    target_root = tmp_path / "new" / "state-a10"
    relative_action = (
        Path("attempts")
        / "rollout-private"
        / "attempt-000"
        / "trajectory"
        / "actions.jsonl"
    )
    relative_video = (
        Path("attempts")
        / "rollout-private"
        / "attempt-000"
        / "videos"
        / "episode_agentview.mp4"
    )
    relative_states = (
        Path("attempts")
        / "rollout-private"
        / "attempt-000"
        / "trajectory"
        / "states.jsonl"
    )
    action_payload = b'{"action":"private"}\n'
    video_payload = b"private-video-bytes"
    states_payload = (
        b'{"state":{"command.available":false,"reset_only":1}}\n'
        b'{"state":{"command.available":true,"command.gripper":1,"stable":1}}\n'
        b'{"state":{"command.available":true,"command.gripper":-1,"stable":2}}\n'
    )
    for relative, payload in (
        (relative_action, action_payload),
        (relative_video, video_payload),
        (relative_states, states_payload),
    ):
        source = source_root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            b"tampered" if tamper_target and relative == relative_video else payload
        )

    store = CampaignStore(target_root)
    store.initialize(_manifest())
    store.record_episode(
        EpisodeRecord(
            episode_id="episode-private",
            logical_id="rollout-private",
            generation=0,
            seed=7,
            policy_rng=11,
            bundle_sha256=None,
            status="valid",
            success=False,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            elapsed_s=1.0,
            artifact_index={
                "states": str(source_root / relative_states),
                "trajectory_index": {
                    "artifact_paths": {
                        "actions": str(source_root / relative_action),
                        "states": str(source_root / relative_states),
                    },
                    "artifact_sha256": {
                        "actions": _sha256(action_payload),
                        "states": _sha256(states_payload),
                    },
                },
                "visual_evidence": {
                    "artifacts": {"episode_video": str(source_root / relative_video)},
                    "artifact_sha256": {"episode_video": _sha256(video_payload)},
                },
            },
            failure_segment=None,
            invalid_reason=None,
            attempt_index=0,
        )
    )
    return store, source_root


def test_rebinds_missing_frozen_sources_and_verifies_complete_index(
    tmp_path: Path,
) -> None:
    store, source_root = _campaign_with_migrated_locators(tmp_path)
    ledger = store.root / "ledgers" / "episodes.jsonl"
    ledger_before = ledger.read_bytes()
    assert _observed_critic_features(store, require_command_rows=True) == ()

    preview = repair_campaign(store.root, execute=False, verify_index=False)
    assert preview == {
        "schema_version": "migrated_artifact_resolver_rebind_v0",
        "accepted_episode_count": 1,
        "frozen_reference_count": 3,
        "existing_current_reference_count": 0,
        "rebound_reference_count": 3,
        "rebound_unique_content_count": 3,
        "all_references_resolved": True,
        "mode": "dry_run",
        "artifact_index_verified": False,
    }
    assert not (store.root / ".harness-private" / "artifact-resolver.json").exists()

    receipt = repair_campaign(store.root, execute=True, verify_index=True)

    assert receipt["artifact_index_verified"] is True
    assert receipt["artifact_index"]["artifact_count"] >= 3
    assert ledger.read_bytes() == ledger_before
    resolver = json.loads(
        (store.root / ".harness-private" / "artifact-resolver.json").read_text()
    )
    file_sources = [
        source["path"]
        for entry in resolver["entries"].values()
        for source in entry["sources"]
        if source.get("kind") == "file"
    ]
    assert file_sources
    assert all(not path.startswith(str(source_root.resolve())) for path in file_sources)
    assert all(path.startswith(str(store.root.resolve())) for path in file_sources)
    assert _observed_critic_features(store, require_command_rows=True) == (
        "command.available",
        "command.gripper",
        "stable",
    )


def test_observed_features_reject_tampered_rebound_state(tmp_path: Path) -> None:
    store, _ = _campaign_with_migrated_locators(tmp_path)
    repair_campaign(store.root, execute=True, verify_index=True)
    states = (
        store.root
        / "attempts"
        / "rollout-private"
        / "attempt-000"
        / "trajectory"
        / "states.jsonl"
    )
    states.write_text('{"state":{"command.available":true}}\n', encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="migrated artifact bytes differ from accepted provenance",
    ):
        _observed_critic_features(store, require_command_rows=True)


def test_rebind_rejects_bytes_that_do_not_match_accepted_digest(
    tmp_path: Path,
) -> None:
    store, _ = _campaign_with_migrated_locators(tmp_path, tamper_target=True)

    with pytest.raises(
        ValueError,
        match="migrated artifact bytes differ from accepted provenance",
    ):
        repair_campaign(store.root, execute=True, verify_index=False)

    assert not (store.root / ".harness-private" / "artifact-resolver.json").exists()
    assert not (
        store.root / ".harness-private" / "migrated-artifact-resolver-rebind.json"
    ).exists()
