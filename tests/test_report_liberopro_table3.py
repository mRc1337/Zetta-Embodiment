"""The Table 3 reporter must not silently score development or incomplete tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evolution.prepare_liberopro_paper_campaigns import PAPER_SETTINGS
from scripts.evolution.report_liberopro_table3 import _score_task, summarize
from scripts.evolution.run_liberopro_final_pure_vla import evaluation_root
from zetta.evolution.gating import evaluate_paired_gate
from zetta.evolution.jsonio import canonical_sha256
from zetta.evolution.models import EpisodeRecord


CANDIDATE = "a" * 64
COMMIT = "b" * 40


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_promotion_evidence(
    state_root: Path, manifest: dict, candidate: str, parent: str | None
) -> None:
    gates_path = state_root / "ledgers/gates.jsonl"
    decisions = [json.loads(line) for line in gates_path.read_text().splitlines()]
    assert len(decisions) == 1 and decisions[0]["kind"] == "heldout_20"
    decisions[0]["decision_id"] = f"gate-{candidate[:8]}-heldout"
    video = state_root / "evidence.mp4"
    latency = state_root / "latency.json"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"video")
    latency.write_bytes(b"{}")
    for kind in ("same_seed", "regression"):
        pairs = [
            {
                "seed": seed,
                "policy_rng": manifest["policy_rng_by_seed"][str(seed)],
                "logical_ids": {
                    arm: f"{kind}-{candidate[:8]}-{seed}-{arm}"
                    for arm in ("parent", "candidate")
                },
            }
            for seed in manifest["rollout_seeds"][:2]
        ]
        gate_root = state_root / "candidates" / candidate / "gates" / kind
        _write_json(
            gate_root / "plan.json",
            {
                "kind": kind,
                "candidate_sha256": candidate,
                "parent_sha256": parent,
                "manifest_sha256": canonical_sha256(manifest),
                "pairs": pairs,
            },
        )
        records = []
        for pair in pairs:
            for arm, logical_id in pair["logical_ids"].items():
                records.append({
                    "episode_id": logical_id,
                    "logical_id": logical_id,
                    "generation": manifest["generation"],
                    "seed": pair["seed"],
                    "policy_rng": pair["policy_rng"],
                    "bundle_sha256": candidate if arm == "candidate" else parent,
                    "status": "valid",
                    "success": arm == "candidate",
                    "started_at": "2026-09-27T00:00:00Z",
                    "finished_at": "2026-09-27T00:01:00Z",
                    "elapsed_s": 60.0,
                    "artifact_index": {
                        "candidate_intervention": arm == "candidate",
                        "initial_observation_identity": {
                            "state_sha256": f"{pair['seed']:064x}",
                            "camera_sha256": {},
                        },
                        "trajectory_index": {
                            "artifact_sha256": {
                                "actions": ("a" if arm == "parent" else "b") * 64,
                            },
                        },
                        "videos": {
                            camera: str(video)
                            for camera in ("agentview", "wrist", "multiview")
                        },
                        "latency_summary": str(latency),
                    },
                })
        valid = gate_root / "ledgers/valid.jsonl"
        valid.parent.mkdir(parents=True, exist_ok=True)
        valid.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        decisions.append(evaluate_paired_gate(
            kind=kind,
            candidate_sha256=candidate,
            parent_sha256=parent,
            candidate_records=[
                EpisodeRecord.from_dict(record)
                for record in records if record["logical_id"].endswith("-candidate")
            ],
            parent_records=[
                EpisodeRecord.from_dict(record)
                for record in records if record["logical_id"].endswith("-parent")
            ],
            expected_seeds=tuple(pair["seed"] for pair in pairs),
            same_seed_pass_rate=0.5 if kind == "same_seed" else 1.0,
        ).as_dict())
    gates_path.write_text(
        "".join(json.dumps(row) + "\n" for row in decisions), encoding="utf-8"
    )
    promotion = {
        "candidate_sha256": candidate,
        "parent_sha256": parent,
        "generation": manifest["generation"],
        "gate_decision_ids": sorted(row["decision_id"] for row in decisions),
    }
    (state_root / "ledgers/promotions.jsonl").write_text(
        json.dumps(promotion) + "\n", encoding="utf-8"
    )


def _completed_task(root: Path, suite: str, task_id: int) -> dict:
    campaign = root / "campaigns" / suite / f"task-{task_id:02d}"
    task = f"{suite}/task{task_id}"
    development = list(range(21, 71))
    manifest = {
        "code_commit": COMMIT,
        "task": task,
        "generation": 0,
        "heldout_seeds": list(range(1, 21)),
        "rollout_seeds": development,
        "policy_rng_by_seed": {str(seed): seed + 1000 for seed in (*development, *range(1, 21))},
        "runtime": {"evolution_policy": {"heldout_mode": "test", "regression_scope": "target_cluster"}},
    }
    _write_json(campaign / "manifest.json", manifest)
    _write_json(campaign / "state/state.json", {"phase": "complete", "current_bundle_sha256": CANDIDATE})
    video = campaign / "state/evidence.mp4"
    latency = campaign / "state/latency.json"
    video.write_bytes(b"video")
    latency.write_bytes(b"{}")
    development_records = []
    for index, seed in enumerate(development):
        development_records.append({
            "episode_id": f"dev-{task}-{seed}",
            "logical_id": f"g0000-rollout-{index:03d}",
            "generation": 0,
            "seed": seed,
            "policy_rng": manifest["policy_rng_by_seed"][str(seed)],
            "bundle_sha256": None,
            "status": "valid",
            "success": False,
            "started_at": "2026-09-27T00:00:00Z",
            "finished_at": "2026-09-27T00:01:00Z",
            "elapsed_s": 60.0,
            "artifact_index": {
                "videos": {camera: str(video) for camera in ("agentview", "wrist", "multiview")},
                "latency_summary": str(latency),
            },
        })
    baseline_ledger = campaign / "state/ledgers/episodes.jsonl"
    baseline_ledger.parent.mkdir(parents=True, exist_ok=True)
    baseline_ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in development_records),
        encoding="utf-8",
    )
    pairs = []
    records = []
    for index in range(20):
        seed = index + 1
        logical_ids = {arm: f"{task}-{seed}-{arm}" for arm in ("parent", "candidate")}
        pairs.append({"pair_index": index, "seed": seed, "policy_rng": seed + 1000, "logical_ids": logical_ids})
        for arm, logical_id in logical_ids.items():
            records.append({
                "episode_id": logical_id,
                "logical_id": logical_id,
                "generation": 0,
                "seed": seed,
                "policy_rng": seed + 1000,
                "bundle_sha256": CANDIDATE if arm == "candidate" else None,
                "status": "valid",
                "success": seed <= (10 if arm == "candidate" else 4),
                "started_at": "2026-09-27T00:00:00Z",
                "finished_at": "2026-09-27T00:01:00Z",
                "elapsed_s": 60.0,
                "artifact_index": {"videos": {"agentview": str(video)}, "latency_summary": str(latency)},
            })
    gate = campaign / "state/candidates" / CANDIDATE / "gates/heldout_20"
    _write_json(gate / "plan.json", {
        "kind": "heldout_20",
        "candidate_sha256": CANDIDATE,
        "parent_sha256": None,
        "manifest_sha256": canonical_sha256(manifest),
        "pairs": pairs,
    })
    valid = gate / "ledgers/valid.jsonl"
    valid.parent.mkdir(parents=True, exist_ok=True)
    valid.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    decisions = campaign / "state/ledgers/gates.jsonl"
    decisions.parent.mkdir(parents=True, exist_ok=True)
    decisions.write_text(json.dumps({
        "kind": "heldout_20",
        "candidate_sha256": CANDIDATE,
        "paired_count": 20,
        "parent_successes": 4,
        "candidate_successes": 10,
    }) + "\n", encoding="utf-8")
    _write_promotion_evidence(campaign / "state", manifest, CANDIDATE, None)
    return {
        "suite": suite,
        "task_id": task_id,
        "task": task,
        "campaign_root": str(campaign.relative_to(root)),
        "development_seeds": development,
    }


def test_report_requires_all_40_heldout_tasks_and_uses_macro_average(tmp_path: Path) -> None:
    rows = []
    for setting, slug, suite in PAPER_SETTINGS:
        for task_id in range(10):
            row = _completed_task(tmp_path, suite, task_id)
            row["setting"] = setting
            rows.append(row)
    _write_json(tmp_path / "campaign-plan.json", {"code_commit": COMMIT, "campaigns": rows})
    report = summarize(tmp_path)
    assert report["status"] == "complete"
    assert report["baseline_overall_macro_pct"] == 20.0
    assert report["zetta_overall_macro_pct"] == 50.0
    assert len(report["settings"]) == 4

    gate = tmp_path / rows[0]["campaign_root"] / "state/candidates" / CANDIDATE / "gates/heldout_20/ledgers/valid.jsonl"
    gate.write_text("\n".join(gate.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
    incomplete = summarize(tmp_path)
    assert incomplete["status"] == "incomplete"
    assert incomplete["completed_tasks"] == 39
    assert "baseline_overall_macro_pct" not in incomplete


def test_report_rejects_missing_or_drifted_development_baseline(tmp_path: Path) -> None:
    row = _completed_task(tmp_path, "libero_goal_task", 0)
    campaign = tmp_path / row["campaign_root"]
    ledger = campaign / "state/ledgers/episodes.jsonl"
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records[:-1]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected 50"):
        _score_task(campaign, row, COMMIT)

    records[0]["policy_rng"] += 1
    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="frozen pure-VLA schedule"):
        _score_task(campaign, row, COMMIT)


def test_report_rejects_promotion_without_paper_development_gates(tmp_path: Path) -> None:
    row = _completed_task(tmp_path, "libero_goal_task", 0)
    campaign = tmp_path / row["campaign_root"]
    gates = campaign / "state/ledgers/gates.jsonl"
    decisions = [json.loads(line) for line in gates.read_text().splitlines()]
    same_seed = next(row for row in decisions if row["kind"] == "same_seed")
    same_seed["candidate_successes"] = 0
    gates.write_text("".join(json.dumps(row) + "\n" for row in decisions), encoding="utf-8")
    with pytest.raises(ValueError, match="same_seed gate missed the paper threshold"):
        _score_task(campaign, row, COMMIT)

    same_seed["candidate_successes"] = 2
    regression = next(row for row in decisions if row["kind"] == "regression")
    regression["candidate_successes"] = 1
    gates.write_text("".join(json.dumps(row) + "\n" for row in decisions), encoding="utf-8")
    with pytest.raises(ValueError, match="regression gate missed the paper threshold"):
        _score_task(campaign, row, COMMIT)

    regression["candidate_successes"] = 2
    gates.write_text("".join(json.dumps(row) + "\n" for row in decisions), encoding="utf-8")
    regression_plan = campaign / "state/candidates" / CANDIDATE / "gates/regression/plan.json"
    plan = json.loads(regression_plan.read_text())
    new_seed = row["development_seeds"][2]
    plan["pairs"][1]["seed"] = new_seed
    plan["pairs"][1]["policy_rng"] = new_seed + 1000
    _write_json(regression_plan, plan)
    with pytest.raises(ValueError, match="originating failure cluster"):
        _score_task(campaign, row, COMMIT)
    plan["pairs"][1]["seed"] = row["development_seeds"][1]
    plan["pairs"][1]["policy_rng"] = row["development_seeds"][1] + 1000
    _write_json(regression_plan, plan)
    promotions = campaign / "state/ledgers/promotions.jsonl"
    promotion = json.loads(promotions.read_text())
    promotion["gate_decision_ids"] = []
    promotions.write_text(json.dumps(promotion) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not bind its gate decisions"):
        _score_task(campaign, row, COMMIT)


def test_report_recounts_development_gate_episodes(tmp_path: Path) -> None:
    row = _completed_task(tmp_path, "libero_goal_task", 0)
    campaign = tmp_path / row["campaign_root"]
    ledger = (
        campaign / "state/candidates" / CANDIDATE
        / "gates/same_seed/ledgers/valid.jsonl"
    )
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    records[1]["success"] = False
    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="decision contradicts valid episodes"):
        _score_task(campaign, row, COMMIT)

    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records[:-1]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="lacks complete valid episode evidence"):
        _score_task(campaign, row, COMMIT)


def test_report_rejects_unattributed_same_seed_success(tmp_path: Path) -> None:
    row = _completed_task(tmp_path, "libero_goal_task", 0)
    campaign = tmp_path / row["campaign_root"]
    ledger = (
        campaign / "state/candidates" / CANDIDATE
        / "gates/same_seed/ledgers/valid.jsonl"
    )
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    for record in records:
        if record["logical_id"].endswith("-candidate"):
            record["artifact_index"]["candidate_intervention"] = False
    ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="causal recomputation"):
        _score_task(campaign, row, COMMIT)


def test_report_rejects_nonbaseline_parent_arm(tmp_path: Path) -> None:
    rows = []
    for setting, _, suite in PAPER_SETTINGS:
        for task_id in range(10):
            row = _completed_task(tmp_path, suite, task_id)
            row["setting"] = setting
            rows.append(row)
    _write_json(tmp_path / "campaign-plan.json", {"code_commit": COMMIT, "campaigns": rows})
    gate = tmp_path / rows[0]["campaign_root"] / "state/candidates" / CANDIDATE / "gates/heldout_20/plan.json"
    plan = json.loads(gate.read_text(encoding="utf-8"))
    plan["parent_sha256"] = "c" * 64
    _write_json(gate, plan)
    report = summarize(tmp_path)
    assert report["status"] == "incomplete"
    assert report["completed_tasks"] == 39
    assert "pure-VLA" in report["incomplete"][0]["reason"]


def test_report_scores_final_promoted_generation_not_completed_parent(tmp_path: Path) -> None:
    row = _completed_task(tmp_path, "libero_goal_task", 0)
    campaign = tmp_path / row["campaign_root"]
    parent_manifest = json.loads((campaign / "manifest.json").read_text())
    child = campaign / "state/children/generation-0001"
    child_manifest = {
        **parent_manifest,
        "generation": 1,
        "active_bundle_sha256": CANDIDATE,
        "parent_bundle_sha256": CANDIDATE,
        "baseline_mode": "active_bundle",
    }
    _write_json(child / "manifest.json", child_manifest)
    _write_json(child / "state.json", {"phase": "complete"})
    _write_json(
        campaign / "state/analysis/generation-continuation.json",
        {
            "parent_manifest_sha256": canonical_sha256(parent_manifest),
            "child_manifest_sha256": canonical_sha256(child_manifest),
            "child_campaign_root": str(child),
            "child_generation": 1,
            "promoted_bundle_sha256": CANDIDATE,
        },
    )
    result = _score_task(campaign, row, COMMIT)
    assert result["baseline_successes"] == 4
    assert result["zetta_successes"] == 10
    assert result["final_generation"] == 1

    handoff = campaign / "state/analysis/generation-continuation.json"
    payload = json.loads(handoff.read_text())
    payload["promoted_bundle_sha256"] = "c" * 64
    _write_json(handoff, payload)
    with pytest.raises(ValueError, match="child binding"):
        _score_task(campaign, row, COMMIT)


def test_report_uses_last_gate_after_two_promotions(tmp_path: Path) -> None:
    row = _completed_task(tmp_path, "libero_goal_task", 0)
    campaign = tmp_path / row["campaign_root"]
    root_manifest = json.loads((campaign / "manifest.json").read_text())
    g1 = campaign / "state/children/generation-0001"
    g1_manifest = {
        **root_manifest,
        "generation": 1,
        "active_bundle_sha256": CANDIDATE,
        "parent_bundle_sha256": CANDIDATE,
        "baseline_mode": "active_bundle",
    }
    _write_json(g1 / "manifest.json", g1_manifest)
    _write_json(g1 / "state.json", {"phase": "complete"})
    _write_json(
        campaign / "state/analysis/generation-continuation.json",
        {
            "parent_manifest_sha256": canonical_sha256(root_manifest),
            "child_manifest_sha256": canonical_sha256(g1_manifest),
            "child_campaign_root": str(g1),
            "child_generation": 1,
            "promoted_bundle_sha256": CANDIDATE,
        },
    )

    final_candidate = "d" * 64
    original_gate = campaign / "state/candidates" / CANDIDATE / "gates/heldout_20"
    final_gate = g1 / "candidates" / final_candidate / "gates/heldout_20"
    plan = json.loads((original_gate / "plan.json").read_text())
    plan["candidate_sha256"] = final_candidate
    plan["parent_sha256"] = CANDIDATE
    plan["manifest_sha256"] = canonical_sha256(g1_manifest)
    _write_json(final_gate / "plan.json", plan)
    records = [json.loads(line) for line in (original_gate / "ledgers/valid.jsonl").read_text().splitlines()]
    for record in records:
        record["generation"] = 1
        seed = record["seed"]
        if record["logical_id"].endswith("-parent"):
            record["bundle_sha256"] = CANDIDATE
            record["success"] = seed <= 10
        else:
            record["bundle_sha256"] = final_candidate
            record["success"] = seed <= 15
    valid = final_gate / "ledgers/valid.jsonl"
    valid.parent.mkdir(parents=True, exist_ok=True)
    valid.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    decision = g1 / "ledgers/gates.jsonl"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text(json.dumps({
        "kind": "heldout_20",
        "candidate_sha256": final_candidate,
        "paired_count": 20,
        "parent_successes": 10,
        "candidate_successes": 15,
    }) + "\n", encoding="utf-8")
    _write_promotion_evidence(g1, g1_manifest, final_candidate, CANDIDATE)
    g2 = g1 / "children/generation-0002"
    g2_manifest = {
        **g1_manifest,
        "generation": 2,
        "active_bundle_sha256": final_candidate,
        "parent_bundle_sha256": final_candidate,
    }
    _write_json(g2 / "manifest.json", g2_manifest)
    _write_json(g2 / "state.json", {"phase": "complete"})
    _write_json(
        g1 / "analysis/generation-continuation.json",
        {
            "parent_manifest_sha256": canonical_sha256(g1_manifest),
            "child_manifest_sha256": canonical_sha256(g2_manifest),
            "child_campaign_root": str(g2),
            "child_generation": 2,
            "promoted_bundle_sha256": final_candidate,
        },
    )

    result = _score_task(campaign, row, COMMIT)
    assert result["baseline_successes"] == 4
    assert result["zetta_successes"] == 15
    assert result["final_generation"] == 2
    assert result["candidate_sha256"] == final_candidate


def test_report_scores_no_promotion_only_with_complete_pure_vla_final_test(tmp_path: Path) -> None:
    row = _completed_task(tmp_path, "libero_goal_task", 0)
    row["setting_slug"] = "goal-t"
    campaign = tmp_path / row["campaign_root"]
    # A candidate may have completed a test gate but failed promotion; its
    # candidate arm must not become the reported final harness.
    source_path = campaign / "manifest.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source.update({"baseline_mode": "strict_pure_vla", "active_bundle_sha256": None})
    _write_json(source_path, source)
    _write_json(campaign / "state/state.json", {"phase": "complete", "current_bundle_sha256": None})
    (campaign / "state/ledgers/promotions.jsonl").unlink()
    development_ledger = campaign / "state/ledgers/episodes.jsonl"
    development_records = [
        json.loads(line) for line in development_ledger.read_text(encoding="utf-8").splitlines()
    ]
    for record in development_records:
        record["success"] = True
    development_records[0]["success"] = False
    development_ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in development_records),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unresolved development failures"):
        _score_task(campaign, row, COMMIT)
    development_records[0]["success"] = True
    development_ledger.write_text(
        "".join(json.dumps(record) + "\n" for record in development_records),
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        _score_task(campaign, row, COMMIT)

    root = evaluation_root(tmp_path, row)
    manifest = {
        **source,
        "rollout_seeds": list(range(1, 21)),
        "heldout_seeds": source["rollout_seeds"][:20],
        "expected_rollouts": 20,
        "expected_heldout": 20,
        "policy_rng_by_seed": {
            str(seed): source["policy_rng_by_seed"][str(seed)]
            for seed in (*range(1, 21), *source["rollout_seeds"][:20])
        },
        "runtime": {
            **source["runtime"],
            "evaluation_scope": "final_pure_vla_test",
            "evaluation_source_manifest_sha256": canonical_sha256(source),
        },
    }
    _write_json(root / "manifest.json", manifest)
    _write_json(root / "state.json", {
        "phase": "rollout",
        "manifest_sha256": canonical_sha256(manifest),
        "current_bundle_sha256": None,
    })
    video = root / "evidence.mp4"
    latency = root / "latency.json"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"video")
    latency.write_bytes(b"{}")
    ledger = root / "ledgers/episodes.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for index in range(20):
        seed = index + 1
        records.append({
            "episode_id": f"test-{seed}",
            "logical_id": f"g0000-rollout-{index:03d}",
            "generation": 0,
            "seed": seed,
            "policy_rng": source["policy_rng_by_seed"][str(seed)],
            "bundle_sha256": None,
            "status": "valid",
            "success": seed <= 7,
            "started_at": "2026-09-27T00:00:00Z",
            "finished_at": "2026-09-27T00:01:00Z",
            "elapsed_s": 60.0,
            "artifact_index": {"videos": {"agentview": str(video)}, "latency_summary": str(latency)},
        })
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    result = _score_task(campaign, row, COMMIT)
    assert result["baseline_successes"] == result["zetta_successes"] == 7
    assert result["candidate_sha256"] is None

    ledger.write_text("".join(json.dumps(record) + "\n" for record in records[:-1]), encoding="utf-8")
    with pytest.raises(ValueError, match="expected 20"):
        _score_task(campaign, row, COMMIT)
