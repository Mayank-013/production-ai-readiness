"""Phase 5.4 — RAG / Data control pack.

QF-0007 and QF-0029 are not canonical. QF-0024 has no supporting control.
Eval siblings stay on Phase 5.1.

Absence of evidence is UNKNOWN, not FAIL.
"""

from __future__ import annotations

P5_RAG_SPECS: list[dict] = [
    {
        "id": "CEE-0401",
        "family_id": "QF-0006",
        "control_id": "CTRL-0152",
        "diagnostic_job": "grounding",
        "strong": [
            "Generated output is checked against retrieved or allowed evidence before it is returned.",
            "A named groundedness_check ties the answer to cited sources.",
        ],
        "supporting": [
            "Citations are attached without a groundedness check.",
        ],
        "insufficient_alone": [
            "A prompt tells the model to use only the provided context.",
        ],
        "contradiction": [
            "Groundedness checking is explicitly skipped on the serving path.",
        ],
        "evidence_sources": ["code"],
        "notes": "Exist-stance grounding. Faithfulness evaluators are grounding_eval.",
    },
    {
        "id": "CEE-0402",
        "family_id": "QF-0028",
        "control_id": "CTRL-0014",
        "diagnostic_job": "query_reformulation",
        "strong": [
            "Agent queries are rewritten before they hit the index so terminology can match.",
            "A named reformulate_query step runs on the retrieval path.",
        ],
        "supporting": [
            "A query-rewrite hint exists without a reformulation function.",
        ],
        "insufficient_alone": [
            "The raw user string is sent to the index unchanged.",
        ],
        "contradiction": [
            "Query reformulation is explicitly skipped.",
        ],
        "evidence_sources": ["code"],
        "notes": "Rewrite before retrieval. Retrieval metrics are retrieval_eval.",
    },
    {
        "id": "CEE-0403",
        "family_id": "QF-0055",
        "control_id": "CTRL-0273",
        "diagnostic_job": "artifact_versioning",
        "strong": [
            "Datasets, models, or prompts are referenced by versioned remote pointers, not copied into git.",
            "A named artifact_version_pointer records the blob or warehouse revision for a run.",
        ],
        "supporting": [
            "A model or dataset name is pinned without a remote version pointer.",
        ],
        "insufficient_alone": [
            "Large blobs are stored in the repository.",
        ],
        "contradiction": [
            "Artifact versioning is explicitly disabled so runs cannot be reproduced.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Reproduce a run via pointers. Model tamper-evidence is model_supply_chain.",
    },
    {
        "id": "CEE-0404",
        "family_id": "QF-0063",
        "control_id": "CTRL-0254",
        "diagnostic_job": "data_retention",
        "strong": [
            "A retention period and automated deletion exist for monitoring or user data.",
            "A named retention_policy deletes data when the period ends.",
        ],
        "supporting": [
            "A retention period is documented without a delete job.",
        ],
        "insufficient_alone": [
            "Logs exist with no stated keep-time.",
        ],
        "contradiction": [
            "Data is explicitly retained forever with deletion disabled.",
        ],
        "evidence_sources": ["code", "ops"],
        "notes": "How long data is kept and what deletes it. Egress filtering is sensitive_egress.",
    },
]
