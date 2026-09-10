"""B3 HackerRankATS trait map.

Combines the 32 reviewed observations into 42 trait conclusions.
Does not inspect the repository. Does not invent observations.
Does not emit numeric confidence. Does not emit EngineeringQuestion rows.

Direct evidence first. Ontology implies after, and only from PRESENT.
Direct provenance wins when both exist. ABSENT is never emitted.

Contract: docs/repo-trait-inference.md
"""

from __future__ import annotations

from collections import defaultdict, deque
from hashlib import sha256
from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.question_family_contract import SPECIALIZATION_LOCKED
from pipeline.system_trait_contract import (
    EXPECTED_REVIEWED_OBSERVATIONS,
    EXPECTED_TRAITS,
    HACKERRANKATS_REPO,
    MAPPING_STATUS_CANDIDATE,
    REPO_TRAIT_DOC,
    REPO_TRAIT_OPEN_STAGE,
    REPO_TRAIT_STAGES,
    SCHEMA_VERSION,
    TRAIT_AGGREGATION_LOCKED,
    TRAIT_AGGREGATION_REVIEW_LOCKED,
    TRAIT_BENCHMARK_LOCKED,
    TraitError,
    assert_trait_aggregation_locked,
    load_trait_conclusion_schema,
)

SOURCE_OBSERVATIONS = "trait_detector_observations_reviewed.jsonl"
SOURCE_CONTRACT = "trait_aggregation.jsonl"
SOURCE_TRAITS = "traits.jsonl"


def _protected(paths: dict[str, Path]) -> dict[str, str]:
    keys = (
        "families",
        "traits",
        "applicability",
        "trait_evidence",
        "trait_detectors",
        "trait_detectors_frozen",
        "trait_detector_observations",
        "trait_detector_observation_review",
        "trait_detector_observations_reviewed",
        "trait_aggregation",
    )
    return {key: sha256(paths[key].read_bytes()).hexdigest() for key in keys}


def observation_id(observation_index: int) -> str:
    return f"obs_{observation_index:04d}"


def independent_key(row: dict) -> tuple[str, str]:
    return (row["detector_id"], row["file"])


def _direct_state(supporting: list[dict]) -> str:
    strong = [row for row in supporting if row["strength"] == "strong"]
    if strong:
        return "PRESENT"
    independent = {independent_key(row) for row in supporting if row["strength"] == "weak"}
    if len(independent) >= 2:
        return "LIKELY"
    return "UNKNOWN"


