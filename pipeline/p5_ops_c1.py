"""Phase 5.5 — Observability / Operations pack.

QF-0018 and QF-0019 stay on C1. QF-0039 and QF-0047 have no supporting control.
"""

from __future__ import annotations

P5_OPS_SPECS: list[dict] = [
    {
        "id": "CEE-0501",
        "family_id": "QF-0037",
        "control_id": "CTRL-0010",
        "diagnostic_job": "rollback_capability",
        "strong": [
            "A rehearsed rollback path reverts a prompt, model, or agent version when quality or errors regress.",
            "A named rollback_release function is wired to the same telemetry that detects the regression.",
        ],
        "supporting": [
            "A previous version pin exists without a rollback path.",
        ],
        "insufficient_alone": [
            "Git history exists with no rollback procedure.",
        ],
        "contradiction": [
            "Rollback is explicitly disabled after a behavior change ships.",
        ],
        "evidence_sources": ["code", "deployment"],
        "notes": "Rehearsed rollback. Change records are change_tracking.",
    },
    {
        "id": "CEE-0502",
        "family_id": "QF-0038",
        "control_id": "CTRL-0037",
        "diagnostic_job": "rollout_strategy",
        "strong": [
            "A canary or staged rollout exposes the change to real load before full promotion.",
            "A named canary_rollout compares control and experimental serving.",
        ],
        "supporting": [
            "A rollout percentage is configured without a canary comparison.",
        ],
        "insufficient_alone": [
            "A deploy script promotes 100% immediately.",
        ],
        "contradiction": [
            "Staged rollout is explicitly skipped for production promotion.",
        ],
        "evidence_sources": ["deployment", "ci"],
        "notes": "How the change is exposed. Rollback is rollback_capability.",
    },
    {
        "id": "CEE-0503",
        "family_id": "QF-0056",
        "control_id": "CTRL-0034",
        "diagnostic_job": "incident_playbook",
        "strong": [
            "A written incident playbook covers anticipated production failures before they happen.",
            "A named incident_playbook lists ordered response steps.",
        ],
        "supporting": [
            "An incident channel exists without a playbook.",
        ],
        "insufficient_alone": [
            "On-call is assigned with no written steps.",
        ],
        "contradiction": [
            "Incident playbooks are explicitly skipped.",
        ],
        "evidence_sources": ["ops"],
        "notes": "Pre-written response. After-action writeup is postmortem.",
    },
    {
        "id": "CEE-0504",
        "family_id": "QF-0057",
        "control_id": "CTRL-0166",
        "diagnostic_job": "postmortem",
        "strong": [
            "Incidents are written up with a standard postmortem template that captures root cause.",
            "A named postmortem_template is used after production incidents.",
        ],
        "supporting": [
            "An incident ticket exists without a postmortem template.",
        ],
        "insufficient_alone": [
            "A chat thread is treated as the only after-action record.",
        ],
        "contradiction": [
            "Postmortems are explicitly skipped after incidents.",
        ],
        "evidence_sources": ["ops"],
        "notes": "After-action capture. The live response steps are incident_playbook.",
    },
]
