# Copyright (c) 2026 Zetta Contributors
"""Replay one development rollout with only slide_grasp enabled, outside gates."""

from __future__ import annotations

import argparse
import copy
import os
import subprocess
import sys
from pathlib import Path

from zetta.evolution.jsonio import atomic_write_json, canonical_sha256, read_json
from zetta.evolution.models import CandidateBundle


def _replace_arg(command: list[str], flag: str, value: str) -> None:
    positions = [index for index, item in enumerate(command) if item == flag]
    if len(positions) != 1 or positions[0] + 1 >= len(command):
        raise ValueError(f"source rollout has no unique {flag}")
    command[positions[0] + 1] = value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-job", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--gpu", type=int, default=3)
    args = parser.parse_args()

    source = read_json(args.source_job)
    job = source.get("job")
    if (
        not isinstance(job, dict)
        or source.get("kind") != "rollout_terminal"
        or source.get("success") is not True
    ):
        raise ValueError("source must be one completed development rollout job")
    if not str(job.get("task", "")).startswith("libero_goal_task/task0"):
        raise ValueError("probe is bound to the bottom-drawer development task")
    if int(job.get("seed", 0)) in range(1, 21):
        raise ValueError("held-out seeds 1--20 are forbidden in this probe")
    command = list(job["command"])
    if Path(command[1]).name != "run_evolution_rollout.py":
        raise ValueError("source job does not invoke the expected rollout runner")
    source_bundle = read_json(command[command.index("--bundle") + 1])
    candidate = CandidateBundle.from_dict(source_bundle)
    if candidate.sha256 != job["bundle_sha256"]:
        raise ValueError("source bundle digest differs from completed job")
    probe_bundle = copy.deepcopy(source_bundle)
    if len(source_bundle["recovery_rules"]) != 1:
        raise ValueError("probe requires exactly one source recovery rule")
    steps = probe_bundle["recovery_rules"][0]["steps"]
    if len(steps) != 1 or steps[0]["tool"] != "semantic_joint_interact":
        raise ValueError("probe requires one semantic_joint_interact step")
    if "slide_grasp" in steps[0]["parameters"]:
        raise ValueError("source must leave slide_grasp at its default")
    steps[0]["parameters"]["slide_grasp"] = True
    modified = CandidateBundle.from_dict(probe_bundle)
    if modified.sha256 == candidate.sha256:
        raise ValueError("slide_grasp did not change the bundle digest")

    root = args.output_root.resolve()
    if root.exists():
        raise FileExistsError(f"non-scored output already exists: {root}")
    root.mkdir(parents=True)
    bundle_path = root / "slide-grasp-bundle.json"
    atomic_write_json(bundle_path, modified.as_dict(), overwrite=False)
    attempt = root / "attempt-000"
    repo = Path(__file__).resolve().parents[2]
    command[0] = sys.executable
    command[1] = str(repo / "robots/libero/run_evolution_rollout.py")
    _replace_arg(command, "--logical-id", "non-scored-slide-grasp-development")
    _replace_arg(command, "--bundle", str(bundle_path))
    _replace_arg(command, "--bundle-sha256", canonical_sha256(modified.as_dict()))
    _replace_arg(command, "--output-dir", str(attempt))
    _replace_arg(command, "--result-file", str(attempt / "episode_record.json"))
    atomic_write_json(
        root / "provenance.json",
        {
            "status": "non_scored_development_probe",
            "source_job_id": job["job_id"],
            "source_bundle_sha256": candidate.sha256,
            "probe_bundle_sha256": modified.sha256,
            "seed": job["seed"],
            "policy_rng": job["policy_rng"],
            "only_bundle_change": "recovery_rules[0].steps[0].parameters.slide_grasp=true",
            "command": command,
        },
        overwrite=False,
    )
    environment = os.environ.copy()
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": str(args.gpu),
            "MUJOCO_GL": "egl",
            "PYOPENGL_PLATFORM": "egl",
            "ZETTA_NON_SCORED_JOINT_TRACE_OUTPUT": str(root / "contact-trace.json"),
            "PYTHONPATH": str(repo)
            + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""),
        }
    )
    return subprocess.run(command, cwd=repo, env=environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