def aggregate_trait_states(
    traits: list[dict],
    observations: list[dict],
    *,
    contract: list[dict] | None = None,
    require_review: bool = True,
) -> list[dict]:
    """Pure aggregator. Observations attach through supports, not detector.trait.

    require_review=True is the HackerRankATS B3 path (VALID + frozen).
    B4 development runs pass require_review=False on raw catalog hits.
    Thresholds do not change.
    """
    if len(traits) != EXPECTED_TRAITS:
        raise TraitError(f"expected {EXPECTED_TRAITS} traits, got {len(traits)}")
    slugs = [row["slug"] for row in traits]
    if len(set(slugs)) != EXPECTED_TRAITS:
        raise TraitError("duplicate trait slugs")
    known = set(slugs)
    implies = {row["slug"]: list(row.get("implies") or []) for row in traits}
    if contract is not None:
        if [row["trait"] for row in contract] != slugs:
            raise TraitError("aggregation contract must match frozen trait order")
        if any(row["one_weak_to"] != "UNKNOWN" for row in contract):
            raise TraitError("one weak must stay UNKNOWN")
        if any(row["absent_allowed"] for row in contract):
            raise TraitError("ABSENT is not allowed")

    by_trait: dict[str, list[dict]] = {slug: [] for slug in slugs}
    for row in observations:
        if require_review:
            if row.get("review_decision") != "VALID":
                raise TraitError(f"B3 admits only VALID reviewed observations: {row.get('detector_id')}")
            if row.get("status") != "frozen":
                raise TraitError(f"B3 admits only frozen reviewed observations: {row.get('detector_id')}")
        if "observation_index" not in row:
            raise TraitError(f"{row.get('detector_id')}: observation_index is required")
        supports = list(row.get("supports") or [])
        if not supports:
            continue
        for slug in supports:
            if slug not in known:
                raise TraitError(f"{row['detector_id']} supports unknown trait {slug}")
            by_trait[slug].append(row)

    direct: dict[str, dict] = {}
    for slug in slugs:
        supporting = by_trait[slug]
        ids = sorted({observation_id(row["observation_index"]) for row in supporting})
        direct[slug] = {
            "state": _direct_state(supporting),
            "observation_ids": ids,
            "strong": [row for row in supporting if row["strength"] == "strong"],
            "weak": [row for row in supporting if row["strength"] == "weak"],
        }

    present = {slug for slug, row in direct.items() if row["state"] == "PRESENT"}
    implied_from: dict[str, set[str]] = defaultdict(set)
    queue = deque(sorted(present))
    while queue:
        src = queue.popleft()
        for dest in implies.get(src, []):
            if dest not in known:
                raise TraitError(f"{src} implies unknown trait {dest}")
            implied_from[dest].add(src)
            if dest not in present:
                present.add(dest)
                queue.append(dest)

    rows: list[dict] = []
    for trait in traits:
        slug = trait["slug"]
        drow = direct[slug]
        sources = sorted(implied_from.get(slug, ()))
        if drow["state"] == "PRESENT":
            state = "PRESENT"
            basis = "direct"
            observation_ids = drow["observation_ids"]
            implied_by = sources
        elif slug in present:
            state = "PRESENT"
            basis = "implied"
            observation_ids = []
            implied_by = sources
        elif drow["state"] == "LIKELY":
            state = "LIKELY"
            basis = "direct"
            observation_ids = drow["observation_ids"]
            implied_by = []
        else:
            state = "UNKNOWN"
            basis = "no_sufficient_evidence"
            observation_ids = []
            implied_by = []
        if state == "ABSENT":
            raise TraitError(f"{slug}: ABSENT is forbidden")
        if state == "PRESENT" and basis == "direct" and not drow["strong"]:
            raise TraitError(f"{slug}: PRESENT direct without a strong observation")
        if state == "PRESENT" and basis == "implied" and not implied_by:
            raise TraitError(f"{slug}: PRESENT implied without a PRESENT source")
        if state == "LIKELY":
            independent = {independent_key(obs) for obs in drow["weak"]}
            if len(independent) < 2:
                raise TraitError(f"{slug}: LIKELY requires 2+ independent weaks")
            if implied_by:
                raise TraitError(f"{slug}: LIKELY must not carry implication")
        if state == "UNKNOWN":
            if observation_ids or implied_by:
                raise TraitError(f"{slug}: UNKNOWN must not carry evidence lists")
            if basis != "no_sufficient_evidence":
                raise TraitError(f"{slug}: UNKNOWN basis must be no_sufficient_evidence")
        rows.append({
            "trait": slug,
            "trait_id": trait["id"],
            "state": state,
            "basis": basis,
            "observation_ids": observation_ids,
            "implied_by": implied_by,
        })

    if len(rows) != EXPECTED_TRAITS:
        raise TraitError(f"expected {EXPECTED_TRAITS} conclusions")
    if any(row["state"] == "ABSENT" for row in rows):
        raise TraitError("ABSENT is forbidden while absence_policy is unknown")
    return rows


