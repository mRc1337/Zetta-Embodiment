from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.evolution.audit_liberopro_runtime_preflight import audit
from zetta.evolution.jsonio import file_sha256


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "matrix"
    root.mkdir()
    plan = root / "campaign-plan.json"
    plan.write_text(
        json.dumps({"code_commit": "a" * 40, "runtime": {"url": "http://127.0.0.1:18731"}}),
        encoding="utf-8",
    )
    model = tmp_path / "rev123"
    norm = model / "physical-intelligence/libero/norm_stats.json"
    norm.parent.mkdir(parents=True)
    norm.write_text("{}", encoding="utf-8")
    weights = model / "model.safetensors"
    weights.write_bytes(b"test weights")
    config = tmp_path / "runtime.yaml"
    config.write_text(
        yaml.safe_dump({"rollout_worker": {"policy_config": {"model_path": str(model)}}}),
        encoding="utf-8",
    )
    preflight = root / "preflight"
    preflight.mkdir()
    provenance = preflight / "checkpoint-provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "campaign_plan_sha256": file_sha256(plan),
                "code_commit": "a" * 40,
                "runtime_config_path": str(config),
                "runtime_config_sha256": file_sha256(config),
                "runtime_url": "http://127.0.0.1:18731",
                "model_path": str(model),
                "model_revision": "rev123",
                "model_safetensors_sha256": file_sha256(weights),
                "norm_stats_sha256": file_sha256(norm),
            }
        ),
        encoding="utf-8",
    )
    return root, config, provenance


def test_preflight_accepts_frozen_matrix_and_checkpoint(tmp_path: Path) -> None:
    root, config, _ = _fixture(tmp_path)
    report = audit(root, config)
    assert report["status"] == "pass"
    assert report["model_revision"] == "rev123"
    assert len(report["verified_files"]) == 2


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("plan", "campaign plan SHA-256"),
        ("config", "runtime config SHA-256"),
        ("weights", "model.safetensors"),
        ("norm", "norm_stats.json"),
    ],
)
def test_preflight_rejects_content_drift(
    tmp_path: Path, target: str, expected: str
) -> None:
    root, config, _ = _fixture(tmp_path)
    model = tmp_path / "rev123"
    files = {
        "plan": root / "campaign-plan.json",
        "config": config,
        "weights": model / "model.safetensors",
        "norm": model / "physical-intelligence/libero/norm_stats.json",
    }
    with files[target].open("ab") as handle:
        handle.write(b"drift")
    with pytest.raises(ValueError, match=expected):
        audit(root, config)


def test_preflight_rejects_model_path_drift(tmp_path: Path) -> None:
    root, config, provenance_path = _fixture(tmp_path)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["model_path"] = str(tmp_path / "other-model")
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    with pytest.raises(ValueError, match="model path"):
        audit(root, config)
