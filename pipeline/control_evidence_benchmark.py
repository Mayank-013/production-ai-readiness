"""C4: sealed HackerRankATS control-evidence benchmark.

Human labels first. One run. Do not retune after unblinding.
False SATISFIED and false FAIL are expensive.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_assess import assess_controls
from pipeline.control_evidence_c1 import EXPECTATION_SPECS
from pipeline.control_evidence_contract import (
    C4_REPO,
    CONTROL_BENCHMARK_LOCKED,
    CONTROL_COMPARISON_SCHEMA_PATH,
    CONTROL_DOC,
    CONTROL_REFERENCE_SCHEMA_PATH,
    EXPECTED_C4_ROWS,
    SCHEMA_VERSION,
    ControlError,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.control_evidence_observe import FAMILY_EXPECTATION, collect_control_observations
from pipeline.system_trait_benchmark_run import DEV_REPO_ROOTS
from pipeline.system_trait_contract import HACKERRANKATS_REPO

# Honest HackerRankATS labels. Resume scoring is not eval_gate.
# Outbound https is not a TLS-enforced server. Logs are not alarms.
REFERENCE_SPECS: list[dict] = [
    {"family_id": "QF-0001", "state": "SATISFIED", "notes": "requests.get(..., timeout=10) is an explicit client deadline."},
    {"family_id": "QF-0003", "state": "PARTIAL", "notes": "GitHub enrichment failure continues; Gemini falls back to Ollama."},
    {"family_id": "QF-0005", "state": "UNKNOWN", "notes": "Resume evaluation is product scoring, not a pre-production behavior gate."},
    {"family_id": "QF-0010", "state": "UNKNOWN", "notes": "No inbound authorization policy on the serving path."},
    {"family_id": "QF-0012", "state": "UNKNOWN", "notes": "No inbound caller identification. Outbound vendor tokens do not count."},
    {"family_id": "QF-0016", "state": "PARTIAL", "notes": "Outbound https URLs. No TLS-enforced listener."},
    {"family_id": "QF-0017", "state": "UNKNOWN", "notes": "Persisted records are not encrypted at rest."},
    {"family_id": "QF-0018", "state": "UNKNOWN", "notes": "logger.error is telemetry, not an alarm."},
    {"family_id": "QF-0019", "state": "SATISFIED", "notes": "Named logger records the request and model path."},
    {"family_id": "QF-0030", "state": "UNKNOWN", "notes": "Prompt instruction is insufficient; no injection filter."},
    {"family_id": "QF-0032", "state": "SATISFIED", "notes": "Pydantic request models validate inbound API payloads."},
    {"family_id": "QF-0035", "state": "PARTIAL", "notes": "Keys come from getenv. No secret scanner. No live literal found."},
]


def _classify(human: str, system: str) -> str:
    if human == "SATISFIED" and system == "SATISFIED":
        return "SATISFIED_TP"
    if system == "SATISFIED" and human != "SATISFIED":
        return "SATISFIED_FP"
    if human == "SATISFIED" and system != "SATISFIED":
        return "SATISFIED_FN"
    if human == "FAIL" and system == "FAIL":
        return "FAIL_TP"
    if system == "FAIL" and human != "FAIL":
        return "FAIL_FP"
    if human == "FAIL" and system != "FAIL":
        return "FAIL_FN"
    if human == "PARTIAL" and system == "PARTIAL":
        return "PARTIAL_MATCH"
    if human == "PARTIAL" and system == "UNKNOWN":
        return "PARTIAL_MISS"
    if human == "UNKNOWN" and system == "UNKNOWN":
        return "UNKNOWN_ABSTAIN"
    return "STATE_MISMATCH"


def write_control_references(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(CONTROL_BENCHMARK_LOCKED, "C4 control benchmark")
    paths = paths or control_paths()
    refuse_overwrite(paths["references"], "the C4 control reference labels")
    schema = load_schema(CONTROL_REFERENCE_SCHEMA_PATH)
    expected = [spec["family_id"] for spec in EXPECTATION_SPECS]
    got = [spec["family_id"] for spec in REFERENCE_SPECS]
    if got != expected:
        raise ControlError("C4 references must follow C1 family order")
    rows = []
    for spec in REFERENCE_SPECS:
        row = {
            "repo": C4_REPO,
            "family_id": spec["family_id"],
            "expectation_id": FAMILY_EXPECTATION[spec["family_id"]],
            "state": spec["state"],
            "notes": spec["notes"],
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, schema, label=row["family_id"])
        rows.append(row)
    if len(rows) != EXPECTED_C4_ROWS:
        raise ControlError(f"expected {EXPECTED_C4_ROWS} C4 rows")
    stats = {
        "repo": C4_REPO,
        "rows": len(rows),
        "by_state": dict(Counter(row["state"] for row in rows)),
        "status": "frozen",
        "note": "Human labels first. Do not retune after unblinding.",
    }
    write_jsonl(paths["references"], rows)
    dump_json(paths["reference_stats"], stats)
    return stats


def compare_control_assessments(references: list[dict], assessments: list[dict]) -> list[dict]:
    schema = load_schema(CONTROL_COMPARISON_SCHEMA_PATH)
    by_fam = {row["family_id"]: row for row in assessments}
    rows = []
    for ref in references:
        sys_row = by_fam.get(ref["family_id"])
        if sys_row is None:
            raise ControlError(f"missing assessment for {ref['family_id']}")
        row = {
            "repo": ref["repo"],
            "family_id": ref["family_id"],
            "expectation_id": ref["expectation_id"],
            "human": ref["state"],
            "system": sys_row["state"],
            "classification": _classify(ref["state"], sys_row["state"]),
            "schema_version": SCHEMA_VERSION,
            "status": "frozen",
        }
        validate_row(row, schema, label=row["family_id"])
        rows.append(row)
    return rows


def write_control_benchmark(
    *,
    paths: dict[str, Path] | None = None,
    repo: Path | None = None,
) -> dict:
    assert_control_locked(CONTROL_BENCHMARK_LOCKED, "C4 control benchmark")
    paths = paths or control_paths()
    refuse_overwrite(paths["evaluation_stats"], "the C4 control evaluation")
    if not paths["references"].exists() or not paths["references"].read_text().strip():
        write_control_references(paths=paths)
    root = repo or DEV_REPO_ROOTS.get("hackerrankats")
    if root is None or not Path(root).exists():
        raise ControlError("HackerRankATS repository is required for C4")
    observations = collect_control_observations(root, repo=HACKERRANKATS_REPO)
    assessments = assess_controls(observations)
    if not paths["observations"].exists() or not paths["observations"].read_text().strip():
        write_jsonl(paths["observations"], observations)
        dump_json(
            paths["observation_stats"],
            {
                "repo": HACKERRANKATS_REPO,
                "observations": len(observations),
                "by_strength": dict(Counter(row["strength"] for row in observations)),
                "status": "frozen",
            },
        )
    if not paths["assessments"].exists() or not paths["assessments"].read_text().strip():
        write_jsonl(paths["assessments"], assessments)
        dump_json(
            paths["assessment_stats"],
            {
                "repo": HACKERRANKATS_REPO,
                "assessments": len(assessments),
                "by_state": dict(Counter(row["state"] for row in assessments)),
                "status": "frozen",
            },
        )
    references = read_jsonl(paths["references"])
    comparison = compare_control_assessments(references, assessments)
    counts = Counter(row["classification"] for row in comparison)
    sat_tp = counts["SATISFIED_TP"]
    sat_fp = counts["SATISFIED_FP"]
    sat_fn = counts["SATISFIED_FN"]
    fail_fp = counts["FAIL_FP"]
    human_sat = sum(1 for row in references if row["state"] == "SATISFIED")
    precision = sat_tp / (sat_tp + sat_fp) if (sat_tp + sat_fp) else None
    recall = sat_tp / human_sat if human_sat else None
    stats = {
        "repo": C4_REPO,
        "rows": len(comparison),
        "classifications": dict(counts),
        "satisfied_tp": sat_tp,
        "satisfied_fp": sat_fp,
        "satisfied_fn": sat_fn,
        "fail_fp": fail_fp,
        "partial_match": counts["PARTIAL_MATCH"],
        "unknown_abstain": counts["UNKNOWN_ABSTAIN"],
        "satisfied_precision": precision,
        "satisfied_recall": recall,
        "exact_state_match": sum(1 for row in comparison if row["human"] == row["system"]),
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "catalog_retuned": False,
        "status": "frozen",
        "next_gate": "runtime_questions",
        "note": (
            "C4 sealed HackerRankATS pack. False SATISFIED and false FAIL "
            f"are expensive. Contract: {CONTROL_DOC}."
        ),
    }
    write_jsonl(paths["comparison"], comparison)
    dump_json(paths["comparison_stats"], stats)
    dump_json(paths["evaluation_stats"], stats)
    return stats
