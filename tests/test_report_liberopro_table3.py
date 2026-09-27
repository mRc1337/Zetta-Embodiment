"""The Table 3 reporter must not silently score development or incomplete tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.evolution.prepare_liberopro_paper_campaigns import PAPER_SETTINGS
from scripts.evolution.report_liberopro_table3 import summarize
from zetta.evolution.jsonio import canonical_sha256


CANDIDATE = "a" * 64
COMMIT = "b" * 40


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


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
    _write_json(campaign / "state/state.json", {"phase": "complete"})
    video = campaign / "state/evidence.mp4"
    latency = campaign / "state/latency.json"
    video.write_bytes(b"video")
    latency.write_bytes(b"{}")
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
