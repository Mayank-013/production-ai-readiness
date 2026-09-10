"""Phase 5.1 — AI Evaluation & Quality pack.

Same frozen C1→C4 schema and safety rules. New dest.
Does not overwrite C1–C4, B4, playbooks, skills, or repo_analysis.
Does not emit one family per CPF. Skills stay out until a later pack
proves new PARTIAL/FAIL classes that need them.

Contract: docs/p5-domains.md
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from pipeline.common import CONSOLIDATION, ROOT, dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence_benchmark import _classify, compare_control_assessments
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
from pipeline.p5_eval_c1 import P5_EVAL_SPECS
from pipeline.p5_eval_observe import (
    P5_EVAL_FAMILY_EXPECTATION,
    collect_p5_eval_observations,
)
from pipeline.question_family_contract import EXPECTED_CANONICAL_FAMILIES
from pipeline.system_trait_contract import HACKERRANKATS_REPO

P5_EVAL_DOC = "docs/p5-domains.md"
P5_EVAL_REPO = "p5_eval_v1"
P5_EVAL_FIXTURE = ROOT / "pipeline" / "fixtures" / "p5_eval_v1"
EXPECTED_P5_EVAL = 6
INHERITED_C1_EVAL_GATE = "QF-0005"

P5_EVAL_REFERENCES: list[dict] = [
    {
        "family_id": "QF-0027",
        "state": "PARTIAL",
        "notes": "ndcg@10 is configured. No retrieval scorer harness.",
    },
    {
        "family_id": "QF-0042",
        "state": "UNKNOWN",
        "notes": "No tool-selection evaluation. Absence is UNKNOWN.",
    },
    {
        "family_id": "QF-0043",
        "state": "PARTIAL",
        "notes": "A production quality score is logged. No online monitor.",
    },
    {
        "family_id": "QF-0044",
        "state": "SATISFIED",
        "notes": "LABELED_EVAL_EXAMPLES holds inputs and reference outputs.",
    },
    {
        "family_id": "QF-0045",
        "state": "SATISFIED",
        "notes": "faithfulness_score compares the answer to retrieved context.",
    },
    {
        "family_id": "QF-0054",
        "state": "FAIL",
        "notes": "allow_train_eval_overlap = True is contradiction evidence.",
    },
]

P5_EVAL_ACTIONS = {
    "QF-0027": {
        "title": "Score retrieval relevance against labeled sources",
        "actions": [
            "Add a retrieval eval harness that computes nDCG, recall@k, or context precision.",
            "Keep the metric attached to labeled relevant sources, not a comment.",
            "Do not treat a metric name in config as a completed control.",
        ],
    },
    "QF-0043": {
        "title": "Monitor production output quality after release",
        "actions": [
            "Run an online eval or production quality monitor on live traffic.",
            "Alert or gate when quality degrades, not only log a score.",
            "Keep pre-production eval_gate separate from this control.",
        ],
    },
    "QF-0054": {
        "title": "Stop allowing train and eval overlap",
        "actions": [
            "Remove allow_train_eval_overlap from the production eval path.",
            "Add an overlap or near-duplicate check across train, eval, and retrieved data.",
            "Fail the suite when leakage is detected.",
        ],
    },
}

P5_EVAL_PLAYBOOK_SPECS: list[dict] = [
    {
        "family_id": "QF-0027",
        "assessment_state": "PARTIAL",
        "evidence_class": "retrieval_metric_no_scored_harness",
        "kind": "finding",
        "evidence_found": [
            "RETRIEVAL_METRIC is set to ndcg@10.",
        ],
        "evidence_missing": [
            "A function that scores ranked results against labeled sources.",
            "A computed nDCG, recall@k, or context-precision value.",
        ],
        "problem": (
            "Retrieval quality is named as a metric but never scored. "
            "The control is a configured string, not an evaluator."
        ),
        "why_it_matters": (
            "A named metric cannot catch irrelevant retrieval. Ranking "
            "regressions ship without a relevance score."
        ),
        "implementation_options": [
            "Build a retrieval eval harness over labeled relevant sources.",
            "Compute nDCG, recall@k, or context precision in that harness.",
            "Fail the suite when the retrieval score drops below a stated bar.",
        ],
        "verification": [
            "A test calls the retrieval scorer on a labeled query.",
            "The metric value is computed, not only configured.",
        ],
        "completion_evidence": [
            "A named evaluate_retrieval or equivalent scorer.",
            "A labeled qrel or relevant-source set used by that scorer.",
        ],
    },
    {
        "family_id": "QF-0043",
        "assessment_state": "PARTIAL",
        "evidence_class": "quality_log_no_online_monitor",
        "kind": "finding",
        "evidence_found": [
            "The serving path logs production_quality_score.",
        ],
        "evidence_missing": [
            "An online eval job on production traffic.",
            "A monitor that can fail or page when quality drops.",
        ],
        "problem": (
            "Production quality is recorded as a log line. There is no "
            "online evaluator watching live outputs after release."
        ),
        "why_it_matters": (
            "Logged scores do not detect quality degradation before it "
            "reaches a large user population."
        ),
        "implementation_options": [
            "Add an online eval or production quality monitor on live traffic.",
            "Keep the monitor separate from the pre-production eval gate.",
            "Alert when the live score drops below a documented threshold.",
        ],
        "verification": [
            "A production-traffic path invokes the online eval.",
            "A quality drop is visible as a monitor failure, not only a log.",
        ],
        "completion_evidence": [
            "An online_eval or production_quality_monitor on the serving path.",
            "A threshold or alarm attached to that monitor.",
        ],
    },
    {
        "family_id": "QF-0054",
        "assessment_state": "FAIL",
        "evidence_class": "allow_train_eval_overlap",
        "kind": "finding",
        "evidence_found": [
            "allow_train_eval_overlap is set to True.",
        ],
        "evidence_missing": [
            "An overlap or leakage check across train, eval, and retrieved data.",
            "A failing suite when splits share items.",
        ],
        "problem": (
            "Train and eval overlap is explicitly allowed. Leakage is not "
            "an unknown absence; it is a stated unsafe setting."
        ),
        "why_it_matters": (
            "Overlapping splits inflate eval scores and hide real quality "
            "regressions. Retrieved or auxiliary copies of eval items do the same."
        ),
        "implementation_options": [
            "Remove allow_train_eval_overlap from the eval path.",
            "Add a leakage or near-duplicate check across splits.",
            "Fail the suite when overlap is detected.",
        ],
        "verification": [
            "The contradiction flag is gone.",
            "A leakage check runs on train, eval, and retrieved data.",
        ],
        "completion_evidence": [
            "allow_train_eval_overlap is not True.",
            "A check_overlap or equivalent leakage detector exists.",
        ],
    },
]


def p5_eval_paths(*, root: Path | None = None) -> dict[str, Path]:
    cons = root or CONSOLIDATION
    dest = cons / "control_evidence" / "p5_eval"
    return {
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
    }


def write_p5_eval_expectations(*, paths: dict[str, Path] | None = None) -> dict:
    paths = paths or p5_eval_paths()
    refuse_overwrite(paths["expectations"], "the Phase 5.1 eval expectations")
    families = {row["id"]: row for row in read_jsonl(paths["families"])}
    if len(families) != EXPECTED_CANONICAL_FAMILIES:
        raise ControlError(f"expected {EXPECTED_CANONICAL_FAMILIES} families")
    controls = {row["canonical_id"] for row in read_jsonl(paths["controls"])}
    schema = load_schema(CONTROL_EXPECTATION_SCHEMA_PATH)
    rows = []
    seen: set[str] = set()
    for spec in P5_EVAL_SPECS:
        fid = spec["family_id"]
        if fid in seen:
            raise ControlError(f"duplicate family {fid}")
        if fid == INHERITED_C1_EVAL_GATE:
            raise ControlError("QF-0005 stays on the frozen C1 dest")
        seen.add(fid)
        family = families.get(fid)
        if family is None:
            raise ControlError(f"{fid} is not a canonical family")
        if spec["diagnostic_job"] != family["diagnostic_job"]:
            raise ControlError(f"{fid}: diagnostic_job drifted from the family")
        supporters = set(family.get("supporting_control_ids") or [])
        supporters |= set(family.get("supporting_cpf_ids") or [])
        if spec["control_id"] not in supporters:
            raise ControlError(f"{fid}: {spec['control_id']} is not a supporting control")
        if spec["control_id"] not in controls:
            raise ControlError(f"{spec['control_id']} is not a canonical control")
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
    if len(rows) != EXPECTED_P5_EVAL:
        raise ControlError(f"expected {EXPECTED_P5_EVAL} expectations, got {len(rows)}")
    stats = {
        "pack": "ai_evaluation_quality",
        "phase": "5.1",
        "expectations": len(rows),
        "families": [row["family_id"] for row in rows],
        "controls": [row["control_id"] for row in rows],
        "inherited_c1": [INHERITED_C1_EVAL_GATE],
        "absence_policy": ABSENCE_POLICY_UNKNOWN,
        "one_per_cpf": False,
        "c1_mutated": False,
        "c4_mutated": False,
        "skills": "not_in_this_pack",
        "status": "frozen",
        "next_gate": "p5_ai_security",
        "note": (
            "Phase 5.1 representative eval/quality pack. "
            "Absence of evidence is UNKNOWN, not FAIL. "
            f"Contract: {P5_EVAL_DOC}."
        ),
    }
    paths["dir"].mkdir(parents=True, exist_ok=True)
    write_jsonl(paths["expectations"], rows)
    dump_json(paths["expectation_stats"], stats)
    return stats


def assess_p5_eval(observations: list[dict], *, repo: str = P5_EVAL_REPO) -> list[dict]:
    schema = load_schema(CONTROL_ASSESSMENT_SCHEMA_PATH)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        by_family[row["family_id"]].append(row)
    rows = []
    for spec in P5_EVAL_SPECS:
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
            "expectation_id": P5_EVAL_FAMILY_EXPECTATION[fid],
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


def build_p5_eval_questions(
    assessments: list[dict],
    families: dict[str, dict],
    *,
    repo: str = P5_EVAL_REPO,
) -> list[dict]:
    schema = load_schema(ENGINEERING_QUESTION_SCHEMA_PATH)
    by_state = {row["family_id"]: row for row in assessments}
    rows = []
    for spec in P5_EVAL_SPECS:
        fid = spec["family_id"]
        family = families[fid]
        assessment = by_state[fid]
        row = {
            "id": f"q:{fid}:canonical",
            "family_id": fid,
            "expectation_id": spec["id"],
            "repo": repo,
            "prompt": family["stem"],
            "specialization_id": f"{fid}.canonical",
            "bindings": {},
            "human_required": False,
            "assessment_state": assessment["state"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    return rows


def build_p5_eval_recommendations(
    assessments: list[dict],
    questions: list[dict],
    *,
    repo: str = P5_EVAL_REPO,
) -> list[dict]:
    schema = load_schema(RECOMMENDATION_SCHEMA_PATH)
    by_family = {spec["family_id"]: spec for spec in P5_EVAL_SPECS}
    q_by_family = {row["family_id"]: row for row in questions}
    rows = []
    n = 0
    for assessment in assessments:
        if assessment["state"] not in {"PARTIAL", "FAIL"}:
            continue
        spec = by_family[assessment["family_id"]]
        pack = P5_EVAL_ACTIONS[assessment["family_id"]]
        question = q_by_family[assessment["family_id"]]
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
            raise ControlError("Phase 5.1 does not attach skill_id")
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    return rows


def write_p5_eval_pack(*, paths: dict[str, Path] | None = None) -> dict:
    paths = paths or p5_eval_paths()
    refuse_overwrite(paths["freeze"], "the Phase 5.1 eval pack")
    if not P5_EVAL_FIXTURE.is_dir():
        raise ControlError(f"missing fixture {P5_EVAL_FIXTURE}")
    c1_before = paths["c1_expectations"].read_bytes()
    c4_before = paths["c4_freeze"].read_bytes()

    c1 = write_p5_eval_expectations(paths=paths)
    families = {row["id"]: row for row in read_jsonl(paths["families"])}

    observations = collect_p5_eval_observations(P5_EVAL_FIXTURE, repo=P5_EVAL_REPO)
    assessments = assess_p5_eval(observations, repo=P5_EVAL_REPO)

    schema = load_schema(CONTROL_REFERENCE_SCHEMA_PATH)
    expected = [spec["family_id"] for spec in P5_EVAL_SPECS]
    got = [spec["family_id"] for spec in P5_EVAL_REFERENCES]
    if got != expected:
        raise ControlError("P5 eval references must follow pack family order")
    references = []
    for spec in P5_EVAL_REFERENCES:
        row = {
            "repo": P5_EVAL_REPO,
            "family_id": spec["family_id"],
            "expectation_id": P5_EVAL_FAMILY_EXPECTATION[spec["family_id"]],
            "state": spec["state"],
            "notes": spec["notes"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, schema, label=row["family_id"])
        references.append(row)

    comparison = compare_control_assessments(references, assessments)
    counts = Counter(row["classification"] for row in comparison)
    sat_tp = counts["SATISFIED_TP"]
    sat_fp = counts["SATISFIED_FP"]
    fail_fp = counts["FAIL_FP"]
    exact = sum(1 for row in comparison if row["human"] == row["system"])
    if sat_fp:
        raise ControlError("Phase 5.1 SATISFIED precision must stay 1.000")
    if fail_fp:
        raise ControlError("Phase 5.1 FAIL false positives are not allowed")
    if exact != EXPECTED_P5_EVAL:
        raise ControlError(f"Phase 5.1 exact match must be {EXPECTED_P5_EVAL}/{EXPECTED_P5_EVAL}")

    questions = build_p5_eval_questions(assessments, families, repo=P5_EVAL_REPO)
    recommendations = build_p5_eval_recommendations(assessments, questions, repo=P5_EVAL_REPO)
    if any(row["assessment_state"] == "UNKNOWN" for row in recommendations):
        raise ControlError("UNKNOWN must not receive a recommendation")
    playbooks = attach_playbooks(recommendations, specs=P5_EVAL_PLAYBOOK_SPECS)
    finding = [row for row in playbooks if row["kind"] == "finding"]
    if len(finding) != len(recommendations):
        raise ControlError("each PARTIAL/FAIL recommendation must receive one finding playbook")

    write_jsonl(paths["references"], references)
    dump_json(paths["reference_stats"], {"repo": P5_EVAL_REPO, "rows": len(references), "status": "frozen"})
    write_jsonl(paths["observations"], observations)
    dump_json(
        paths["observation_stats"],
        {
            "repo": P5_EVAL_REPO,
            "observations": len(observations),
            "by_strength": dict(Counter(row["strength"] for row in observations)),
            "by_family": dict(Counter(row["family_id"] for row in observations)),
            "status": "frozen",
        },
    )
    write_jsonl(paths["assessments"], assessments)
    dump_json(
        paths["assessment_stats"],
        {
            "repo": P5_EVAL_REPO,
            "assessments": len(assessments),
            "by_state": dict(Counter(row["state"] for row in assessments)),
            "absence_is_unknown": True,
            "fail_requires_contradiction": True,
            "status": "frozen",
        },
    )
    write_jsonl(paths["comparison"], comparison)
    eval_stats = {
        "pack": "ai_evaluation_quality",
        "phase": "5.1",
        "repo": P5_EVAL_REPO,
        "rows": len(comparison),
        "classifications": dict(counts),
        "satisfied_tp": sat_tp,
        "satisfied_fp": sat_fp,
        "fail_fp": fail_fp,
        "partial_match": counts["PARTIAL_MATCH"],
        "unknown_abstain": counts["UNKNOWN_ABSTAIN"],
        "fail_tp": counts["FAIL_TP"],
        "satisfied_precision": 1.0,
        "exact_state_match": exact,
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "c1_mutated": False,
        "catalog_retuned": False,
        "status": "frozen",
        "next_gate": "p5_ai_security",
        "note": (
            "Sealed Phase 5.1 fixture pack. False SATISFIED and false FAIL "
            f"are expensive. Contract: {P5_EVAL_DOC}."
        ),
    }
    dump_json(paths["comparison_stats"], eval_stats)
    dump_json(paths["evaluation_stats"], eval_stats)
    write_jsonl(paths["questions"], questions)
    dump_json(
        paths["question_stats"],
        {
            "questions": len(questions),
            "families": [row["family_id"] for row in questions],
            "match_policy": "unresolved",
            "one_per_cpf": False,
            "status": "frozen",
        },
    )
    write_jsonl(paths["recommendations"], recommendations)
    dump_json(
        paths["recommendation_stats"],
        {
            "recommendations": len(recommendations),
            "states": sorted({row["assessment_state"] for row in recommendations}),
            "unknown_recommended": False,
            "skills": "not_in_this_pack",
            "status": "frozen",
        },
    )
    write_jsonl(paths["playbooks"], playbooks)
    dump_json(
        paths["playbook_stats"],
        {
            "playbooks": len(playbooks),
            "finding": len(finding),
            "catalog": sum(1 for row in playbooks if row["kind"] == "catalog"),
            "unknown_playbooks": 0,
            "family_blind": False,
            "skills": "not_in_this_pack",
            "status": "frozen",
        },
    )
    freeze = {
        "pack": "ai_evaluation_quality",
        "phase": "5.1",
        "repo": P5_EVAL_REPO,
        "expectations": EXPECTED_P5_EVAL,
        "inherited_c1": [INHERITED_C1_EVAL_GATE],
        "c4": eval_stats,
        "questions": len(questions),
        "recommendations": len(recommendations),
        "playbooks": len(playbooks),
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "skills": "not_in_this_pack",
        "c1_dest_frozen": True,
        "later_domains": [
            "ai_security",
            "agent_runtime",
            "rag_data",
            "observability_ops",
            "cost_resource",
        ],
        "later_domains_status": "proposal",
        "status": "frozen",
        "next_gate": "p5_ai_security",
        "note": (
            "Phase 5.1 written through finding playbooks. "
            "A skill cannot declare victory. "
            f"Contract: {P5_EVAL_DOC}. C1 contract: {CONTROL_DOC}."
        ),
    }
    dump_json(paths["freeze"], freeze)
    if paths["c1_expectations"].read_bytes() != c1_before:
        raise ControlError("Phase 5.1 mutated the frozen C1 dest")
    if paths["c4_freeze"].read_bytes() != c4_before:
        raise ControlError("Phase 5.1 mutated the frozen C4 dest")
    return {
        "c1": c1,
        "c4": eval_stats,
        "questions": len(questions),
        "recommendations": len(recommendations),
        "playbooks": len(playbooks),
        "freeze": str(paths["freeze"]),
        "next_gate": "p5_ai_security",
        "note": freeze["note"],
    }
