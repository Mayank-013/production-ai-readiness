"""Phase 5.3 — Agent Runtime control pack.

Representative pack. QF-0001 and QF-0003 stay on C1.
QF-0041 stays on Phase 5.2. QF-0021 is reserved for cost/resource.

Absence of evidence is UNKNOWN, not FAIL.
"""

from __future__ import annotations

P5_RUNTIME_SPECS: list[dict] = [
    {
        "id": "CEE-0301",
        "family_id": "QF-0023",
        "control_id": "CTRL-0053",
        "diagnostic_job": "human_approval",
        "strong": [
            "A human-approval gate blocks high-impact agent or tool actions until an approver confirms.",
            "A named require_human_approval check runs on the execution path before the side effect.",
        ],
        "supporting": [
            "An approval workflow is configured without a runtime gate on the call site.",
        ],
        "insufficient_alone": [
            "A comment says actions require approval.",
            "A permission check exists with no distinct approval step.",
        ],
        "contradiction": [
            "Human approval is explicitly bypassed on a high-impact action.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Approval before execution. Least privilege is permission_boundary.",
    },
    {
        "id": "CEE-0302",
        "family_id": "QF-0008",
        "control_id": "CTRL-0004",
        "diagnostic_job": "idempotent_replay",
        "strong": [
            "An idempotency key is stored and checked so a replay does not repeat the side effect.",
            "The runtime returns the prior outcome when the same agent event or tool request is delivered twice.",
        ],
        "supporting": [
            "An idempotency key is generated without a store-and-compare check.",
        ],
        "insufficient_alone": [
            "A UUID is created per request and never compared to prior executions.",
        ],
        "contradiction": [
            "Idempotency checking is explicitly skipped so duplicates execute twice.",
        ],
        "evidence_sources": ["code"],
        "notes": "Replay safety. Whether to retry is retry_classification. Wait bounds are bound_work.",
    },
    {
        "id": "CEE-0303",
        "family_id": "QF-0064",
        "control_id": "CTRL-0268",
        "diagnostic_job": "structured_output",
        "strong": [
            "Tool or model output is schema-validated before the agent loop continues.",
            "A named validate_structured_output check requires the machine-readable shape.",
        ],
        "supporting": [
            "A response-format hint is set without a runtime schema check.",
        ],
        "insufficient_alone": [
            "Free-text results are parsed with best-effort regex only.",
        ],
        "contradiction": [
            "Structured-output validation is explicitly skipped.",
        ],
        "evidence_sources": ["code"],
        "notes": "Machine-readable shape for downstream consume. Input validation of inbound requests is QF-0032.",
    },
    {
        "id": "CEE-0304",
        "family_id": "QF-0025",
        "control_id": "CTRL-0042",
        "diagnostic_job": "retry_classification",
        "strong": [
            "Failures are classified as retryable or not before a retry is issued.",
            "A named classify_failure function decides retry, fallback, or human handoff.",
        ],
        "supporting": [
            "A retryable-error list exists without a classify-before-retry step.",
        ],
        "insufficient_alone": [
            "A retry loop retries every exception.",
        ],
        "contradiction": [
            "Retry classification is explicitly skipped so every failure is retried.",
        ],
        "evidence_sources": ["code"],
        "notes": "Classify before recover. Retry pacing is a different family. Cutoffs are slow_cutoff.",
    },
    {
        "id": "CEE-0305",
        "family_id": "QF-0050",
        "control_id": "CTRL-0138",
        "diagnostic_job": "session_binding",
        "strong": [
            "A session is bound to one principal and cannot be guessed or reused by another.",
            "Session tokens are unique, high-entropy, and checked against the initiating principal.",
        ],
        "supporting": [
            "A session id is issued without binding it to the principal.",
        ],
        "insufficient_alone": [
            "A cookie is set with no session-to-principal check.",
        ],
        "contradiction": [
            "Session reuse or sharing is explicitly allowed.",
        ],
        "evidence_sources": ["code"],
        "notes": "Bind the session to one principal. Caller identity is authentication.",
    },
    {
        "id": "CEE-0306",
        "family_id": "QF-0004",
        "control_id": "CTRL-0048",
        "diagnostic_job": "slow_cutoff",
        "strong": [
            "A dependency that is too slow or error-prone is cut off automatically.",
            "Error-rate or timeout thresholds move the dependency from serving to blocked.",
        ],
        "supporting": [
            "A timeout count is recorded without a cutoff that stops serving.",
        ],
        "insufficient_alone": [
            "A timeout exists on a single call with no persistent-unhealthy cutoff.",
        ],
        "contradiction": [
            "Automatic cutoff is explicitly disabled for a slow or erroring dependency.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Slow-or-erroring cutoffs. Unavailable/failover is degrade_path. Wait bounds are bound_work.",
    },
]
