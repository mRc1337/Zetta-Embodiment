#!/usr/bin/env python3
# Copyright (c) 2026 Zetta Contributors
"""Rebind frozen episode artifacts after a campaign-root migration.

Accepted ``EpisodeRecord`` rows are immutable and can therefore retain absolute
artifact locators from an older ``state`` directory.  This utility adds only
missing/current file sources to the campaign-private resolver.  A source is
accepted only when its suffix below one legacy state directory resolves inside
the target campaign and its bytes match the frozen SHA-256 in the accepted
episode record.

The command prints and stores only aggregate counts.  It never emits artifact
paths, episode identifiers, seeds, trajectory contents, or provider material.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from zetta.evolution.jsonio import atomic_write_json, directory_lock, file_sha256
from zetta.evolution.lifecycle import (
    _agent_artifact_index,
    _agent_hash,
    _artifact_type,
    _completed_gate_episode_rows,
    _content_id,
    _fixed_summary,
    _load_resolver,
    _persist_resolver,
    _register_artifact,
    _resolver_path,
)
from zetta.evolution.store import CampaignStore

_SHA256 = re.compile(r"[0-9a-f]{64}")
_STATE_COMPONENT = re.compile(r"state(?:-a[0-9]+)?")
_ARTIFACT_GROUPS = (
    ("trajectory_index", "artifact_paths"),
    ("visual_evidence", "artifacts"),
)


def _accepted_rows(store: CampaignStore) -> list[tuple[str, dict[str, Any]]]:
    rows = [
        ("episode_record", row)
        for row in store.episodes.records()
        if row.get("status") == "valid"
    ]
    rows.extend((role, row) for _, row, role in _completed_gate_episode_rows(store))
    return rows


def _frozen_artifact_references(
    rows: Iterable[tuple[str, dict[str, Any]]],
) -> Iterable[tuple[str, dict[str, Any], str, str, str]]:
    for episode_role, row in rows:
        artifact_index = row.get("artifact_index")
        if not isinstance(artifact_index, dict):
            continue
        for group, paths_key in _ARTIFACT_GROUPS:
            container = artifact_index.get(group)
            if not isinstance(container, dict):
                continue
            paths = container.get(paths_key)
            digests = container.get("artifact_sha256")
            if paths is None or digests is None:
                continue
            if not isinstance(paths, dict) or not isinstance(digests, dict):
                raise ValueError("episode artifact provenance is incomplete")
            if set(paths) != set(digests):
                raise ValueError("episode artifact path/hash keys do not match")
            for name, locator in paths.items():
                digest = digests[name]
                if not isinstance(locator, str) or not locator or "\n" in locator:
                    raise ValueError("episode artifact locator is malformed")
                if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                    raise ValueError(
                        "episode artifact provenance has a malformed digest"
                    )
                raw_key = f"{group}.{paths_key}.{name}"
                yield episode_role, row, raw_key, locator, digest


def _has_current_file_source(*, campaign_root: Path, entry: dict[str, Any]) -> bool:
    root = campaign_root.resolve()
    for source in entry.get("sources", ()):
        if not isinstance(source, dict) or source.get("kind") != "file":
            continue
        value = source.get("path")
        if not isinstance(value, str) or not value or "\n" in value:
            continue
        path = Path(value).resolve()
        if path.is_relative_to(root) and path.is_file():
            return True
    return False


def _rebound_path(*, campaign_root: Path, locator: str, digest: str) -> Path:
    legacy = Path(locator)
    if not legacy.is_absolute():
        raise ValueError("migrated artifact locator is not absolute")
    anchors = [
        index
        for index, component in enumerate(legacy.parts)
        if _STATE_COMPONENT.fullmatch(component)
    ]
    if len(anchors) != 1 or anchors[0] == len(legacy.parts) - 1:
        raise ValueError("migrated artifact locator has no unique state anchor")
    root = campaign_root.resolve()
    target = root.joinpath(*legacy.parts[anchors[0] + 1 :]).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("migrated artifact target is unavailable")
    if file_sha256(target) != digest:
        raise ValueError("migrated artifact bytes differ from accepted provenance")
    return target


def plan_resolver_rebind(
    *,
    store: CampaignStore,
    resolver: dict[str, Any],
    rows: Iterable[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a validated resolver copy and a path-free aggregate receipt."""

    rows = tuple(rows)
    updated = copy.deepcopy(resolver)
    root = store.root.resolve()
    reference_count = 0
    existing_reference_count = 0
    rebound_reference_count = 0
    rebound_content_ids: set[str] = set()
    for episode_role, row, raw_key, locator, digest in _frozen_artifact_references(
        rows
    ):
        reference_count += 1
        content_id = _content_id(resolver=updated, digest=digest)
        entry = updated["entries"].get(content_id)
        if isinstance(entry, dict):
            if entry.get("content_sha256") != digest or entry.get(
                "agent_hash"
            ) != _agent_hash(resolver=updated, digest=digest):
                raise ValueError(
                    "artifact resolver entry failed keyed-integrity validation"
                )
            if _has_current_file_source(campaign_root=root, entry=entry):
                existing_reference_count += 1
                continue
        target = _rebound_path(
            campaign_root=root,
            locator=locator,
            digest=digest,
        )
        artifact_type = _artifact_type(
            locator,
            path=target,
            role="indexed_artifact",
        )
        _register_artifact(
            resolver=updated,
            digest=digest,
            artifact_type=artifact_type,
            summary=_fixed_summary(artifact_type),
            source={
                "kind": "file",
                "path": str(target),
                "role": "indexed_artifact",
                "raw_key": raw_key,
                "episode_id": row["episode_id"],
                "logical_id": row["logical_id"],
                "digest_authority": "accepted_episode_record_migration",
                "episode_role": episode_role,
            },
        )
        rebound_reference_count += 1
        rebound_content_ids.add(content_id)

    receipt = {
        "schema_version": "migrated_artifact_resolver_rebind_v0",
        "accepted_episode_count": len(rows),
        "frozen_reference_count": reference_count,
        "existing_current_reference_count": existing_reference_count,
        "rebound_reference_count": rebound_reference_count,
        "rebound_unique_content_count": len(rebound_content_ids),
        "all_references_resolved": (
            existing_reference_count + rebound_reference_count == reference_count
        ),
    }
    if not receipt["all_references_resolved"]:
        raise ValueError("not every frozen artifact reference was resolved")
    return updated, receipt


