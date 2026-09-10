"""Phase 5.6 — Cost / Resource pack."""

from __future__ import annotations

from pipeline.common import ROOT
from pipeline.p5_cost_c1 import P5_COST_SPECS
from pipeline.p5_cost_observe import P5_COST_FAMILY_EXPECTATION, collect_p5_cost_observations
from pipeline.p5_pack_write import assess_pack, domain_paths, write_domain_pack

P5_COST_REPO = "p5_cost_v1"
P5_COST_FIXTURE = ROOT / "pipeline" / "fixtures" / "p5_cost_v1"
EXPECTED_P5_COST = 4
DROPPED = ["QF-0058", "QF-0060"]

P5_COST_REFERENCES = [
    {"family_id": "QF-0021", "state": "SATISFIED", "notes": "apply_session_ttl evicts short-term state."},
    {"family_id": "QF-0022", "state": "PARTIAL", "notes": "service_quota is set. No sizing step."},
    {"family_id": "QF-0053", "state": "UNKNOWN", "notes": "No inference cache. Absence is UNKNOWN."},
    {"family_id": "QF-0059", "state": "FAIL", "notes": "skip_quota_alarm = True is contradiction evidence."},
]

P5_COST_ACTIONS = {
    "QF-0022": {
        "title": "Size service quotas for growth",
        "actions": [
            "Determine service quotas from deployment pattern and growth.",
            "Keep the configured number, and add a sizing step.",
            "Do not rely on cloud defaults alone.",
        ],
    },
    "QF-0059": {
        "title": "Stop skipping quota alarms",
        "actions": [
            "Remove skip_quota_alarm.",
            "Alert when quota or constraint errors appear in logs or metrics.",
            "Intervene before the hard limit is hit.",
        ],
    },
}

P5_COST_PLAYBOOKS = [
    {
        "family_id": "QF-0022",
        "assessment_state": "PARTIAL",
        "evidence_class": "quota_number_no_sizing",
        "kind": "finding",
        "evidence_found": ["service_quota is set to 1000."],
        "evidence_missing": ["A determine_service_quota step that accounts for growth."],
        "problem": "A quota number exists without a sizing step for the deployment pattern.",
        "why_it_matters": "An arbitrary quota either wastes headroom or fails under real growth.",
        "implementation_options": [
            "Add determine_service_quota from availability and consumption growth.",
            "Review the number when the serving shape changes.",
            "Keep the alarm family separate.",
        ],
        "verification": [
            "A sizing function or review produces the quota.",
            "skip_quota_sizing is not True.",
        ],
        "completion_evidence": [
            "A named determine_service_quota path.",
            "The configured number is an output of that step.",
        ],
    },
    {
        "family_id": "QF-0059",
        "assessment_state": "FAIL",
        "evidence_class": "skip_quota_alarm",
        "kind": "finding",
        "evidence_found": ["skip_quota_alarm is set to True."],
        "evidence_missing": ["An alarm on quota or constraint errors."],
        "problem": "Quota alarming is explicitly skipped. Hard limits can be hit without a page.",
        "why_it_matters": "Constraint errors become outages and retry storms before anyone is notified.",
        "implementation_options": [
            "Remove skip_quota_alarm.",
            "Scan logs or metrics for quota errors and alert.",
            "Page before the hard limit is exhausted.",
        ],
        "verification": [
            "The contradiction flag is gone.",
            "A quota error produces an alert.",
        ],
        "completion_evidence": [
            "skip_quota_alarm is not True.",
            "A quota_alarm or quota_constraint_alert exists.",
        ],
    },
]


def p5_cost_paths(*, root=None):
    return domain_paths("p5_cost", root=root, extra_guards=["p5_rag_freeze", "p5_ops_freeze"])


def assess_p5_cost(observations, *, repo=P5_COST_REPO):
    return assess_pack(observations, P5_COST_SPECS, P5_COST_FAMILY_EXPECTATION, repo=repo)


def write_p5_cost_pack(*, paths=None):
    return write_domain_pack(
        pack="cost_resource",
        phase="5.6",
        dest_name="p5_cost",
        repo=P5_COST_REPO,
        fixture=P5_COST_FIXTURE,
        specs=P5_COST_SPECS,
        references=P5_COST_REFERENCES,
        actions=P5_COST_ACTIONS,
        playbooks=P5_COST_PLAYBOOKS,
        collect=collect_p5_cost_observations,
        expectation_map=P5_COST_FAMILY_EXPECTATION,
        inherited_c1=[],
        dropped=DROPPED,
        blocked={"QF-0001", "QF-0003"},
        next_gate="phase_5_complete",
        later_domains=[],
        extra_guard_keys=["p5_rag_freeze", "p5_ops_freeze"],
        paths=paths,
    )
