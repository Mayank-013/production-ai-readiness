"""Collect frozen-catalog observations from substrate IR."""

from __future__ import annotations

from pathlib import Path

from pipeline.repo_inspection.detectors import detect_from_ir
from pipeline.repo_inspection.index import index_repository
from pipeline.system_trait_contract import (
    EXPECTED_FROZEN_DETECTORS,
    MAPPING_STATUS_FROZEN,
    TRAIT_STATES,
    FORBIDDEN_TRAIT_STATES,
    TraitError,
    load_trait_detector_observation_schema,
)
from pipeline.system_trait_detector_run import _dedup_key, _validate_observation
import json
import re


def collect_ir_observations(repo: Path, catalog_rows: list[dict]) -> tuple[list[dict], dict, dict]:
    repo = Path(repo).expanduser().resolve()
    if not repo.is_dir():
        raise TraitError(f"repository is not a directory: {repo}")
    if len(catalog_rows) != EXPECTED_FROZEN_DETECTORS:
        raise TraitError(f"expected {EXPECTED_FROZEN_DETECTORS} frozen detectors")
    if any(row.get("status") != MAPPING_STATUS_FROZEN for row in catalog_rows):
        raise TraitError("B4-v2 admits only the frozen catalog")
    catalog = {row["detector_id"]: row for row in catalog_rows}
    schema = load_trait_detector_observation_schema()
    indexed = index_repository(repo)
    by_rel = {row["file"]: row for row in indexed["files"]}
    # Need line counts for span checks: re-walk is expensive; use evidence file nodes.
    line_count = {}
    for row in indexed["evidence"]:
        if row["kind"] == "file":
            line_count[row["file"]] = row["end_line"]
    errors = []
    raw_hits = []
    fired = set()
    for spec in catalog_rows:
        try:
            hits = detect_from_ir(indexed["evidence"], spec)
        except Exception as exc:  # noqa: BLE001
            errors.append({"detector_id": spec["detector_id"], "error": type(exc).__name__})
            continue
        for hit in hits:
            raw_hits.append(hit)
            fired.add(spec["detector_id"])
    seen = set()
    observations = []
    for hit in raw_hits:
        key = _dedup_key(hit)
        if key in seen:
            continue
        seen.add(key)
        raw = json.dumps(hit)
        if any(re.search(rf"\b{state}\b", raw) for state in list(TRAIT_STATES) + list(FORBIDDEN_TRAIT_STATES)):
            raise TraitError(f"{hit['detector_id']}: observation emitted a trait state")
        _validate_observation(hit, schema, catalog)
        observations.append(hit)
    valid_file = 0
    valid_span = 0
    for row in observations:
        if row["file"] not in by_rel:
            continue
        valid_file += 1
        start = row["location"]["start_line"]
        end = row["location"]["end_line"]
        n = line_count.get(row["file"], 1)
        if 1 <= start <= end <= max(1, n):
            valid_span += 1
    if valid_file != len(observations) or valid_span != len(observations) or errors:
        raise TraitError(
            "IR observation run failed execution integrity: "
            f"valid_file={valid_file} valid_span={valid_span} "
            f"errors={errors} n={len(observations)}"
        )
    meta = {
        "repo": str(repo),
        "repo_name": repo.name,
        "repo_files_considered": indexed["stats"]["considered"],
        "repo_files_indexed": indexed["stats"]["files"],
        "detectors_attempted": len(catalog_rows),
        "detectors_fired": len(fired),
        "observations": len(observations),
        "strong_observations": sum(1 for row in observations if row["strength"] == "strong"),
        "weak_observations": sum(1 for row in observations if row["strength"] == "weak"),
        "fired_detector_ids": sorted(fired),
        "source_languages": indexed["stats"]["source_languages"],
        "ir_nodes": indexed["stats"]["nodes"],
        "b4_runner_unchanged": True,
        "language_specific_detectors": False,
    }
    return observations, indexed["stats"], meta
