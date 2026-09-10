"""Phase 5.5 — Observability / Operations pack."""

from __future__ import annotations

from pipeline.common import ROOT
from pipeline.p5_ops_c1 import P5_OPS_SPECS
from pipeline.p5_ops_observe import P5_OPS_FAMILY_EXPECTATION, collect_p5_ops_observations
from pipeline.p5_pack_write import assess_pack, domain_paths, write_domain_pack

P5_OPS_REPO = "p5_ops_v1"
P5_OPS_FIXTURE = ROOT / "pipeline" / "fixtures" / "p5_ops_v1"
EXPECTED_P5_OPS = 4
DROPPED = ["QF-0039", "QF-0047"]
INHERITED_C1 = ["QF-0018", "QF-0019"]

P5_OPS_REFERENCES = [
    {"family_id": "QF-0037", "state": "SATISFIED", "notes": "rollback_release reverts a shipped version."},
    {"family_id": "QF-0038", "state": "PARTIAL", "notes": "rollout_percent is set. No canary comparison."},
    {"family_id": "QF-0056", "state": "UNKNOWN", "notes": "No incident playbook. Absence is UNKNOWN."},
    {"family_id": "QF-0057", "state": "FAIL", "notes": "skip_postmortem = True is contradiction evidence."},
]

P5_OPS_ACTIONS = {
    "QF-0038": {
        "title": "Stage the rollout before full promotion",
        "actions": [
            "Run a canary or staged rollout under real load.",
            "Compare control and experimental serving before 100% promotion.",
            "Do not treat a percentage alone as a canary.",
        ],
    },
    "QF-0057": {
        "title": "Stop skipping postmortems",
        "actions": [
            "Remove skip_postmortem.",
            "Write incidents on a standard template that captures root cause.",
            "Use the writeups for trend analysis.",
        ],
    },
}

P5_OPS_PLAYBOOKS = [
    {
        "family_id": "QF-0038",
        "assessment_state": "PARTIAL",
        "evidence_class": "rollout_percent_no_canary",
        "kind": "finding",
        "evidence_found": ["rollout_percent is set to 10."],
        "evidence_missing": ["A canary_rollout that compares control and experimental serving."],
        "problem": "A rollout percentage exists without a canary comparison under real load.",
        "why_it_matters": "Partial traffic without a control comparison cannot tell a regression from noise.",
        "implementation_options": [
            "Add a canary_rollout with control and experimental systems.",
            "Promote only after the canary stays healthy.",
            "Keep rollback wired to the same telemetry.",
        ],
        "verification": [
            "A canary path runs before full promotion.",
            "skip_staged_rollout is not True.",
        ],
        "completion_evidence": [
            "A named canary_rollout or canary_deployment.",
            "The percentage is attached to that canary, not used alone.",
        ],
    },
    {
        "family_id": "QF-0057",
        "assessment_state": "FAIL",
        "evidence_class": "skip_postmortem",
        "kind": "finding",
        "evidence_found": ["skip_postmortem is set to True."],
        "evidence_missing": ["A standard postmortem template after incidents."],
        "problem": "Postmortems are explicitly skipped. After-action learning is disabled.",
        "why_it_matters": "Without a consistent writeup, the same trigger repeats and trends are invisible.",
        "implementation_options": [
            "Remove skip_postmortem.",
            "Adopt a postmortem_template that captures root cause and trigger.",
            "Review writeups on a schedule.",
        ],
        "verification": [
            "The contradiction flag is gone.",
            "A completed incident produces a templated postmortem.",
        ],
        "completion_evidence": [
            "skip_postmortem is not True.",
            "A postmortem_template or write_postmortem path exists.",
        ],
    },
]


def p5_ops_paths(*, root=None):
    return domain_paths("p5_ops", root=root, extra_guards=["p5_rag_freeze"])


def assess_p5_ops(observations, *, repo=P5_OPS_REPO):
    return assess_pack(observations, P5_OPS_SPECS, P5_OPS_FAMILY_EXPECTATION, repo=repo)


def write_p5_ops_pack(*, paths=None):
    return write_domain_pack(
        pack="observability_ops",
        phase="5.5",
        dest_name="p5_ops",
        repo=P5_OPS_REPO,
        fixture=P5_OPS_FIXTURE,
        specs=P5_OPS_SPECS,
        references=P5_OPS_REFERENCES,
        actions=P5_OPS_ACTIONS,
        playbooks=P5_OPS_PLAYBOOKS,
        collect=collect_p5_ops_observations,
        expectation_map=P5_OPS_FAMILY_EXPECTATION,
        inherited_c1=INHERITED_C1,
        dropped=DROPPED,
        blocked=set(INHERITED_C1),
        next_gate="p5_cost_resource",
        later_domains=["cost_resource"],
        extra_guard_keys=["p5_rag_freeze"],
        paths=paths,
    )
