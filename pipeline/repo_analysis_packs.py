"""Mechanical pack registry for integrated repo-analysis.

Each pack keeps its own sealed specs, detectors, assessments,
recommendations, and playbooks. The merge layer does not reinterpret
C1–C4 or Phase 5 C3 rules.

A family is owned by at most one pack. Dropped families stay out.
"""

from __future__ import annotations

from pipeline.control_evidence_assess import assess_controls
from pipeline.control_evidence_c1 import EXPECTATION_SPECS
from pipeline.control_evidence_observe import collect_control_observations
from pipeline.control_recommendations import ACTIONS as C1_ACTIONS
from pipeline.gap_playbook import PLAYBOOK_SPECS as C1_PLAYBOOKS
from pipeline.p5_cost import P5_COST_ACTIONS, P5_COST_PLAYBOOKS, assess_p5_cost
from pipeline.p5_cost_c1 import P5_COST_SPECS
from pipeline.p5_cost_observe import collect_p5_cost_observations
from pipeline.p5_eval import P5_EVAL_ACTIONS, P5_EVAL_PLAYBOOK_SPECS, assess_p5_eval
from pipeline.p5_eval_c1 import P5_EVAL_SPECS
from pipeline.p5_eval_observe import collect_p5_eval_observations
from pipeline.p5_ops import P5_OPS_ACTIONS, P5_OPS_PLAYBOOKS, assess_p5_ops
from pipeline.p5_ops_c1 import P5_OPS_SPECS
from pipeline.p5_ops_observe import collect_p5_ops_observations
from pipeline.p5_rag import P5_RAG_ACTIONS, P5_RAG_PLAYBOOKS, assess_p5_rag
from pipeline.p5_rag_c1 import P5_RAG_SPECS
from pipeline.p5_rag_observe import collect_p5_rag_observations
from pipeline.p5_runtime import P5_RUNTIME_ACTIONS, P5_RUNTIME_PLAYBOOK_SPECS, assess_p5_runtime
from pipeline.p5_runtime_c1 import P5_RUNTIME_SPECS
from pipeline.p5_runtime_observe import collect_p5_runtime_observations
from pipeline.p5_security import P5_SECURITY_ACTIONS, P5_SECURITY_PLAYBOOK_SPECS, assess_p5_security
from pipeline.p5_security_c1 import P5_SECURITY_SPECS
from pipeline.p5_security_observe import collect_p5_security_observations

DROPPED_FAMILIES = frozenset(
    {
        "QF-0007",
        "QF-0024",
        "QF-0029",
        "QF-0039",
        "QF-0047",
        "QF-0052",
        "QF-0058",
        "QF-0060",
    }
)

PACKS: list[dict] = [
    {
        "id": "c1",
        "specs": EXPECTATION_SPECS,
        "collect": collect_control_observations,
        "assess": assess_controls,
        "actions": C1_ACTIONS,
        "playbooks": C1_PLAYBOOKS,
        "c1": True,
    },
    {
        "id": "p5_eval",
        "specs": P5_EVAL_SPECS,
        "collect": collect_p5_eval_observations,
        "assess": assess_p5_eval,
        "actions": P5_EVAL_ACTIONS,
        "playbooks": P5_EVAL_PLAYBOOK_SPECS,
        "c1": False,
    },
    {
        "id": "p5_security",
        "specs": P5_SECURITY_SPECS,
        "collect": collect_p5_security_observations,
        "assess": assess_p5_security,
        "actions": P5_SECURITY_ACTIONS,
        "playbooks": P5_SECURITY_PLAYBOOK_SPECS,
        "c1": False,
    },
    {
        "id": "p5_runtime",
        "specs": P5_RUNTIME_SPECS,
        "collect": collect_p5_runtime_observations,
        "assess": assess_p5_runtime,
        "actions": P5_RUNTIME_ACTIONS,
        "playbooks": P5_RUNTIME_PLAYBOOK_SPECS,
        "c1": False,
    },
    {
        "id": "p5_rag",
        "specs": P5_RAG_SPECS,
        "collect": collect_p5_rag_observations,
        "assess": assess_p5_rag,
        "actions": P5_RAG_ACTIONS,
        "playbooks": P5_RAG_PLAYBOOKS,
        "c1": False,
    },
    {
        "id": "p5_ops",
        "specs": P5_OPS_SPECS,
        "collect": collect_p5_ops_observations,
        "assess": assess_p5_ops,
        "actions": P5_OPS_ACTIONS,
        "playbooks": P5_OPS_PLAYBOOKS,
        "c1": False,
    },
    {
        "id": "p5_cost",
        "specs": P5_COST_SPECS,
        "collect": collect_p5_cost_observations,
        "assess": assess_p5_cost,
        "actions": P5_COST_ACTIONS,
        "playbooks": P5_COST_PLAYBOOKS,
        "c1": False,
    },
]


def instantiated_families() -> list[str]:
    rows = []
    seen: set[str] = set()
    for pack in PACKS:
        for spec in pack["specs"]:
            fid = spec["family_id"]
            if fid in DROPPED_FAMILIES:
                raise RuntimeError(f"dropped family {fid} leaked into {pack['id']}")
            if fid in seen:
                raise RuntimeError(f"{fid} is owned by more than one pack")
            seen.add(fid)
            rows.append(fid)
    return rows


EXPECTED_INSTANTIATED = 42


def pack_by_family() -> dict[str, str]:
    out = {}
    for pack in PACKS:
        for spec in pack["specs"]:
            out[spec["family_id"]] = pack["id"]
    return out


