# Copyright (c) 2026 Zetta Contributors
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.evolution.prepare_liberopro_paper_campaigns import (
    HELDOUT_SEEDS,
    PAPER_SETTINGS,
    _parser,
    build_matrix_plan,
    materialize_matrix,
)
from zetta.evolution.jsonio import read_json


def _catalog() -> dict:
    return {
        "suites": [
            {
                "suite": suite,
                "task_count": 10,
                "tasks": [
                    {
                        "task_id": task_id,
                        "task_name": f"{suite}_task_{task_id}",
                        "language": f"instruction for {suite} task {task_id}",
                        "init_state_count": 50,
                    }
                    for task_id in range(10)
                ],
            }
            for _, _, suite in PAPER_SETTINGS
        ]
    }


def test_paper_matrix_has_all_cases_and_strict_seed_partition() -> None:
    plan = build_matrix_plan(
        catalog=_catalog(),
        code_commit="a" * 40,
        master_seed=260816590,
        runtime_url="http://127.0.0.1:18730",
        runtime_policy_id="pi05",
    )

    assert plan["summary"] == {
        "setting_count": 4,
        "tasks_per_setting": 10,
        "campaign_count": 40,
        "development_rollout_slots_per_round": 2000,
        "heldout_episodes_per_method": 800,
        "all_init_states_nonempty": True,
        "seed_partitions_disjoint": True,
        "official_horizons": True,
    }
    assert plan["heldout"]["mode"] == "test"
    assert plan["heldout"]["used_for_promotion"] is False
    assert plan["development"]["target_cluster_count"] == 1
    assert plan["development"]["representative"] == "deterministic_medoid"
    assert plan["development"]["historical_cluster_regression_rate"] == 1.0
    assert len({row["campaign_id"] for row in plan["campaigns"]}) == 40
    for row in plan["campaigns"]:
        assert len(row["development_seeds"]) == 50
        assert len(set(row["development_seeds"])) == 50
        assert tuple(row["heldout_seeds"]) == HELDOUT_SEEDS
        assert set(row["development_seeds"]).isdisjoint(HELDOUT_SEEDS)
        assert row["evaluation_horizon"]["is_standard"] is True


def test_paper_matrix_rejects_empty_init_states() -> None:
    catalog = _catalog()
    catalog["suites"][0]["tasks"][3]["init_state_count"] = 0

    with pytest.raises(ValueError, match="has no init states"):
        build_matrix_plan(
            catalog=catalog,
            code_commit="a" * 40,
            master_seed=7,
            runtime_url="http://127.0.0.1:18730",
            runtime_policy_id="pi05",
        )


def test_materialized_matrix_freezes_paper_protocol_and_resumes(tmp_path: Path) -> None:
    output = tmp_path / "paper-campaigns"
    args = _parser().parse_args(
        [
            "--output-root",
            str(output),
            "--repository-root",
            str(Path(__file__).resolve().parents[1]),
            "--runtime-python",
            sys.executable,
            "--code-commit",
            "b" * 40,
        ]
    )

    first = materialize_matrix(args, catalog=_catalog())
    assert first["status"] == "prepared"
    assert len(first["campaigns"]) == 40

    sample = read_json(output / "campaigns/goal-t/task-00/manifest.json")
    policy = sample["runtime"]["evolution_policy"]
    assert policy["heldout_mode"] == "test"
    assert policy["skip_regression_gate"] is False
    assert policy["same_seed_pass_rate"] == 0.5
    assert policy["maximum_target_clusters"] == 1
    assert sample["runtime"]["latency"]["enabled"] is True
    assert "--record-latency" in sample["runtime"]["rollout_command"]
    assert sample["expected_rollouts"] == 50
    assert sample["expected_heldout"] == 20

    args.resume = True
    second = materialize_matrix(args, catalog=_catalog())
    assert second["campaigns"] == first["campaigns"]
