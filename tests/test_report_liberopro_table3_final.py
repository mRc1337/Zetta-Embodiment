"""The final reporter scores only complete post-evolution test evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evolution import report_liberopro_table3_final as final_report
from scripts.evolution.prepare_liberopro_paper_campaigns import PAPER_SETTINGS
from scripts.evolution.report_liberopro_table3 import _score_final_harness
from scripts.evolution.run_liberopro_final_harness import (
    _evaluation_manifest,
    evaluation_root,
)
from zetta.evolution.jsonio import atomic_write_json, canonical_sha256, file_sha256
from zetta.evolution.models import CampaignManifest
from zetta.evolution.store import CampaignStore


def _final_harness_fixture(tmp_path: Path) -> tuple[Path, dict, dict]:
    bundle = {"candidate_id": "final"}
    bundle_sha = canonical_sha256(bundle)
    bundle_file = tmp_path / "bundle.json"
    atomic_write_json(bundle_file, bundle, overwrite=False)
    development = tuple(range(21, 71))
    heldout = tuple(range(1, 21))
    source = CampaignManifest(
        campaign_id="goal-t-task0-g0001",
        environment="libero_pro",
        task="libero_goal_task/task0",
        generation=1,
        code_commit="a" * 40,
        prompt_sha256="b" * 64,
        model="test-model",
        tool_catalog_sha256="c" * 64,
        rollout_seeds=development,
        heldout_seeds=heldout,
        policy_rng_by_seed={str(seed): seed + 1000 for seed in (*development, *heldout)},
        expected_rollouts=50,
        expected_heldout=20,
        parent_bundle_sha256=bundle_sha,
        active_bundle_sha256=bundle_sha,
        baseline_mode="active_bundle",
        runtime={
            "rollout_command": ["example", "{seed}"],
            "bundle_files_by_sha": {bundle_sha: str(bundle_file)},
        },
    )
    row = {"setting_slug": "goal-t", "task_id": 0, "task": source.task}
    campaign = tmp_path / "campaigns/goal-t/task-00"
    campaign.mkdir(parents=True)
    final = evaluation_root(tmp_path, row)
    CampaignStore(final).initialize(_evaluation_manifest(source))
    video = final / "evidence.mp4"
    latency = final / "latency.json"
    video.write_bytes(b"video")
    latency.write_bytes(b"{}")
    actions = final / "actions.jsonl"
    actions.write_bytes(b"[]\n")
    artifact_paths = {"actions": str(actions), "video-00": str(video)}
    artifact_hashes = {
        name: file_sha256(Path(path)) for name, path in artifact_paths.items()
    }
    records = []
    for index, seed in enumerate(heldout):
        records.append({
            "episode_id": f"final-{seed}",
            "logical_id": f"g0001-rollout-{index:03d}",
            "generation": 1,
            "seed": seed,
            "policy_rng": source.policy_rng_by_seed[str(seed)],
            "bundle_sha256": bundle_sha,
            "status": "valid",
            "success": seed <= 12,
            "started_at": "2026-09-28T00:00:00Z",
            "finished_at": "2026-09-28T00:01:00Z",
            "elapsed_s": 60.0,
            "artifact_index": {
                "trajectory_index": {
                    "artifact_paths": artifact_paths,
                    "artifact_sha256": artifact_hashes,
                },
                "videos": {
                    name: str(video)
                    for name in ("agentview", "wrist", "multiview")
                },
                "latency_summary": str(latency),
            },
        })
    ledger = final / "ledgers/episodes.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return campaign, row, source.as_dict()


def test_final_harness_scores_exact_frozen_test_episodes(tmp_path: Path) -> None:
    campaign, row, source = _final_harness_fixture(tmp_path)
    assert _score_final_harness(campaign, row, source, verify_artifact_hashes=True) == 12


def test_final_harness_rejects_seed_drift(tmp_path: Path) -> None:
    campaign, row, source = _final_harness_fixture(tmp_path)
    ledger = evaluation_root(tmp_path, row) / "ledgers/episodes.jsonl"
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    records[0]["seed"] = 21
    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="frozen test schedule"):
        _score_final_harness(campaign, row, source, verify_artifact_hashes=True)


def test_final_harness_rejects_rewritten_video(tmp_path: Path) -> None:
    campaign, row, source = _final_harness_fixture(tmp_path)
    video = evaluation_root(tmp_path, row) / "evidence.mp4"
    video.write_bytes(b"rewritten video")
    with pytest.raises(ValueError, match="artifact hash differs"):
        _score_final_harness(campaign, row, source, verify_artifact_hashes=True)


def test_final_report_rejects_early_heldout_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = tmp_path / "campaigns/goal-t/task-00"
    node = campaign / "state"
    plan = node / "candidates" / ("d" * 64) / "gates/heldout_20/plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")
    development = list(range(21, 71))
    manifest = {
        "rollout_seeds": development,
        "policy_rng_by_seed": {
            str(seed): seed + 1000 for seed in (*development, *range(1, 21))
        },
        "runtime": {
            "evolution_policy": {
                "heldout_mode": "test",
                "regression_scope": "target_cluster",
            }
        },
    }
    monkeypatch.setattr(final_report, "_lineage", lambda *args: [(node, manifest)])
    monkeypatch.setattr(final_report, "_verify_development_baseline", lambda *args: 0)
    row = {"task": "libero_goal_task/task0", "task_id": 0, "development_seeds": development}
    with pytest.raises(ValueError, match="scheduled during evolution"):
        final_report._score_task(campaign, row, "a" * 40)


def test_final_report_requires_all_40_tasks_before_macro_average(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {
            "setting": setting,
            "task_id": task_id,
            "campaign_root": f"campaigns/{slug}/task-{task_id:02d}",
        }
        for setting, slug, _ in PAPER_SETTINGS
        for task_id in range(10)
    ]
    (tmp_path / "campaign-plan.json").write_text(
        json.dumps({"code_commit": "a" * 40, "campaigns": rows}), encoding="utf-8"
    )
    monkeypatch.setattr(
        final_report,
        "_score_task",
        lambda root, row, commit: {
            "task_id": row["task_id"],
            "baseline_rate_pct": 20.0,
            "zetta_rate_pct": 60.0,
        },
    )
    complete = final_report.summarize(tmp_path)
    assert complete["status"] == "complete"
    assert complete["baseline_overall_macro_pct"] == 20.0
    assert complete["zetta_overall_macro_pct"] == 60.0
    assert complete["episodes_per_task_method"] == 20

    def one_missing(root: Path, row: dict, commit: str) -> dict:
        if row["task_id"] == 0 and row["setting"] == PAPER_SETTINGS[0][0]:
            raise ValueError("final test is incomplete")
        return {"task_id": row["task_id"], "baseline_rate_pct": 20.0, "zetta_rate_pct": 60.0}

    monkeypatch.setattr(final_report, "_score_task", one_missing)
    incomplete = final_report.summarize(tmp_path)
    assert incomplete["status"] == "incomplete"
    assert incomplete["completed_tasks"] == 39
    assert "baseline_overall_macro_pct" not in incomplete
