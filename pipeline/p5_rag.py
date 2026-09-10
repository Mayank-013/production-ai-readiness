"""Phase 5.4 — RAG / Data pack."""

from __future__ import annotations

from pathlib import Path

from pipeline.common import ROOT
from pipeline.p5_pack_write import assess_pack, domain_paths, write_domain_pack
from pipeline.p5_rag_c1 import P5_RAG_SPECS
from pipeline.p5_rag_observe import P5_RAG_FAMILY_EXPECTATION, collect_p5_rag_observations

P5_RAG_REPO = "p5_rag_v1"
P5_RAG_FIXTURE = ROOT / "pipeline" / "fixtures" / "p5_rag_v1"
EXPECTED_P5_RAG = 4
DROPPED = ["QF-0007", "QF-0029", "QF-0024"]
INHERITED_EVAL = ["QF-0027", "QF-0044", "QF-0045", "QF-0054"]

P5_RAG_REFERENCES = [
    {"family_id": "QF-0006", "state": "SATISFIED", "notes": "groundedness_check ties the answer to sources."},
    {"family_id": "QF-0028", "state": "PARTIAL", "notes": "A rewrite hint exists. No reformulate_query."},
    {"family_id": "QF-0055", "state": "UNKNOWN", "notes": "No artifact version pointer. Absence is UNKNOWN."},
    {"family_id": "QF-0063", "state": "FAIL", "notes": "retain_forever = True is contradiction evidence."},
]

P5_RAG_ACTIONS = {
    "QF-0028": {
        "title": "Reformulate queries before retrieval",
        "actions": [
            "Rewrite agent queries so they match index terminology.",
            "Keep the hint, and add a reformulate_query step on the retrieval path.",
            "Do not send the raw user string as the only query.",
        ],
    },
    "QF-0063": {
        "title": "Stop retaining monitoring or user data forever",
        "actions": [
            "Remove retain_forever from the data path.",
            "Set a retention period and an automated delete job.",
            "Honor individual deletion requests.",
        ],
    },
}

P5_RAG_PLAYBOOKS = [
    {
        "family_id": "QF-0028",
        "assessment_state": "PARTIAL",
        "evidence_class": "rewrite_hint_no_reformulator",
        "kind": "finding",
        "evidence_found": ["query_rewrite_hint is set."],
        "evidence_missing": ["A reformulate_query function on the retrieval path."],
        "problem": "A rewrite hint exists, but queries are not reformulated before they hit the index.",
        "why_it_matters": "Agent wording often misses index terms. Retrieval then looks like a quality bug.",
        "implementation_options": [
            "Add a reformulate_query step before the index call.",
            "Expand acronyms and aliases that the corpus uses.",
            "Keep the original query as a fallback, not the only query.",
        ],
        "verification": [
            "A mismatched-term query is rewritten before retrieval.",
            "The index sees the reformulated string.",
        ],
        "completion_evidence": [
            "A named reformulate_query function.",
            "skip_query_reformulation is not True.",
        ],
    },
    {
        "family_id": "QF-0063",
        "assessment_state": "FAIL",
        "evidence_class": "retain_forever",
        "kind": "finding",
        "evidence_found": ["retain_forever is set to True."],
        "evidence_missing": ["A retention period and automated deletion."],
        "problem": "Monitoring or user data is explicitly kept forever. Deletion is disabled.",
        "why_it_matters": "Unbounded retention increases leak surface and violates stated keep-times.",
        "implementation_options": [
            "Remove retain_forever.",
            "Set retention_days and an automated delete job.",
            "Document how individual deletion requests are handled.",
        ],
        "verification": [
            "The contradiction flag is gone.",
            "Expired records are deleted by a job.",
        ],
        "completion_evidence": [
            "retain_forever is not True.",
            "A retention_policy or automated_deletion path exists.",
        ],
    },
]


def p5_rag_paths(*, root: Path | None = None):
    return domain_paths("p5_rag", root=root)


def assess_p5_rag(observations, *, repo=P5_RAG_REPO):
    return assess_pack(observations, P5_RAG_SPECS, P5_RAG_FAMILY_EXPECTATION, repo=repo)


def write_p5_rag_pack(*, paths=None):
    return write_domain_pack(
        pack="rag_data",
        phase="5.4",
        dest_name="p5_rag",
        repo=P5_RAG_REPO,
        fixture=P5_RAG_FIXTURE,
        specs=P5_RAG_SPECS,
        references=P5_RAG_REFERENCES,
        actions=P5_RAG_ACTIONS,
        playbooks=P5_RAG_PLAYBOOKS,
        collect=collect_p5_rag_observations,
        expectation_map=P5_RAG_FAMILY_EXPECTATION,
        inherited_c1=[],
        dropped=DROPPED,
        blocked=set(INHERITED_EVAL),
        next_gate="p5_observability_ops",
        later_domains=["observability_ops", "cost_resource"],
        extra_guard_keys=[],
        paths=paths,
    )
