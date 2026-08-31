#!/usr/bin/env python3
"""Install and verify LIBERO-Pro benchmark registration in ``liberopro``.

The upstream checkout uses the ``libero.libero`` import namespace while the
evaluation environment intentionally installs it as ``liberopro.liberopro``.
This tool performs that one namespace adaptation, preserves PyTorch 2.6+
loading compatibility, synchronizes the four official perturbation suites,
and emits a JSON report suitable for experiment evidence.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PRO_SUITES = (
    "libero_goal_task",
    "libero_goal_swap",
    "libero_10_task",
    "libero_10_swap",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_benchmark_init(source: str) -> str:
    rendered = source.replace(
        "from libero.libero import get_libero_path",
        "from liberopro.liberopro import get_libero_path",
    ).replace(
        "from libero.libero.benchmark.libero_suite_task_map import libero_task_map",
        "from liberopro.liberopro.benchmark.libero_suite_task_map import libero_task_map",
    )
    # torch>=2.6 defaults weights_only=True, but LIBERO init states contain
    # numpy objects and are trusted local benchmark assets.
    rendered = rendered.replace(
        "torch.load(init_states_path)",
        "torch.load(init_states_path, weights_only=False)",
    )
    ast.parse(rendered)
    for suite in PRO_SUITES:
        class_name = suite.upper()
        if f'class {class_name}(Benchmark):' not in rendered:
            raise ValueError(f"source registration is missing {class_name}")
    return rendered


def _load_task_map(source: str) -> dict[str, list[str]]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "libero_task_map"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                break
            return value
    raise ValueError("could not read libero_task_map from source")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.replace(path)


def integrate(
    *,
    source_package: Path,
    target_package: Path,
    backup_root: Path,
    execute: bool,
) -> dict[str, object]:
    source_package = source_package.expanduser().resolve()
    target_package = target_package.expanduser().resolve()
    source_benchmark = source_package / "benchmark"
    target_benchmark = target_package / "benchmark"
    source_init = source_benchmark / "__init__.py"
    source_map = source_benchmark / "libero_suite_task_map.py"
    if not source_init.is_file() or not source_map.is_file():
        raise ValueError(f"invalid source package: {source_package}")
    if not (target_package / "__init__.py").is_file():
        raise ValueError(f"invalid target package: {target_package}")

    rendered_init = _render_benchmark_init(source_init.read_text(encoding="utf-8"))
    rendered_map = source_map.read_text(encoding="utf-8")
    task_map = _load_task_map(rendered_map)
    source_counts = {suite: len(task_map.get(suite, [])) for suite in PRO_SUITES}
    if any(count != 10 for count in source_counts.values()):
        raise ValueError(f"expected 10 source tasks per suite, got {source_counts}")

    targets = {
        target_benchmark / "__init__.py": rendered_init,
        target_benchmark / "libero_suite_task_map.py": rendered_map,
    }
    changed_code = [
        str(path)
        for path, content in targets.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]

    data_plan: list[tuple[Path, Path]] = []
    for data_dir in ("bddl_files", "init_files"):
        for suite in PRO_SUITES:
            source_dir = source_package / data_dir / suite
            if not source_dir.is_dir():
                raise ValueError(f"missing source data directory: {source_dir}")
            data_plan.append((source_dir, target_package / data_dir / suite))

    backup_dir: Path | None = None
    if execute and changed_code:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = backup_root.expanduser().resolve() / stamp
        backup_dir.mkdir(parents=True, exist_ok=False)
        for path in targets:
            if path.is_file():
                shutil.copy2(path, backup_dir / path.name)
        for path, content in targets.items():
            _atomic_write(path, content)

    copied_data_files = 0
    if execute:
        for source_dir, target_dir in data_plan:
            before = {
                path.relative_to(target_dir).as_posix(): _sha256(path)
                for path in target_dir.rglob("*")
                if path.is_file()
            } if target_dir.is_dir() else {}
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
            after = {
                path.relative_to(target_dir).as_posix(): _sha256(path)
                for path in target_dir.rglob("*")
                if path.is_file()
            }
            copied_data_files += sum(before.get(name) != digest for name, digest in after.items())

    report = {
        "schema_version": 1,
        "executed": execute,
        "source_package": str(source_package),
        "target_package": str(target_package),
        "pro_suites": list(PRO_SUITES),
        "source_task_counts": source_counts,
        "changed_code_before_execute": changed_code,
        "copied_or_updated_data_files": copied_data_files,
        "backup_dir": str(backup_dir) if backup_dir else None,
    }
    if execute:
        report["target_code_sha256"] = {
            path.name: _sha256(path) for path in targets
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--target-package", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    report = integrate(
        source_package=args.source_package,
        target_package=args.target_package,
        backup_root=args.backup_root,
        execute=args.execute,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
