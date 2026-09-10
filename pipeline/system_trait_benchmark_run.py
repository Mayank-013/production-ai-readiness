"""B4 development B2+B3 runs.

Runs the frozen detector catalog and frozen B3 aggregation on the seven
development repos. Does not overwrite the first HackerRankATS observation
dest, reviewed dest, or B3 map dest. Does not overwrite the 294 labels.
Does not add detectors or change aggregation thresholds.
Does not write comparison dests. Held-out stays locked.

Contract: docs/repo-trait-inference.md
"""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.question_family_contract import SPECIALIZATION_LOCKED
from pipeline.system_trait_contract import (
    DEV_REFERENCE_REPO_IDS,
    EXPECTED_DEV_BENCHMARK_CONCLUSIONS,
    EXPECTED_DEV_REFERENCE_REPOS,
    EXPECTED_DEV_REFERENCE_ROWS,
    EXPECTED_FROZEN_DETECTORS,
    EXPECTED_TRAITS,
    FORBIDDEN_TRAIT_STATES,
    HELD_OUT_REPO_IDS,
    INFERRED_TRAIT_STATES,
    MAPPING_STATUS_CANDIDATE,
    REFERENCE_LABELS,
    REPO_TRAIT_DOC,
    REPO_TRAIT_OPEN_STAGE,
    REPO_TRAIT_STAGES,
    SCHEMA_VERSION,
    TRAIT_BENCHMARK_COMPARISON_LOCKED,
    TRAIT_BENCHMARK_ERROR_ANALYSIS_LOCKED,
    TRAIT_BENCHMARK_HELD_OUT_REFERENCE_LOCKED,
    TRAIT_BENCHMARK_LOCKED,
    TRAIT_STATES,
    TraitError,
    assert_trait_benchmark_locked,
    load_trait_benchmark_conclusion_schema,
    load_trait_benchmark_observation_schema,
    trait_benchmark_locked_message,
)
from pipeline.system_trait_detector_run import collect_detector_observations
from pipeline.system_trait_map import aggregate_trait_states

ROOT = Path(__file__).resolve().parent.parent
DEV_REPO_ROOTS = {
    "hackerrankats": Path("/Users/mauryans/Projects/HackerRankATS"),
    "prometheus": ROOT / "engineering-kb" / "oss" / "prometheus" / "prometheus",
    "otel_collector": ROOT
    / "engineering-kb"
    / "oss"
    / "opentelemetry-collector"
    / "opentelemetry-collector",
    "vllm": ROOT / "engineering-kb" / "oss" / "vllm" / "vllm",
    "langgraph": Path("/tmp/forgeai-b4-dev/langgraph"),
    "llama_index": Path("/tmp/forgeai-b4-dev/llama_index"),
    "meilisearch": Path("/tmp/forgeai-b4-dev/meilisearch"),
}
COMPARISON_OUTCOMES = {
    ("PRESENT", "PRESENT"): "TP_PRESENT",
    ("PRESENT", "LIKELY"): "UNDERCONFIDENT",
    ("PRESENT", "UNKNOWN"): "FN",
    ("NOT_PRESENT", "PRESENT"): "FP_PRESENT",
    ("NOT_PRESENT", "LIKELY"): "FP_LIKELY",
    ("NOT_PRESENT", "UNKNOWN"): "TN_ABSTAIN",
}


def _protected(paths: dict[str, Path]) -> dict[str, str]:
    keys = (
        "families",
        "traits",
        "applicability",
        "trait_evidence",
        "trait_detectors_frozen",
        "trait_detector_observations",
        "trait_detector_observations_reviewed",
        "trait_aggregation",
        "trait_conclusions",
        "trait_benchmark",
        "trait_benchmark_references",
    )
    return {key: sha256(paths[key].read_bytes()).hexdigest() for key in keys}


def development_repo_root(repo_id: str) -> Path:
    if repo_id not in DEV_REFERENCE_REPO_IDS:
        raise TraitError(f"{repo_id} is not a development benchmark repo")
    if repo_id in HELD_OUT_REPO_IDS:
        raise TraitError(f"{repo_id} is held-out; do not run it this pass")
    root = DEV_REPO_ROOTS[repo_id]
    if not root.is_dir():
        raise TraitError(f"development repo is missing: {repo_id} -> {root}")
    return root.resolve()


def comparison_outcome(human_label: str, system_state: str) -> str:
    """Score one pair. UNRESOLVED is out of scope, not negative truth."""
    if human_label not in REFERENCE_LABELS:
        raise TraitError(f"invalid human label {human_label}")
    if system_state not in INFERRED_TRAIT_STATES:
        raise TraitError(f"invalid system state {system_state}")
    if human_label == "UNRESOLVED":
        return "OUT_OF_SCOPE"
    return COMPARISON_OUTCOMES[(human_label, system_state)]


