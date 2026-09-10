"""Mechanical agent brief for Cursor / host-model product UX.

Built from existing assessment rows. No LLM.
Attach skill_id only when the frozen catalog matches family+state+class.
Unverified families are a full hunt list (one row per family), not a cap of five.

brief.json keeps machine IDs and hunt hints for the host agent.
brief.md is human-readable: what's working, what's missing, what to hunt.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.common import CONSOLIDATION, read_jsonl
from pipeline.control_evidence_contract import ControlError
from pipeline.repo_analysis_hunt import (
    PACK_LOOK_IN,
    binding_look_in,
    binding_noun,
    hunt_hint,
    hunt_label,
    pack_label,
)
from pipeline.repo_analysis_suggest import select_skill_suggestions
from pipeline.repo_analysis_packs import PACKS, pack_by_family
from pipeline.skills import SKILL_SPECS, attach_skills, skill_paths

# Plain-language labels for product UX. Codes stay in JSON for the agent.
JOB_LABELS: dict[str, str] = {
    "bound_work": "Limits on how long or how much work a request can run",
    "degrade_path": "Graceful fallback when a dependency is down",
    "eval_gate": "Quality checks before shipping model or prompt changes",
    "permission_boundary": "Who is allowed to do what",
    "authentication": "How callers are identified before they are authorized",
    "encrypt_transit": "Encryption for data in transit (TLS)",
    "encrypt_rest": "Encryption for data at rest",
    "unhealthy_detect": "Detecting unhealthy services or dependencies",
    "telemetry_exist": "Logging and operational telemetry",
    "prompt_injection": "Protection against prompt injection",
    "input_validation": "Validation of structured inputs",
    "hardcoded_secrets": "Keeping secrets out of the source tree",
    "retrieval_eval": "Measuring whether retrieval returns relevant sources",
    "tool_selection_eval": "Checking that the agent picks the right tool",
    "online_eval": "Measuring quality on live or sampled production traffic",
    "eval_dataset": "Labeled examples so behavior can be scored",
    "grounding_eval": "Checking that answers stay faithful to retrieved evidence",
    "eval_leakage": "Keeping train, eval, and retrieved data from leaking into each other",
    "labeled_examples": "Labeled examples so behavior can be scored",
    "train_eval_leakage": "Keeping train, eval, and retrieved data from leaking into each other",
    "agent_sec_assessment": "Security review aimed at agent misuse",
    "sandbox_isolation": "Isolating tool execution from the control plane",
    "tool_catalog_scope": "Which tools the agent can use on a given turn",
    "sensitive_egress": "Stopping sensitive data from leaving in outputs",
    "red_team": "Adversarial testing after the system ships",
    "dependency_integrity": "Trusting third-party or generated dependencies before they ship",
    "human_approval": "Human approval before high-impact actions",
    "idempotent_replay": "Safe behavior if the same operation runs twice",
    "structured_output": "Enforcing a machine-readable response shape",
    "retry_classification": "Separating retryable failures from ones that must not retry",
    "session_binding": "Binding agent sessions so they cannot be confused",
    "slow_cutoff": "Cutting off a dependency that is too slow or error-prone",
    "grounding": "Keeping generated output tied to retrieved evidence",
    "query_reformulation": "Rewriting queries so retrieval can match the index",
    "artifact_versioning": "Versioning datasets, models, and prompts for replay",
    "data_retention": "How long data is kept and how it is deleted",
    "rollback_capability": "Ability to roll back a bad release",
    "rollout_strategy": "Controlled rollout of changes",
    "incident_playbook": "Incident response playbooks",
    "postmortem": "Post-incident learning",
    "resource_bound": "Bounds on resources that can grow without limit",
    "quota_capacity": "Capacity and quota planning",
    "inference_cache": "Reusing stable results so equivalent work is not paid for twice",
    "quota_alarm": "Alerts when cost or quota is about to blow",
}

TRAIT_LABELS: dict[str, str] = {
    "backend_service": "backend service",
    "internet_facing": "internet-facing",
    "stateful": "stateful",
    "multi_tenant": "multi-tenant",
    "background_worker": "background workers",
    "on_device": "on-device",
    "ci_pipeline": "CI pipeline",
    "serves_production": "production serving",
    "ships_behavior_change": "ships behavior changes",
    "human_user": "human users",
    "external_caller": "external callers",
    "service_to_service": "service-to-service calls",
    "external_dependency": "external dependencies",
    "persists_data": "persists data",
    "uses_cache": "uses a cache",
    "public_api": "public API",
    "third_party_code": "third-party dependencies",
    "llm": "large language models",
    "prompt_managed": "managed prompts",
    "generative_output": "generative output",
    "model_endpoint": "model endpoints",
    "model_training": "model training",
    "model_artifact": "model artifacts",
    "retrieval_system": "retrieval",
    "rag": "RAG",
    "agent_memory": "agent memory",
    "agentic": "an agentic workflow",
    "tool_using_agent": "a tool-using agent",
    "computer_use": "computer use",
    "human_in_the_loop": "human-in-the-loop",
    "eval_harness": "an evaluation harness",
    "eval_datasets": "evaluation datasets",
    "handles_secrets": "handles secrets",
    "retains_user_data": "retains user data",
    "produces_logs": "produces logs",
    "untrusted_input": "untrusted input",
    "untrusted_context": "untrusted context",
    "sessioned_auth": "sessioned auth",
    "oncall_owned": "on-call ownership",
    "security_operations": "security operations",
    "metered_cost": "metered cost",
    "cloud_quota": "cloud quotas",
}


def job_label(diagnostic_job: str) -> str:
    if diagnostic_job.startswith("QF-"):
        return "This production control"
    return JOB_LABELS.get(diagnostic_job, diagnostic_job.replace("_", " "))


def trait_sentence(traits: list[str]) -> str:
    if not traits:
        return "No production AI traits were detected in this repository."
    labels = [TRAIT_LABELS.get(t, t.replace("_", " ")) for t in traits]
    if len(labels) == 1:
        return f"This repository looks like a system that uses {labels[0]}."
    if len(labels) == 2:
        return f"This repository looks like a system with {labels[0]} and {labels[1]}."
    return (
        "This repository looks like a system with "
        + ", ".join(labels[:-1])
        + f", and {labels[-1]}."
    )


def _spec_jobs() -> dict[str, str]:
    out: dict[str, str] = {}
    for pack in PACKS:
        for spec in pack["specs"]:
            out[spec["family_id"]] = spec["diagnostic_job"]
    return out


def _pack_order() -> dict[str, int]:
    return {pack["id"]: i for i, pack in enumerate(PACKS)}


def build_agent_brief(
    *,
    report: dict,
    findings: list[dict],
    playbooks: list[dict],
    questions: list[dict],
    assessments: list[dict],
    skills: list[dict] | None = None,
) -> dict:
    """Product brief. Host LLM may phrase this; it must not re-score."""
    skills = skills if skills is not None else list(SKILL_SPECS)
    jobs = _spec_jobs()
    pack_rank = _pack_order()
    ownership = pack_by_family()
    by_pb = {row["id"]: row for row in playbooks}
    attachments = {
        row["finding_id"]: row for row in attach_skills(findings, skills=skills)
    }
    skill_by_id = {row["id"]: row for row in skills}

    satisfied = []
    for row in assessments:
        if row["state"] != "SATISFIED":
            continue
        job = jobs.get(row["family_id"], row["family_id"])
        satisfied.append(
            {
                "family_id": row["family_id"],
                "pack": row.get("pack") or ownership.get(row["family_id"]),
                "diagnostic_job": job,
                "label": job_label(job),
            }
        )

    brief_findings = []
    partial_without_skill = []
    for finding in findings:
        if finding["assessment_state"] == "UNKNOWN":
            raise ControlError("UNKNOWN must not appear as a finding in the brief")
        pb = by_pb.get(finding.get("playbook_id") or "")
        attach = attachments.get(finding["id"])
        job = jobs.get(finding["family_id"], finding["family_id"])
        skill_id = attach["skill_id"] if attach else None
        skill = skill_by_id.get(skill_id or "") if skill_id else None
        item = {
            "id": finding["id"],
            "family_id": finding["family_id"],
            "assessment_state": finding["assessment_state"],
            "title": finding["title"],
            "label": job_label(job),
            "diagnostic_job": job,
            "pack": finding.get("pack"),
            "evidence_class": finding.get("evidence_class"),
            "problem": pb["problem"] if pb else None,
            "next": (pb["implementation_options"][0] if pb and pb.get("implementation_options") else None),
            "playbook_available": bool(finding.get("playbook_available")),
            "skill_id": skill_id,
            "skill_name": skill["name"] if skill else None,
            "fixable": bool(skill_id),
            "actions": list(finding.get("actions") or []),
        }
        brief_findings.append(item)
        if not attach and finding["assessment_state"] in {"PARTIAL", "FAIL"}:
            partial_without_skill.append(
                {
                    "family_id": finding["family_id"],
                    "assessment_state": finding["assessment_state"],
                    "title": finding["title"],
                    "label": job_label(job),
                    "diagnostic_job": job,
                    "pack": finding.get("pack"),
                    "note": "Incomplete evidence. No automatic fix available yet.",
                }
            )

    finding_ids = {row["family_id"] for row in findings}
    for row in assessments:
        if row["state"] not in {"PARTIAL", "FAIL"}:
            continue
        if row["family_id"] in finding_ids:
            continue
        job = jobs.get(row["family_id"], row["family_id"])
        partial_without_skill.append(
            {
                "family_id": row["family_id"],
                "assessment_state": row["state"],
                "title": finding_title_for_job(job, row["state"]),
                "label": job_label(job),
                "diagnostic_job": job,
                "pack": row.get("pack") or ownership.get(row["family_id"]),
                "note": "Incomplete evidence. No automatic fix available yet.",
            }
        )

    unknown_rows = [
        row for row in questions if row.get("assessment_state") == "UNKNOWN"
    ]
    unknown_rows.sort(
        key=lambda row: (
            pack_rank.get(ownership.get(row["family_id"], ""), 99),
            row["family_id"],
            row.get("id") or "",
        )
    )
    hunt_rows = []
    seen_cards: set[str] = set()
    for row in unknown_rows:
        card_id = row.get("id") or f"{row['family_id']}:{row.get('specialization_id') or row.get('prompt')}"
        if card_id in seen_cards:
            continue
        seen_cards.add(card_id)
        job = jobs.get(row["family_id"], row["family_id"])
        pack = ownership.get(row["family_id"])
        hint = hunt_hint(job)
        bindings = dict(row.get("bindings") or {})
        look_in = list(PACK_LOOK_IN.get(pack or "", []))
        for extra in binding_look_in(bindings):
            if extra not in look_in:
                look_in.append(extra)
        hunt_rows.append(
            {
                "family_id": row["family_id"],
                "specialization_id": row.get("specialization_id"),
                "pack": pack,
                "pack_label": pack_label(pack),
                "diagnostic_job": job,
                "bindings": bindings,
                "binding": binding_noun(bindings),
                "label": hunt_label(job, bindings, job_label_fn=job_label),
                "prompt": row["prompt"],
                "look_for": hint["look_for"],
                "look_in": look_in,
                "enough_when": hint["enough_when"],
            }
        )
    grouped: list[dict] = []
    by_pack: dict[str, list[dict]] = {}
    for row in hunt_rows:
        by_pack.setdefault(row["pack"] or "other", []).append(row)
    for pack_id, _rank in sorted(pack_rank.items(), key=lambda item: item[1]):
        areas = by_pack.pop(pack_id, None)
        if not areas:
            continue
        grouped.append(
            {
                "pack": pack_id,
                "pack_label": pack_label(pack_id),
                "count": len(areas),
                "areas": areas,
            }
        )
    for pack_id, areas in by_pack.items():
        grouped.append(
            {
                "pack": pack_id,
                "pack_label": pack_label(pack_id),
                "count": len(areas),
                "areas": areas,
            }
        )

    traits = list(report.get("traits_present") or [])
    fixable = [row for row in brief_findings if row.get("skill_id")]
    suggestions = select_skill_suggestions(findings=brief_findings)
    return {
        "repo": report["repo"],
        "repo_path": report["repo_path"],
        "system_summary": trait_sentence(traits),
        "traits_present": traits,
        "applicable_families": len(report.get("applicable_families") or []),
        "applicable_c1_families": len(report.get("applicable_c1_families") or []),
        "by_state": dict(report["by_state"]),
        "satisfied": satisfied,
        "findings": brief_findings,
        "partial_without_skill": partial_without_skill,
        "fixable_count": len(fixable),
        "unknown": {
            "count": report["by_state"].get("UNKNOWN", 0),
            "specializations": len(hunt_rows),
            "questions": hunt_rows,
            "grouped": grouped,
            "hunt_required": True,
            "note": (
                "Not verified by detectors. Host must search the user's repo for every "
                "area before writing the review. Spotted files are not SATISFIED. "
                "Missing files are not FAIL. Do not patch these areas."
            ),
        },
        "composite_score": None,
        "skill_suggestions": suggestions,
        "skills": {
            "pipeline": "locked",
            "host_agent": "hunt_then_search_skills_for_this_repo_and_apply_catalog_skill_id_only",
            "catalog_skill_ids": sorted({row["skill_id"] for row in fixable}),
        },
        "note": (
            "Mechanical brief for the host coding agent. "
            "User-facing text must stay human-readable (no QF-/SKL- codes). "
            "Do not invent SATISFIED or FAIL. Hunt every unverified area, then narrate. "
            "Do not patch UNKNOWN. Apply only findings that carry skill_id."
        ),
    }


def finding_title_for_job(job: str, state: str) -> str:
    label = job_label(job)
    if state == "PARTIAL":
        return f"{label} is only partly in place"
    return f"{label} has a confirmed problem"


def render_brief_md(brief: dict) -> str:
    """Human-readable product brief. Codes live in brief.json only."""
    by = brief["by_state"]
    lines = [
        f"# Agent brief — {brief['repo']}",
        "",
        "_Internal. Do not send this file to the customer. Rewrite a review that only cites their files._",
        "",
        brief.get("system_summary") or trait_sentence(brief.get("traits_present") or []),
        "",
        "## What looks in place",
        "",
    ]
    if brief["satisfied"]:
        for row in brief["satisfied"]:
            lines.append(f"- {row.get('label') or job_label(row['diagnostic_job'])}")
        lines.append("")
    else:
        lines.append("- Nothing in the applicable set was fully evidenced yet.")
        lines.append("")

    lines.append("## What is missing or incomplete")
    lines.append("")
    missing_any = False
    for finding in brief["findings"]:
        missing_any = True
        label = finding.get("label") or finding["title"]
        if finding.get("fixable"):
            lines.append(f"- **Needs a fix:** {label}")
        else:
            lines.append(f"- **Incomplete:** {label}")
        if finding.get("problem"):
            lines.append(f"  {finding['problem']}")
        if finding.get("next"):
            lines.append(f"  **Do next:** {finding['next']}")
        elif finding.get("actions"):
            lines.append(f"  **Do next:** {finding['actions'][0]}")
        lines.append("")
    for row in brief["partial_without_skill"]:
        # Skip duplicates already listed as findings without skill
        if any(f["family_id"] == row["family_id"] for f in brief["findings"]):
            continue
        missing_any = True
        lines.append(f"- **Incomplete:** {row.get('label') or row['title']}")
        lines.append(f"  {row.get('note') or 'Needs more evidence or a manual fix.'}")
        lines.append("")
    if not missing_any:
        lines.append("- No incomplete or broken controls were evidenced in this scan.")
        lines.append("")

    unknown = brief["unknown"]
    lines.append("## Agent hunt list (do not send to the customer)")
    lines.append("")
    if unknown["count"] == 0:
        lines.append("- Everything applicable was scored from repository evidence.")
        lines.append("")
    else:
        spec_n = unknown.get("specializations") or len(unknown.get("questions") or [])
        extra = (
            f" That is {spec_n} specialized questions for this system."
            if spec_n and spec_n != unknown["count"]
            else ""
        )
        lines.append(
            f"The scan could not score **{unknown['count']} areas**.{extra} "
            "That is not a failure. Search this repository for each specialized "
            "question before writing the user review. A file you find is a clue, "
            "not a passing score. A file you do not find is not a confirmed break."
        )
        lines.append("")
        groups = unknown.get("grouped") or [
            {"pack_label": "Areas", "areas": unknown.get("questions") or []}
        ]
        for group in groups:
            lines.append(f"### {group.get('pack_label') or 'Areas'}")
            lines.append("")
            for row in group.get("areas") or []:
                lines.append(f"- **{row['label']}**")
                if row.get("prompt"):
                    lines.append(f"  {row['prompt']}")
                if row.get("enough_when"):
                    lines.append(f"  Enough when: {row['enough_when']}")
                look = ", ".join(row.get("look_for") or [])
                if look:
                    lines.append(f"  Search for: `{look}`")
            lines.append("")

    suggestions = brief.get("skill_suggestions") or {}
    apply_now = suggestions.get("apply_now") or []
    lines.append("## Skill suggestions (agent only — do not paste IDs)")
    lines.append("")
    for row in apply_now:
        lines.append(f"- **Apply now:** {row.get('label')}")
        if row.get("why"):
            lines.append(f"  {row['why']}")
    lines.append(
        "- **Public:** do not use a canned list. From this repo’s problems, "
        "web-search a skill and advertise the best current match."
    )
    lines.append("")

    lines.append("## What you should do now")
    lines.append("")
    fixable = [row for row in brief["findings"] if row.get("fixable")]
    if fixable:
        lines.append(
            f"1. Fix the **{len(fixable)}** incomplete area"
            f"{'' if len(fixable) == 1 else 's'} with a clear next step above."
        )
        lines.append(
            "2. Re-run this assessment after the change so the detectors can confirm it closed."
        )
        if unknown["count"]:
            spec_n = unknown.get("specializations") or unknown["count"]
            lines.append(
                f"3. After the repo walk, say which of the {spec_n} "
                "specialized questions showed up in the tree and which did not. "
                "Lead the user review with the few that can hurt this system."
            )
    elif unknown["count"]:
        spec_n = unknown.get("specializations") or unknown["count"]
        lines.append(
            "1. There is nothing auto-fixable from this scan."
        )
        lines.append(
            f"2. Walk all {spec_n} specialized questions in this repo, then say "
            "what showed up and what did not. Lead with the few that can hurt this system."
        )
    else:
        lines.append(
            "1. Nothing incomplete was evidenced for the areas this scan could check."
        )
        lines.append(
            "2. Re-run after major changes; this is not a score and it does not cover every risk."
        )
    lines.append("")
    lines.append(
        "_Do not paste this brief. Customer review: only their paths; omit anything with no file._"
    )
    lines.append("")
    return "\n".join(lines)


def load_catalog_skills(*, root: Path | None = None) -> list[dict]:
    path = skill_paths(root=root or CONSOLIDATION)["skills"]
    if path.exists():
        return read_jsonl(path)
    return list(SKILL_SPECS)
