"""Write the frozen system-trait ontology.

Family applicability mapping lives in system_trait_applicability.py.
Does not emit specialized stems. Does not mutate canonical families.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pipeline.common import CONSOLIDATION, dump_json, write_jsonl
from pipeline.question_family_contract import SPECIALIZATION_LOCKED
from pipeline.system_trait_contract import (
    EXPECTED_SLOTS,
    EXPECTED_TRAITS,
    FAMILY_APPLICABILITY_LOCKED,
    SCHEMA_VERSION,
    SPECIALIZATION_TEMPLATE_LOCKED,
    TRAIT_MAX,
    TRAIT_MIN,
    TRAIT_ONTOLOGY_LOCKED,
    TraitError,
    assert_ontology_locked,
    validate_catalog,
)

TRAIT_SPECS: list[dict] = [
    {"slug": "backend_service", "kind": "shape", "stem": "The system is a long-running networked service.", "implies": [], "notes": "Not a product genre. Compose with internet_facing, stateful, llm."},
    {"slug": "internet_facing", "kind": "shape", "stem": "The system accepts requests from untrusted networks.", "implies": [], "notes": "Does not imply backend_service; an on-device app can be internet-facing."},
    {"slug": "stateful", "kind": "shape", "stem": "The system retains sessions, stores, caches, or queues across requests.", "implies": []},
    {"slug": "multi_tenant", "kind": "shape", "stem": "One runtime is shared across tenants or customers.", "implies": []},
    {"slug": "background_worker", "kind": "shape", "stem": "Work runs as jobs or async workers rather than only request/response.", "implies": []},
    {"slug": "on_device", "kind": "shape", "stem": "Inference or logic runs on a client or device, not only a remote service.", "implies": []},
    {"slug": "ci_pipeline", "kind": "shape", "stem": "The system is built, tested, or shipped through CI/CD.", "implies": []},
    {"slug": "serves_production", "kind": "shape", "stem": "The system is operated as a production workload.", "implies": []},
    {"slug": "ships_behavior_change", "kind": "shape", "stem": "Prompts, models, config, or code are released as behavior changes.", "implies": []},
    {"slug": "human_user", "kind": "principal", "stem": "A human authenticates or acts in the system.", "implies": []},
    {"slug": "external_caller", "kind": "principal", "stem": "Untrusted or third-party callers invoke the system.", "implies": []},
    {"slug": "service_to_service", "kind": "principal", "stem": "Other workloads call this system with machine identity.", "implies": []},
    {"slug": "external_dependency", "kind": "dependency", "stem": "The system waits on a remote call, model, store, or peer.", "implies": []},
    {"slug": "persists_data", "kind": "dependency", "stem": "The system writes data that outlives a request.", "implies": []},
    {"slug": "uses_cache", "kind": "dependency", "stem": "The system serves or stores cached results that can go stale.", "implies": []},
    {"slug": "public_api", "kind": "dependency", "stem": "The system exposes a versioned API to callers outside the deploy.", "implies": []},
    {"slug": "third_party_code", "kind": "dependency", "stem": "The system ships third-party or generated dependencies.", "implies": []},
    {"slug": "llm", "kind": "capability", "stem": "The system invokes a language or multimodal model.", "implies": []},
    {"slug": "prompt_managed", "kind": "capability", "stem": "Prompts are shipped, versioned, or configured as artifacts.", "implies": ["llm"]},
    {"slug": "generative_output", "kind": "capability", "stem": "The system emits model-generated text or structured output.", "implies": ["llm"]},
    {"slug": "model_endpoint", "kind": "capability", "stem": "The system calls a hosted or local model endpoint.", "implies": ["llm"]},
    {"slug": "model_training", "kind": "capability", "stem": "The system trains, fine-tunes, or updates model weights.", "implies": []},
    {"slug": "model_artifact", "kind": "capability", "stem": "The system loads or ships model weights or bundled extras.", "implies": []},
    {"slug": "retrieval_system", "kind": "capability", "stem": "The system searches an index, corpus, or knowledge store.", "implies": []},
    {"slug": "rag", "kind": "capability", "stem": "Generation is grounded in retrieved documents or embeddings.", "implies": ["llm", "retrieval_system"], "notes": "Retrieval without generation is retrieval_system, not rag."},
    {"slug": "agent_memory", "kind": "capability", "stem": "The system persists agent or session memory for later turns.", "implies": ["stateful"]},
    {"slug": "agentic", "kind": "capability", "stem": "The system plans or iterates toward a goal across steps.", "implies": ["llm"]},
    {"slug": "tool_using_agent", "kind": "capability", "stem": "An agent selects and invokes tools.", "implies": ["agentic"]},
    {"slug": "computer_use", "kind": "capability", "stem": "An agent operates a computer or browser environment.", "implies": ["tool_using_agent"]},
    {"slug": "human_in_the_loop", "kind": "capability", "stem": "Some actions require a human to approve before they run.", "implies": []},
    {"slug": "eval_harness", "kind": "control_plane", "stem": "The system can score behavior with an evaluation pipeline.", "implies": []},
    {"slug": "eval_datasets", "kind": "control_plane", "stem": "Labeled examples exist for scoring behavior.", "implies": []},
    {"slug": "handles_secrets", "kind": "control_plane", "stem": "The system uses credentials, keys, or tokens.", "implies": []},
    {"slug": "retains_user_data", "kind": "control_plane", "stem": "The system stores user or monitoring data over time.", "implies": ["persists_data"]},
    {"slug": "produces_logs", "kind": "control_plane", "stem": "The system emits logs, traces, or metrics.", "implies": []},
    {"slug": "untrusted_input", "kind": "control_plane", "stem": "Callers or tools supply data that must be validated before use.", "implies": []},
    {"slug": "untrusted_context", "kind": "control_plane", "stem": "Retrieved, web, or tool content can enter model context.", "implies": ["llm"]},
    {"slug": "sessioned_auth", "kind": "control_plane", "stem": "Callers are bound to a session or principal across requests.", "implies": []},
    {"slug": "oncall_owned", "kind": "operations", "stem": "Humans are paged or playbooks exist for incidents.", "implies": ["serves_production"]},
    {"slug": "security_operations", "kind": "operations", "stem": "Security telemetry or response is in scope.", "implies": []},
    {"slug": "metered_cost", "kind": "operations", "stem": "Usage of tokens, inference, or agents is billed or budgeted.", "implies": []},
    {"slug": "cloud_quota", "kind": "operations", "stem": "Cloud or service quotas can throttle the workload.", "implies": []},
]

SLOT_SPECS: list[dict] = [
    {"slug": "operation", "role": "The work being bounded, retried, or cut off."},
    {"slug": "dependency", "role": "The remote system, model, store, or peer being called."},
    {"slug": "principal", "role": "Who or what is authenticated or authorized."},
    {"slug": "state", "role": "Retained data such as cache, session, memory, or store."},
    {"slug": "artifact", "role": "A shipped object: prompt, model, dataset, secret, or dependency."},
    {"slug": "resource", "role": "Capacity that can exhaust: memory, pool, quota, or tenant."},
    {"slug": "deployment", "role": "Where or how a change is released: service, region, or experiment."},
    {"slug": "evaluator", "role": "How behavior is scored: harness, dataset, judge, or red team."},
    {"slug": "channel", "role": "The path data takes: network, disk, log, or output."},
    {"slug": "surface", "role": "The interface: API, tool, browser, or public endpoint."},
]


def trait_paths(*, root: Path | None = None) -> dict[str, Path]:
    cons = root or CONSOLIDATION
    tdir = cons / "system_traits"
    return {
        "root": cons,
        "dir": tdir,
        "traits": tdir / "traits.jsonl",
        "slots": tdir / "slots.jsonl",
        "stats": tdir / "ontology_stats.json",
        "applicability": tdir / "applicability.jsonl",
        "applicability_stats": tdir / "applicability_stats.json",
        "applicability_review": tdir / "applicability_review.jsonl",
        "applicability_review_stats": tdir / "applicability_review_stats.json",
        "families": cons / "question_families" / "canonical" / "families.jsonl",
        "graph": cons / "canonical" / "question_families.jsonl",
        "specialization_templates": tdir / "specialization_templates.jsonl",
        "specialization_template_stats": tdir / "specialization_template_stats.json",
        "specialization_review": tdir / "specialization_review.jsonl",
        "specialization_review_stats": tdir / "specialization_review_stats.json",
        "specialization_expansion": tdir / "specialization_expansion.jsonl",
        "specialization_expansion_stats": tdir / "specialization_expansion_stats.json",
        "specialization_expansion_review": tdir / "specialization_expansion_review.jsonl",
        "specialization_expansion_review_stats": tdir / "specialization_expansion_review_stats.json",
        "trait_evidence": tdir / "trait_evidence.jsonl",
        "trait_evidence_stats": tdir / "trait_evidence_stats.json",
        "trait_detectors": tdir / "trait_detectors.jsonl",
        "trait_detector_stats": tdir / "trait_detector_stats.json",
        "trait_detector_review": tdir / "trait_detector_review.jsonl",
        "trait_detector_review_stats": tdir / "trait_detector_review_stats.json",
        "trait_detectors_expanded": tdir / "trait_detectors_expanded.jsonl",
        "trait_detector_expansion_stats": tdir / "trait_detector_expansion_stats.json",
        "trait_detector_expansion_review": tdir / "trait_detector_expansion_review.jsonl",
        "trait_detector_expansion_review_stats": tdir / "trait_detector_expansion_review_stats.json",
        "trait_detectors_frozen": tdir / "trait_detectors_frozen.jsonl",
        "trait_detector_freeze_stats": tdir / "trait_detector_freeze_stats.json",
        "trait_detector_observations": tdir / "trait_detector_observations.jsonl",
        "trait_detector_observation_stats": tdir / "trait_detector_observation_stats.json",
        "trait_detector_observation_review": tdir / "trait_detector_observation_review.jsonl",
        "trait_detector_observation_review_stats": tdir / "trait_detector_observation_review_stats.json",
        "trait_detector_runner_fix_stats": tdir / "trait_detector_runner_fix_stats.json",
        "trait_detector_observations_reviewed": tdir / "trait_detector_observations_reviewed.jsonl",
        "trait_detector_observations_reviewed_stats": tdir / "trait_detector_observations_reviewed_stats.json",
        "trait_aggregation": tdir / "trait_aggregation.jsonl",
        "trait_aggregation_stats": tdir / "trait_aggregation_stats.json",
        "trait_conclusions": tdir / "trait_conclusions.jsonl",
        "trait_conclusion_stats": tdir / "trait_conclusion_stats.json",
        "trait_benchmark": tdir / "trait_benchmark.jsonl",
        "trait_benchmark_metrics": tdir / "trait_benchmark_metrics.jsonl",
        "trait_benchmark_stats": tdir / "trait_benchmark_stats.json",
        "trait_benchmark_references": tdir / "trait_benchmark_references.jsonl",
        "trait_benchmark_reference_stats": tdir / "trait_benchmark_reference_stats.json",
        "trait_benchmark_observations": tdir / "trait_benchmark_observations.jsonl",
        "trait_benchmark_observation_stats": tdir / "trait_benchmark_observation_stats.json",
        "trait_benchmark_conclusions": tdir / "trait_benchmark_conclusions.jsonl",
        "trait_benchmark_conclusion_stats": tdir / "trait_benchmark_conclusion_stats.json",
        "trait_benchmark_comparison": tdir / "trait_benchmark_comparison.jsonl",
        "trait_benchmark_comparison_stats": tdir / "trait_benchmark_comparison_stats.json",
        "trait_benchmark_family_activation": tdir / "trait_benchmark_family_activation.jsonl",
        "trait_benchmark_remediation_dir": tdir / "development_remediation",
        "trait_benchmark_error_analysis": tdir / "development_remediation" / "error_analysis.jsonl",
        "trait_benchmark_fixes": tdir / "development_remediation" / "fixes.jsonl",
        "trait_benchmark_regression_results": tdir / "development_remediation" / "regression_results.json",
        "trait_benchmark_rerun_manifest": tdir / "development_remediation" / "rerun_manifest.json",
        "trait_benchmark_comparison_after": tdir / "development_remediation" / "comparison_after.jsonl",
        "trait_benchmark_comparison_after_stats": tdir / "development_remediation" / "comparison_after_stats.json",
        "trait_benchmark_remediation_stats": tdir / "development_remediation" / "remediation_stats.json",
        "trait_benchmark_remediation_freeze": tdir / "development_remediation" / "freeze.json",
        "trait_benchmark_held_out_dir": tdir / "held_out_evaluation",
        "trait_benchmark_held_out_references": tdir / "held_out_evaluation" / "references.jsonl",
        "trait_benchmark_held_out_reference_stats": tdir / "held_out_evaluation" / "reference_stats.json",
        "trait_benchmark_held_out_observations": tdir / "held_out_evaluation" / "observations.jsonl",
        "trait_benchmark_held_out_observation_stats": tdir / "held_out_evaluation" / "observation_stats.json",
        "trait_benchmark_held_out_conclusions": tdir / "held_out_evaluation" / "conclusions.jsonl",
        "trait_benchmark_held_out_conclusion_stats": tdir / "held_out_evaluation" / "conclusion_stats.json",
        "trait_benchmark_held_out_comparison": tdir / "held_out_evaluation" / "comparison.jsonl",
        "trait_benchmark_held_out_comparison_stats": tdir / "held_out_evaluation" / "comparison_stats.json",
        "trait_benchmark_held_out_family_activation": tdir / "held_out_evaluation" / "family_activation.jsonl",
        "trait_benchmark_held_out_evaluation_stats": tdir / "held_out_evaluation" / "evaluation_stats.json",
        "trait_benchmark_final_evaluation": tdir / "final_evaluation" / "evaluation.json",
        "trait_benchmark_baseline_freeze": tdir / "b4_baseline" / "freeze.json",
        "trait_benchmark_v2_dir": tdir / "b4_v2",
        "trait_benchmark_v2_observations": tdir / "b4_v2" / "observations.jsonl",
        "trait_benchmark_v2_observation_stats": tdir / "b4_v2" / "observation_stats.json",
        "trait_benchmark_v2_conclusions": tdir / "b4_v2" / "conclusions.jsonl",
        "trait_benchmark_v2_conclusion_stats": tdir / "b4_v2" / "conclusion_stats.json",
        "trait_benchmark_v2_comparison": tdir / "b4_v2" / "comparison.jsonl",
        "trait_benchmark_v2_comparison_stats": tdir / "b4_v2" / "comparison_stats.json",
        "trait_benchmark_v2_family_activation": tdir / "b4_v2" / "family_activation.jsonl",
        "trait_benchmark_v2_stats": tdir / "b4_v2" / "evaluation_stats.json",
        "trait_benchmark_v2_freeze": tdir / "b4_v2" / "freeze.json",
    }


def _build_traits() -> list[dict]:
    rows = []
    for i, spec in enumerate(TRAIT_SPECS, start=1):
        row = {
            "id": f"TRAIT-{i:04d}",
            "schema_version": SCHEMA_VERSION,
            "status": "canonical",
            "slug": spec["slug"],
            "kind": spec["kind"],
            "stem": spec["stem"],
            "implies": list(spec.get("implies") or []),
            "conflicts": [],
        }
        if spec.get("notes"):
            row["notes"] = spec["notes"]
        rows.append(row)
    return rows


def _build_slots() -> list[dict]:
    rows = []
    for i, spec in enumerate(SLOT_SPECS, start=1):
        rows.append({
            "id": f"SLOT-{i:04d}",
            "schema_version": SCHEMA_VERSION,
            "status": "canonical",
            "slug": spec["slug"],
            "role": spec["role"],
        })
    return rows


def write_system_trait_ontology(*, paths: dict[str, Path] | None = None) -> dict:
    assert_ontology_locked()
    if TRAIT_ONTOLOGY_LOCKED:
        raise TraitError("System-trait ontology stays locked.")
    paths = paths or trait_paths()
    for key in ("traits", "slots", "stats"):
        dest = paths[key]
        if dest.exists() and dest.read_text(encoding="utf-8").strip():
            raise TraitError(f"{dest.name} already exists; refusing to overwrite the trait ontology")
    if paths["graph"].exists():
        raise TraitError("canonical/question_families.jsonl already exists; ontology will not overwrite")

    traits = _build_traits()
    slots = _build_slots()
    if len(traits) != EXPECTED_TRAITS:
        raise TraitError(f"expected {EXPECTED_TRAITS} traits, got {len(traits)}")
    if len(slots) != EXPECTED_SLOTS:
        raise TraitError(f"expected {EXPECTED_SLOTS} slots, got {len(slots)}")
    if not (TRAIT_MIN <= len(traits) <= TRAIT_MAX):
        raise TraitError(f"trait catalog must be {TRAIT_MIN}–{TRAIT_MAX}, got {len(traits)}")
    validate_catalog(traits, slots)

    stats = {
        "traits": len(traits),
        "slots": len(slots),
        "traits_by_kind": dict(Counter(row["kind"] for row in traits)),
        "implies_edges": sum(len(row["implies"]) for row in traits),
        "canonical_families_mutated": False,
        "applicability_mapping": "locked" if FAMILY_APPLICABILITY_LOCKED else "open",
        "specialization_templates": "locked" if SPECIALIZATION_TEMPLATE_LOCKED else "open",
        "questions": "locked" if SPECIALIZATION_LOCKED else "open",
        "next_gate": "family_applicability_mapping",
        "note": (
            "Frozen compositional trait catalog for the 53 families. "
            "Do not map applies_when yet. Do not emit specialized stems."
        ),
    }
    write_jsonl(paths["traits"], traits)
    write_jsonl(paths["slots"], slots)
    dump_json(paths["stats"], stats)
    return stats


def map_family_applicability(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_applicability import map_family_applicability as _map

    return _map(paths=paths)


def write_applicability_review(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_review import write_applicability_review as _write

    return _write(paths=paths)


def freeze_family_applicability(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_review import freeze_family_applicability as _freeze

    return _freeze(paths=paths)


def build_specialization_templates(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_specialize import build_specialization_templates as _build

    return _build(paths=paths)


def write_specialization_review(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_specialize import write_specialization_review as _write

    return _write(paths=paths)


def freeze_specialization_templates(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_specialize import freeze_specialization_templates as _freeze

    return _freeze(paths=paths)


def expand_specialization_templates(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_specialize import expand_specialization_templates as _expand

    return _expand(paths=paths)


def write_expansion_template_review(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_expand_review import write_expansion_template_review as _write

    return _write(paths=paths)


def freeze_specialization_expansion(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_expand import freeze_specialization_expansion as _freeze

    return _freeze(paths=paths)


def write_trait_evidence_contract(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_evidence import write_trait_evidence_contract as _write

    return _write(paths=paths)


def write_trait_detectors(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detectors import write_trait_detectors as _write

    return _write(paths=paths)


def write_trait_detector_review(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_review import write_trait_detector_review as _write

    return _write(paths=paths)


def write_expanded_trait_detectors(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_expand import write_expanded_trait_detectors as _write

    return _write(paths=paths)


def write_expanded_trait_detector_review(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_expand_review import write_expanded_trait_detector_review as _write

    return _write(paths=paths)


def freeze_trait_detectors(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_freeze import freeze_trait_detectors as _freeze

    return _freeze(paths=paths)


def run_trait_detectors(*, repo: Path | None = None, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_run import run_trait_detectors as _run

    return _run(repo=repo, paths=paths)


def review_trait_detector_observations(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_observation_review import (
        review_trait_detector_observations as _review,
    )

    return _review(paths=paths)


def fix_trait_detector_runner(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_runner_fix import fix_trait_detector_runner as _fix

    return _fix(paths=paths)


def freeze_reviewed_observations(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_detector_observation_freeze import (
        freeze_reviewed_observations as _freeze,
    )

    return _freeze(paths=paths)


def write_trait_aggregation_contract(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_aggregation import write_trait_aggregation_contract as _write

    return _write(paths=paths)


def write_hackerrankats_trait_map(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_map import write_hackerrankats_trait_map as _write

    return _write(paths=paths)


def write_trait_benchmark_design(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark import write_trait_benchmark_design as _write

    return _write(paths=paths)


def write_development_reference_labels(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_references import (
        write_development_reference_labels as _write,
    )

    return _write(paths=paths)


def write_development_trait_benchmark(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_run import (
        write_development_trait_benchmark as _write,
    )

    return _write(paths=paths)


def write_development_trait_benchmark_comparison(
    *,
    paths: dict[str, Path] | None = None,
) -> dict:
    from pipeline.system_trait_benchmark_compare import (
        write_development_trait_benchmark_comparison as _write,
    )

    return _write(paths=paths)


def write_development_remediation(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_remediation import (
        write_development_remediation as _write,
    )

    return _write(paths=paths)


def freeze_development_remediation(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_remediation_freeze import (
        freeze_development_remediation as _freeze,
    )

    return _freeze(paths=paths)


def write_held_out_evaluation(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_held_out import (
        write_held_out_evaluation as _write,
    )

    return _write(paths=paths)


def write_final_b4_evaluation(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_final import (
        write_final_b4_evaluation as _write,
    )

    return _write(paths=paths)


def write_b4_v2(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_v2 import write_b4_v2 as _write

    return _write(paths=paths)


def freeze_b4_baseline(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_baseline_freeze import (
        freeze_b4_baseline as _freeze,
    )

    return _freeze(paths=paths)


def freeze_b4_v2(*, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait_benchmark_v2_freeze import freeze_b4_v2 as _freeze

    return _freeze(paths=paths)