def repair_campaign(
    campaign_root: Path,
    *,
    execute: bool,
    verify_index: bool,
) -> dict[str, Any]:
    store = CampaignStore(campaign_root)
    rows = _accepted_rows(store)
    resolver_path = _resolver_path(store)
    resolver_path.parent.mkdir(parents=True, exist_ok=True)
    with directory_lock(resolver_path.with_name(".artifact-resolver.lock")):
        resolver = _load_resolver(store)
        updated, receipt = plan_resolver_rebind(
            store=store,
            resolver=resolver,
            rows=rows,
        )
        receipt["mode"] = "execute" if execute else "dry_run"
        if execute:
            _persist_resolver(store, updated)

    if verify_index:
        if not execute:
            raise ValueError("--verify-index requires --execute")
        index = _agent_artifact_index(store)
        receipt["artifact_index"] = {
            "artifact_count": len(index["artifacts"]),
            "relationship_count": len(index["relationships"]),
            "diagnostic_telemetry_count": len(index["diagnostic_telemetry"]),
        }
        receipt["artifact_index_verified"] = True
    else:
        receipt["artifact_index_verified"] = False

    if execute:
        atomic_write_json(
            campaign_root
            / ".harness-private"
            / "migrated-artifact-resolver-rebind.json",
            receipt,
            overwrite=True,
        )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify-index", action="store_true")
    args = parser.parse_args()
    receipt = repair_campaign(
        args.campaign_root,
        execute=args.execute,
        verify_index=args.verify_index,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
