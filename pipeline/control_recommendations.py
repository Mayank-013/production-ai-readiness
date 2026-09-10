"""Recommendations for PARTIAL and FAIL assessments.

UNKNOWN does not earn a recommendation.
SATISFIED does not earn a recommendation.
Skills and validation stay locked.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_c1 import EXPECTATION_SPECS
from pipeline.control_evidence_contract import (
    CONTROL_RECOMMENDATIONS_LOCKED,
    RECOMMENDATION_SCHEMA_PATH,
    SCHEMA_VERSION,
    SKILLS_LOCKED,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.system_trait_contract import HACKERRANKATS_REPO

ACTIONS = {
    "QF-0003": {
        "title": "Make the degrade path explicit for primary dependencies",
        "actions": [
            "Name the fallback when GitHub or the model provider is unavailable.",
            "Return a reduced result instead of only logging the exception.",
            "Document which features continue when the primary dependency is down.",
        ],
    },
    "QF-0016": {
        "title": "Enforce TLS on the serving and dependency channels",
        "actions": [
            "Require HTTPS for inbound API traffic, not only outbound vendor URLs.",
            "Refuse plaintext listeners in the deploy configuration.",
            "Keep client calls on https and verify certificates.",
        ],
    },
    "QF-0035": {
        "title": "Scan for embedded credentials and keep secrets out of the tree",
        "actions": [
            "Add an automated secret scanner on the source tree and CI.",
            "Keep API keys in a secret manager or environment, never in source.",
            "Rotate any credential that has ever been committed.",
        ],
    },
}


def build_recommendations(
    assessments: list[dict],
    questions: list[dict],
    *,
    repo: str = HACKERRANKATS_REPO,
) -> list[dict]:
    schema = load_schema(RECOMMENDATION_SCHEMA_PATH)
    by_family = {spec["family_id"]: spec for spec in EXPECTATION_SPECS}
    q_by_family: dict[str, list[dict]] = {}
    for row in questions:
        q_by_family.setdefault(row["family_id"], []).append(row)
    rows = []
    n = 0
    for assessment in assessments:
        if assessment["state"] not in {"PARTIAL", "FAIL"}:
            continue
        spec = by_family[assessment["family_id"]]
        pack = ACTIONS.get(assessment["family_id"])
        if pack is None:
            pack = {
                "title": f"Close the {spec['diagnostic_job']} gap",
                "actions": [
                    f"Add repository evidence that {spec['diagnostic_job']} exists.",
                    "Do not treat absence from this repo as a confirmed failure.",
                ],
            }
        question = (q_by_family.get(assessment["family_id"]) or [{"id": f"q:{assessment['family_id']}:canonical"}])[0]
        n += 1
        row = {
            "id": f"rec:{assessment['family_id']}:{n:02d}",
            "family_id": assessment["family_id"],
            "expectation_id": assessment["expectation_id"],
            "question_id": question["id"],
            "control_id": spec["control_id"],
            "repo": repo,
            "assessment_state": assessment["state"],
            "title": pack["title"],
            "actions": list(pack["actions"]),
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        if not SKILLS_LOCKED:
            row["skill_id"] = f"skill:{spec['diagnostic_job']}"
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    return rows


def write_recommendations(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(CONTROL_RECOMMENDATIONS_LOCKED, "Recommendations")
    paths = paths or control_paths()
    refuse_overwrite(paths["recommendations"], "the recommendation dest")
    rows = build_recommendations(
        read_jsonl(paths["assessments"]),
        read_jsonl(paths["questions"]) if paths["questions"].exists() else [],
    )
    stats = {
        "repo": HACKERRANKATS_REPO,
        "recommendations": len(rows),
        "states": sorted({row["assessment_state"] for row in rows}),
        "unknown_recommended": False,
        "skills": "locked",
        "validation": "locked",
        "status": "frozen",
        "note": "PARTIAL and FAIL only. UNKNOWN is not a recommendation.",
    }
    write_jsonl(paths["recommendations"], rows)
    dump_json(paths["recommendation_stats"], stats)
    return stats
