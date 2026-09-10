"""C3: assess applicable controls.

    strong evidence found        → SATISFIED
    supporting only              → PARTIAL
    no sufficient evidence       → UNKNOWN
    contradiction evidence       → FAIL

Insufficient-alone observations never upgrade a state.
Not finding evidence is not FAIL.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_c1 import EXPECTATION_SPECS
from pipeline.control_evidence_contract import (
    CONTROL_ASSESS_LOCKED,
    CONTROL_ASSESSMENT_SCHEMA_PATH,
    SCHEMA_VERSION,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.control_evidence_observe import FAMILY_EXPECTATION
from pipeline.system_trait_contract import HACKERRANKATS_REPO


def assess_controls(observations: list[dict], *, repo: str = HACKERRANKATS_REPO) -> list[dict]:
    schema = load_schema(CONTROL_ASSESSMENT_SCHEMA_PATH)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        by_family[row["family_id"]].append(row)
    rows = []
    for spec in EXPECTATION_SPECS:
        fid = spec["family_id"]
        hits = by_family.get(fid) or []
        strengths = {row["strength"] for row in hits}
        if "contradiction" in strengths:
            state, basis = "FAIL", "contradiction"
        elif "strong" in strengths:
            state, basis = "SATISFIED", "strong"
        elif "supporting" in strengths:
            state, basis = "PARTIAL", "supporting"
        else:
            state, basis = "UNKNOWN", "no_sufficient_evidence"
        row = {
            "repo": repo,
            "expectation_id": FAMILY_EXPECTATION[fid],
            "family_id": fid,
            "state": state,
            "basis": basis,
            "observation_ids": [hit["id"] for hit in hits if hit["strength"] != "insufficient"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, schema, label=f"{repo}:{fid}")
        rows.append(row)
    return rows


def write_control_assessments(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(CONTROL_ASSESS_LOCKED, "C3 control assessment")
    paths = paths or control_paths()
    refuse_overwrite(paths["assessments"], "the C3 control assessments")
    observations = read_jsonl(paths["observations"])
    rows = assess_controls(observations)
    from collections import Counter

    stats = {
        "repo": HACKERRANKATS_REPO,
        "assessments": len(rows),
        "by_state": dict(Counter(row["state"] for row in rows)),
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "status": "frozen",
        "note": "C3. Absence of evidence is UNKNOWN, not FAIL.",
    }
    write_jsonl(paths["assessments"], rows)
    dump_json(paths["assessment_stats"], stats)
    return stats