def spec_by_family() -> dict[str, dict]:
    out = {}
    for pack in PACKS:
        for spec in pack["specs"]:
            out[spec["family_id"]] = spec
    return out


def playbook_specs() -> list[dict]:
    rows = []
    for pack in PACKS:
        rows.extend(pack["playbooks"])
    return rows


def assert_pack_registry() -> list[str]:
    rows = instantiated_families()
    if len(rows) != EXPECTED_INSTANTIATED:
        raise RuntimeError(
            f"expected {EXPECTED_INSTANTIATED} instantiated families, got {len(rows)}"
        )
    leaked = sorted(DROPPED_FAMILIES & set(rows))
    if leaked:
        raise RuntimeError(f"dropped families leaked into the runtime set: {leaked}")
    return rows


def applicable_pack_families(
    specs: list[dict],
    present: set[str],
    traits: list[dict],
    applicability: list[dict],
) -> list[str]:
    from pipeline.system_trait_contract import family_applies

    app_by = {row["family_id"]: row for row in applicability}
    out = []
    for spec in specs:
        fid = spec["family_id"]
        mapping = app_by.get(fid)
        if mapping is None:
            raise RuntimeError(f"{fid} has no applicability rule")
        if family_applies(mapping, present, traits=traits) == "APPLY":
            out.append(fid)
    return out


def build_pack_questions(
    assessments: list[dict],
    specs: list[dict],
    families: dict[str, dict],
    *,
    repo: str,
) -> list[dict]:
    """Canonical-stem fallback. `--repo-analysis` uses specialize_pack instead."""
    from pipeline.control_evidence_contract import (
        ENGINEERING_QUESTION_SCHEMA_PATH,
        SCHEMA_VERSION,
        load_schema,
        validate_row,
    )

    schema = load_schema(ENGINEERING_QUESTION_SCHEMA_PATH)
    spec_by = {spec["family_id"]: spec for spec in specs}
    rows = []
    for assessment in assessments:
        fid = assessment["family_id"]
        spec = spec_by[fid]
        family = families[fid]
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


def build_pack_recommendations(
    assessments: list[dict],
    questions: list[dict],
    specs: list[dict],
    actions: dict,
    *,
    repo: str,
) -> list[dict]:
    from pipeline.control_evidence_contract import (
        RECOMMENDATION_SCHEMA_PATH,
        SCHEMA_VERSION,
        SKILLS_LOCKED,
        ControlError,
        load_schema,
        validate_row,
    )

    schema = load_schema(RECOMMENDATION_SCHEMA_PATH)
    spec_by = {spec["family_id"]: spec for spec in specs}
    q_by_family = {row["family_id"]: row for row in questions}
    rows = []
    n = 0
    for assessment in assessments:
        if assessment["state"] not in {"PARTIAL", "FAIL"}:
            continue
        if assessment["family_id"] not in actions:
            continue
        spec = spec_by[assessment["family_id"]]
        pack = actions[assessment["family_id"]]
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
            raise ControlError("integrated repo-analysis does not attach skill_id")
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    return rows


def classify_pack_evidence_class(
    family_id: str,
    state: str,
    observations: list[dict],
    *,
    specs: list[dict],
) -> str | None:
    """Use the pack's written playbook class when live strength matches."""
    hits = [row for row in observations if row["family_id"] == family_id]
    strengths = {row["strength"] for row in hits}
    for spec in specs:
        if spec["family_id"] != family_id or spec["assessment_state"] != state:
            continue
        if state == "FAIL" and "contradiction" in strengths:
            return spec["evidence_class"]
        if state == "PARTIAL" and "supporting" in strengths:
            return spec["evidence_class"]
    return None


def assessment_evidence(family_id: str, observations: list[dict], strengths: set[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in observations:
        if row["family_id"] != family_id or row["strength"] not in strengths:
            continue
        snippet = " ".join((row.get("snippet") or "").split())
        if len(snippet) < 8 or snippet in seen:
            continue
        seen.add(snippet)
        out.append(snippet[:160])
        if len(out) >= 5:
            break
    return out


def stamp_assessment(
    assessment: dict,
    *,
    pack: str,
    observations: list[dict],
) -> dict:
    """Copy a C3 row and add pack provenance. Does not mutate the C3 row."""
    strengths = {
        "SATISFIED": {"strong"},
        "PARTIAL": {"supporting", "strong"},
        "FAIL": {"contradiction"},
        "UNKNOWN": set(),
    }[assessment["state"]]
    return {
        **assessment,
        "pack": pack,
        "evidence": assessment_evidence(assessment["family_id"], observations, strengths),
    }


def c1_identity(row: dict) -> dict:
    """Fields that must match the frozen 12-family dest."""
    return {
        "family_id": row["family_id"],
        "expectation_id": row["expectation_id"],
        "state": row["state"],
        "basis": row["basis"],
        "observation_ids": list(row.get("observation_ids") or []),
    }


def finding_identity(row: dict) -> dict:
    return {
        "id": row["id"],
        "family_id": row["family_id"],
        "expectation_id": row["expectation_id"],
        "question_id": row["question_id"],
        "recommendation_id": row["recommendation_id"],
        "assessment_state": row["assessment_state"],
        "title": row["title"],
        "actions": list(row["actions"]),
        "playbook_id": row.get("playbook_id"),
        "playbook_available": row.get("playbook_available"),
        "evidence_class": row.get("evidence_class"),
        "repo": row["repo"],
    }
