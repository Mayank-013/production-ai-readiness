"""C2 for the Phase 5.6 Cost / Resource pack."""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.control_evidence_contract import CONTROL_OBSERVATION_SCHEMA_PATH, SCHEMA_VERSION, load_schema, validate_row
from pipeline.p5_cost_c1 import P5_COST_SPECS
from pipeline.repo_inspection.index import walk_sources

P5_COST_FAMILY_EXPECTATION = {spec["family_id"]: spec["id"] for spec in P5_COST_SPECS}

SPECS = [
    ("QF-0021", "strong", re.compile(r"def\s+apply_session_ttl|sliding_window_eviction", re.I)),
    ("QF-0021", "supporting", re.compile(r"max_store_size\s*=", re.I)),
    ("QF-0021", "insufficient", re.compile(r"unbounded store", re.I)),
    ("QF-0021", "contradiction", re.compile(r"ttl_disabled\s*=\s*True", re.I)),
    ("QF-0022", "strong", re.compile(r"def\s+determine_service_quota", re.I)),
    ("QF-0022", "supporting", re.compile(r"service_quota\s*=", re.I)),
    ("QF-0022", "insufficient", re.compile(r"cloud default quota", re.I)),
    ("QF-0022", "contradiction", re.compile(r"skip_quota_sizing\s*=\s*True", re.I)),
    ("QF-0053", "strong", re.compile(r"prompt_cache|def\s+inference_cache", re.I)),
    ("QF-0053", "supporting", re.compile(r"cache_library_imported", re.I)),
    ("QF-0053", "insufficient", re.compile(r"http cache only", re.I)),
    ("QF-0053", "contradiction", re.compile(r"inference_cache_disabled\s*=\s*True", re.I)),
    ("QF-0059", "strong", re.compile(r"def\s+quota_alarm|quota_constraint_alert", re.I)),
    ("QF-0059", "supporting", re.compile(r"quota_metric_export", re.I)),
    ("QF-0059", "insufficient", re.compile(r"logger.*quota", re.I)),
    ("QF-0059", "contradiction", re.compile(r"skip_quota_alarm\s*=\s*True", re.I)),
]
SKIP = {"cache", "resumecache", "uploads", "tmp", "temp", "testdata", "fixtures"}


def collect_p5_cost_observations(root: Path | str, *, repo: str) -> list[dict]:
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
                    "id": f"p5c_cobs_{n:04d}",
                    "repo": repo,
                    "expectation_id": P5_COST_FAMILY_EXPECTATION[family_id],
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
