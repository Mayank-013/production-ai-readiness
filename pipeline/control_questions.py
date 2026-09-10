"""Emit EngineeringQuestion rows from frozen specialization templates.

match_policy stays unresolved: every matching specialization is emitted.
No matching specialization uses the canonical stem, not NOT_APPLICABLE.
Does not emit one question per CPF object.

`--emit-runtime-questions` stays C1-pack only (frozen dest).
`--repo-analysis` may pass any pack's specs so Phase 5 uses the same matcher.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_c1 import EXPECTATION_SPECS
from pipeline.control_evidence_contract import (
    CONTROL_QUESTIONS_LOCKED,
    ENGINEERING_QUESTION_SCHEMA_PATH,
    SCHEMA_VERSION,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.control_evidence_observe import FAMILY_EXPECTATION
from pipeline.system_trait_contract import (
    HACKERRANKATS_REPO,
    family_applies,
    traits_match,
)

# Frozen empty templates: canonical stem only. Two of these are not in the 42.
EMPTY_SPECIALIZATION_FAMILIES = frozenset(
    {"QF-0017", "QF-0031", "QF-0041", "QF-0047", "QF-0057", "QF-0065"}
)


def specialization_inventory(
    *,
    specs_by_pack: list[dict],
    specializations: dict[str, dict],
) -> list[dict]:
    """Read-only table: instantiated family vs frozen template stems."""
    rows = []
    for pack in specs_by_pack:
        for spec in pack["specs"]:
            fid = spec["family_id"]
            template = specializations.get(fid) or {}
            stems = list(template.get("specializations") or [])
            rows.append(
                {
                    "family_id": fid,
                    "pack": pack["id"],
                    "diagnostic_job": spec.get("diagnostic_job"),
                    "template_stems": len(stems),
                    "empty": fid in EMPTY_SPECIALIZATION_FAMILIES or not stems,
                }
            )
    return rows


def present_traits(conclusions: list[dict], *, repo: str = HACKERRANKATS_REPO) -> set[str]:
    return {
        row["trait"]
        for row in conclusions
        if row.get("repo") == repo and row.get("state") == "PRESENT"
    }


def load_specializations(paths: dict[str, Path]) -> dict[str, dict]:
    rows = []
    rows.extend(read_jsonl(paths["specialization_templates"]))
    if paths["specialization_expansion"].exists():
        rows.extend(read_jsonl(paths["specialization_expansion"]))
    return {row["family_id"]: row for row in rows}


def specialize_pack(
    *,
    present: set[str],
    traits: list[dict],
    applicability: list[dict],
    specializations: dict[str, dict],
    families: dict[str, dict],
    assessments: dict[str, dict],
    repo: str = HACKERRANKATS_REPO,
    specs: list[dict] | None = None,
) -> list[dict]:
    """Emit every matching specialization for the given pack specs.

    Default specs are the C1 pack (frozen runtime-question dest).
    Assessment state is copied from the family row; it is not rescored.
    """
    schema = load_schema(ENGINEERING_QUESTION_SCHEMA_PATH)
    app_by = {row["family_id"]: row for row in applicability}
    spec_rows = list(specs) if specs is not None else list(EXPECTATION_SPECS)
    rows = []
    n = 0
    for spec in spec_rows:
        fid = spec["family_id"]
        mapping = app_by[fid]
        if family_applies(mapping, present, traits=traits) != "APPLY":
            continue
        family = families[fid]
        template = specializations.get(fid) or {}
        matches = []
        for spec_row in template.get("specializations") or []:
            when = spec_row.get("when")
            if when and traits_match(when, present, traits=traits):
                matches.append(spec_row)
        if not matches:
            matches = [
                {
                    "id": f"{fid}.canonical",
                    "bindings": {},
                    "specialized_stem": family["stem"],
                }
            ]
        assessment = assessments.get(fid) or {}
        expectation_id = spec.get("id") or FAMILY_EXPECTATION[fid]
        for match in matches:
            n += 1
            row = {
                "id": f"q:{fid}:{match['id']}",
                "family_id": fid,
                "expectation_id": expectation_id,
                "repo": repo,
                "prompt": match["specialized_stem"],
                "specialization_id": match["id"],
                "bindings": dict(match.get("bindings") or {}),
                "human_required": False,
                "schema_version": SCHEMA_VERSION,
                "status": "frozen",
            }
            if assessment.get("state"):
                row["assessment_state"] = assessment["state"]
            validate_row(row, schema, label=row["id"])
            rows.append(row)
    return rows


def write_runtime_questions(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(CONTROL_QUESTIONS_LOCKED, "Runtime EngineeringQuestion emission")
    paths = paths or control_paths()
    refuse_overwrite(paths["questions"], "the runtime EngineeringQuestion dest")
    traits = read_jsonl(paths["traits"])
    present = present_traits(read_jsonl(paths["trait_conclusions"]))
    questions = specialize_pack(
        present=present,
        traits=traits,
        applicability=read_jsonl(paths["applicability"]),
        specializations=load_specializations(paths),
        families={row["id"]: row for row in read_jsonl(paths["families"])},
        assessments={row["family_id"]: row for row in read_jsonl(paths["assessments"])}
        if paths["assessments"].exists()
        else {},
    )
    stats = {
        "repo": HACKERRANKATS_REPO,
        "questions": len(questions),
        "families": sorted({row["family_id"] for row in questions}),
        "match_policy": "unresolved",
        "one_per_cpf": False,
        "canonical_stem_fallback": sum(
            1 for row in questions if row["specialization_id"].endswith(".canonical")
        ),
        "status": "frozen",
        "note": (
            "C1 pack only. match_policy stays unresolved. "
            "Multiple matching specializations are all emitted."
        ),
    }
    write_jsonl(paths["questions"], questions)
    dump_json(paths["question_stats"], stats)
    return stats