def _validate_benchmark_row(row: dict, schema: dict) -> None:
    missing = [k for k in schema["required"] if k not in row]
    if missing:
        raise TraitError(f"{row.get('repo_id')}.{row.get('detector_id') or row.get('trait')}: missing {missing}")
    extra = set(row) - set(schema["properties"])
    if extra:
        raise TraitError(
            f"{row.get('repo_id')}.{row.get('detector_id') or row.get('trait')}: "
            f"unknown fields {sorted(extra)}"
        )


def write_development_trait_benchmark(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait import trait_paths

    assert_trait_benchmark_locked()
    if TRAIT_BENCHMARK_LOCKED:
        raise TraitError(trait_benchmark_locked_message())
    paths = paths or trait_paths()
    obs_dest = paths["trait_benchmark_observations"]
    obs_stats_dest = paths["trait_benchmark_observation_stats"]
    concl_dest = paths["trait_benchmark_conclusions"]
    stats_dest = paths["trait_benchmark_conclusion_stats"]
    for target in (obs_dest, obs_stats_dest, concl_dest, stats_dest):
        if target.exists() and target.read_text(encoding="utf-8").strip():
            raise TraitError(f"{target.name} already exists; refusing to overwrite development B4 runs")
    before = _protected(paths)

    references = read_jsonl(paths["trait_benchmark_references"])
    if len(references) != EXPECTED_DEV_REFERENCE_ROWS:
        raise TraitError(
            f"expected {EXPECTED_DEV_REFERENCE_ROWS} frozen reference labels, got {len(references)}"
        )
    if any(row["split"] != "development" for row in references):
        raise TraitError("development runs admit only development reference labels")
    if any(row["repo_id"] in HELD_OUT_REPO_IDS for row in references):
        raise TraitError("held-out labels leaked into the development reference dest")

    catalog_rows = read_jsonl(paths["trait_detectors_frozen"])
    if len(catalog_rows) != EXPECTED_FROZEN_DETECTORS:
        raise TraitError(f"expected {EXPECTED_FROZEN_DETECTORS} frozen detectors")
    traits = read_jsonl(paths["traits"])
    if len(traits) != EXPECTED_TRAITS:
        raise TraitError(f"expected {EXPECTED_TRAITS} traits")
    slugs = [row["slug"] for row in traits]
    contract = read_jsonl(paths["trait_aggregation"])
    obs_schema = load_trait_benchmark_observation_schema()
    concl_schema = load_trait_benchmark_conclusion_schema()

    observations: list[dict] = []
    conclusions: list[dict] = []
    per_repo: list[dict] = []
    state_counts = {state: 0 for state in sorted(INFERRED_TRAIT_STATES)}
    basis_counts = {"direct": 0, "implied": 0, "no_sufficient_evidence": 0}

    for repo_id in DEV_REFERENCE_REPO_IDS:
        root = development_repo_root(repo_id)
        hits, _idx, meta = collect_detector_observations(root, catalog_rows)
        stamped: list[dict] = []
        for i, hit in enumerate(hits, start=1):
            raw = json_without_states(hit)
            if raw is None:
                raise TraitError(f"{repo_id}: observation emitted a trait state")
            row = {
                "repo_id": repo_id,
                "detector_id": hit["detector_id"],
                "trait": hit["trait"],
                "supports": list(hit["supports"]),
                "observation": hit["observation"],
                "strength": hit["strength"],
                "file": hit["file"],
                "location": dict(hit["location"]),
                "observation_index": i,
                "schema_version": SCHEMA_VERSION,
            }
            _validate_benchmark_row(row, obs_schema)
            observations.append(row)
            stamped.append(row)
        states = aggregate_trait_states(
            traits,
            stamped,
            contract=contract,
            require_review=False,
        )
        if [row["trait"] for row in states] != slugs:
            raise TraitError(f"{repo_id}: conclusions must match frozen trait order")
        repo_states = {"PRESENT": 0, "LIKELY": 0, "UNKNOWN": 0}
        for state_row in states:
            rec = {
                "repo_id": repo_id,
                "trait": state_row["trait"],
                "trait_id": state_row["trait_id"],
                "state": state_row["state"],
                "basis": state_row["basis"],
                "observation_ids": list(state_row["observation_ids"]),
                "implied_by": list(state_row["implied_by"]),
                "split": "development",
                "status": MAPPING_STATUS_CANDIDATE,
                "schema_version": SCHEMA_VERSION,
            }
            _validate_benchmark_row(rec, concl_schema)
            if rec["state"] not in INFERRED_TRAIT_STATES:
                raise TraitError(f"{repo_id}.{rec['trait']}: invalid state {rec['state']}")
            if rec["state"] == "ABSENT":
                raise TraitError(f"{repo_id}.{rec['trait']}: ABSENT is forbidden")
            conclusions.append(rec)
            state_counts[rec["state"]] += 1
            basis_counts[rec["basis"]] += 1
            repo_states[rec["state"]] += 1
        per_repo.append({
            "repo_id": repo_id,
            "repo": meta["repo"],
            "files_considered": meta["repo_files_considered"],
            "files_indexed": meta["repo_files_indexed"],
            "observations": meta["observations"],
            "strong_observations": meta["strong_observations"],
            "weak_observations": meta["weak_observations"],
            "detectors_fired": meta["detectors_fired"],
            "fired_detector_ids": meta["fired_detector_ids"],
            "present": repo_states["PRESENT"],
            "likely": repo_states["LIKELY"],
            "unknown": repo_states["UNKNOWN"],
        })

    if len(conclusions) != EXPECTED_DEV_BENCHMARK_CONCLUSIONS:
        raise TraitError(
            f"expected {EXPECTED_DEV_BENCHMARK_CONCLUSIONS} conclusions, got {len(conclusions)}"
        )
    if {row["repo_id"] for row in conclusions} != set(DEV_REFERENCE_REPO_IDS):
        raise TraitError("development conclusions drifted from the development set")
    if {row["repo_id"] for row in conclusions} & set(HELD_OUT_REPO_IDS):
        raise TraitError("held-out repos leaked into development conclusions")
    after = _protected(paths)
    if after != before:
        raise TraitError("development B4 runs mutated a protected dest")

    obs_stats = {
        "repos": EXPECTED_DEV_REFERENCE_REPOS,
        "observations": len(observations),
        "strong_observations": sum(1 for row in observations if row["strength"] == "strong"),
        "weak_observations": sum(1 for row in observations if row["strength"] == "weak"),
        "split": "development",
        "held_out_run": False,
        "first_run_dest_reused": False,
        "review_claimed": False,
        "catalog": "trait_detectors_frozen.jsonl",
        "status": "written",
        "per_repo": per_repo,
    }
    stats = {
        "repos": EXPECTED_DEV_REFERENCE_REPOS,
        "rows": len(conclusions),
        "observations": len(observations),
        "present": state_counts["PRESENT"],
        "likely": state_counts["LIKELY"],
        "unknown": state_counts["UNKNOWN"],
        "absent": 0,
        "basis_direct": basis_counts["direct"],
        "basis_implied": basis_counts["implied"],
        "basis_no_sufficient_evidence": basis_counts["no_sufficient_evidence"],
        "split": "development",
        "held_out_run": False,
        "reference_rows_unchanged": len(references),
        "catalog_retuned": False,
        "aggregation_thresholds_changed": False,
        "first_run_dest_overwritten": False,
        "reviewed_dest_overwritten": False,
        "map_dest_overwritten": False,
        "comparison_written": False,
        "error_analysis_written": False,
        "scoring": {
            "truth_labels": sorted(REFERENCE_LABELS),
            "inferred_states": sorted(INFERRED_TRAIT_STATES),
            "unresolved_excluded_from_precision_recall": True,
            "unresolved_is_not_negative_truth": True,
            "present_vs_present": "TP",
            "present_vs_likely": "undercall",
            "present_vs_unknown": "FN",
            "not_present_vs_present": "expensive_FP",
            "not_present_vs_likely": "weaker_FP",
            "not_present_vs_unknown": "correct_abstention",
            "composite_pass_fail": "unresolved",
        },
        "status": MAPPING_STATUS_CANDIDATE,
        "open_stage": REPO_TRAIT_OPEN_STAGE,
        "stages": list(REPO_TRAIT_STAGES),
        "comparison": "locked" if TRAIT_BENCHMARK_COMPARISON_LOCKED else "open",
        "error_analysis": "locked" if TRAIT_BENCHMARK_ERROR_ANALYSIS_LOCKED else "open",
        "held_out_references": "locked" if TRAIT_BENCHMARK_HELD_OUT_REFERENCE_LOCKED else "open",
        "questions": "locked" if SPECIALIZATION_LOCKED else "open",
        "protected_dests_mutated": False,
        "next_gate": "development_comparison",
        "per_repo": per_repo,
        "note": (
            "Development B2+B3 runs only. Frozen catalog + frozen B3 rules "
            "on the seven development repos. HackerRankATS was re-run into "
            "B4 dests; the first observation dest and B3 map dest were not "
            "reused. Comparison dests are not written. UNRESOLVED stays out "
            "of scope for scoring. Do not add detectors or change thresholds. "
            f"Contract: {REPO_TRAIT_DOC}."
        ),
    }
    write_jsonl(obs_dest, observations)
    dump_json(obs_stats_dest, obs_stats)
    write_jsonl(concl_dest, conclusions)
    dump_json(stats_dest, stats)
    return stats


def json_without_states(row: dict) -> dict | None:
    raw = json.dumps(row)
    for state in list(TRAIT_STATES) + list(FORBIDDEN_TRAIT_STATES):
        if re.search(rf"\b{state}\b", raw):
            return None
    return row
