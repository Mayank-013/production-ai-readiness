"""Gap playbooks attached to PARTIAL and FAIL findings.

A playbook answers: given this finding, what should an engineer do next,
how should they verify it, and what evidence would close the gap.

Attached to the finding, not blindly to the family.
UNKNOWN does not receive a playbook.

Contract: docs/gap-playbooks.md
"""

from __future__ import annotations

from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_contract import (
    ControlError,
    PLAYBOOK_DOC,
    PLAYBOOK_LOCKED,
    PLAYBOOK_SCHEMA_PATH,
    PLAYBOOK_SCHEMA_VERSION,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)

# Finding-shaped specs. Keyed by (family_id, assessment_state, evidence_class).
# FAIL rows are catalog counterparts so PARTIAL ≠ FAIL can be validated.
PLAYBOOK_SPECS: list[dict] = [
    {
        "family_id": "QF-0003",
        "assessment_state": "PARTIAL",
        "evidence_class": "supporting_fallback_no_named_failover",
        "kind": "finding",
        "evidence_found": [
            "Gemini key missing falls back to Ollama.",
            "GitHub path prints a fallback to the first seven projects.",
        ],
        "evidence_missing": [
            "A named failover for a down model endpoint or GitHub outage.",
            "A test that exercises the dependency-down path.",
            "Telemetry when the fallback activates.",
        ],
        "problem": (
            "Dependencies are used, but fallback and degradation behavior is incomplete. "
            "Existing fallbacks cover a missing API key and a truncated project list, "
            "not timeout, outage, or repeated errors on the primary remote calls."
        ),
        "why_it_matters": (
            "When GitHub or the model provider is unavailable, the hiring path can "
            "fail closed without a defined reduced result. Callers cannot tell a "
            "degraded answer from a crash."
        ),
        "implementation_options": [
            "Identify each hard external dependency on the serving path.",
            "Define behavior for timeout, outage, and repeated errors.",
            "Choose fail-fast, fallback provider, cached or stale response, queue, or an explicit unavailable state.",
            "Make that behavior a named branch in code or config, not an implicit except-and-log.",
            "Emit a log or metric when the degrade path activates.",
        ],
        "verification": [
            "A test that fails the GitHub or model dependency and expects the degraded response.",
            "Timeout or failure injection on the outbound client.",
            "The expected reduced or unavailable result is observed, not an unhandled exception.",
        ],
        "completion_evidence": [
            "An explicit fallback or degradation branch for the primary dependency.",
            "A test covering dependency failure.",
            "Telemetry for fallback activation.",
        ],
    },
    {
        "family_id": "QF-0003",
        "assessment_state": "FAIL",
        "evidence_class": "refuse_to_degrade",
        "kind": "catalog",
        "evidence_found": [
            "A primary dependency outage is handled by crashing or by an explicit refuse-to-degrade flag.",
        ],
        "evidence_missing": [
            "Any alternate or reduced path.",
        ],
        "problem": (
            "The system refuses to degrade when a primary dependency is unavailable. "
            "This is a contradiction of the degrade-path control, not mere absence."
        ),
        "why_it_matters": (
            "A hard crash or refuse-to-degrade flag turns a dependency outage into "
            "a total serving failure with no caller-visible reduced mode."
        ),
        "implementation_options": [
            "Remove the refuse-to-degrade flag from the serving path.",
            "Replace crash-only handling with a named unavailable or fallback result.",
            "Keep fail-fast only where the product contract requires it, and document that contract.",
        ],
        "verification": [
            "Dependency-down test no longer crashes the serving path.",
            "Callers receive the documented unavailable or fallback payload.",
        ],
        "completion_evidence": [
            "Refuse-to-degrade or crash-only handling is gone from the serving path.",
            "A named degrade or unavailable branch exists and is tested.",
        ],
    },
    {
        "family_id": "QF-0016",
        "assessment_state": "PARTIAL",
        "evidence_class": "outbound_https_no_serving_tls",
        "kind": "finding",
        "evidence_found": [
            "Outbound dependency URLs use https, including GitHub API calls.",
        ],
        "evidence_missing": [
            "A TLS listener, HTTPS redirect, or ingress that refuses plaintext on the serving surface.",
            "Deployment-level proof that HTTP cannot silently reach the API.",
        ],
        "problem": (
            "Outbound HTTPS exists, but serving-path TLS enforcement is not established. "
            "Client https URLs do not prove the API cannot be reached in plaintext."
        ),
        "why_it_matters": (
            "A plaintext serving surface exposes session and candidate data on the "
            "externally reachable path even when vendor calls already use https."
        ),
        "implementation_options": [
            "Determine where TLS terminates: process, reverse proxy, or ingress.",
            "Verify HTTP cannot silently reach the serving surface.",
            "Redirect or reject plaintext where the product is internet-reachable.",
            "Keep certificates and private keys outside the source tree.",
            "Test the externally reachable path, not only outbound client URLs.",
        ],
        "verification": [
            "Probe the advertised serving host over HTTP and expect redirect or reject.",
            "Confirm the TLS listener, proxy, or ingress config is the path traffic uses.",
            "Confirm certificates are loaded from deploy secrets, not committed files.",
        ],
        "completion_evidence": [
            "TLS listener, proxy, or ingress config for the serving surface.",
            "No unintended plaintext serving path.",
            "Deployment-level verification of the reachable path.",
        ],
    },
    {
        "family_id": "QF-0016",
        "assessment_state": "FAIL",
        "evidence_class": "plaintext_listener_tls_disabled",
        "kind": "catalog",
        "evidence_found": [
            "A public listener is configured to serve the API over plaintext with TLS disabled.",
        ],
        "evidence_missing": [
            "Any TLS enforcement on the serving surface.",
        ],
        "problem": (
            "The serving path is configured to accept plaintext and TLS is explicitly disabled. "
            "That is a contradiction, not an UNKNOWN about where TLS terminates."
        ),
        "why_it_matters": (
            "An intentional plaintext listener puts credentials and candidate data on the wire."
        ),
        "implementation_options": [
            "Disable the plaintext public listener.",
            "Require TLS at the process, proxy, or ingress that terminates the serving path.",
            "Fail deploy if TLS is off for an internet-reachable surface.",
        ],
        "verification": [
            "The previous plaintext port no longer serves the API.",
            "The reachable path negotiates TLS.",
        ],
        "completion_evidence": [
            "Plaintext public listener removed or bound to localhost only.",
            "TLS required on the advertised serving path.",
        ],
    },
    {
        "family_id": "QF-0035",
        "assessment_state": "PARTIAL",
        "evidence_class": "getenv_no_scanner",
        "kind": "finding",
        "evidence_found": [
            "GITHUB_TOKEN, GEMINI_API_KEY, and OPENAI_API_KEY are read from the environment.",
        ],
        "evidence_missing": [
            "An automated secret scanner in pre-commit or CI.",
            "A documented rotation path if a credential is found in the tree.",
        ],
        "problem": (
            "Secrets are read from the environment, but embedded-secret prevention is not established. "
            "Env reads are supporting evidence, not a scanner or a leak-response path."
        ),
        "why_it_matters": (
            "Without a scanner and a rotation procedure, a committed key can sit in "
            "history after the runtime has already moved to getenv."
        ),
        "implementation_options": [
            "Add secret scanning in pre-commit and CI.",
            "Scan history where the repository has been shared or published.",
            "Block known credential patterns on the merge path.",
            "Prefer temporary or external secret sources over long-lived env files in the tree.",
            "Define a rotation procedure for detected leakage.",
        ],
        "verification": [
            "The scanner runs on a pull request and can fail the build.",
            "A planted test credential is caught, then removed from the fixture.",
            "A clean scan result exists for the default branch.",
        ],
        "completion_evidence": [
            "Scanner configuration in the repository.",
            "A CI or pre-commit gate that can fail on secrets.",
            "A clean scan result.",
            "A documented remediation and rotation path.",
        ],
    },
    {
        "family_id": "QF-0035",
        "assessment_state": "FAIL",
        "evidence_class": "live_literal_in_source",
        "kind": "catalog",
        "evidence_found": [
            "A live credential, private key, or password literal is embedded in source.",
        ],
        "evidence_missing": [
            "Removal of the literal and rotation of the exposed credential.",
        ],
        "problem": (
            "A live credential is embedded in the source tree. That is a contradiction "
            "of hardcoded-secret handling, not an UNKNOWN about where secrets live."
        ),
        "why_it_matters": (
            "Anyone with the tree has the credential. Env reads elsewhere do not cancel the leak."
        ),
        "implementation_options": [
            "Remove the literal from source and history as appropriate.",
            "Rotate the exposed credential immediately.",
            "Move the replacement into a secret manager or environment.",
            "Add a scanner so the same class of literal cannot merge again.",
        ],
        "verification": [
            "The literal is gone from the default branch.",
            "The old credential is revoked.",
            "A scanner gate fails if the same pattern is reintroduced.",
        ],
        "completion_evidence": [
            "No live credential literal in source.",
            "Rotation record for the exposed secret.",
            "Scanner configuration that would have caught the literal.",
        ],
    },
]


