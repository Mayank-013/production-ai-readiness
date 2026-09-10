"""Phase 5.3 — Agent Runtime pack.

Same frozen C1→C4 schema. New dest.
Does not overwrite C1–C4, B4, playbooks, skills, repo_analysis, p5_eval, or p5_security.
QF-0041 stays on 5.2. QF-0021 is reserved for cost/resource.

Contract: docs/p5-domains.md
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from pipeline.common import CONSOLIDATION, ROOT, dump_json, read_jsonl, write_jsonl
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
from pipeline.p5_runtime_c1 import P5_RUNTIME_SPECS
from pipeline.p5_runtime_observe import (
    P5_RUNTIME_FAMILY_EXPECTATION,
    collect_p5_runtime_observations,
)
from pipeline.question_family_contract import EXPECTED_CANONICAL_FAMILIES

P5_RUNTIME_DOC = "docs/p5-domains.md"
P5_RUNTIME_REPO = "p5_runtime_v1"
P5_RUNTIME_FIXTURE = ROOT / "pipeline" / "fixtures" / "p5_runtime_v1"
EXPECTED_P5_RUNTIME = 6
DROPPED = ["QF-0041", "QF-0021"]
INHERITED_C1 = ["QF-0001", "QF-0003"]
OWNED_ELSEWHERE = {
    "QF-0041",
    "QF-0021",
    "QF-0027",
    "QF-0042",
    "QF-0043",
    "QF-0044",
    "QF-0045",
    "QF-0054",
    "QF-0031",
    "QF-0040",
    "QF-0049",
    "QF-0051",
    "QF-0062",
}

P5_RUNTIME_REFERENCES: list[dict] = [
    {"family_id": "QF-0023", "state": "SATISFIED", "notes": "require_human_approval gates the action."},
    {"family_id": "QF-0008", "state": "PARTIAL", "notes": "An idempotency key is set. No store-and-compare."},
    {"family_id": "QF-0064", "state": "SATISFIED", "notes": "validate_structured_output checks required fields."},
    {"family_id": "QF-0025", "state": "PARTIAL", "notes": "RETRYABLE_ERRORS is listed. No classify-before-retry."},
    {"family_id": "QF-0050", "state": "UNKNOWN", "notes": "No session-to-principal binding. Absence is UNKNOWN."},
    {"family_id": "QF-0004", "state": "FAIL", "notes": "cutoff_disabled = True is contradiction evidence."},
]

P5_RUNTIME_ACTIONS = {
    "QF-0008": {
        "title": "Store and compare idempotency keys",
        "actions": [
            "Keep the idempotency key, and store the prior outcome.",
            "Return the stored result when the same agent event is delivered twice.",
            "Do not treat a generated key as replay safety.",
        ],
    },
    "QF-0025": {
        "title": "Classify failures before retrying",
        "actions": [
            "Classify each failure as retryable, fallback, or human handoff.",
            "Retry only transient errors from that classification.",
            "Do not treat a retryable-error list as a completed classifier.",
        ],
    },
    "QF-0004": {
        "title": "Stop disabling slow-dependency cutoff",
        "actions": [
            "Remove cutoff_disabled from the serving path.",
            "Cut off a dependency that stays too slow or error-prone.",
            "Fail closed or degrade when the cutoff fires.",
        ],
    },
}

P5_RUNTIME_PLAYBOOK_SPECS: list[dict] = [
    {
        "family_id": "QF-0008",
        "assessment_state": "PARTIAL",
        "evidence_class": "idempotency_key_no_store",
        "kind": "finding",
        "evidence_found": ["An idempotency_key is assigned to the agent step."],
        "evidence_missing": [
            "A store that records the key and prior outcome.",
            "A replay path that returns the stored result.",
        ],
        "problem": (
            "An idempotency key is minted but never compared. A replay can "
            "repeat the side effect."
        ),
        "why_it_matters": (
            "Agent events are delivered at least once. Duplicate tool calls "
            "double-charge, double-write, or double-notify."
        ),
        "implementation_options": [
            "Store the idempotency key and the first outcome.",
            "On replay, return the stored outcome without re-executing.",
            "Apply the check to high-impact tool calls first.",
        ],
        "verification": [
            "Delivering the same key twice does not repeat the side effect.",
            "The second call returns the stored result.",
        ],
        "completion_evidence": [
            "A check_idempotency or idempotency_store path.",
            "skip_idempotency is not True.",
        ],
    },
    {
        "family_id": "QF-0025",
        "assessment_state": "PARTIAL",
        "evidence_class": "retryable_list_no_classifier",
        "kind": "finding",
        "evidence_found": ["RETRYABLE_ERRORS names timeout and unavailable."],
        "evidence_missing": [
            "A classify_failure step before retry.",
            "A path that does not retry unrecoverable errors.",
        ],
        "problem": (
            "Retryable names exist as a list. Failures are not classified "
            "before a retry is issued."
        ),
        "why_it_matters": (
            "Retrying auth, validation, or permanent errors amplifies load "
            "and hides the real failure."
        ),
        "implementation_options": [
            "Classify each failure before recover.",
            "Retry transients, fall back on persistent errors, escalate the rest.",
            "Keep the list as input to the classifier, not as the control.",
        ],
        "verification": [
            "A permanent error is not retried.",
            "A timeout is classified as retryable before the retry.",
        ],
        "completion_evidence": [
            "A classify_failure or classify_before_retry function.",
            "skip_retry_classification is not True.",
        ],
    },
    {
        "family_id": "QF-0004",
        "assessment_state": "FAIL",
        "evidence_class": "cutoff_disabled",
        "kind": "finding",
        "evidence_found": ["cutoff_disabled is set to True."],
        "evidence_missing": [
            "An automatic cutoff on persistent timeout or error rate.",
            "A blocked or degraded path when the cutoff fires.",
        ],
        "problem": (
            "Automatic cutoff is explicitly disabled. A slow or erroring "
            "dependency can keep being served."
        ),
        "why_it_matters": (
            "Without a cutoff, the agent loop waits on a dying dependency "
            "until the caller times out or the queue backs up."
        ),
        "implementation_options": [
            "Remove cutoff_disabled from the serving path.",
            "Set error-rate and timeout thresholds that block the dependency.",
            "Probe for recovery instead of staying on the failing path.",
        ],
        "verification": [
            "The contradiction flag is gone.",
            "A persistent timeout or error rate stops serving that dependency.",
        ],
        "completion_evidence": [
            "cutoff_disabled is not True.",
            "A cutoff_unhealthy_dependency or error_rate_cutoff exists.",
        ],
    },
]


def p5_runtime_paths(*, root: Path | None = None) -> dict[str, Path]:
    cons = root or CONSOLIDATION
    dest = cons / "control_evidence" / "p5_runtime"
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
        "p5_eval_freeze": cons / "control_evidence" / "p5_eval" / "freeze.json",
        "p5_security_freeze": cons / "control_evidence" / "p5_security" / "freeze.json",
    }


def write_p5_runtime_expectations(*, paths: dict[str, Path] | None = None) -> dict:
    paths = paths or p5_runtime_paths()
    refuse_overwrite(paths["expectations"], "the Phase 5.3 runtime expectations")
    families = {row["id"]: row for row in read_jsonl(paths["families"])}
    if len(families) != EXPECTED_CANONICAL_FAMILIES:
        raise ControlError(f"expected {EXPECTED_CANONICAL_FAMILIES} families")
    controls = {row["canonical_id"] for row in read_jsonl(paths["controls"])}
    schema = load_schema(CONTROL_EXPECTATION_SCHEMA_PATH)
    rows = []
    seen: set[str] = set()
    for spec in P5_RUNTIME_SPECS:
        fid = spec["family_id"]
        if fid in seen:
            raise ControlError(f"duplicate family {fid}")
        if fid in INHERITED_C1:
            raise ControlError(f"{fid} stays on the frozen C1 dest")
        if fid in OWNED_ELSEWHERE:
            raise ControlError(f"{fid} is owned by an earlier pack")
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
    if len(rows) != EXPECTED_P5_RUNTIME:
        raise ControlError(f"expected {EXPECTED_P5_RUNTIME} expectations, got {len(rows)}")
    stats = {
        "pack": "agent_runtime",
        "phase": "5.3",
        "expectations": len(rows),
        "families": [row["family_id"] for row in rows],
        "controls": [row["control_id"] for row in rows],
        "inherited_c1": list(INHERITED_C1),
        "dropped": list(DROPPED),
        "absence_policy": ABSENCE_POLICY_UNKNOWN,
        "one_per_cpf": False,
        "c1_mutated": False,
        "skills": "not_in_this_pack",
        "status": "frozen",
        "next_gate": "p5_rag_data",
        "note": (
            "Phase 5.3 representative agent-runtime pack. "
            "Absence of evidence is UNKNOWN, not FAIL. "
            f"Contract: {P5_RUNTIME_DOC}."
        ),
    }
    paths["dir"].mkdir(parents=True, exist_ok=True)
    write_jsonl(paths["expectations"], rows)
    dump_json(paths["expectation_stats"], stats)
    return stats


def assess_p5_runtime(observations: list[dict], *, repo: str = P5_RUNTIME_REPO) -> list[dict]:
    schema = load_schema(CONTROL_ASSESSMENT_SCHEMA_PATH)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        by_family[row["family_id"]].append(row)
    rows = []
    for spec in P5_RUNTIME_SPECS:
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
            "expectation_id": P5_RUNTIME_FAMILY_EXPECTATION[fid],
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


def build_p5_runtime_questions(assessments, families, *, repo=P5_RUNTIME_REPO):
    schema = load_schema(ENGINEERING_QUESTION_SCHEMA_PATH)
    by_state = {row["family_id"]: row for row in assessments}
    rows = []
    for spec in P5_RUNTIME_SPECS:
        fid = spec["family_id"]
        row = {
            "id": f"q:{fid}:canonical",
            "family_id": fid,
            "expectation_id": spec["id"],
            "repo": repo,
            "prompt": families[fid]["stem"],
            "specialization_id": f"{fid}.canonical",
            "bindings": {},
            "human_required": False,
            "assessment_state": by_state[fid]["state"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    return rows


def build_p5_runtime_recommendations(assessments, questions, *, repo=P5_RUNTIME_REPO):
    schema = load_schema(RECOMMENDATION_SCHEMA_PATH)
    by_family = {spec["family_id"]: spec for spec in P5_RUNTIME_SPECS}
    q_by_family = {row["family_id"]: row for row in questions}
    rows = []
    n = 0
    for assessment in assessments:
        if assessment["state"] not in {"PARTIAL", "FAIL"}:
            continue
        spec = by_family[assessment["family_id"]]
        pack = P5_RUNTIME_ACTIONS[assessment["family_id"]]
        n += 1
        row = {
            "id": f"rec:{assessment['family_id']}:{n:02d}",
            "family_id": assessment["family_id"],
            "expectation_id": assessment["expectation_id"],
            "question_id": q_by_family[assessment["family_id"]]["id"],
            "control_id": spec["control_id"],
            "repo": repo,
            "assessment_state": assessment["state"],
            "title": pack["title"],
            "actions": list(pack["actions"]),
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        if not SKILLS_LOCKED:
            raise ControlError("Phase 5.3 does not attach skill_id")
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    return rows


def write_p5_runtime_pack(*, paths: dict[str, Path] | None = None) -> dict:
    paths = paths or p5_runtime_paths()
    refuse_overwrite(paths["freeze"], "the Phase 5.3 runtime pack")
    if not P5_RUNTIME_FIXTURE.is_dir():
        raise ControlError(f"missing fixture {P5_RUNTIME_FIXTURE}")
    guards = {
        "c1": paths["c1_expectations"].read_bytes(),
        "c4": paths["c4_freeze"].read_bytes(),
        "p5_eval": paths["p5_eval_freeze"].read_bytes(),
        "p5_security": paths["p5_security_freeze"].read_bytes(),
    }
    c1 = write_p5_runtime_expectations(paths=paths)
    families = {row["id"]: row for row in read_jsonl(paths["families"])}
    observations = collect_p5_runtime_observations(P5_RUNTIME_FIXTURE, repo=P5_RUNTIME_REPO)
    assessments = assess_p5_runtime(observations, repo=P5_RUNTIME_REPO)
    schema = load_schema(CONTROL_REFERENCE_SCHEMA_PATH)
    if [s["family_id"] for s in P5_RUNTIME_REFERENCES] != [s["family_id"] for s in P5_RUNTIME_SPECS]:
        raise ControlError("P5 runtime references must follow pack family order")
    references = []
    for spec in P5_RUNTIME_REFERENCES:
        row = {
            "repo": P5_RUNTIME_REPO,
            "family_id": spec["family_id"],
            "expectation_id": P5_RUNTIME_FAMILY_EXPECTATION[spec["family_id"]],
            "state": spec["state"],
            "notes": spec["notes"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, schema, label=row["family_id"])
        references.append(row)
    comparison = compare_control_assessments(references, assessments)
    counts = Counter(row["classification"] for row in comparison)
    sat_fp = counts["SATISFIED_FP"]
    fail_fp = counts["FAIL_FP"]
    exact = sum(1 for row in comparison if row["human"] == row["system"])
    if sat_fp:
        raise ControlError("Phase 5.3 SATISFIED precision must stay 1.000")
    if fail_fp:
        raise ControlError("Phase 5.3 FAIL false positives are not allowed")
    if exact != EXPECTED_P5_RUNTIME:
        raise ControlError(f"Phase 5.3 exact match must be {EXPECTED_P5_RUNTIME}/{EXPECTED_P5_RUNTIME}")
    questions = build_p5_runtime_questions(assessments, families, repo=P5_RUNTIME_REPO)
    recommendations = build_p5_runtime_recommendations(assessments, questions, repo=P5_RUNTIME_REPO)
    playbooks = attach_playbooks(recommendations, specs=P5_RUNTIME_PLAYBOOK_SPECS)
    finding = [row for row in playbooks if row["kind"] == "finding"]
    if len(finding) != len(recommendations):
        raise ControlError("each PARTIAL/FAIL recommendation must receive one finding playbook")
    write_jsonl(paths["references"], references)
    dump_json(paths["reference_stats"], {"repo": P5_RUNTIME_REPO, "rows": len(references), "status": "frozen"})
    write_jsonl(paths["observations"], observations)
    dump_json(
        paths["observation_stats"],
        {
            "repo": P5_RUNTIME_REPO,
            "observations": len(observations),
            "by_strength": dict(Counter(row["strength"] for row in observations)),
            "status": "frozen",
        },
    )
    write_jsonl(paths["assessments"], assessments)
    dump_json(
        paths["assessment_stats"],
        {
            "repo": P5_RUNTIME_REPO,
            "assessments": len(assessments),
            "by_state": dict(Counter(row["state"] for row in assessments)),
            "absence_is_unknown": True,
            "fail_requires_contradiction": True,
            "status": "frozen",
        },
    )
    write_jsonl(paths["comparison"], comparison)
    eval_stats = {
        "pack": "agent_runtime",
        "phase": "5.3",
        "repo": P5_RUNTIME_REPO,
        "rows": len(comparison),
        "classifications": dict(counts),
        "satisfied_tp": counts["SATISFIED_TP"],
        "satisfied_fp": sat_fp,
        "fail_fp": fail_fp,
        "partial_match": counts["PARTIAL_MATCH"],
        "unknown_abstain": counts["UNKNOWN_ABSTAIN"],
        "fail_tp": counts["FAIL_TP"],
        "satisfied_precision": 1.0,
        "exact_state_match": exact,
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "status": "frozen",
        "next_gate": "p5_rag_data",
        "note": f"Sealed Phase 5.3 fixture pack. Contract: {P5_RUNTIME_DOC}.",
    }
    dump_json(paths["comparison_stats"], eval_stats)
    dump_json(paths["evaluation_stats"], eval_stats)
    write_jsonl(paths["questions"], questions)
    dump_json(paths["question_stats"], {"questions": len(questions), "status": "frozen"})
    write_jsonl(paths["recommendations"], recommendations)
    dump_json(
        paths["recommendation_stats"],
        {
            "recommendations": len(recommendations),
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
            "unknown_playbooks": 0,
            "skills": "not_in_this_pack",
            "status": "frozen",
        },
    )
    freeze = {
        "pack": "agent_runtime",
        "phase": "5.3",
        "repo": P5_RUNTIME_REPO,
        "expectations": EXPECTED_P5_RUNTIME,
        "inherited_c1": list(INHERITED_C1),
        "dropped": list(DROPPED),
        "c4": eval_stats,
        "questions": len(questions),
        "recommendations": len(recommendations),
        "playbooks": len(playbooks),
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "skills": "not_in_this_pack",
        "later_domains": ["rag_data", "observability_ops", "cost_resource"],
        "later_domains_status": "proposal",
        "status": "frozen",
        "next_gate": "p5_rag_data",
        "note": (
            "Phase 5.3 written through finding playbooks. "
            "QF-0041 stays on 5.2. QF-0021 reserved for cost. "
            f"Contract: {P5_RUNTIME_DOC}. C1 contract: {CONTROL_DOC}."
        ),
    }
    dump_json(paths["freeze"], freeze)
    if paths["c1_expectations"].read_bytes() != guards["c1"]:
        raise ControlError("Phase 5.3 mutated the frozen C1 dest")
    if paths["c4_freeze"].read_bytes() != guards["c4"]:
        raise ControlError("Phase 5.3 mutated the frozen C4 dest")
    if paths["p5_eval_freeze"].read_bytes() != guards["p5_eval"]:
        raise ControlError("Phase 5.3 mutated the frozen Phase 5.1 dest")
    if paths["p5_security_freeze"].read_bytes() != guards["p5_security"]:
        raise ControlError("Phase 5.3 mutated the frozen Phase 5.2 dest")
    return {
        "c1": c1,
        "c4": eval_stats,
        "questions": len(questions),
        "recommendations": len(recommendations),
        "playbooks": len(playbooks),
        "dropped": list(DROPPED),
        "freeze": str(paths["freeze"]),
        "next_gate": "p5_rag_data",
        "note": freeze["note"],
    }
