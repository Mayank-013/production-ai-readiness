"""C2 for the Phase 5.3 Agent Runtime pack."""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.control_evidence_contract import (
    CONTROL_OBSERVATION_SCHEMA_PATH,
    SCHEMA_VERSION,
    load_schema,
    validate_row,
)
from pipeline.p5_runtime_c1 import P5_RUNTIME_SPECS
from pipeline.repo_inspection.index import walk_sources

P5_RUNTIME_FAMILY_EXPECTATION = {spec["family_id"]: spec["id"] for spec in P5_RUNTIME_SPECS}

APPROVAL_STRONG = re.compile(r"def\s+require_human_approval|human_approval_gate", re.I)
APPROVAL_SUPPORT = re.compile(r"approval_workflow", re.I)
APPROVAL_INSUFF = re.compile(r"actions require approval", re.I)
APPROVAL_CONTRA = re.compile(r"bypass_human_approval\s*=\s*True", re.I)

IDEM_STRONG = re.compile(r"def\s+check_idempotency|idempotency_store", re.I)
IDEM_SUPPORT = re.compile(r"idempotency_key\s*=", re.I)
IDEM_INSUFF = re.compile(r"uuid4\(\)", re.I)
IDEM_CONTRA = re.compile(r"skip_idempotency\s*=\s*True", re.I)

STRUCT_STRONG = re.compile(r"def\s+validate_structured_output|all_fields_required", re.I)
STRUCT_SUPPORT = re.compile(r"response_format\s*=", re.I)
STRUCT_INSUFF = re.compile(r"best.effort regex", re.I)
STRUCT_CONTRA = re.compile(r"skip_structured_output\s*=\s*True", re.I)

RETRY_STRONG = re.compile(r"def\s+classify_failure|classify_before_retry", re.I)
RETRY_SUPPORT = re.compile(r"RETRYABLE_ERRORS", re.I)
RETRY_INSUFF = re.compile(r"retry every exception", re.I)
RETRY_CONTRA = re.compile(r"skip_retry_classification\s*=\s*True", re.I)

SESSION_STRONG = re.compile(r"def\s+bind_session_to_principal|session_uniqueness_check", re.I)
SESSION_SUPPORT = re.compile(r"issue_session_id", re.I)
SESSION_INSUFF = re.compile(r"set_cookie\(", re.I)
SESSION_CONTRA = re.compile(r"allow_session_reuse\s*=\s*True", re.I)

CUTOFF_STRONG = re.compile(r"def\s+cutoff_unhealthy_dependency|error_rate_cutoff", re.I)
CUTOFF_SUPPORT = re.compile(r"dependency_timeout_count\s*=", re.I)
CUTOFF_INSUFF = re.compile(r"single.call timeout", re.I)
CUTOFF_CONTRA = re.compile(r"cutoff_disabled\s*=\s*True", re.I)

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
    ("QF-0023", "strong", APPROVAL_STRONG),
    ("QF-0023", "supporting", APPROVAL_SUPPORT),
    ("QF-0023", "insufficient", APPROVAL_INSUFF),
    ("QF-0023", "contradiction", APPROVAL_CONTRA),
    ("QF-0008", "strong", IDEM_STRONG),
    ("QF-0008", "supporting", IDEM_SUPPORT),
    ("QF-0008", "insufficient", IDEM_INSUFF),
    ("QF-0008", "contradiction", IDEM_CONTRA),
    ("QF-0064", "strong", STRUCT_STRONG),
    ("QF-0064", "supporting", STRUCT_SUPPORT),
    ("QF-0064", "insufficient", STRUCT_INSUFF),
    ("QF-0064", "contradiction", STRUCT_CONTRA),
    ("QF-0025", "strong", RETRY_STRONG),
    ("QF-0025", "supporting", RETRY_SUPPORT),
    ("QF-0025", "insufficient", RETRY_INSUFF),
    ("QF-0025", "contradiction", RETRY_CONTRA),
    ("QF-0050", "strong", SESSION_STRONG),
    ("QF-0050", "supporting", SESSION_SUPPORT),
    ("QF-0050", "insufficient", SESSION_INSUFF),
    ("QF-0050", "contradiction", SESSION_CONTRA),
    ("QF-0004", "strong", CUTOFF_STRONG),
    ("QF-0004", "supporting", CUTOFF_SUPPORT),
    ("QF-0004", "insufficient", CUTOFF_INSUFF),
    ("QF-0004", "contradiction", CUTOFF_CONTRA),
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


def collect_p5_runtime_observations(root: Path | str, *, repo: str) -> list[dict]:
    idx = walk_sources(Path(root))
    schema = load_schema(CONTROL_OBSERVATION_SCHEMA_PATH)
    observations = []
    n = 0
    for family_id, strength, pattern in OBSERVE_SPECS:
        for file, line, snippet in _hits(idx.files, pattern):
            n += 1
            row = {
                "id": f"p5r_cobs_{n:04d}",
                "repo": repo,
                "expectation_id": P5_RUNTIME_FAMILY_EXPECTATION[family_id],
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
