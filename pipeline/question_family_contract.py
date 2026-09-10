"""Question-family schema and merge contract.

Construction, trait specialization, detectors, and repo analysis stay locked
except completed family waves. Canonical CPF, the 40-edge graph, and the 53
canonical families stay frozen after this promotion pass.

Contract: docs/question-families.md
Schema: engineering-intelligence/schemas/question_family.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "question_family.json"
CONTRACT_DOC = "docs/question-families.md"

SCHEMA_VERSION = "family-0.1"
# Wave-1–3 construction, review, and canonical family promotion are done.
# Trait ontology is this pass. Applicability mapping, specialization templates,
# and EngineeringQuestion generation stay locked.
WAVE1_CONSTRUCTION_LOCKED = False
FAMILY_EXPANSION_LOCKED = False
NOVEL_FAMILY_DISCOVERY_LOCKED = False
NOVEL_FAMILY_REVIEW_LOCKED = False
FURTHER_NOVEL_DISCOVERY_LOCKED = True
CANONICAL_FAMILY_PROMOTION_LOCKED = False
EXPANSION_REVIEW_LOCKED = False
FAMILY_REVIEW_LOCKED = False
CONSTRUCTION_LOCKED = FURTHER_NOVEL_DISCOVERY_LOCKED
SPECIALIZATION_LOCKED = True
EXPECTED_CANONICAL_FAMILIES = 53
WAVE1_MIN = 20
WAVE1_MAX = 30
WAVE2_NEW_MIN = 10
WAVE2_NEW_MAX = 40
WAVE3_MIN = 20
WAVE3_MAX = 30
REVIEW_DECISIONS = frozenset({"accept", "split", "merge_with", "reject"})
ATTACHMENT_DECISIONS = frozenset({"attach", "drop"})

ID_RE = re.compile(r"^QF-[0-9]{4}$")
CTRL_RE = re.compile(r"^CTRL-[0-9]{4}$")
FAIL_RE = re.compile(r"^FAIL-[0-9]{4}$")
PRIN_RE = re.compile(r"^PRIN-[0-9]{4}$")
REL_RE = re.compile(r"^REL-[0-9]{4}$")
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")

STANCES = frozenset({"exist", "measure", "verify"})
STATUSES = frozenset({"candidate", "canonical", "rejected"})
MVP_AREAS = frozenset({
    "llm_application_lifecycle",
    "agent_design_runtime",
    "evaluation",
    "ai_observability",
    "ai_security",
    "model_inference_deployment",
    "rag_data_grounding",
    "reliability_recovery",
    "cost_resource_management",
    "change_release_management",
})

# Related jobs that must not share a family solely because they co-occur.
# Same diagnostic_job is required to merge; these pairs are the split reminders.
ANTI_MERGE_JOBS = frozenset({
    frozenset({"bound_work", "retry_policy"}),
    frozenset({"bound_work", "retry_without_bound"}),
    frozenset({"bound_work", "circuit_break"}),
    frozenset({"bound_work", "slow_cutoff"}),
    frozenset({"bound_work", "resource_bound"}),
    frozenset({"retry_policy", "circuit_break"}),
    frozenset({"retry_policy", "degrade_path"}),
    frozenset({"degrade_path", "slow_cutoff"}),
    frozenset({"eval_gate", "telemetry_exist"}),
    frozenset({"eval_gate", "observability"}),
    frozenset({"permission_boundary", "authentication"}),
    frozenset({"encrypt_rest", "encrypt_transit"}),
    frozenset({"backup", "replication"}),
    frozenset({"quota_capacity", "resource_bound"}),
    frozenset({"rate_limit", "concurrency"}),
    frozenset({"failover", "retry_without_bound"}),
    frozenset({"grounding", "retrieval_quality"}),
    frozenset({"prompt_injection", "input_validation"}),
    frozenset({"prompt_injection", "agent_sec_assessment"}),
    frozenset({"input_validation", "output_sanitization"}),
    frozenset({"idempotent_replay", "state_ownership"}),
    frozenset({"unhealthy_detect", "telemetry_exist"}),
    frozenset({"retry_classification", "retry_backoff"}),
    frozenset({"retrieval_eval", "query_reformulation"}),
    frozenset({"retrieval_eval", "retrieval_poisoning"}),
    frozenset({"query_reformulation", "retrieval_poisoning"}),
    frozenset({"rollout_strategy", "rollback_capability"}),
    frozenset({"rollout_strategy", "change_tracking"}),
    frozenset({"rollback_capability", "change_tracking"}),
    frozenset({"credential_lifetime", "credential_rotation"}),
    frozenset({"credential_lifetime", "hardcoded_secrets"}),
    frozenset({"credential_rotation", "hardcoded_secrets"}),
    frozenset({"bound_work", "retry_classification"}),
    frozenset({"bound_work", "retry_backoff"}),
    frozenset({"eval_gate", "online_eval"}),
    frozenset({"online_eval", "unhealthy_detect"}),
    frozenset({"online_eval", "telemetry_exist"}),
    frozenset({"online_eval", "quality_drift"}),
    frozenset({"grounding", "grounding_eval"}),
    frozenset({"grounding_eval", "retrieval_eval"}),
    frozenset({"eval_gate", "eval_dataset"}),
    frozenset({"eval_dataset", "eval_leakage"}),
    frozenset({"quota_capacity", "quota_alarm"}),
    frozenset({"quota_capacity", "throttling"}),
    frozenset({"throttling", "bound_work"}),
    frozenset({"throttling", "retry_backoff"}),
    frozenset({"cost_metering", "cost_rightsize"}),
    frozenset({"cost_metering", "quota_capacity"}),
    frozenset({"sandbox_isolation", "permission_boundary"}),
    frozenset({"tool_catalog_scope", "tool_selection_eval"}),
    frozenset({"sensitive_egress", "hardcoded_secrets"}),
    frozenset({"session_binding", "authentication"}),
    frozenset({"red_team", "agent_sec_assessment"}),
    frozenset({"red_team", "prompt_injection"}),
    frozenset({"model_supply_chain", "dependency_integrity"}),
    frozenset({"inference_cache", "freshness"}),
    frozenset({"artifact_versioning", "change_tracking"}),
    frozenset({"incident_playbook", "unhealthy_detect"}),
    frozenset({"incident_playbook", "postmortem"}),
    frozenset({"log_integrity", "telemetry_exist"}),
    frozenset({"quality_drift", "unhealthy_detect"}),
    frozenset({"data_retention", "telemetry_exist"}),
    frozenset({"structured_output", "input_validation"}),
    frozenset({"deprecated_api", "permission_boundary"}),
    frozenset({"alert_hygiene", "unhealthy_detect"}),
})

REQUIRED = (
    "id",
    "schema_version",
    "status",
    "stem",
    "diagnostic_job",
    "question_stance",
    "supporting_control_ids",
    "supporting_failure_mode_ids",
    "supporting_principle_ids",
    "specialization_slots",
)


class FamilyError(RuntimeError):
    pass


def construction_locked_message() -> str:
    return (
        "A further novel-family wave stays locked. "
        "Uncited CPF is not a reason to expand. "
        f"Schema/contract: {CONTRACT_DOC}."
    )


def novel_review_locked_message() -> str:
    return (
        "Novel-family review stays locked. "
        "Decisions remain accept / split / merge_with / reject. "
        "Attachments are attach / drop. "
        "Split grandchildren stay unresolved. "
        f"Contract: {CONTRACT_DOC}."
    )


def promotion_locked_message() -> str:
    return (
        "Canonical family promotion stays locked. "
        f"Schema/contract: {CONTRACT_DOC}."
    )


def expansion_review_locked_message() -> str:
    return (
        "Expansion review stays locked. "
        "Decisions remain accept / split / merge_with / reject. "
        "Split children are not auto-accepted. "
        f"Contract: {CONTRACT_DOC}."
    )


def questions_locked_message() -> str:
    return (
        "EngineeringQuestion generation stays locked. "
        "Specialization templates stay locked. "
        f"Schema/contract: {CONTRACT_DOC}."
    )


def review_locked_message() -> str:
    return (
        "Question-family review stays locked. "
        "Decisions are accept / split / merge_with / reject. "
        f"Contract: {CONTRACT_DOC}."
    )


def assert_construction_locked() -> None:
    if FURTHER_NOVEL_DISCOVERY_LOCKED:
        raise FamilyError(construction_locked_message())


def assert_novel_review_locked() -> None:
    if NOVEL_FAMILY_REVIEW_LOCKED:
        raise FamilyError(novel_review_locked_message())


def assert_expansion_review_locked() -> None:
    if EXPANSION_REVIEW_LOCKED:
        raise FamilyError(expansion_review_locked_message())


def assert_promotion_locked() -> None:
    if CANONICAL_FAMILY_PROMOTION_LOCKED:
        raise FamilyError(promotion_locked_message())


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def supporting_ids(family: dict) -> list[str]:
    out: list[str] = []
    for key, pat in (
        ("supporting_control_ids", CTRL_RE),
        ("supporting_failure_mode_ids", FAIL_RE),
        ("supporting_principle_ids", PRIN_RE),
    ):
        for oid in family.get(key) or []:
            if not pat.match(oid):
                raise FamilyError(f"bad supporting id {oid} in {key}")
            out.append(oid)
    for oid in family.get("supporting_relationship_ids") or []:
        if not REL_RE.match(oid):
            raise FamilyError(f"bad supporting_relationship_id {oid}")
    return out


def validate_family(family: dict) -> dict:
    """Admit a family *record*. Does not construct families."""
    missing = [k for k in REQUIRED if k not in family]
    if missing:
        raise FamilyError(f"missing fields: {missing}")
    if family.get("schema_version") != SCHEMA_VERSION:
        raise FamilyError(f"schema_version must be {SCHEMA_VERSION}")
    if not ID_RE.match(family.get("id") or ""):
        raise FamilyError("id must match QF-0000")
    if family.get("status") not in STATUSES:
        raise FamilyError("status must be candidate, canonical, or rejected")
    stem = (family.get("stem") or "").strip()
    if len(stem) < 12 or "?" not in stem:
        raise FamilyError("stem must be an interrogative sentence")
    job = family.get("diagnostic_job") or ""
    if not SLUG_RE.match(job):
        raise FamilyError("diagnostic_job must be a lowercase slug")
    if family.get("question_stance") not in STANCES:
        raise FamilyError("question_stance must be exist, measure, or verify")
    for area in family.get("mvp_areas") or []:
        if area not in MVP_AREAS:
            raise FamilyError(f"unknown mvp_area {area}")
    ids = supporting_ids(family)
    if not ids:
        raise FamilyError("at least one supporting CPF id is required")
    for slot in family.get("specialization_slots") or []:
        if not SLUG_RE.match(slot):
            raise FamilyError(f"bad specialization_slot {slot}")
    for other in family.get("does_not_merge_with") or []:
        if not SLUG_RE.match(other):
            raise FamilyError(f"bad does_not_merge_with {other}")
        if other == job:
            raise FamilyError("does_not_merge_with cannot include own diagnostic_job")
    extra = set(family) - set(REQUIRED) - {
        "mvp_areas",
        "supporting_relationship_ids",
        "does_not_merge_with",
        "applies_when",
        "human_required",
        "notes",
        "wave",
        "split_from",
        "supporting_cpf_ids",
        "promotion",
    }
    if family.get("wave") not in (None, "wave1", "wave2", "wave3"):
        raise FamilyError("wave must be wave1, wave2, or wave3")
    split_from = family.get("split_from")
    if split_from is not None and not ID_RE.match(split_from):
        raise FamilyError("split_from must match QF-0000")
    if "supporting_cpf_ids" in family and list(family["supporting_cpf_ids"]) != ids:
        raise FamilyError(f"{family.get('id')}: supporting_cpf_ids must match typed supporting lists")
    promo = family.get("promotion")
    if promo is not None:
        if not isinstance(promo, dict):
            raise FamilyError("promotion must be an object")
        if promo.get("reviewed") is not True:
            raise FamilyError("promotion.reviewed must be true")
        if promo.get("source_wave") not in ("wave1", "wave2", "wave3"):
            raise FamilyError("promotion.source_wave must be wave1, wave2, or wave3")
    if family.get("status") == "canonical" and promo is None:
        raise FamilyError("canonical families require promotion provenance")
    if extra:
        raise FamilyError(f"unknown fields: {sorted(extra)}")
    return family


def jobs_anti_merged(job_a: str, job_b: str) -> bool:
    if job_a == job_b:
        return False
    return frozenset({job_a, job_b}) in ANTI_MERGE_JOBS


def merge_veto(left: dict, right: dict) -> str | None:
    """Why two family candidates must stay split. None means merge is *allowed*, not required.

    Default construction bias is still split when grouping objects. This only
    admits merging two already-proposed families.
    """
    validate_family(left)
    validate_family(right)
    if left["diagnostic_job"] != right["diagnostic_job"]:
        if jobs_anti_merged(left["diagnostic_job"], right["diagnostic_job"]):
            return "anti_merge"
        return "job_mismatch"
    if left["question_stance"] != right["question_stance"]:
        return "stance_mismatch"
    banned = set(left.get("does_not_merge_with") or []) | set(right.get("does_not_merge_with") or [])
    if left["diagnostic_job"] in banned:
        return "does_not_merge_with"
    if left["stem"].strip() != right["stem"].strip():
        # Same job+stance with different stems is a wording conflict for review, not auto-merge.
        return "stem_mismatch"
    return None


def one_to_one_forbidden(n_objects: int, n_families: int) -> bool:
    """Construction must shrink the 537, not emit one family per object."""
    if n_objects <= 0 or n_families <= 0:
        return True
    return n_families >= n_objects


def slot_is_specialization(family: dict, slot: str) -> bool:
    validate_family(family)
    return slot in (family.get("specialization_slots") or [])
