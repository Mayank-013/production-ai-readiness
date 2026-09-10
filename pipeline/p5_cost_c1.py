"""Phase 5.6 — Cost / Resource pack.

QF-0021 was reserved here from the agent-runtime proposal.
QF-0058 and QF-0060 have no supporting control.
"""

from __future__ import annotations

P5_COST_SPECS: list[dict] = [
    {
        "id": "CEE-0601",
        "family_id": "QF-0021",
        "control_id": "CTRL-0288",
        "diagnostic_job": "resource_bound",
        "strong": [
            "Short-term state has a TTL or sliding-window eviction so it cannot grow without bound.",
            "A named apply_session_ttl evicts session or cache entries.",
        ],
        "supporting": [
            "A max size constant exists without an eviction path.",
        ],
        "insufficient_alone": [
            "A store is used with no bound.",
        ],
        "contradiction": [
            "TTL or eviction is explicitly disabled on the growing store.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "What can grow without bound. Quotas are quota_capacity.",
    },
    {
        "id": "CEE-0602",
        "family_id": "QF-0022",
        "control_id": "CTRL-0017",
        "diagnostic_job": "quota_capacity",
        "strong": [
            "Service quotas are sized for the deployment pattern and growth before production.",
            "A named determine_service_quota accounts for availability and consumption growth.",
        ],
        "supporting": [
            "A quota number is configured without a sizing step.",
        ],
        "insufficient_alone": [
            "Cloud default quotas are relied on with no review.",
        ],
        "contradiction": [
            "Quota sizing is explicitly skipped.",
        ],
        "evidence_sources": ["config", "ops"],
        "notes": "Capacity sizing. Alarms on quota errors are quota_alarm.",
    },
    {
        "id": "CEE-0603",
        "family_id": "QF-0053",
        "control_id": "CTRL-0291",
        "diagnostic_job": "inference_cache",
        "strong": [
            "Stable prompt prefixes or prior inference results are cached so equivalent work is not paid twice.",
            "A named prompt_cache or inference_cache is enabled on the model path.",
        ],
        "supporting": [
            "A cache library is imported without a prompt or inference cache.",
        ],
        "insufficient_alone": [
            "HTTP caching is treated as inference caching.",
        ],
        "contradiction": [
            "Prompt or inference caching is explicitly disabled.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Reuse of stable model work. Resource growth bounds are resource_bound.",
    },
    {
        "id": "CEE-0604",
        "family_id": "QF-0059",
        "control_id": "CTRL-0022",
        "diagnostic_job": "quota_alarm",
        "strong": [
            "Quota or constraint errors are scanned and an alert fires before hard limits are hit.",
            "A named quota_alarm watches logs or metrics for constraint errors.",
        ],
        "supporting": [
            "Quota metrics are exported without an alarm.",
        ],
        "insufficient_alone": [
            "A logger records a quota error with no alert.",
        ],
        "contradiction": [
            "Quota alarming is explicitly skipped.",
        ],
        "evidence_sources": ["ops", "code"],
        "notes": "Alarm on quota proximity. Sizing the quota is quota_capacity.",
    },
]
