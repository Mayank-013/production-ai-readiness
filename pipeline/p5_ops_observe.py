"""C2 for the Phase 5.5 Observability / Operations pack."""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.control_evidence_contract import CONTROL_OBSERVATION_SCHEMA_PATH, SCHEMA_VERSION, load_schema, validate_row
from pipeline.p5_ops_c1 import P5_OPS_SPECS
from pipeline.repo_inspection.index import walk_sources

P5_OPS_FAMILY_EXPECTATION = {spec["family_id"]: spec["id"] for spec in P5_OPS_SPECS}

SPECS = [
    ("QF-0037", "strong", re.compile(r"def\s+rollback_release|rollback_path_rehearsed", re.I)),
    ("QF-0037", "supporting", re.compile(r"previous_version_pin\s*=", re.I)),
    ("QF-0037", "insufficient", re.compile(r"git history only", re.I)),
    ("QF-0037", "contradiction", re.compile(r"rollback_disabled\s*=\s*True", re.I)),
    ("QF-0038", "strong", re.compile(r"def\s+canary_rollout|canary_deployment", re.I)),
    ("QF-0038", "supporting", re.compile(r"rollout_percent\s*=", re.I)),
    ("QF-0038", "insufficient", re.compile(r"promote 100%", re.I)),
    ("QF-0038", "contradiction", re.compile(r"skip_staged_rollout\s*=\s*True", re.I)),
    ("QF-0056", "strong", re.compile(r"incident_playbook\s*=|def\s+incident_playbook", re.I)),
    ("QF-0056", "supporting", re.compile(r"incident_channel\s*=", re.I)),
    ("QF-0056", "insufficient", re.compile(r"on-call assigned", re.I)),
    ("QF-0056", "contradiction", re.compile(r"skip_incident_playbook\s*=\s*True", re.I)),
    ("QF-0057", "strong", re.compile(r"postmortem_template|def\s+write_postmortem", re.I)),
    ("QF-0057", "supporting", re.compile(r"incident_ticket\s*=", re.I)),
    ("QF-0057", "insufficient", re.compile(r"chat thread after-action", re.I)),
    ("QF-0057", "contradiction", re.compile(r"skip_postmortem\s*=\s*True", re.I)),
]
SKIP = {"cache", "resumecache", "uploads", "tmp", "temp", "testdata", "fixtures"}


def collect_p5_ops_observations(root: Path | str, *, repo: str) -> list[dict]:
    idx = walk_sources(Path(root))
    schema = load_schema(CONTROL_OBSERVATION_SCHEMA_PATH)
    rows = []
    n = 0
    for family_id, strength, pattern in SPECS:
        for rec in idx.files:
            if set(rec.rel.lower().split("/")) & SKIP:
                continue
            for i, line in enumerate(rec.lines, 1):
                if line.lstrip().startswith(("#", "//", "*")) or not pattern.search(line):
                    continue
                n += 1
                row = {
                    "id": f"p5o_cobs_{n:04d}",
                    "repo": repo,
                    "expectation_id": P5_OPS_FAMILY_EXPECTATION[family_id],
                    "family_id": family_id,
                    "strength": strength,
                    "file": rec.rel,
                    "start_line": i,
                    "snippet": line.strip()[:160],
                    "signal": pattern.pattern,
                    "schema_version": SCHEMA_VERSION,
                    "status": "frozen",
                }
                validate_row(row, schema, label=row["id"])
                rows.append(row)
    return rows
