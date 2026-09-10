"""C2 for the Phase 5.2 AI Security pack.

Language-neutral signals. Does not mutate the frozen C1 or Phase 5.1 observers.
Does not conclude SATISFIED/PARTIAL/UNKNOWN/FAIL.
"""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.control_evidence_contract import (
    CONTROL_OBSERVATION_SCHEMA_PATH,
    SCHEMA_VERSION,
    load_schema,
    validate_row,
)
from pipeline.p5_security_c1 import P5_SECURITY_SPECS
from pipeline.repo_inspection.index import walk_sources

P5_SECURITY_FAMILY_EXPECTATION = {spec["family_id"]: spec["id"] for spec in P5_SECURITY_SPECS}

AGENT_ASSESS_STRONG = re.compile(
    r"def\s+agent_security_assessment|agent_threat_assessment|"
    r"pen_test.*prompt injection chains",
    re.I,
)
AGENT_ASSESS_SUPPORT = re.compile(r"agent_misuse_scenarios", re.I)
AGENT_ASSESS_INSUFF = re.compile(r"generic OWASP scan", re.I)
AGENT_ASSESS_CONTRA = re.compile(r"exclude_agent_from_security_scope\s*=\s*True", re.I)

SANDBOX_STRONG = re.compile(
    r"harness_vs_sandbox|isolated_sandbox_client|sandbox_compute_boundary",
    re.I,
)
SANDBOX_SUPPORT = re.compile(r"sandbox_client\s*=", re.I)
SANDBOX_INSUFF = re.compile(r"docker mentioned", re.I)
SANDBOX_CONTRA = re.compile(r"sandbox_disabled\s*=\s*True", re.I)

CATALOG_STRONG = re.compile(
    r"def\s+select_tools_for_turn|task_relevant_tools",
    re.I,
)
CATALOG_SUPPORT = re.compile(r"tool_allowlist", re.I)
CATALOG_INSUFF = re.compile(r"full_tool_catalog", re.I)
CATALOG_CONTRA = re.compile(r"expose_all_tools\s*=\s*True", re.I)

EGRESS_STRONG = re.compile(
    r"def\s+scan_agent_output|pii_egress_filter|def\s+redact_sensitive_output",
    re.I,
)
EGRESS_SUPPORT = re.compile(r"redact_eval_export", re.I)
EGRESS_INSUFF = re.compile(r"do not paste secrets", re.I)
EGRESS_CONTRA = re.compile(r"skip_output_scan\s*=\s*True", re.I)

REDTEAM_STRONG = re.compile(
    r"scheduled_red_team|red_team_exercise",
    re.I,
)
REDTEAM_SUPPORT = re.compile(r"ADVERSARIAL_PROMPTS", re.I)
REDTEAM_INSUFF = re.compile(r"mentions red team", re.I)
REDTEAM_CONTRA = re.compile(r"red_team_disabled\s*=\s*True", re.I)

DEPS_STRONG = re.compile(
    r"trusted_source_gate|verify_dependency_provenance",
    re.I,
)
DEPS_SUPPORT = re.compile(r"dependency_sbom|package_lock", re.I)
DEPS_INSUFF = re.compile(r"requirements.txt present", re.I)
DEPS_CONTRA = re.compile(r"skip_dependency_scan\s*=\s*True", re.I)

SKIP_REL_PARTS = {
    "cache",
    "resumecache",
    "uploads",
    "tmp",
    "temp",
    "testdata",
    "fixtures",
}
KEEP_JSON_NAMES = {
    "package.json",
    "tsconfig.json",
    "compose.json",
    ".eslintrc.json",
}

OBSERVE_SPECS = [
    ("QF-0031", "strong", AGENT_ASSESS_STRONG),
    ("QF-0031", "supporting", AGENT_ASSESS_SUPPORT),
    ("QF-0031", "insufficient", AGENT_ASSESS_INSUFF),
    ("QF-0031", "contradiction", AGENT_ASSESS_CONTRA),
    ("QF-0040", "strong", SANDBOX_STRONG),
    ("QF-0040", "supporting", SANDBOX_SUPPORT),
    ("QF-0040", "insufficient", SANDBOX_INSUFF),
    ("QF-0040", "contradiction", SANDBOX_CONTRA),
    ("QF-0041", "strong", CATALOG_STRONG),
    ("QF-0041", "supporting", CATALOG_SUPPORT),
    ("QF-0041", "insufficient", CATALOG_INSUFF),
    ("QF-0041", "contradiction", CATALOG_CONTRA),
    ("QF-0049", "strong", EGRESS_STRONG),
    ("QF-0049", "supporting", EGRESS_SUPPORT),
    ("QF-0049", "insufficient", EGRESS_INSUFF),
    ("QF-0049", "contradiction", EGRESS_CONTRA),
    ("QF-0051", "strong", REDTEAM_STRONG),
    ("QF-0051", "supporting", REDTEAM_SUPPORT),
    ("QF-0051", "insufficient", REDTEAM_INSUFF),
    ("QF-0051", "contradiction", REDTEAM_CONTRA),
    ("QF-0062", "strong", DEPS_STRONG),
    ("QF-0062", "supporting", DEPS_SUPPORT),
    ("QF-0062", "insufficient", DEPS_INSUFF),
    ("QF-0062", "contradiction", DEPS_CONTRA),
]


def _skip_file(rel: str) -> bool:
    parts = {part.lower() for part in rel.split("/")}
    if parts & SKIP_REL_PARTS:
        return True
    name = rel.rsplit("/", 1)[-1].lower()
    if name.endswith(".json") and name not in KEEP_JSON_NAMES:
        return True
    return False


def _skip_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*")


def _hits(files, pattern) -> list[tuple[str, int, str]]:
    rows = []
    for rec in files:
        if _skip_file(rec.rel):
            continue
        for i, line in enumerate(rec.lines, 1):
            if _skip_line(line):
                continue
            if pattern.search(line):
                rows.append((rec.rel, i, line.strip()[:160]))
    return rows


def collect_p5_security_observations(root: Path | str, *, repo: str) -> list[dict]:
    idx = walk_sources(Path(root))
    schema = load_schema(CONTROL_OBSERVATION_SCHEMA_PATH)
    observations = []
    n = 0
    for family_id, strength, pattern in OBSERVE_SPECS:
        for file, line, snippet in _hits(idx.files, pattern):
            n += 1
            row = {
                "id": f"p5s_cobs_{n:04d}",
                "repo": repo,
                "expectation_id": P5_SECURITY_FAMILY_EXPECTATION[family_id],
                "family_id": family_id,
                "strength": strength,
                "file": file,
                "start_line": line,
                "snippet": snippet,
                "signal": pattern.pattern if hasattr(pattern, "pattern") else str(pattern),
                "schema_version": SCHEMA_VERSION,
                "status": "frozen",
            }
            validate_row(row, schema, label=row["id"])
            observations.append(row)
    return observations