def _spec_key(row: dict) -> tuple[str, str]:
    return row["family_id"], row["assessment_state"]


def catalog_playbooks_for_validation(
    finding_keys: set[tuple[str, str]],
    *,
    start: int = 9001,
) -> list[dict]:
    """Catalog counterparts so PARTIAL≠FAIL can be validated on a live run."""
    rows = []
    n = start - 1
    for spec in PLAYBOOK_SPECS:
        if _spec_key(spec) in finding_keys:
            continue
        n += 1
        rows.append(_row({**spec, "kind": "catalog"}, n, recommendation=None))
    return rows


def attach_playbooks(
    recommendations: list[dict],
    *,
    specs: list[dict] | None = None,
) -> list[dict]:
    specs = specs or PLAYBOOK_SPECS
    schema = load_schema(PLAYBOOK_SCHEMA_PATH)
    by_key = {_spec_key(spec): spec for spec in specs}
    if len(by_key) != len(specs):
        raise ControlError("playbook specs must be unique on family_id + assessment_state")
    rows = []
    n = 0
    attached_keys: set[tuple[str, str]] = set()
    for rec in recommendations:
        if rec["assessment_state"] not in {"PARTIAL", "FAIL"}:
            raise ControlError("playbooks attach only to PARTIAL or FAIL recommendations")
        spec = by_key.get((rec["family_id"], rec["assessment_state"]))
        if spec is None:
            raise ControlError(
                f"no playbook spec for {rec['family_id']} {rec['assessment_state']}"
            )
        n += 1
        row = _row({**spec, "kind": "finding"}, n, recommendation=rec)
        validate_row(row, schema, label=row["id"])
        rows.append(row)
        attached_keys.add(_spec_key(spec))
    for spec in specs:
        if _spec_key(spec) in attached_keys:
            continue
        n += 1
        row = _row({**spec, "kind": "catalog"}, n, recommendation=None)
        validate_row(row, schema, label=row["id"])
        rows.append(row)
    unknown = [rec for rec in recommendations if rec.get("assessment_state") == "UNKNOWN"]
    if unknown:
        raise ControlError("UNKNOWN recommendations cannot receive playbooks")
    return rows


