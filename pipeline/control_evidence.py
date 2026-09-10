"""Control evidence layer: paths, C1 writer, and the sealed C1–recommendation run.

Does not overwrite B4 dests. Does not fork trait detectors.
Does not emit one expectation or question per CPF object.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.common import CONSOLIDATION, dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence_c1 import EXPECTATION_SPECS
from pipeline.control_evidence_contract import (
    ABSENCE_POLICY_UNKNOWN,
    C4_REPO,
    CONTROL_DOC,
    CONTROL_EVIDENCE_LOCKED,
    CONTROL_EXPECTATION_SCHEMA_PATH,
    CONTROL_LAYER_LOCKED,
    CONTROL_QUESTIONS_LOCKED,
    CONTROL_RECOMMENDATIONS_LOCKED,
    CONTROL_STAGES,
    EXPECTED_EXPECTATIONS,
    SCHEMA_VERSION,
    SKILLS_LOCKED,
    ControlError,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.question_family_contract import EXPECTED_CANONICAL_FAMILIES
from pipeline.system_trait_contract import EXPECTED_TRAITS, HACKERRANKATS_REPO


def control_paths(*, root: Path | None = None) -> dict[str, Path]:
    cons = root or CONSOLIDATION
    cdir = cons / "control_evidence"
    c4 = cdir / "c4"
    tdir = cons / "system_traits"
    return {
        "root": cons,
        "dir": cdir,
        "families": cons / "question_families" / "canonical" / "families.jsonl",
        "controls": cons / "canonical" / "controls.jsonl",
        "traits": tdir / "traits.jsonl",
        "applicability": tdir / "applicability.jsonl",
        "specialization_templates": tdir / "specialization_templates.jsonl",
        "specialization_expansion": tdir / "specialization_expansion.jsonl",
        "trait_conclusions": tdir / "trait_conclusions.jsonl",
        "expectations": cdir / "expectations.jsonl",
        "expectation_stats": cdir / "expectation_stats.json",
        "c4_dir": c4,
        "references": c4 / "references.jsonl",
        "reference_stats": c4 / "reference_stats.json",
        "observations": c4 / "observations.jsonl",
        "observation_stats": c4 / "observation_stats.json",
        "assessments": c4 / "assessments.jsonl",
        "assessment_stats": c4 / "assessment_stats.json",
        "comparison": c4 / "comparison.jsonl",
        "comparison_stats": c4 / "comparison_stats.json",
        "questions": c4 / "questions.jsonl",
        "question_stats": c4 / "question_stats.json",
        "recommendations": c4 / "recommendations.jsonl",
        "recommendation_stats": c4 / "recommendation_stats.json",
        "evaluation_stats": c4 / "evaluation_stats.json",
        "freeze": c4 / "freeze.json",
        "playbooks": cdir / "playbooks" / "playbooks.jsonl",
        "playbook_stats": cdir / "playbooks" / "playbook_stats.json",
        "playbook_validation": cdir / "playbooks" / "validation.jsonl",
        "playbook_validation_stats": cdir / "playbooks" / "validation_stats.json",
        "playbook_freeze": cdir / "playbooks" / "freeze.json",
        "trait_benchmark_v2_stats": tdir / "b4_v2" / "evaluation_stats.json",
        "trait_benchmark_v2_freeze": tdir / "b4_v2" / "freeze.json",
    }


def write_control_evidence_expectations(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(CONTROL_EVIDENCE_LOCKED, "C1 control evidence expectations")
    paths = paths or control_paths()
    refuse_overwrite(paths["expectations"], "the C1 control evidence expectations")
    families = {row["id"]: row for row in read_jsonl(paths["families"])}
    if len(families) != EXPECTED_CANONICAL_FAMILIES:
        raise ControlError(f"expected {EXPECTED_CANONICAL_FAMILIES} families")
    controls = {row["canonical_id"] for row in read_jsonl(paths["controls"])}
    schema = load_schema(CONTROL_EXPECTATION_SCHEMA_PATH)
    rows = []
    seen_families: set[str] = set()
    for i, spec in enumerate(EXPECTATION_SPECS, start=1):
        fid = spec["family_id"]
        if fid in seen_families:
            raise ControlError(f"duplicate family {fid}")
        seen_families.add(fid)
        family = families.get(fid)
        if family is None:
            raise ControlError(f"{fid} is not a canonical family")
        if spec["diagnostic_job"] != family["diagnostic_job"]:
            raise ControlError(f"{fid}: diagnostic_job drifted from the family")
        if spec["control_id"] not in family.get("supporting_control_ids") and spec["control_id"] not in family.get(
            "supporting_cpf_ids", []
        ):
            raise ControlError(f"{fid}: {spec['control_id']} is not a supporting control")
        if spec["control_id"] not in controls:
            raise ControlError(f"{spec['control_id']} is not a canonical control")
        row = {
            "id": f"CEE-{i:04d}",
            "family_id": fid,
            "control_id": spec["control_id"],
            "diagnostic_job": spec["diagnostic_job"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
            "absence_policy": ABSENCE_POLICY_UNKNOWN,
            "strong": list(spec["strong"]),
            "supporting": list(spec.get("supporting") or []),
            "insufficient_alone": list(spec.get("insufficient_alone") or []),
            "contradiction": list(spec.get("contradiction") or []),
            "evidence_sources": list(spec["evidence_sources"]),
        }
        if spec.get("notes"):
            row["notes"] = spec["notes"]
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    if len(rows) != EXPECTED_EXPECTATIONS:
        raise ControlError(f"expected {EXPECTED_EXPECTATIONS} expectations, got {len(rows)}")
    stats = {
        "expectations": len(rows),
        "families": sorted(seen_families),
        "controls": [row["control_id"] for row in rows],
        "absence_policy": ABSENCE_POLICY_UNKNOWN,
        "status": "frozen",
        "stages": list(CONTROL_STAGES),
        "open_stage": "C1",
        "one_per_cpf": False,
        "canonical_families_mutated": False,
        "ontology_mutated": False,
        "b4_mutated": False,
        "skills": "locked" if SKILLS_LOCKED else "open",
        "next_gate": "control_evidence_detection",
        "note": (
            "C1 only. Representative pack. Absence of evidence is UNKNOWN, "
            f"not FAIL. Contract: {CONTROL_DOC}."
        ),
    }
    write_jsonl(paths["expectations"], rows)
    dump_json(paths["expectation_stats"], stats)
    return stats


def write_control_layer(*, paths: dict[str, Path] | None = None, repo: Path | None = None) -> dict:
    """Sealed C1 through recommendations for the C4 repo."""
    assert_control_locked(CONTROL_LAYER_LOCKED, "Control layer")
    paths = paths or control_paths()
    from pipeline.control_evidence_benchmark import write_control_benchmark
    from pipeline.control_questions import write_runtime_questions
    from pipeline.control_recommendations import write_recommendations

    stats = {}
    if not paths["expectations"].exists() or not paths["expectations"].read_text(encoding="utf-8").strip():
        if CONTROL_EVIDENCE_LOCKED:
            raise ControlError("C1 dest is missing while C1 is locked")
        stats["c1"] = write_control_evidence_expectations(paths=paths)
    else:
        stats["c1"] = {"expectations": EXPECTED_EXPECTATIONS, "reused": True}
    stats["c4"] = write_control_benchmark(paths=paths, repo=repo)
    if CONTROL_QUESTIONS_LOCKED and paths["questions"].exists() and paths["questions"].read_text().strip():
        stats["questions"] = {"reused": True}
    else:
        stats["questions"] = write_runtime_questions(paths=paths)
    if CONTROL_RECOMMENDATIONS_LOCKED and paths["recommendations"].exists() and paths["recommendations"].read_text().strip():
        stats["recommendations"] = {"reused": True}
    else:
        stats["recommendations"] = write_recommendations(paths=paths)
    stats["repo"] = HACKERRANKATS_REPO
    stats["traits"] = EXPECTED_TRAITS
    stats["skills"] = "locked"
    stats["validation"] = "locked"
    stats["repo_analysis"] = "locked"
    freeze = {
        "repo": C4_REPO,
        "c1_expectations": EXPECTED_EXPECTATIONS,
        "c4": stats["c4"],
        "questions": stats["questions"],
        "recommendations": stats["recommendations"],
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "skills": "locked",
        "validation": "locked",
        "repo_analysis": "locked",
        "status": "frozen",
        "next_gate": "full_repo_analysis",
        "note": (
            "Control layer written through recommendations. "
            "Not finding evidence is UNKNOWN, not FAIL. "
            f"Contract: {CONTROL_DOC}."
        ),
    }
    if not paths["freeze"].exists() or not paths["freeze"].read_text().strip():
        dump_json(paths["freeze"], freeze)
    stats["freeze"] = str(paths["freeze"])
    stats["next_gate"] = "full_repo_analysis"
    stats["note"] = freeze["note"]
    return stats
