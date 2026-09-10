"""Validate gap playbooks.

Checks are mechanical:

- finding playbooks attach to a PARTIAL/FAIL recommendation
- UNKNOWN and SATISFIED have no playbook
- PARTIAL and FAIL specs for the same family are not the same playbook
- completion evidence is not a restatement of evidence already found
- verification names a test, scan, probe, or deploy check

Contract: docs/gap-playbooks.md
"""

from __future__ import annotations

from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_contract import (
    ControlError,
    PLAYBOOK_DOC,
    PLAYBOOK_VALIDATION_LOCKED,
    PLAYBOOK_VALIDATION_SCHEMA_PATH,
    PLAYBOOK_SCHEMA_VERSION,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.gap_playbook import PLAYBOOK_SPECS

CONCRETE_TOKS = (
    "test",
    "inject",
    "probe",
    "scan",
    "scanner",
    "ci",
    "pre-commit",
    "deploy",
    "redirect",
    "reject",
    "tls",
    "revoke",
    "fail",
)


def _overlap(left: list[str], right: list[str]) -> bool:
    a = {" ".join(item.lower().split()) for item in left}
    b = {" ".join(item.lower().split()) for item in right}
    return bool(a & b)


def _verification_concrete(items: list[str]) -> bool:
    blob = " ".join(items).lower()
    return any(tok in blob for tok in CONCRETE_TOKS)


def validate_playbooks(
    playbooks: list[dict],
    recommendations: list[dict],
    assessments: list[dict],
) -> list[dict]:
    schema = load_schema(PLAYBOOK_VALIDATION_SCHEMA_PATH)
    rec_ids = {row["id"] for row in recommendations}
    rec_states = {row["id"]: row["assessment_state"] for row in recommendations}
    assessed_unknown = {row["family_id"] for row in assessments if row["state"] == "UNKNOWN"}
    assessed_satisfied = {row["family_id"] for row in assessments if row["state"] == "SATISFIED"}
    by_family_state: dict[tuple[str, str], dict] = {}
    for row in playbooks:
        by_family_state[(row["family_id"], row["assessment_state"])] = row
    rows = []
    for row in playbooks:
        finding_attached = True
        unknown_excluded = True
        state_specific = True
        completion_closes = True
        verification_ok = _verification_concrete(row["verification"])
        notes = []
        if row["kind"] == "finding":
            if row.get("recommendation_id") not in rec_ids:
                finding_attached = False
                notes.append("finding playbook missing recommendation_id")
            elif rec_states[row["recommendation_id"]] != row["assessment_state"]:
                finding_attached = False
                notes.append("playbook state does not match the finding")
        if row["family_id"] in assessed_unknown and row["kind"] == "finding":
            unknown_excluded = False
            notes.append("UNKNOWN family received a finding playbook")
        if row["family_id"] in assessed_satisfied and row["kind"] == "finding":
            notes.append("SATISFIED family received a finding playbook")
            finding_attached = False
        sibling_state = "FAIL" if row["assessment_state"] == "PARTIAL" else "PARTIAL"
        sibling = by_family_state.get((row["family_id"], sibling_state))
        if sibling is None:
            state_specific = False
            notes.append("missing counterpart playbook for the other state")
        elif sibling["problem"] == row["problem"]:
            state_specific = False
            notes.append("PARTIAL and FAIL problems are identical")
        elif sibling["implementation_options"] == row["implementation_options"]:
            state_specific = False
            notes.append("PARTIAL and FAIL options are identical")
        if _overlap(row["completion_evidence"], row.get("evidence_found") or []):
            completion_closes = False
            notes.append("completion evidence restates evidence already found")
        if not row.get("evidence_missing"):
            completion_closes = False
            notes.append("playbook does not name missing evidence")
        decision = "accept"
        if not all(
            [
                finding_attached,
                unknown_excluded,
                state_specific,
                completion_closes,
                verification_ok,
            ]
        ):
            decision = "revise"
        out = {
            "playbook_id": row["id"],
            "decision": decision,
            "finding_attached": finding_attached,
            "unknown_excluded": unknown_excluded,
            "state_specific": state_specific,
            "completion_closes_gap": completion_closes,
            "verification_concrete": verification_ok,
            "schema_version": PLAYBOOK_SCHEMA_VERSION,
            "status": "frozen",
        }
        if notes:
            out["notes"] = "; ".join(notes)
        validate_row(out, schema, label=row["id"])
        rows.append(out)
    return rows


def write_playbook_validation(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(PLAYBOOK_VALIDATION_LOCKED, "Playbook validation")
    paths = paths or control_paths()
    refuse_overwrite(paths["playbook_validation"], "the playbook validation dest")
    playbooks = read_jsonl(paths["playbooks"])
    reviews = validate_playbooks(
        playbooks,
        read_jsonl(paths["recommendations"]),
        read_jsonl(paths["assessments"]),
    )
    accept = sum(1 for row in reviews if row["decision"] == "accept")
    if accept != len(reviews):
        raise ControlError("playbook validation must accept every written playbook")
    if len(PLAYBOOK_SPECS) != len(playbooks):
        raise ControlError("validation dest must cover every playbook spec")
    stats = {
        "playbooks": len(reviews),
        "accept": accept,
        "revise": 0,
        "reject": 0,
        "unknown_playbooks": 0,
        "family_blind": False,
        "status": "frozen",
        "next_gate": "full_repo_analysis",
        "note": (
            "Playbook validation is mechanical. Finding attachment, UNKNOWN "
            "exclusion, and PARTIAL≠FAIL all passed. Skills stay omitted. "
            f"Full repo analysis stays locked. Contract: {PLAYBOOK_DOC}."
        ),
    }
    write_jsonl(paths["playbook_validation"], reviews)
    dump_json(paths["playbook_validation_stats"], stats)
    freeze = {
        "playbooks": len(playbooks),
        "finding": sum(1 for row in playbooks if row["kind"] == "finding"),
        "catalog": sum(1 for row in playbooks if row["kind"] == "catalog"),
        "validation_accept": accept,
        "unknown_playbooks": 0,
        "recommendations_mutated": False,
        "control_dests_mutated": False,
        "status": "frozen",
        "next_gate": "full_repo_analysis",
        "note": stats["note"],
    }
    if not paths["playbook_freeze"].exists() or not paths["playbook_freeze"].read_text().strip():
        dump_json(paths["playbook_freeze"], freeze)
    return stats