def _row(spec: dict, n: int, *, recommendation: dict | None) -> dict:
    row = {
        "id": f"PB-{n:04d}",
        "kind": spec["kind"],
        "family_id": spec["family_id"],
        "assessment_state": spec["assessment_state"],
        "evidence_class": spec["evidence_class"],
        "evidence_found": list(spec["evidence_found"]),
        "evidence_missing": list(spec["evidence_missing"]),
        "problem": spec["problem"],
        "why_it_matters": spec["why_it_matters"],
        "implementation_options": list(spec["implementation_options"]),
        "verification": list(spec["verification"]),
        "completion_evidence": list(spec["completion_evidence"]),
        "schema_version": PLAYBOOK_SCHEMA_VERSION,
        "status": "frozen",
    }
    if recommendation is not None:
        row["recommendation_id"] = recommendation["id"]
        row["expectation_id"] = recommendation["expectation_id"]
        row["question_id"] = recommendation["question_id"]
        row["repo"] = recommendation.get("repo")
    return row


def write_gap_playbooks(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(PLAYBOOK_LOCKED, "Gap playbooks")
    paths = paths or control_paths()
    refuse_overwrite(paths["playbooks"], "the gap playbook dest")
    recs = read_jsonl(paths["recommendations"])
    if any(row["assessment_state"] == "UNKNOWN" for row in recs):
        raise ControlError("UNKNOWN must not appear in the recommendation dest")
    rows = attach_playbooks(recs)
    finding = [row for row in rows if row["kind"] == "finding"]
    catalog = [row for row in rows if row["kind"] == "catalog"]
    if len(finding) != len(recs):
        raise ControlError("each PARTIAL/FAIL recommendation must receive one finding playbook")
    stats = {
        "playbooks": len(rows),
        "finding": len(finding),
        "catalog": len(catalog),
        "unknown_playbooks": 0,
        "family_blind": False,
        "status": "frozen",
        "next_gate": "playbook_validation",
        "note": (
            "Playbooks attach to findings, not families. "
            "UNKNOWN stays out. "
            f"Contract: {PLAYBOOK_DOC}."
        ),
    }
    write_jsonl(paths["playbooks"], rows)
    dump_json(paths["playbook_stats"], stats)
    return stats
