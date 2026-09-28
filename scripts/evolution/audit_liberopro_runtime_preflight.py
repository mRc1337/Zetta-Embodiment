#!/usr/bin/env python3
"""Fail closed if a LIBERO-Pro matrix no longer uses its frozen checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from zetta.evolution.jsonio import file_sha256, read_json


def audit(
    matrix_root: Path,
    runtime_config: Path,
    provenance_path: Path | None = None,
) -> dict[str, Any]:
    root = matrix_root.resolve()
    config_path = runtime_config.resolve()
    provenance_path = (
        provenance_path.resolve()
        if provenance_path is not None
        else root / "preflight/checkpoint-provenance.json"
    )
    provenance = read_json(provenance_path)
    plan_path = root / "campaign-plan.json"

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    require(
        file_sha256(plan_path) == provenance.get("campaign_plan_sha256"),
        "campaign plan SHA-256 differs from checkpoint provenance",
    )
    plan = read_json(plan_path)
    require(
        plan.get("code_commit") == provenance.get("code_commit"),
        "code commit differs from checkpoint provenance",
    )
    require(
        str(config_path) == provenance.get("runtime_config_path"),
        "runtime config path differs from checkpoint provenance",
    )
    require(
        file_sha256(config_path) == provenance.get("runtime_config_sha256"),
        "runtime config SHA-256 differs from checkpoint provenance",
    )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    require(
        plan.get("runtime", {}).get("url") == provenance.get("runtime_url"),
        "runtime URL differs from checkpoint provenance",
    )
    policy = config["rollout_worker"]["policy_config"]
    model_path = Path(policy["model_path"]).resolve()
    require(
        str(model_path) == provenance.get("model_path"),
        "configured model path differs from checkpoint provenance",
    )
    require(
        model_path.name == provenance.get("model_revision"),
        "configured model revision differs from checkpoint provenance",
    )
    expected_files = {
        "model.safetensors": "model_safetensors_sha256",
        "physical-intelligence/libero/norm_stats.json": "norm_stats_sha256",
    }
    verified: dict[str, str] = {}
    for relative, field in expected_files.items():
        target = model_path / relative
        require(target.is_file(), f"checkpoint file missing: {relative}")
        digest = file_sha256(target)
        require(
            digest == provenance.get(field),
            f"checkpoint file SHA-256 differs: {relative}",
        )
        verified[relative] = digest
    return {
        "status": "pass",
        "matrix_root": str(root),
        "code_commit": plan["code_commit"],
        "campaign_plan_sha256": provenance["campaign_plan_sha256"],
        "runtime_config_sha256": provenance["runtime_config_sha256"],
        "model_revision": provenance["model_revision"],
        "verified_files": verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--runtime-config", type=Path, required=True)
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            audit(args.matrix_root, args.runtime_config, args.provenance),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
