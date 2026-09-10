"""System-trait ontology and applicability contract.

Traits decide whether a family is in scope. Slots decide how to ask.
The canonical family decides what engineering judgment is tested.

Specialization-template construction, 12-family review, remaining-41
expansion, and expansion freeze are done. B2 detector catalog is frozen.
The first repo observation run, execution review, runner fix, and
reviewed-observation freeze are written. The B3 aggregation contract
and HackerRankATS map are written. B4 design, development labels,
development B2+B3 runs, development comparison, the one
development remediation pass, and the remediation freeze are
written. The sealed held-out evaluation is written. The final
B4 evaluation is written. The B4 benchmark baseline is frozen. Repo inspection substrate v1
and B4-v2 are written and frozen. Formal aggregation review stays locked.
Control evidence C1–C4, C1-pack questions, and recommendations are written.
Do not overwrite B4 dests. Do not fork the 84 detectors by language.
Do not chase the remaining 56 FNs.

Contract: docs/system-traits.md
Repo trait inference: docs/repo-trait-inference.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAIT_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "system_trait.json"
SLOT_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "specialization_slot.json"
APPLICABILITY_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "family_applicability.json"
APPLICABILITY_REVIEW_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "family_applicability_review.json"
SPECIALIZATION_TEMPLATE_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "family_specialization_template.json"
SPECIALIZATION_REVIEW_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "family_specialization_review.json"
SPECIALIZATION_EXPANSION_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "family_specialization_expansion.json"
SPECIALIZATION_EXPANSION_REVIEW_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "family_specialization_expansion_review.json"
TRAIT_EVIDENCE_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_evidence.json"
TRAIT_DETECTOR_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_detector.json"
TRAIT_DETECTOR_OBSERVATION_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_detector_observation.json"
TRAIT_DETECTOR_OBSERVATION_REVIEW_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_detector_observation_review.json"
TRAIT_DETECTOR_OBSERVATION_REVIEWED_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_detector_observation_reviewed.json"
TRAIT_AGGREGATION_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_aggregation.json"
TRAIT_CONCLUSION_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_conclusion.json"
TRAIT_BENCHMARK_REPO_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_repo.json"
TRAIT_BENCHMARK_REFERENCE_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_reference.json"
TRAIT_BENCHMARK_METRIC_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_metric.json"
TRAIT_BENCHMARK_OBSERVATION_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_observation.json"
TRAIT_BENCHMARK_CONCLUSION_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_conclusion.json"
TRAIT_BENCHMARK_COMPARISON_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_comparison.json"
TRAIT_BENCHMARK_FAMILY_ACTIVATION_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_family_activation.json"
TRAIT_BENCHMARK_ERROR_ANALYSIS_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_error_analysis.json"
TRAIT_BENCHMARK_FIX_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_benchmark_fix.json"
TRAIT_DETECTOR_REVIEW_SCHEMA_PATH = ROOT / "engineering-intelligence" / "schemas" / "trait_detector_review.json"
CONTRACT_DOC = "docs/system-traits.md"
REPO_TRAIT_DOC = "docs/repo-trait-inference.md"

SCHEMA_VERSION = "trait-0.1"
TRAIT_ONTOLOGY_LOCKED = False
FAMILY_APPLICABILITY_LOCKED = False
APPLICABILITY_REVIEW_LOCKED = False
APPLICABILITY_FREEZE_LOCKED = False
SPECIALIZATION_TEMPLATE_LOCKED = False
SPECIALIZATION_REVIEW_LOCKED = False
SPECIALIZATION_CONTRACT_FREEZE_LOCKED = False
SPECIALIZATION_EXPANSION_LOCKED = False
SPECIALIZATION_EXPANSION_REVIEW_LOCKED = False
SPECIALIZATION_EXPANSION_FREEZE_LOCKED = False
TRAIT_EVIDENCE_LOCKED = False
TRAIT_DETECTORS_LOCKED = False
TRAIT_DETECTOR_REVIEW_LOCKED = False
TRAIT_DETECTOR_EXPANSION_LOCKED = False
TRAIT_DETECTOR_EXPANSION_REVIEW_LOCKED = False
TRAIT_DETECTOR_CATALOG_FREEZE_LOCKED = False
TRAIT_DETECTOR_RUN_LOCKED = False
TRAIT_DETECTOR_OBSERVATION_REVIEW_LOCKED = False
TRAIT_DETECTOR_RUNNER_FIX_LOCKED = False
TRAIT_DETECTOR_REVIEWED_OBSERVATIONS_LOCKED = False
TRAIT_AGGREGATION_CONTRACT_LOCKED = False
TRAIT_AGGREGATION_LOCKED = False
TRAIT_AGGREGATION_REVIEW_LOCKED = True
TRAIT_BENCHMARK_DESIGN_LOCKED = False
TRAIT_BENCHMARK_REFERENCE_LOCKED = True
TRAIT_BENCHMARK_HELD_OUT_REFERENCE_LOCKED = True
TRAIT_BENCHMARK_LOCKED = True
TRAIT_BENCHMARK_COMPARISON_LOCKED = True
TRAIT_BENCHMARK_ERROR_ANALYSIS_LOCKED = True
TRAIT_BENCHMARK_REMEDIATION_FREEZE_LOCKED = True
TRAIT_BENCHMARK_HELD_OUT_EVALUATION_LOCKED = True
TRAIT_BENCHMARK_FINAL_EVALUATION_LOCKED = True
TRAIT_BENCHMARK_BASELINE_FREEZE_LOCKED = True
TRAIT_BENCHMARK_V2_LOCKED = True
FROZEN_V2_TP_PRESENT = 53
FROZEN_V2_FP_PRESENT = 0
FROZEN_V2_FN = 56
FROZEN_V2_PRESENT_PRECISION = 1.0
FROZEN_V2_PRESENT_RECALL = 53 / 109
FROZEN_B4_RESULT = {
    "precision_safety": "PASS",
    "family_activation_safety": "PASS",
    "static_trait_recall": "INSUFFICIENT",
    "cross_language_repository_support": "INSUFFICIENT",
    "architecture_validated": True,
    "repo_analysis_readiness": "NOT_YET",
}
FROZEN_B4_WALKER_GAPS = (".go", ".java", ".cc", ".cpp", ".c", ".h", ".hpp")
EXPECTED_DEV_ERRORS = 113
FROZEN_HELD_OUT_TP_PRESENT = 7
FROZEN_HELD_OUT_FP_PRESENT = 0
FROZEN_HELD_OUT_FN = 102
FROZEN_HELD_OUT_TN_ABSTAIN = 111
FROZEN_HELD_OUT_OUT_OF_SCOPE = 32
FROZEN_HELD_OUT_PRESENT_PRECISION = 1.0
FROZEN_HELD_OUT_PRESENT_RECALL = 7 / 109
FROZEN_HELD_OUT_WEIGHTED_ERROR = 102
FROZEN_HELD_OUT_FAMILY_ACTIVATION_FP = 0
FROZEN_HELD_OUT_LABELS = {
    "present": 109,
    "not_present": 111,
    "unresolved": 32,
}
FROZEN_HELD_OUT_SYSTEM = {
    "present": 7,
    "likely": 0,
    "unknown": 245,
    "observations": 35,
}
FROZEN_HELD_OUT_TRUE_PRESENTS = (
    ("envoy", "third_party_code", "direct"),
    ("argo_cd", "third_party_code", "direct"),
    ("langchain", "third_party_code", "direct"),
    ("langchain", "llm", "implied"),
    ("langchain", "retrieval_system", "implied"),
    ("langchain", "rag", "direct"),
    ("backstage", "third_party_code", "direct"),
)
FROZEN_HELD_OUT_ZERO_TP_REPOS = ("kafka", "torchserve")
FROZEN_REMEDIATION_CAUSES = {
    "DETECTOR_MISS": 75,
    "EXPECTED_STATIC_LIMITATION": 35,
    "RUNNER_MISS": 2,
    "ONTOLOGY_IMPLICATION": 1,
    "AGGREGATION_MISS": 0,
    "REFERENCE_LABEL_ISSUE": 0,
}
FROZEN_RUNNER_FIXES = 2
FROZEN_AFTER_TP_PRESENT = 27
FROZEN_AFTER_FP_PRESENT = 0
FROZEN_AFTER_FN = 111
FROZEN_AFTER_PRESENT_PRECISION = 1.0
FROZEN_AFTER_PRESENT_RECALL = 27 / 138
FROZEN_AFTER_WEIGHTED_ERROR = 111
FROZEN_REMAINING_DETECTOR_MISS = (("vllm", "llm"),)
ERROR_CAUSES = frozenset({
    "RUNNER_MISS",
    "AGGREGATION_MISS",
    "REFERENCE_LABEL_ISSUE",
    "ONTOLOGY_IMPLICATION",
    "DETECTOR_MISS",
    "EXPECTED_STATIC_LIMITATION",
})
REMEDIATION_ACTIONS = frozenset({"FIX", "DOCUMENT"})
DEV_REPO_LANGUAGES = {
    "hackerrankats": "python",
    "prometheus": "go",
    "otel_collector": "go",
    "vllm": "python",
    "langgraph": "python",
    "llama_index": "python",
    "meilisearch": "rust",
}
EXPECTED_DEV_REFERENCE_REPOS = 7
EXPECTED_DEV_REFERENCE_ROWS = 294
EXPECTED_DEV_BENCHMARK_CONCLUSIONS = 294
EXPECTED_DEV_COMPARISON_ROWS = 294
EXPECTED_HELD_OUT_REPOS = 6
EXPECTED_HELD_OUT_REFERENCE_ROWS = 252
FP_PRESENT_WEIGHT = 2
FP_LIKELY_WEIGHT = 1
FN_WEIGHT = 1
COMPARISON_CLASSES = frozenset({
    "TP_PRESENT",
    "UNDERCONFIDENT",
    "FN",
    "FP_PRESENT",
    "FP_LIKELY",
    "TN_ABSTAIN",
    "OUT_OF_SCOPE",
})
REFERENCE_LABELS = frozenset({"PRESENT", "NOT_PRESENT", "UNRESOLVED"})
INFERRED_TRAIT_STATES = frozenset({"PRESENT", "LIKELY", "UNKNOWN"})
DEV_REFERENCE_REPO_IDS = (
    "hackerrankats",
    "prometheus",
    "otel_collector",
    "vllm",
    "langgraph",
    "llama_index",
    "meilisearch",
)
HELD_OUT_REPO_IDS = (
    "envoy",
    "argo_cd",
    "kafka",
    "langchain",
    "torchserve",
    "backstage",
)
HACKERRANKATS_REPO = "HackerRankATS"
FIRST_OBSERVATION_REPO = ROOT / "pipeline" / "fixtures" / "first_observation_repo"
FORBIDDEN_TRAIT_STATES = ("PRESENT", "LIKELY", "ABSENT", "UNKNOWN")
TRAIT_MIN = 30
TRAIT_MAX = 50
EXPECTED_TRAITS = 42
EXPECTED_SLOTS = 10
EXPECTED_MAPPINGS = 53
EXPECTED_REVIEW_FAMILIES = 12
EXPECTED_REVIEW_CASES = 86
EXPECTED_IMPLICATION_CASES = 15
EXPECTED_HARD_NEGATIVES = 43
MAPPING_STATUS_CANDIDATE = "candidate"
MAPPING_STATUS_FROZEN = "frozen"
REVIEW_PATCHES = ("QF-0001", "QF-0003")
EXPECTED_SPECIALIZATION_FAMILIES = 12
SPECIALIZATION_FAMILY_IDS = (
    "QF-0001",
    "QF-0003",
    "QF-0006",
    "QF-0010",
    "QF-0012",
    "QF-0019",
    "QF-0023",
    "QF-0027",
    "QF-0038",
    "QF-0042",
    "QF-0055",
    "QF-0060",
)
MATCH_POLICY_UNRESOLVED = "unresolved"
MATCH_POLICIES = frozenset({
    "unresolved",
    "most_specific",
    "all_matching",
    "per_component",
})
EXTRA_REQUIREMENT_TOKS = frozenset({
    "timeout",
    "fallback",
    "canary",
    "blue-green",
    "kubernetes",
    "gpu",
    "ndcg",
    "sla",
    "threshold",
    "backoff",
    "escalate",
    "circuit",
    "iteration",
    "iterations",
})
SPECIALIZATION_REVIEW_DECISIONS = frozenset({"accept", "revise", "reject"})
SPECIALIZATION_GATES = (
    "SAME_JOB",
    "SAME_STANCE",
    "BINDING_SUPPORTED",
    "NO_EXTRA_REQUIREMENT",
)
EXPECTED_SPECIALIZATION_REVIEWS = 55
EXPECTED_SPECIALIZATION_ACCEPT = 50
EXPECTED_SPECIALIZATION_REVISE = 5
EXPECTED_SPECIALIZATION_REJECT = 0
EXPECTED_FROZEN_SPECIALIZATIONS = 53
EXPECTED_EXPANSION_FAMILIES = 41
EXPECTED_EXPANSION_CANDIDATES = 94
EXPECTED_EXPANSION_EMPTY = 6
EXPECTED_EXPANSION_REVIEW_FAMILIES = 26
EXPECTED_EXPANSION_REVIEWS = 69
EXPECTED_EXPANSION_REVIEW_ACCEPT = 63
EXPECTED_EXPANSION_REVIEW_REVISE = 6
EXPECTED_EXPANSION_REVIEW_REJECT = 0
EXPECTED_EXPANSION_FROZEN = 90
ABSENCE_POLICY_UNKNOWN = "unknown"
TRAIT_STATES = frozenset({"PRESENT", "LIKELY", "UNKNOWN", "ABSENT"})
EVIDENCE_SOURCES = frozenset({
    "code",
    "config",
    "dependencies",
    "architecture",
    "tests",
    "ci",
    "deployment",
    "ops",
})
HIGH_FP_TRAITS = frozenset({
    "llm",
    "rag",
    "agentic",
    "tool_using_agent",
    "retrieval_system",
    "uses_cache",
    "external_dependency",
    "serves_production",
    "internet_facing",
    "model_endpoint",
    "computer_use",
    "untrusted_context",
    "generative_output",
    "public_api",
    "stateful",
})
DETECTOR_FORBIDDEN_TOKS = (
    "**",
    "*.",
    "regex",
    "re.search",
    "glob(",
    "semgrep",
)
REPO_TRAIT_STAGES = ("B1", "B2", "B3", "B4")
REPO_TRAIT_OPEN_STAGE = "B4"
BENCHMARK_COVERAGE_ROLES = (
    "plain_backend",
    "llm_without_rag",
    "real_rag",
    "retrieval_without_generation",
    "agentic_without_tools",
    "tool_using_agent",
    "background_worker",
    "stateful",
    "multi_tenant",
    "model_serving",
    "human_facing",
    "deployment_heavy",
)
EXPECTED_BENCHMARK_REPOS = 13
EXPECTED_BENCHMARK_DEVELOPMENT = 7
EXPECTED_BENCHMARK_HELD_OUT = 6
EXPECTED_BENCHMARK_COVERAGE_ROLES = 12
EXPECTED_BENCHMARK_METRICS = 14
DETECTOR_TYPES = frozenset({
    "dependency",
    "import_usage",
    "api_usage",
    "config",
    "code_structure",
    "dataflow",
    "deployment_iac",
    "semantic",
})
EVIDENCE_STRENGTHS = frozenset({"strong", "weak"})
DETECTOR_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+\.v[1-9][0-9]*$")
COMPOSITIONAL_TRAITS = frozenset({"rag", "tool_using_agent"})
OVERCLAIM_DETECTOR_TYPES = frozenset({
    "dependency",
    "import_usage",
    "deployment_iac",
    "config",
})
FORBIDDEN_TRAIT_ALIASES = frozenset({"database", "cache", "kubernetes"})
REPRESENTATIVE_DETECTOR_TRAITS = (
    "backend_service",
    "internet_facing",
    "multi_tenant",
    "background_worker",
    "external_dependency",
    "persists_data",
    "uses_cache",
    "llm",
    "model_endpoint",
    "retrieval_system",
    "rag",
    "agentic",
    "tool_using_agent",
)
EXPECTED_DETECTOR_TRAITS = 13
EXPECTED_DETECTORS = 26
EXPECTED_DETECTOR_REVIEWS = 26
EXPECTED_EXPANDED_TRAITS = 42
EXPECTED_EXPANDED_DETECTORS = 84
EXPECTED_EXPANDED_STRONG_TRAITS = 41
EXPECTED_EXPANDED_WEAK_TRAITS = 42
EXPECTED_EXPANDED_BOTH_TRAITS = 41
EXPECTED_EXPANDED_NO_DETECTOR = 0
TRAITS_NO_STRONG_STATIC = frozenset({"serves_production"})
TRAITS_REQUIRING_SEMANTIC_LATER = frozenset({"serves_production"})
EXPECTED_DETECTOR_REVIEW_ACCEPT = 23
EXPECTED_DETECTOR_REVIEW_REVISE = 3
EXPECTED_DETECTOR_REVIEW_REJECT = 0
EXPECTED_EXPANDED_NEW_DETECTORS = 58
EXPECTED_EXPANDED_REVIEW_ACCEPT = 54
EXPECTED_EXPANDED_REVIEW_REVISE = 4
EXPECTED_EXPANDED_REVIEW_REJECT = 0
EXPECTED_EXPANDED_REVIEW_STRONG = 29
EXPECTED_EXPANDED_REVIEW_WEAK = 29
DETECTOR_GATES = (
    "OBSERVATION_REPRODUCIBLE",
    "SUPPORTS_EXACT",
    "STRENGTH_CALIBRATED",
    "NO_OVERCLAIM",
)
DETECTOR_REVIEW_DECISIONS = frozenset({"accept", "revise", "reject"})
DETECTOR_REVIEW_TAGS = (
    "dependency_package",
    "framework_import",
    "exposed_port",
    "iac_config",
    "model_sdk",
    "retrieval_library",
    "agent_framework",
    "dataflow_chain",
    "runtime_use",
    "presence_only",
)
DETECTOR_REVISE_IDS = (
    "internet_facing.public_listener.v1",
    "rag.retrieval_to_generation.v1",
    "tool_using_agent.model_selects_tool.v1",
)
EXPANDED_DETECTOR_REVISE_IDS = (
    "external_caller.inbound_trust.v1",
    "cloud_quota.throttling.v1",
    "generative_output.sdk_only.v1",
    "security_operations.sast_only.v1",
)
EXPECTED_FROZEN_DETECTORS = EXPECTED_EXPANDED_DETECTORS
EXPECTED_FROZEN_STRONG_TRAITS = EXPECTED_EXPANDED_STRONG_TRAITS
EXPECTED_FROZEN_DETECTOR_TRAITS = EXPECTED_EXPANDED_TRAITS
EXPECTED_FROZEN_REVISES = EXPECTED_EXPANDED_REVIEW_REVISE
EXPECTED_OBSERVATION_REVIEWS = 33
EXPECTED_OBSERVATION_REVIEW_VALID = 32
EXPECTED_OBSERVATION_REVIEW_MISSTATED = 1
EXPECTED_OBSERVATION_REVIEW_FALSE_HIT = 0
EXPECTED_OBSERVATION_REVIEW_BAD_SPAN = 0
EXPECTED_OBSERVATION_REVIEW_DUPLICATE = 0
OBSERVATION_REVIEW_GATES = (
    "MATCHES_OBSERVES",
    "SPAN_CONTAINS_EVIDENCE",
    "OBSERVATION_ACCURATE",
    "INDEPENDENT",
)
OBSERVATION_REVIEW_DECISIONS = frozenset({
    "VALID",
    "FALSE_HIT",
    "BAD_SPAN",
    "DUPLICATE",
    "MISSTATED_OBSERVATION",
})
OBSERVATION_DEFECT_CLASSES = frozenset({"none", "runner", "catalog_contract"})
OBSERVATION_RUNNER_REGRESSIONS = (
    "protocol_stub_not_llm_call",
    "env_example_indexed",
    "orchestrator_not_io_span",
    "requirements_not_lockfile",
)
EXPECTED_REVIEWED_OBSERVATIONS = 32
STRONG_DETECTOR_INVARIANT = (
    "A strong detector must demonstrate the capability itself, not merely "
    "a correlated structure, configuration, dependency, or security artifact."
)
STRONG_WIRING_DETECTOR_IDS = frozenset({
    "ci_pipeline.jobs_run.v1",
    "ships_behavior_change.release_path.v1",
    "third_party_code.lockfile_shipped.v1",
    "oncall_owned.paging_wired.v1",
    "security_operations.telemetry_or_ir.v1",
})
ALLOWED_RELATED_SUPPORTS = {
    "internet_facing.dockerfile_expose.v1": (),
    "third_party_code.package_manager_empty.v1": (),
    "rag.vector_dependency.v1": ("retrieval_system",),
    "tool_using_agent.langgraph_import.v1": ("agentic",),
    "generative_output.sdk_only.v1": ("llm",),
    "security_operations.sast_only.v1": (),
}
EXPANSION_REVIEW_TAGS = (
    "overlap",
    "broad_trait",
    "principal_surface",
    "artifact_deployment",
    "channel_surface",
    "generic_binding",
    "singleton",
)
EXPANSION_FOCUS_FAMILY_IDS = (
    "QF-0004",
    "QF-0005",
    "QF-0008",
    "QF-0011",
    "QF-0016",
    "QF-0018",
    "QF-0022",
    "QF-0028",
    "QF-0030",
    "QF-0032",
    "QF-0034",
    "QF-0036",
    "QF-0037",
    "QF-0039",
    "QF-0043",
    "QF-0044",
    "QF-0045",
    "QF-0049",
    "QF-0050",
    "QF-0051",
    "QF-0052",
    "QF-0053",
    "QF-0056",
    "QF-0058",
    "QF-0059",
    "QF-0062",
)
EXPANSION_EMPTY_FAMILY_IDS = (
    "QF-0017",
    "QF-0031",
    "QF-0041",
    "QF-0047",
    "QF-0057",
    "QF-0065",
)
EXPANSION_REVISE_IDS = (
    "QF-0004.s02",
    "QF-0005.s02",
    "QF-0005.s03",
    "QF-0011.s04",
    "QF-0016.s04",
    "QF-0044.s01",
)
EXPANSION_DROP_IDS = (
    "QF-0004.s02",
    "QF-0005.s02",
    "QF-0005.s03",
    "QF-0016.s04",
)
CANONICAL_STEM_FALLBACK = (
    "No specialization match means use the canonical stem, not NOT_APPLICABLE."
)
SPECIALIZATION_REVISE_IDS = (
    "QF-0010.s04",
    "QF-0012.s05",
    "QF-0027.s03",
    "QF-0038.s05",
    "QF-0042.s03",
)
SPECIALIZATION_DROP_IDS = ("QF-0027.s03", "QF-0042.s03")
SPECIALIZATION_CONTRACT_INVARIANT = (
    "Multiple valid specializations may match simultaneously. "
    "Template validity is independent of runtime selection policy."
)
APPLY = "APPLY"
NOT_APPLICABLE = "NOT_APPLICABLE"
CORRECT = "CORRECT"
FALSE_POSITIVE = "FALSE_POSITIVE"
FALSE_NEGATIVE = "FALSE_NEGATIVE"
OVER_CONSTRAINED = "OVER_CONSTRAINED"
UNDER_CONSTRAINED = "UNDER_CONSTRAINED"
ONTOLOGY_LIMITATION = "ONTOLOGY_LIMITATION"
REVIEW_DECISIONS = frozenset({
    CORRECT,
    FALSE_POSITIVE,
    FALSE_NEGATIVE,
    OVER_CONSTRAINED,
    UNDER_CONSTRAINED,
    ONTOLOGY_LIMITATION,
})
SOLE_BROAD_REQUIRED = frozenset({"backend_service", "serves_production"})
REVIEWED_FAMILY_IDS = (
    "QF-0001",
    "QF-0003",
    "QF-0005",
    "QF-0006",
    "QF-0010",
    "QF-0012",
    "QF-0018",
    "QF-0023",
    "QF-0027",
    "QF-0038",
    "QF-0042",
    "QF-0060",
)

TRAIT_ID_RE = re.compile(r"^TRAIT-[0-9]{4}$")
SLOT_ID_RE = re.compile(r"^SLOT-[0-9]{4}$")
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
KINDS = frozenset({
    "shape",
    "principal",
    "dependency",
    "capability",
    "control_plane",
    "operations",
})
GENRE_TOKS = frozenset({"agentic", "rag", "multi_tenant", "production", "agent"})


class TraitError(RuntimeError):
    pass


def ontology_locked_message() -> str:
    return (
        "System-trait ontology stays locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def applicability_locked_message() -> str:
    return (
        "Family applicability mapping stays locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def applicability_review_locked_message() -> str:
    return (
        "The 12-family applicability review stays locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def applicability_freeze_locked_message() -> str:
    return (
        "Applicability freeze stays locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def specialization_template_locked_message() -> str:
    return (
        "Specialization templates stay locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def specialization_review_locked_message() -> str:
    return (
        "The 12-family specialization review stays locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def specialization_contract_freeze_locked_message() -> str:
    return (
        "Specialization contract freeze stays locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def specialization_expansion_locked_message() -> str:
    return (
        "Expansion to the remaining 41 families stays locked. "
        f"Contract: {CONTRACT_DOC}."
    )


def specialization_expansion_review_locked_message() -> str:
    return (
        "Expanded-template edge-case review stays locked. "
        "Construction of the remaining 41 is candidate-only. "
        "Do not auto-trust generated bindings. Do not resolve match_policy. "
        f"Contract: {CONTRACT_DOC}."
    )


def specialization_expansion_freeze_locked_message() -> str:
    return (
        "Specialization expansion freeze stays locked. "
        "Review edge cases before freezing the remaining 41. "
        f"Contract: {CONTRACT_DOC}."
    )


def trait_evidence_locked_message() -> str:
    return (
        "The trait evidence contract stays locked. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detectors_locked_message() -> str:
    return (
        "Trait detector catalog stays locked. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_review_locked_message() -> str:
    return (
        "Trait detector review stays locked. "
        "The representative catalog is candidate-only. Do not auto-trust detectors. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_expansion_locked_message() -> str:
    return (
        "Expansion of detectors to all 42 traits stays locked. "
        "Validate the representative set first. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_expansion_review_locked_message() -> str:
    return (
        "Expanded-catalog review stays locked. "
        "Review the risky new rows before any repo scan. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_catalog_freeze_locked_message() -> str:
    return (
        "B2 detector catalog freeze stays locked. "
        "Apply expanded-catalog revises before freezing. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_run_locked_message() -> str:
    return (
        "The first repo observation run stays locked. "
        "B2 detector catalog is frozen. The next openable step is a raw "
        "observation run against one repository, without PRESENT/LIKELY/"
        "ABSENT/UNKNOWN. Do not inspect repos this pass. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_observation_review_locked_message() -> str:
    return (
        "Observation execution review stays locked. "
        "Review detector implementation quality before opening B3. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_runner_fix_locked_message() -> str:
    return (
        "Runner regression/fix stays locked. "
        "Observation execution review identified one unresolved runner "
        "defect (lockfile detector on requirements.txt). Do not freeze "
        "reviewed observations or open B3 this pass. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_detector_reviewed_observations_locked_message() -> str:
    return (
        "Reviewed observation freeze stays locked. "
        "Fix the unresolved runner defect and pass the regression cases "
        "before replacing the HackerRankATS observation dest. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_aggregation_contract_locked_message() -> str:
    return (
        "The B3 aggregation contract stays locked. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_aggregation_locked_message() -> str:
    return (
        "The HackerRankATS trait map stays locked. "
        "Write the aggregation contract first. Do not emit "
        "PRESENT/LIKELY/UNKNOWN from the map until that contract is written. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_aggregation_review_locked_message() -> str:
    return (
        "The B3 aggregation review stay locked. "
        "Formal review is deferred; it is not a B4 design gate. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_design_locked_message() -> str:
    return (
        "The B4 benchmark design stays locked. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_reference_locked_message() -> str:
    return (
        "Development B4 human reference labels are frozen. "
        "Do not overwrite the 294 development rows. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_held_out_reference_locked_message() -> str:
    return (
        "Held-out B4 evaluation stays locked. "
        "Label, run, and compare the six held-out repos in one phase. "
        "Do not fix or retune before scoring, including runner defects. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_held_out_evaluation_locked_message() -> str:
    return trait_benchmark_held_out_reference_locked_message()


def trait_benchmark_final_evaluation_locked_message() -> str:
    return (
        "Final B4 evaluation is written. "
        "It summarizes the sealed benchmark; it does not retune the "
        "system. Do not overwrite the evaluation dest. Do not freeze a "
        "composite pass/fail score. Do not fix B4. Baseline freeze "
        f"stays locked. Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_v2_locked_message() -> str:
    return (
        "B4-v2 is written. Original B4 stays immutable. "
        "Do not overwrite the v2 pack or retune the catalog. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_baseline_freeze_locked_message() -> str:
    return (
        "The B4 benchmark baseline is frozen. "
        "Do not overwrite the baseline freeze dest, held-out pack, "
        "final evaluation dest, or development dests. Do not fix B4. "
        "Original B4 stays immutable. B4-v2 is later. Next engineering "
        f"work is the repo inspection substrate. Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_remediation_freeze_locked_message() -> str:
    return (
        "Development remediation freeze is frozen. "
        "Development B4 is locked. Do not overwrite the freeze dest or "
        "the remediation pack. Do not recursively remediate "
        "comparison-after. Held-out evaluation stays locked. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_locked_message() -> str:
    return (
        "Development B2+B3 runs are frozen. "
        "Do not overwrite the development observation or conclusion dests. "
        "Do not add detectors or change aggregation thresholds. "
        "Comparison stays locked. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_comparison_locked_message() -> str:
    return (
        "Development B4 comparison is frozen. "
        "Do not overwrite the comparison dest. "
        "Do not retune detectors or change aggregation thresholds. "
        "Do not overwrite or recursively remediate the remediation pack. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def trait_benchmark_error_analysis_locked_message() -> str:
    return (
        "Development remediation is frozen. "
        "Do not overwrite the remediation pack or recursively remediate "
        "comparison-after. Held-out labels stay locked. "
        f"Contract: {REPO_TRAIT_DOC}."
    )


def assert_ontology_locked() -> None:
    if TRAIT_ONTOLOGY_LOCKED:
        raise TraitError(ontology_locked_message())


def assert_applicability_locked() -> None:
    if FAMILY_APPLICABILITY_LOCKED:
        raise TraitError(applicability_locked_message())


def assert_applicability_review_locked() -> None:
    if APPLICABILITY_REVIEW_LOCKED:
        raise TraitError(applicability_review_locked_message())


def assert_specialization_template_locked() -> None:
    if SPECIALIZATION_TEMPLATE_LOCKED:
        raise TraitError(specialization_template_locked_message())


def assert_specialization_review_locked() -> None:
    if SPECIALIZATION_REVIEW_LOCKED:
        raise TraitError(specialization_review_locked_message())


def assert_specialization_contract_freeze_locked() -> None:
    if SPECIALIZATION_CONTRACT_FREEZE_LOCKED:
        raise TraitError(specialization_contract_freeze_locked_message())


def assert_specialization_expansion_locked() -> None:
    if SPECIALIZATION_EXPANSION_LOCKED:
        raise TraitError(specialization_expansion_locked_message())


def assert_specialization_expansion_review_locked() -> None:
    if SPECIALIZATION_EXPANSION_REVIEW_LOCKED:
        raise TraitError(specialization_expansion_review_locked_message())


def assert_specialization_expansion_freeze_locked() -> None:
    if SPECIALIZATION_EXPANSION_FREEZE_LOCKED:
        raise TraitError(specialization_expansion_freeze_locked_message())


def assert_applicability_freeze_locked() -> None:
    if APPLICABILITY_FREEZE_LOCKED:
        raise TraitError(applicability_freeze_locked_message())


def assert_trait_evidence_locked() -> None:
    if TRAIT_EVIDENCE_LOCKED:
        raise TraitError(trait_evidence_locked_message())


def assert_trait_detectors_locked() -> None:
    if TRAIT_DETECTORS_LOCKED:
        raise TraitError(trait_detectors_locked_message())


def assert_trait_detector_review_locked() -> None:
    if TRAIT_DETECTOR_REVIEW_LOCKED:
        raise TraitError(trait_detector_review_locked_message())


def assert_trait_detector_expansion_locked() -> None:
    if TRAIT_DETECTOR_EXPANSION_LOCKED:
        raise TraitError(trait_detector_expansion_locked_message())


def assert_trait_detector_expansion_review_locked() -> None:
    if TRAIT_DETECTOR_EXPANSION_REVIEW_LOCKED:
        raise TraitError(trait_detector_expansion_review_locked_message())


def assert_trait_detector_catalog_freeze_locked() -> None:
    if TRAIT_DETECTOR_CATALOG_FREEZE_LOCKED:
        raise TraitError(trait_detector_catalog_freeze_locked_message())


def assert_trait_detector_run_locked() -> None:
    if TRAIT_DETECTOR_RUN_LOCKED:
        raise TraitError(trait_detector_run_locked_message())


def assert_trait_detector_observation_review_locked() -> None:
    if TRAIT_DETECTOR_OBSERVATION_REVIEW_LOCKED:
        raise TraitError(trait_detector_observation_review_locked_message())


def assert_trait_detector_runner_fix_locked() -> None:
    if TRAIT_DETECTOR_RUNNER_FIX_LOCKED:
        raise TraitError(trait_detector_runner_fix_locked_message())


def assert_trait_aggregation_contract_locked() -> None:
    if TRAIT_AGGREGATION_CONTRACT_LOCKED:
        raise TraitError(trait_aggregation_contract_locked_message())


def assert_trait_detector_reviewed_observations_locked() -> None:
    if TRAIT_DETECTOR_REVIEWED_OBSERVATIONS_LOCKED:
        raise TraitError(trait_detector_reviewed_observations_locked_message())


def assert_trait_aggregation_locked() -> None:
    if TRAIT_AGGREGATION_LOCKED:
        raise TraitError(trait_aggregation_locked_message())


def assert_trait_aggregation_review_locked() -> None:
    if TRAIT_AGGREGATION_REVIEW_LOCKED:
        raise TraitError(trait_aggregation_review_locked_message())


def assert_trait_benchmark_design_locked() -> None:
    if TRAIT_BENCHMARK_DESIGN_LOCKED:
        raise TraitError(trait_benchmark_design_locked_message())


def assert_trait_benchmark_reference_locked() -> None:
    if TRAIT_BENCHMARK_REFERENCE_LOCKED:
        raise TraitError(trait_benchmark_reference_locked_message())


def assert_trait_benchmark_held_out_reference_locked() -> None:
    if TRAIT_BENCHMARK_HELD_OUT_REFERENCE_LOCKED:
        raise TraitError(trait_benchmark_held_out_reference_locked_message())


def assert_trait_benchmark_locked() -> None:
    if TRAIT_BENCHMARK_LOCKED:
        raise TraitError(trait_benchmark_locked_message())


def assert_trait_benchmark_comparison_locked() -> None:
    if TRAIT_BENCHMARK_COMPARISON_LOCKED:
        raise TraitError(trait_benchmark_comparison_locked_message())


def assert_trait_benchmark_error_analysis_locked() -> None:
    if TRAIT_BENCHMARK_ERROR_ANALYSIS_LOCKED:
        raise TraitError(trait_benchmark_error_analysis_locked_message())


def assert_trait_benchmark_remediation_freeze_locked() -> None:
    if TRAIT_BENCHMARK_REMEDIATION_FREEZE_LOCKED:
        raise TraitError(trait_benchmark_remediation_freeze_locked_message())


def assert_trait_benchmark_held_out_evaluation_locked() -> None:
    if TRAIT_BENCHMARK_HELD_OUT_EVALUATION_LOCKED:
        raise TraitError(trait_benchmark_held_out_evaluation_locked_message())


def assert_trait_benchmark_final_evaluation_locked() -> None:
    if TRAIT_BENCHMARK_FINAL_EVALUATION_LOCKED:
        raise TraitError(trait_benchmark_final_evaluation_locked_message())


def assert_trait_benchmark_baseline_freeze_locked() -> None:
    if TRAIT_BENCHMARK_BASELINE_FREEZE_LOCKED:
        raise TraitError(trait_benchmark_baseline_freeze_locked_message())


def assert_trait_benchmark_v2_locked() -> None:
    if TRAIT_BENCHMARK_V2_LOCKED:
        raise TraitError(trait_benchmark_v2_locked_message())


def load_trait_schema() -> dict:
    return json.loads(TRAIT_SCHEMA_PATH.read_text())


def load_slot_schema() -> dict:
    return json.loads(SLOT_SCHEMA_PATH.read_text())


def load_applicability_schema() -> dict:
    return json.loads(APPLICABILITY_SCHEMA_PATH.read_text())


def load_applicability_review_schema() -> dict:
    return json.loads(APPLICABILITY_REVIEW_SCHEMA_PATH.read_text())


def load_specialization_template_schema() -> dict:
    return json.loads(SPECIALIZATION_TEMPLATE_SCHEMA_PATH.read_text())


def load_specialization_review_schema() -> dict:
    return json.loads(SPECIALIZATION_REVIEW_SCHEMA_PATH.read_text())


def load_specialization_expansion_schema() -> dict:
    return json.loads(SPECIALIZATION_EXPANSION_SCHEMA_PATH.read_text())


def load_specialization_expansion_review_schema() -> dict:
    return json.loads(SPECIALIZATION_EXPANSION_REVIEW_SCHEMA_PATH.read_text())


def load_trait_evidence_schema() -> dict:
    return json.loads(TRAIT_EVIDENCE_SCHEMA_PATH.read_text())


def load_trait_detector_schema() -> dict:
    return json.loads(TRAIT_DETECTOR_SCHEMA_PATH.read_text())


def load_trait_detector_observation_schema() -> dict:
    return json.loads(TRAIT_DETECTOR_OBSERVATION_SCHEMA_PATH.read_text())


def load_trait_detector_review_schema() -> dict:
    return json.loads(TRAIT_DETECTOR_REVIEW_SCHEMA_PATH.read_text())


def load_trait_detector_observation_review_schema() -> dict:
    return json.loads(TRAIT_DETECTOR_OBSERVATION_REVIEW_SCHEMA_PATH.read_text())


def load_trait_detector_observation_reviewed_schema() -> dict:
    return json.loads(TRAIT_DETECTOR_OBSERVATION_REVIEWED_SCHEMA_PATH.read_text())


def load_trait_aggregation_schema() -> dict:
    return json.loads(TRAIT_AGGREGATION_SCHEMA_PATH.read_text())


def load_trait_conclusion_schema() -> dict:
    return json.loads(TRAIT_CONCLUSION_SCHEMA_PATH.read_text())


def load_trait_benchmark_repo_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_REPO_SCHEMA_PATH.read_text())


def load_trait_benchmark_reference_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_REFERENCE_SCHEMA_PATH.read_text())


def load_trait_benchmark_metric_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_METRIC_SCHEMA_PATH.read_text())


def load_trait_benchmark_observation_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_OBSERVATION_SCHEMA_PATH.read_text())


def load_trait_benchmark_conclusion_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_CONCLUSION_SCHEMA_PATH.read_text())


def load_trait_benchmark_comparison_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_COMPARISON_SCHEMA_PATH.read_text())


def load_trait_benchmark_family_activation_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_FAMILY_ACTIVATION_SCHEMA_PATH.read_text())


def load_trait_benchmark_error_analysis_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_ERROR_ANALYSIS_SCHEMA_PATH.read_text())


def load_trait_benchmark_fix_schema() -> dict:
    return json.loads(TRAIT_BENCHMARK_FIX_SCHEMA_PATH.read_text())


def slug_is_compound_genre(slug: str) -> bool:
    """True for concatenated product types, not for a single atom."""
    if "_and_" in slug:
        return True
    hits = [tok for tok in GENRE_TOKS if tok != slug and tok in slug]
    return len(hits) >= 2


def validate_trait(trait: dict, *, known_slugs: set[str] | None = None) -> dict:
    missing = [
        k for k in ("id", "schema_version", "status", "slug", "kind", "stem", "implies", "conflicts")
        if k not in trait
    ]
    if missing:
        raise TraitError(f"missing trait fields: {missing}")
    if trait.get("schema_version") != SCHEMA_VERSION:
        raise TraitError(f"schema_version must be {SCHEMA_VERSION}")
    if not TRAIT_ID_RE.match(trait.get("id") or ""):
        raise TraitError("id must match TRAIT-0000")
    if trait.get("status") != "canonical":
        raise TraitError("trait status must be canonical")
    slug = trait.get("slug") or ""
    if not SLUG_RE.match(slug) or len(slug) < 3:
        raise TraitError(f"bad trait slug {slug}")
    if slug_is_compound_genre(slug):
        raise TraitError(f"trait slug concatenates a product genre: {slug}")
    if trait.get("kind") not in KINDS:
        raise TraitError(f"unknown trait kind {trait.get('kind')}")
    stem = (trait.get("stem") or "").strip()
    if len(stem) < 12 or "?" in stem:
        raise TraitError("trait stem must be a declarative sentence, not a question")
    extra = set(trait) - {
        "id", "schema_version", "status", "slug", "kind", "stem", "implies", "conflicts", "notes",
    }
    if extra:
        raise TraitError(f"unknown trait fields: {sorted(extra)}")
    for key in ("implies", "conflicts"):
        seen: set[str] = set()
        for other in trait.get(key) or []:
            if not SLUG_RE.match(other):
                raise TraitError(f"bad {key} slug {other}")
            if other == slug:
                raise TraitError(f"{slug} cannot {key} itself")
            if other in seen:
                raise TraitError(f"duplicate {key} slug {other}")
            seen.add(other)
            if known_slugs is not None and other not in known_slugs:
                raise TraitError(f"{key} references unknown slug {other}")
    return trait


def validate_slot(slot: dict) -> dict:
    missing = [k for k in ("id", "schema_version", "status", "slug", "role") if k not in slot]
    if missing:
        raise TraitError(f"missing slot fields: {missing}")
    if slot.get("schema_version") != SCHEMA_VERSION:
        raise TraitError(f"schema_version must be {SCHEMA_VERSION}")
    if not SLOT_ID_RE.match(slot.get("id") or ""):
        raise TraitError("id must match SLOT-0000")
    if slot.get("status") != "canonical":
        raise TraitError("slot status must be canonical")
    slug = slot.get("slug") or ""
    if not SLUG_RE.match(slug) or len(slug) < 3:
        raise TraitError(f"bad slot slug {slug}")
    role = (slot.get("role") or "").strip()
    if len(role) < 8:
        raise TraitError("slot role must describe the noun")
    extra = set(slot) - {"id", "schema_version", "status", "slug", "role", "notes"}
    if extra:
        raise TraitError(f"unknown slot fields: {sorted(extra)}")
    return slot


def expand_implies(present: set[str], implies: dict[str, list[str]]) -> set[str]:
    out = set(present)
    changed = True
    guard = 0
    while changed:
        guard += 1
        if guard > 64:
            raise TraitError("implies expansion did not terminate")
        changed = False
        for slug in list(out):
            for child in implies.get(slug) or []:
                if child not in out:
                    out.add(child)
                    changed = True
    return out


def _assert_implies_acyclic(implies: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    seen: set[str] = set()

    def walk(slug: str) -> None:
        if slug in seen:
            return
        if slug in visiting:
            raise TraitError(f"implies cycle at {slug}")
        visiting.add(slug)
        for child in implies.get(slug) or []:
            walk(child)
        visiting.remove(slug)
        seen.add(slug)

    for slug in implies:
        walk(slug)


def validate_catalog(traits: list[dict], slots: list[dict]) -> None:
    if not (TRAIT_MIN <= len(traits) <= TRAIT_MAX):
        raise TraitError(f"trait catalog must be {TRAIT_MIN}–{TRAIT_MAX}, got {len(traits)}")
    if len(slots) != EXPECTED_SLOTS:
        raise TraitError(f"expected {EXPECTED_SLOTS} slots, got {len(slots)}")
    slugs: set[str] = set()
    ids: set[str] = set()
    implies: dict[str, list[str]] = {}
    for trait in traits:
        slug = trait["slug"]
        if slug in slugs:
            raise TraitError(f"duplicate trait slug {slug}")
        if trait["id"] in ids:
            raise TraitError(f"duplicate trait id {trait['id']}")
        slugs.add(slug)
        ids.add(trait["id"])
        implies[slug] = list(trait.get("implies") or [])
    for trait in traits:
        validate_trait(trait, known_slugs=slugs)
    _assert_implies_acyclic(implies)
    slot_slugs: set[str] = set()
    slot_ids: set[str] = set()
    for slot in slots:
        validate_slot(slot)
        if slot["slug"] in slot_slugs:
            raise TraitError(f"duplicate slot slug {slot['slug']}")
        if slot["id"] in slot_ids:
            raise TraitError(f"duplicate slot id {slot['id']}")
        slot_slugs.add(slot["slug"])
        slot_ids.add(slot["id"])


def _match(condition: object, present: set[str], known: set[str]) -> bool:
    if isinstance(condition, str):
        if condition not in known:
            raise TraitError(f"unknown trait slug in condition: {condition}")
        return condition in present
    if not isinstance(condition, dict) or len(condition) != 1:
        raise TraitError("condition must be a slug or a single-key any/all/not object")
    key, value = next(iter(condition.items()))
    if key == "any":
        if not isinstance(value, list) or not value:
            raise TraitError("any requires a non-empty list")
        return any(_match(item, present, known) for item in value)
    if key == "all":
        if not isinstance(value, list) or not value:
            raise TraitError("all requires a non-empty list")
        return all(_match(item, present, known) for item in value)
    if key == "not":
        return not _match(value, present, known)
    raise TraitError(f"unknown condition key {key}")


def traits_match(
    condition: object,
    present: set[str],
    *,
    traits: list[dict],
) -> bool:
    """True if the family applies. False is NOT_APPLICABLE."""
    known = {row["slug"] for row in traits}
    implies = {row["slug"]: list(row.get("implies") or []) for row in traits}
    expanded = expand_implies(set(present), implies)
    unknown = expanded - known
    if unknown:
        raise TraitError(f"unknown present traits: {sorted(unknown)}")
    return _match(condition, expanded, known)


def iter_condition_slugs(condition: object):
    if isinstance(condition, str):
        yield condition
        return
    if not isinstance(condition, dict) or len(condition) != 1:
        raise TraitError("condition must be a slug or a single-key any/all/not object")
    key, value = next(iter(condition.items()))
    if key in ("any", "all"):
        if not isinstance(value, list) or not value:
            raise TraitError(f"{key} requires a non-empty list")
        for item in value:
            yield from iter_condition_slugs(item)
        return
    if key == "not":
        yield from iter_condition_slugs(value)
        return
    raise TraitError(f"unknown condition key {key}")


def validate_mapping(row: dict, *, known_slugs: set[str], family_ids: set[str] | None = None) -> dict:
    missing = [k for k in ("family_id", "schema_version", "status", "required", "optional", "not") if k not in row]
    if missing:
        raise TraitError(f"missing mapping fields: {missing}")
    if row.get("schema_version") != SCHEMA_VERSION:
        raise TraitError(f"schema_version must be {SCHEMA_VERSION}")
    fid = row.get("family_id") or ""
    if not re.compile(r"^QF-[0-9]{4}$").match(fid):
        raise TraitError("family_id must match QF-0000")
    if family_ids is not None and fid not in family_ids:
        raise TraitError(f"{fid} is not a canonical family")
    if row.get("status") not in ("candidate", "canonical", "frozen"):
        raise TraitError("mapping status must be candidate, canonical, or frozen")
    extra = set(row) - {
        "family_id", "schema_version", "status", "required", "optional", "not", "notes", "diagnostic_job",
    }
    if extra:
        raise TraitError(f"{fid}: unknown mapping fields {sorted(extra)}")
    required_slugs = list(iter_condition_slugs(row["required"]))
    if not required_slugs:
        raise TraitError(f"{fid}: required must cite at least one trait")
    unknown_required = [s for s in required_slugs if s not in known_slugs]
    if unknown_required:
        raise TraitError(f"{fid}: unknown required traits {unknown_required}")
    if set(required_slugs) <= SOLE_BROAD_REQUIRED:
        raise TraitError(f"{fid}: required is only a broad shape trait {sorted(set(required_slugs))}")
    seen_opt: set[str] = set()
    for slug in row.get("optional") or []:
        if slug not in known_slugs:
            raise TraitError(f"{fid}: unknown optional trait {slug}")
        if slug in seen_opt:
            raise TraitError(f"{fid}: duplicate optional trait {slug}")
        seen_opt.add(slug)
    seen_not: set[str] = set()
    for slug in row.get("not") or []:
        if slug not in known_slugs:
            raise TraitError(f"{fid}: unknown not trait {slug}")
        if slug in seen_not:
            raise TraitError(f"{fid}: duplicate not trait {slug}")
        seen_not.add(slug)
    return row


def family_applies(mapping: dict, present: set[str], *, traits: list[dict]) -> str:
    """APPLY or NOT_APPLICABLE. optional is ignored."""
    known = {row["slug"] for row in traits}
    validate_mapping(mapping, known_slugs=known)
    implies = {row["slug"]: list(row.get("implies") or []) for row in traits}
    expanded = expand_implies(set(present), implies)
    unknown = expanded - known
    if unknown:
        raise TraitError(f"unknown present traits: {sorted(unknown)}")
    for slug in mapping.get("not") or []:
        if slug in expanded:
            return NOT_APPLICABLE
    if not traits_match(mapping["required"], present, traits=traits):
        return NOT_APPLICABLE
    return APPLY
