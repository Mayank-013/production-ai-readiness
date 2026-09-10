"""Shared Phase 5 dest writer for remaining domain packs.

Does not rewrite Phase 5.1–5.3 modules. Absence is UNKNOWN.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from pipeline.common import CONSOLIDATION, dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence_benchmark import compare_control_assessments
from pipeline.control_evidence_contract import (
    ABSENCE_POLICY_UNKNOWN,
    CONTROL_ASSESSMENT_SCHEMA_PATH,
    CONTROL_DOC,
    CONTROL_EXPECTATION_SCHEMA_PATH,
    CONTROL_REFERENCE_SCHEMA_PATH,
    ENGINEERING_QUESTION_SCHEMA_PATH,
    RECOMMENDATION_SCHEMA_PATH,
    SCHEMA_VERSION,
    SKILLS_LOCKED,
    ControlError,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.gap_playbook import attach_playbooks
from pipeline.question_family_contract import EXPECTED_CANONICAL_FAMILIES

P5_DOC = "docs/p5-domains.md"


def domain_paths(dest_name: str, *, root: Path | None = None, extra_guards: list[str] | None = None) -> dict[str, Path]:
    cons = root or CONSOLIDATION
    dest = cons / "control_evidence" / dest_name
    paths = {
        "root": cons,
        "dir": dest,
        "families": cons / "question_families" / "canonical" / "families.jsonl",
        "controls": cons / "canonical" / "controls.jsonl",
        "expectations": dest / "expectations.jsonl",
        "expectation_stats": dest / "expectation_stats.json",
        "references": dest / "references.jsonl",
        "reference_stats": dest / "reference_stats.json",
        "observations": dest / "observations.jsonl",
        "observation_stats": dest / "observation_stats.json",
        "assessments": dest / "assessments.jsonl",
        "assessment_stats": dest / "assessment_stats.json",
        "comparison": dest / "comparison.jsonl",
        "comparison_stats": dest / "comparison_stats.json",
        "questions": dest / "questions.jsonl",
        "question_stats": dest / "question_stats.json",
        "recommendations": dest / "recommendations.jsonl",
        "recommendation_stats": dest / "recommendation_stats.json",
        "playbooks": dest / "playbooks.jsonl",
        "playbook_stats": dest / "playbook_stats.json",
        "evaluation_stats": dest / "evaluation_stats.json",
        "freeze": dest / "freeze.json",
        "c1_expectations": cons / "control_evidence" / "expectations.jsonl",
        "c4_freeze": cons / "control_evidence" / "c4" / "freeze.json",
        "p5_eval_freeze": cons / "control_evidence" / "p5_eval" / "freeze.json",
        "p5_security_freeze": cons / "control_evidence" / "p5_security" / "freeze.json",
        "p5_runtime_freeze": cons / "control_evidence" / "p5_runtime" / "freeze.json",
    }
    for name in extra_guards or []:
        paths[name] = cons / "control_evidence" / name.replace("_freeze", "") / "freeze.json"
    return paths


def assess_pack(observations, specs, expectation_map, *, repo: str) -> list[dict]:
    schema = load_schema(CONTROL_ASSESSMENT_SCHEMA_PATH)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        by_family[row["family_id"]].append(row)
    rows = []
    for spec in specs:
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
            "expectation_id": expectation_map[fid],
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


def write_domain_pack(
    *,
    pack: str,
    phase: str,
    dest_name: str,
    repo: str,
    fixture: Path,
    specs: list[dict],
    references: list[dict],
    actions: dict,
    playbooks: list[dict],
    collect,
    expectation_map: dict[str, str],
    inherited_c1: list[str],
    dropped: list[str],
    blocked: set[str],
    next_gate: str,
    later_domains: list[str],
    extra_guard_keys: list[str] | None = None,
    paths: dict[str, Path] | None = None,
) -> dict:
    paths = paths or domain_paths(dest_name, extra_guards=extra_guard_keys)
    refuse_overwrite(paths["freeze"], f"the Phase {phase} {pack} pack")
    if not fixture.is_dir():
        raise ControlError(f"missing fixture {fixture}")
    guard_keys = ["c1_expectations", "c4_freeze", "p5_eval_freeze", "p5_security_freeze", "p5_runtime_freeze"]
    guard_keys.extend(extra_guard_keys or [])
    guards = {key: paths[key].read_bytes() for key in guard_keys if paths[key].exists()}

    refuse_overwrite(paths["expectations"], f"the Phase {phase} {pack} expectations")
    families = {row["id"]: row for row in read_jsonl(paths["families"])}
    if len(families) != EXPECTED_CANONICAL_FAMILIES:
        raise ControlError(f"expected {EXPECTED_CANONICAL_FAMILIES} families")
    controls = {row["canonical_id"] for row in read_jsonl(paths["controls"])}
    schema = load_schema(CONTROL_EXPECTATION_SCHEMA_PATH)
    rows = []
    seen: set[str] = set()
    for spec in specs:
        fid = spec["family_id"]
        if fid in seen:
            raise ControlError(f"duplicate family {fid}")
        if fid in inherited_c1 or fid in blocked:
            raise ControlError(f"{fid} is owned by an earlier pack")
        seen.add(fid)
        family = families.get(fid)
        if family is None:
            raise ControlError(f"{fid} is not a canonical family")
        if spec["diagnostic_job"] != family["diagnostic_job"]:
            raise ControlError(f"{fid}: diagnostic_job drifted from the family")
        supporters = set(family.get("supporting_control_ids") or [])
        supporters |= set(family.get("supporting_cpf_ids") or [])
        if spec["control_id"] not in supporters or spec["control_id"] not in controls:
            raise ControlError(f"{fid}: {spec['control_id']} is not a supporting control")
        row = {
            "id": spec["id"],
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
    paths["dir"].mkdir(parents=True, exist_ok=True)
    write_jsonl(paths["expectations"], rows)
    dump_json(
        paths["expectation_stats"],
        {
            "pack": pack,
            "phase": phase,
            "expectations": len(rows),
            "families": [row["family_id"] for row in rows],
            "inherited_c1": list(inherited_c1),
            "dropped": list(dropped),
            "absence_policy": ABSENCE_POLICY_UNKNOWN,
            "status": "frozen",
            "next_gate": next_gate,
        },
    )

    observations = collect(fixture, repo=repo)
    assessments = assess_pack(observations, specs, expectation_map, repo=repo)
    if [s["family_id"] for s in references] != [s["family_id"] for s in specs]:
        raise ControlError(f"Phase {phase} references must follow pack family order")
    ref_schema = load_schema(CONTROL_REFERENCE_SCHEMA_PATH)
    ref_rows = []
    for spec in references:
        row = {
            "repo": repo,
            "family_id": spec["family_id"],
            "expectation_id": expectation_map[spec["family_id"]],
            "state": spec["state"],
            "notes": spec["notes"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, ref_schema, label=row["family_id"])
        ref_rows.append(row)
    comparison = compare_control_assessments(ref_rows, assessments)
    counts = Counter(row["classification"] for row in comparison)
    exact = sum(1 for row in comparison if row["human"] == row["system"])
    if counts.get("SATISFIED_FP") or counts.get("FAIL_FP") or exact != len(specs):
        raise ControlError(f"Phase {phase} C4 must be exact with SATISFIED/FAIL precision 1.000")

    q_schema = load_schema(ENGINEERING_QUESTION_SCHEMA_PATH)
    questions = []
    by_state = {row["family_id"]: row for row in assessments}
    for spec in specs:
        row = {
            "id": f"q:{spec['family_id']}:canonical",
            "family_id": spec["family_id"],
            "expectation_id": spec["id"],
            "repo": repo,
            "prompt": families[spec["family_id"]]["stem"],
            "specialization_id": f"{spec['family_id']}.canonical",
            "bindings": {},
            "human_required": False,
            "assessment_state": by_state[spec["family_id"]]["state"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, q_schema, label=row["id"])
        questions.append(row)

    rec_schema = load_schema(RECOMMENDATION_SCHEMA_PATH)
    recommendations = []
    n = 0
    spec_by = {spec["family_id"]: spec for spec in specs}
    q_by = {row["family_id"]: row for row in questions}
    for assessment in assessments:
        if assessment["state"] not in {"PARTIAL", "FAIL"}:
            continue
        n += 1
        pack_actions = actions[assessment["family_id"]]
        row = {
            "id": f"rec:{assessment['family_id']}:{n:02d}",
            "family_id": assessment["family_id"],
            "expectation_id": assessment["expectation_id"],
            "question_id": q_by[assessment["family_id"]]["id"],
            "control_id": spec_by[assessment["family_id"]]["control_id"],
            "repo": repo,
            "assessment_state": assessment["state"],
            "title": pack_actions["title"],
            "actions": list(pack_actions["actions"]),
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        if not SKILLS_LOCKED:
            raise ControlError(f"Phase {phase} does not attach skill_id")
        validate_row(row, rec_schema, label=row["id"])
        recommendations.append(row)
    playbook_rows = attach_playbooks(recommendations, specs=playbooks)
    finding = [row for row in playbook_rows if row["kind"] == "finding"]
    if len(finding) != len(recommendations):
        raise ControlError("each PARTIAL/FAIL recommendation must receive one finding playbook")

    write_jsonl(paths["references"], ref_rows)
    dump_json(paths["reference_stats"], {"repo": repo, "rows": len(ref_rows), "status": "frozen"})
    write_jsonl(paths["observations"], observations)
    dump_json(paths["observation_stats"], {"repo": repo, "observations": len(observations), "status": "frozen"})
    write_jsonl(paths["assessments"], assessments)
    dump_json(
        paths["assessment_stats"],
        {
            "repo": repo,
            "assessments": len(assessments),
            "by_state": dict(Counter(row["state"] for row in assessments)),
            "absence_is_unknown": True,
            "fail_requires_contradiction": True,
            "status": "frozen",
        },
    )
    write_jsonl(paths["comparison"], comparison)
    eval_stats = {
        "pack": pack,
        "phase": phase,
        "repo": repo,
        "rows": len(comparison),
        "classifications": dict(counts),
        "satisfied_tp": counts.get("SATISFIED_TP", 0),
        "satisfied_fp": counts.get("SATISFIED_FP", 0),
        "fail_fp": counts.get("FAIL_FP", 0),
        "partial_match": counts.get("PARTIAL_MATCH", 0),
        "unknown_abstain": counts.get("UNKNOWN_ABSTAIN", 0),
        "fail_tp": counts.get("FAIL_TP", 0),
        "satisfied_precision": 1.0,
        "exact_state_match": exact,
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "status": "frozen",
        "next_gate": next_gate,
        "note": f"Sealed Phase {phase} fixture pack. Contract: {P5_DOC}.",
    }
    dump_json(paths["comparison_stats"], eval_stats)
    dump_json(paths["evaluation_stats"], eval_stats)
    write_jsonl(paths["questions"], questions)
    dump_json(paths["question_stats"], {"questions": len(questions), "status": "frozen"})
    write_jsonl(paths["recommendations"], recommendations)
    dump_json(
        paths["recommendation_stats"],
        {"recommendations": len(recommendations), "skills": "not_in_this_pack", "status": "frozen"},
    )
    write_jsonl(paths["playbooks"], playbook_rows)
    dump_json(
        paths["playbook_stats"],
        {"playbooks": len(playbook_rows), "finding": len(finding), "unknown_playbooks": 0, "status": "frozen"},
    )
    freeze = {
        "pack": pack,
        "phase": phase,
        "repo": repo,
        "expectations": len(specs),
        "inherited_c1": list(inherited_c1),
        "dropped": list(dropped),
        "c4": eval_stats,
        "questions": len(questions),
        "recommendations": len(recommendations),
        "playbooks": len(playbook_rows),
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "skills": "not_in_this_pack",
        "later_domains": later_domains,
        "later_domains_status": "proposal" if later_domains else "none",
        "status": "frozen",
        "next_gate": next_gate,
        "note": f"Phase {phase} written through finding playbooks. Contract: {P5_DOC}. C1 contract: {CONTROL_DOC}.",
    }
    dump_json(paths["freeze"], freeze)
    for key, before in guards.items():
        if paths[key].read_bytes() != before:
            raise ControlError(f"Phase {phase} mutated {key}")
    return {
        "c4": eval_stats,
        "questions": len(questions),
        "recommendations": len(recommendations),
        "playbooks": len(playbook_rows),
        "dropped": list(dropped),
        "freeze": str(paths["freeze"]),
        "next_gate": next_gate,
        "note": freeze["note"],
    }
