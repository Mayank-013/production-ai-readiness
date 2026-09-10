"""C2 for the Phase 5.4 RAG / Data pack."""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.control_evidence_contract import (
    CONTROL_OBSERVATION_SCHEMA_PATH,
    SCHEMA_VERSION,
    load_schema,
    validate_row,
)
from pipeline.p5_rag_c1 import P5_RAG_SPECS
from pipeline.repo_inspection.index import walk_sources

P5_RAG_FAMILY_EXPECTATION = {spec["family_id"]: spec["id"] for spec in P5_RAG_SPECS}

GROUND_STRONG = re.compile(r"def\s+groundedness_check|require_source_attribution", re.I)
GROUND_SUPPORT = re.compile(r"attach_citations\s*=", re.I)
GROUND_INSUFF = re.compile(r"only use the provided context", re.I)
GROUND_CONTRA = re.compile(r"skip_groundedness_check\s*=\s*True", re.I)

REWRITE_STRONG = re.compile(r"def\s+reformulate_query", re.I)
REWRITE_SUPPORT = re.compile(r"query_rewrite_hint", re.I)
REWRITE_INSUFF = re.compile(r"raw user query to index", re.I)
REWRITE_CONTRA = re.compile(r"skip_query_reformulation\s*=\s*True", re.I)

VERSION_STRONG = re.compile(r"artifact_version_pointer|def\s+pin_artifact_revision", re.I)
VERSION_SUPPORT = re.compile(r"pinned_model_name\s*=", re.I)
VERSION_INSUFF = re.compile(r"store blobs in git", re.I)
VERSION_CONTRA = re.compile(r"artifact_versioning_disabled\s*=\s*True", re.I)

RETAIN_STRONG = re.compile(r"def\s+retention_policy|automated_deletion", re.I)
RETAIN_SUPPORT = re.compile(r"retention_days\s*=", re.I)
RETAIN_INSUFF = re.compile(r"no stated keep-time", re.I)
RETAIN_CONTRA = re.compile(r"retain_forever\s*=\s*True", re.I)

SKIP_REL_PARTS = {"cache", "resumecache", "uploads", "tmp", "temp", "testdata", "fixtures"}
KEEP_JSON_NAMES = {"package.json", "tsconfig.json", "compose.json", ".eslintrc.json"}

OBSERVE_SPECS = [
    ("QF-0006", "strong", GROUND_STRONG),
    ("QF-0006", "supporting", GROUND_SUPPORT),
    ("QF-0006", "insufficient", GROUND_INSUFF),
    ("QF-0006", "contradiction", GROUND_CONTRA),
    ("QF-0028", "strong", REWRITE_STRONG),
    ("QF-0028", "supporting", REWRITE_SUPPORT),
    ("QF-0028", "insufficient", REWRITE_INSUFF),
    ("QF-0028", "contradiction", REWRITE_CONTRA),
    ("QF-0055", "strong", VERSION_STRONG),
    ("QF-0055", "supporting", VERSION_SUPPORT),
    ("QF-0055", "insufficient", VERSION_INSUFF),
    ("QF-0055", "contradiction", VERSION_CONTRA),
    ("QF-0063", "strong", RETAIN_STRONG),
    ("QF-0063", "supporting", RETAIN_SUPPORT),
    ("QF-0063", "insufficient", RETAIN_INSUFF),
    ("QF-0063", "contradiction", RETAIN_CONTRA),
]


def _skip_file(rel: str) -> bool:
    parts = {part.lower() for part in rel.split("/")}
    if parts & SKIP_REL_PARTS:
        return True
    name = rel.rsplit("/", 1)[-1].lower()
    return name.endswith(".json") and name not in KEEP_JSON_NAMES


def _skip_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*")


def collect_p5_rag_observations(root: Path | str, *, repo: str) -> list[dict]:
    idx = walk_sources(Path(root))
    schema = load_schema(CONTROL_OBSERVATION_SCHEMA_PATH)
    observations = []
    n = 0
    for family_id, strength, pattern in OBSERVE_SPECS:
        for rec in idx.files:
            if _skip_file(rec.rel):
                continue
            for i, line in enumerate(rec.lines, 1):
                if _skip_line(line) or not pattern.search(line):
                    continue
                n += 1
                row = {
                    "id": f"p5g_cobs_{n:04d}",
                    "repo": repo,
                    "expectation_id": P5_RAG_FAMILY_EXPECTATION[family_id],
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
                observations.append(row)
    return observations
