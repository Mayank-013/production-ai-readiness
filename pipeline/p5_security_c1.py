"""Phase 5.2 — AI Security control pack.

Representative pack. Not 53 families. Not 333 controls.
Inherited C1 security families stay on the frozen C1 dest.
QF-0052 model_supply_chain is dropped: no supporting control.

Absence of evidence is UNKNOWN, not FAIL.
"""

from __future__ import annotations

P5_SECURITY_SPECS: list[dict] = [
    {
        "id": "CEE-0201",
        "family_id": "QF-0031",
        "control_id": "CTRL-0012",
        "diagnostic_job": "agent_sec_assessment",
        "strong": [
            "A security assessment explicitly covers agent tool invocations, delegation, and prompt-injection chains.",
            "A named agent_security_assessment exercises agent-specific misuse, not only generic appsec.",
        ],
        "supporting": [
            "An assessment plan lists agent-misuse scenarios without an executable assessment.",
        ],
        "insufficient_alone": [
            "A generic OWASP or dependency scan with no agent-specific scope.",
            "Security policy prose without an assessment that can run.",
        ],
        "contradiction": [
            "Security assessment scope explicitly excludes agent, tool, or LLM behavior.",
        ],
        "evidence_sources": ["tests", "architecture"],
        "notes": "Assessment coverage of agent threats. The injection control itself is QF-0030. Ongoing exercises are red_team.",
    },
    {
        "id": "CEE-0202",
        "family_id": "QF-0040",
        "control_id": "CTRL-0284",
        "diagnostic_job": "sandbox_isolation",
        "strong": [
            "Tool or computer-use execution runs in an isolated sandbox separate from the agent harness.",
            "Harness state and credentials stay in trusted infrastructure while compute uses a sandbox client.",
        ],
        "supporting": [
            "A sandbox client is named without a harness-versus-compute split.",
        ],
        "insufficient_alone": [
            "Docker is mentioned with tools executing beside secrets.",
            "A process-boundary comment with no isolation boundary.",
        ],
        "contradiction": [
            "Sandbox isolation is explicitly disabled for high-risk tools.",
        ],
        "evidence_sources": ["code", "architecture"],
        "notes": "Harness vs sandbox compute. Least privilege is permission_boundary.",
    },
    {
        "id": "CEE-0203",
        "family_id": "QF-0041",
        "control_id": "CTRL-0289",
        "diagnostic_job": "tool_catalog_scope",
        "strong": [
            "Each turn offers only task-relevant tools instead of the full catalog.",
            "A selector prunes the tool schema before the model call.",
        ],
        "supporting": [
            "A tool allowlist exists without per-turn selection.",
        ],
        "insufficient_alone": [
            "A tools list is documented and always injected in full.",
        ],
        "contradiction": [
            "Every registered tool, including admin or destructive tools, is forced into every turn.",
        ],
        "evidence_sources": ["code"],
        "notes": "Which tools are offered. Authorization is permission_boundary. Whether the agent picked the right tool is tool_selection_eval.",
    },
    {
        "id": "CEE-0204",
        "family_id": "QF-0049",
        "control_id": "CTRL-0057",
        "diagnostic_job": "sensitive_egress",
        "strong": [
            "Agent or model output is scanned for PII, credentials, or classified data before egress.",
            "A named output filter masks or blocks sensitive data on the response path.",
        ],
        "supporting": [
            "Logs or eval exports redact identifiers without a serving-path output scan.",
        ],
        "insufficient_alone": [
            "A comment says not to paste secrets into prompts.",
            "Logging exists with no output-side filter.",
        ],
        "contradiction": [
            "Output scanning is explicitly skipped on the egress path.",
        ],
        "evidence_sources": ["code"],
        "notes": "Egress from outputs and handoffs. Embedded source secrets are hardcoded_secrets.",
    },
    {
        "id": "CEE-0205",
        "family_id": "QF-0051",
        "control_id": "CTRL-0229",
        "diagnostic_job": "red_team",
        "strong": [
            "Scheduled red-team or adversarial exercises run after the system ships.",
            "Experts or a recurring job attempt jailbreak, injection, and extraction on a live or staging path.",
        ],
        "supporting": [
            "An adversarial prompt suite exists without a scheduled post-ship exercise.",
        ],
        "insufficient_alone": [
            "A README mentions red team with no runnable exercise.",
            "A single launch pen test with no recurrence.",
        ],
        "contradiction": [
            "Post-ship red teaming is explicitly disabled.",
        ],
        "evidence_sources": ["tests", "ops"],
        "notes": "Ongoing adversarial exercises. Assessment coverage is agent_sec_assessment. The injection control is QF-0030.",
    },
    {
        "id": "CEE-0206",
        "family_id": "QF-0062",
        "control_id": "CTRL-0097",
        "diagnostic_job": "dependency_integrity",
        "strong": [
            "Release confirms third-party dependencies are from trusted sources before production.",
            "A provenance or trusted-source gate blocks unreviewed packages on the serving path.",
        ],
        "supporting": [
            "A lockfile or SBOM exists without a trusted-source verify gate.",
        ],
        "insufficient_alone": [
            "A requirements or package manifest exists with no verify step.",
        ],
        "contradiction": [
            "Dependency scanning or trusted-source verification is explicitly skipped.",
        ],
        "evidence_sources": ["ci", "dependencies"],
        "notes": "Software and package trust. Model-artifact tampering is model_supply_chain and is not in this pack.",
    },
]