def aggregate_trait_conclusions(
    traits: list[dict],
    observations: list[dict],
    *,
    contract: list[dict] | None = None,
    require_review: bool = True,
) -> list[dict]:
    """HackerRankATS B3 row builder. Thresholds live in aggregate_trait_states."""
    schema = load_trait_conclusion_schema()
    rows: list[dict] = []
    for state_row in aggregate_trait_states(
        traits,
        observations,
        contract=contract,
        require_review=require_review,
    ):
        row = {
            "repo": HACKERRANKATS_REPO,
            "trait": state_row["trait"],
            "trait_id": state_row["trait_id"],
            "state": state_row["state"],
            "basis": state_row["basis"],
            "observation_ids": state_row["observation_ids"],
            "implied_by": state_row["implied_by"],
            "status": MAPPING_STATUS_CANDIDATE,
            "schema_version": SCHEMA_VERSION,
        }
        missing = [k for k in schema["required"] if k not in row]
        if missing:
            raise TraitError(f"{row['trait']}: missing {missing}")
        extra = set(row) - set(schema["properties"])
        if extra:
            raise TraitError(f"{row['trait']}: unknown fields {sorted(extra)}")
        rows.append(row)
    return rows


def write_hackerrankats_trait_map(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait import trait_paths

    assert_trait_aggregation_locked()
    if TRAIT_AGGREGATION_LOCKED:
        raise TraitError("The HackerRankATS trait map stays locked.")
    paths = paths or trait_paths()
    dest = paths["trait_conclusions"]
    stats_dest = paths["trait_conclusion_stats"]
    for target in (dest, stats_dest):
        if target.exists() and target.read_text(encoding="utf-8").strip():
            raise TraitError(f"{target.name} already exists; refusing to overwrite the HackerRankATS trait map")
    before = _protected(paths)

    traits = read_jsonl(paths["traits"])
    observations = read_jsonl(paths["trait_detector_observations_reviewed"])
    contract = read_jsonl(paths["trait_aggregation"])
    if len(observations) != EXPECTED_REVIEWED_OBSERVATIONS:
        raise TraitError(
            f"expected {EXPECTED_REVIEWED_OBSERVATIONS} reviewed observations, got {len(observations)}"
        )
    rows = aggregate_trait_conclusions(traits, observations, contract=contract)
    after = _protected(paths)
    if after != before:
        raise TraitError("trait map mutated a protected dest")

    counts = {"PRESENT": 0, "LIKELY": 0, "UNKNOWN": 0}
    bases = {"direct": 0, "implied": 0, "no_sufficient_evidence": 0}
    for row in rows:
        counts[row["state"]] += 1
        bases[row["basis"]] += 1
    attached = sorted({obs_id for row in rows for obs_id in row["observation_ids"]})
    unused_obs = [
        observation_id(row["observation_index"])
        for row in observations
        if not row.get("supports")
    ]

    stats = {
        "repo": HACKERRANKATS_REPO,
        "traits": len(rows),
        "reviewed_observations": len(observations),
        "attached_observation_ids": len(attached),
        "unused_empty_supports": len(unused_obs),
        "present": counts["PRESENT"],
        "likely": counts["LIKELY"],
        "unknown": counts["UNKNOWN"],
        "absent": 0,
        "basis_direct": bases["direct"],
        "basis_implied": bases["implied"],
        "basis_no_sufficient_evidence": bases["no_sufficient_evidence"],
        "confidence_emitted": False,
        "input": SOURCE_OBSERVATIONS,
        "source_contract": SOURCE_CONTRACT,
        "source_traits": SOURCE_TRAITS,
        "status": MAPPING_STATUS_CANDIDATE,
        "open_stage": REPO_TRAIT_OPEN_STAGE,
        "stages": list(REPO_TRAIT_STAGES),
        "aggregation_review": "locked" if TRAIT_AGGREGATION_REVIEW_LOCKED else "open",
        "benchmark": "locked" if TRAIT_BENCHMARK_LOCKED else "open",
        "questions": "locked" if SPECIALIZATION_LOCKED else "open",
        "protected_dests_mutated": False,
        "repo_inspected": False,
        "next_gate": "aggregation_review",
        "note": (
            "HackerRankATS trait map only. Derived from the 32 reviewed "
            "observations and the B3 aggregation contract. No numeric "
            "confidence. No ABSENT. Implication runs after direct and "
            "only from PRESENT. Direct provenance wins. Review this map "
            "before B4. "
            f"Contract: {REPO_TRAIT_DOC}."
        ),
    }
    write_jsonl(dest, rows)
    dump_json(stats_dest, stats)
    return stats
