"""Catalog apply-now rows only.

Public skills are not seeded here. The host writes a problem statement
from this repo and web-searches a skill at review time.
"""

from __future__ import annotations


def select_skill_suggestions(*, findings: list[dict]) -> dict:
    """Catalog findings the host may apply. Public list stays empty."""
    apply_now = []
    seen: set[str] = set()
    for finding in findings:
        skill_id = finding.get("skill_id")
        if not skill_id or skill_id in seen:
            continue
        if finding.get("assessment_state") not in {"PARTIAL", "FAIL"}:
            continue
        seen.add(skill_id)
        apply_now.append(
            {
                "kind": "apply_now",
                "label": finding.get("skill_name") or finding.get("label"),
                "why": finding.get("problem") or finding.get("next") or finding.get("label"),
                "skill_id": skill_id,
                "diagnostic_job": finding.get("diagnostic_job"),
            }
        )
    return {
        "apply_now": apply_now,
        "public": [],
        "public_policy": "host_dynamic",
        "note": (
            "apply_now may be applied from the catalog. "
            "Do not use a static public list. Form a problem from this repo, "
            "web-search a skill for that problem, and advertise it. "
            "Do not apply public skills. Do not show skill_id to the customer."
        ),
    }
