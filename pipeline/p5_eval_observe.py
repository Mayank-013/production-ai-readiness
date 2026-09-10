"""C2 for the Phase 5.1 AI Evaluation & Quality pack.

Language-neutral signals. Does not mutate the frozen C1 observer.
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
from pipeline.p5_eval_c1 import P5_EVAL_SPECS
from pipeline.repo_inspection.index import walk_sources

P5_EVAL_FAMILY_EXPECTATION = {spec["family_id"]: spec["id"] for spec in P5_EVAL_SPECS}

RETRIEVAL_EVAL_STRONG = re.compile(
    r"def\s+\w*(evaluate_retrieval|retrieval_eval|score_retrieval)\w*|"
    r"ContextPrecision|ndcg_score\(|recall_at_k\(|mean_reciprocal_rank\(",
    re.I,
)
RETRIEVAL_EVAL_SUPPORT = re.compile(
    r"ndcg@\d+|recall@k|context[_ ]precision|retrieval_metric",
    re.I,
)
RETRIEVAL_EVAL_INSUFF = re.compile(r"evaluate retrieval quality", re.I)
RETRIEVAL_EVAL_CONTRA = re.compile(
    r"skip_retrieval_eval\s*=\s*True|retrieval_eval_disabled\s*=\s*True",
    re.I,
)

TOOL_SEL_STRONG = re.compile(
    r"def\s+\w*(tool_selection_eval|evaluate_tool_choice|score_tool_selection)\w*|"
    r"tool_choice_accuracy",
    re.I,
)
TOOL_SEL_SUPPORT = re.compile(r"tool_selection_test|expected_tool\s*=", re.I)
TOOL_SEL_INSUFF = re.compile(r"tool_catalog", re.I)
TOOL_SEL_CONTRA = re.compile(r"skip_tool_selection_eval\s*=\s*True", re.I)

ONLINE_STRONG = re.compile(
    r"online_eval|production_quality_monitor|eval_on_production_traffic",
    re.I,
)
ONLINE_SUPPORT = re.compile(r"production_quality_score", re.I)
ONLINE_INSUFF = re.compile(r"offline[_ ]eval_only", re.I)
ONLINE_CONTRA = re.compile(r"online_eval_disabled\s*=\s*True", re.I)

DATASET_STRONG = re.compile(r"LABELED_EVAL_EXAMPLES|class\s+EvalDataset\b", re.I)
DATASET_SUPPORT = re.compile(r"gold_labels|eval_examples", re.I)
DATASET_INSUFF = re.compile(r"evals folder", re.I)
DATASET_CONTRA = re.compile(
    r"no_gold_labels\s*=\s*True|eval_dataset_disabled\s*=\s*True",
    re.I,
)

GROUND_STRONG = re.compile(
    r"FaithfulnessEvaluator|def\s+faithfulness_score|groundedness_score\(|faithfulness_eval",
    re.I,
)
GROUND_SUPPORT = re.compile(r"citation_check|check_citations", re.I)
GROUND_INSUFF = re.compile(r"be faithful|stay grounded", re.I)
GROUND_CONTRA = re.compile(r"skip_faithfulness_eval\s*=\s*True", re.I)

LEAK_STRONG = re.compile(
    r"def\s+\w*(check_overlap|leakage_check|dedup_splits)\w*|train_eval_overlap_check",
    re.I,
)
LEAK_SUPPORT = re.compile(r"separate_train_eval|holdout_split", re.I)
LEAK_INSUFF = re.compile(r"train_test_split\(", re.I)
LEAK_CONTRA = re.compile(r"allow_train_eval_overlap\s*=\s*True", re.I)

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
    ("QF-0027", "strong", RETRIEVAL_EVAL_STRONG),
    ("QF-0027", "supporting", RETRIEVAL_EVAL_SUPPORT),
    ("QF-0027", "insufficient", RETRIEVAL_EVAL_INSUFF),
    ("QF-0027", "contradiction", RETRIEVAL_EVAL_CONTRA),
    ("QF-0042", "strong", TOOL_SEL_STRONG),
    ("QF-0042", "supporting", TOOL_SEL_SUPPORT),
    ("QF-0042", "insufficient", TOOL_SEL_INSUFF),
    ("QF-0042", "contradiction", TOOL_SEL_CONTRA),
    ("QF-0043", "strong", ONLINE_STRONG),
    ("QF-0043", "supporting", ONLINE_SUPPORT),
    ("QF-0043", "insufficient", ONLINE_INSUFF),
    ("QF-0043", "contradiction", ONLINE_CONTRA),
    ("QF-0044", "strong", DATASET_STRONG),
    ("QF-0044", "supporting", DATASET_SUPPORT),
    ("QF-0044", "insufficient", DATASET_INSUFF),
    ("QF-0044", "contradiction", DATASET_CONTRA),
    ("QF-0045", "strong", GROUND_STRONG),
    ("QF-0045", "supporting", GROUND_SUPPORT),
    ("QF-0045", "insufficient", GROUND_INSUFF),
    ("QF-0045", "contradiction", GROUND_CONTRA),
    ("QF-0054", "strong", LEAK_STRONG),
    ("QF-0054", "supporting", LEAK_SUPPORT),
    ("QF-0054", "insufficient", LEAK_INSUFF),
    ("QF-0054", "contradiction", LEAK_CONTRA),
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


def collect_p5_eval_observations(root: Path | str, *, repo: str) -> list[dict]:
    idx = walk_sources(Path(root))
    schema = load_schema(CONTROL_OBSERVATION_SCHEMA_PATH)
    observations = []
    n = 0
    for family_id, strength, pattern in OBSERVE_SPECS:
        for file, line, snippet in _hits(idx.files, pattern):
            n += 1
            row = {
                "id": f"p5e_cobs_{n:04d}",
                "repo": repo,
                "expectation_id": P5_EVAL_FAMILY_EXPECTATION[family_id],
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
