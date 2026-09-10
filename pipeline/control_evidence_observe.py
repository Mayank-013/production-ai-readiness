"""C2: observe control evidence over repository sources.

Language-neutral signals. Does not mutate the frozen trait IR extractor.
Does not conclude SATISFIED/PARTIAL/UNKNOWN/FAIL.
"""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_contract import (
    CONTROL_OBSERVE_LOCKED,
    CONTROL_OBSERVATION_SCHEMA_PATH,
    SCHEMA_VERSION,
    ControlError,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.repo_inspection.index import walk_sources
from pipeline.system_trait_contract import HACKERRANKATS_REPO

OUTBOUND = re.compile(
    r"requests\.(get|post|put|delete)|httpx\.(get|post)|http\.Get|http\.Post|"
    r"client\.Do|HttpClient\.send|curl_easy_perform|\bfetch\(|axios\.(get|post)",
    re.I,
)
TIMEOUT_ON_CALL = re.compile(r"timeout\s*=\s*(None|0|[1-9]\d*)", re.I)
EXPLICIT_TIMEOUT = re.compile(r"timeout\s*=\s*[1-9]\d*", re.I)
DISABLED_TIMEOUT = re.compile(r"timeout\s*=\s*(None|0)\b", re.I)
CANCEL = re.compile(r"WithTimeout|AbortSignal|CancellationToken|context\.WithCancel")
FALLBACK = re.compile(r"fall(?:ing)? back|failover|fallback to|alternate (?:backend|provider|resource)", re.I)
EXCEPT_CONTINUE = re.compile(r"except\s+\w*(RequestException|Timeout|ConnectionError|APIError)", re.I)
EVAL_GATE = re.compile(r"eval[s_].*(threshold|gate|min_score)|quality[_ ]threshold", re.I)
EVAL_CI = re.compile(r"evals?/|eval-gate|eval_gate")
RESUME_EVAL = re.compile(r"evaluate_resume|run_evaluation|EvaluationData|resume evaluation", re.I)
AUTHORIZE = re.compile(
    r"require_role|has_permission|check_permission|authorize\(|Depends\(\s*require_|permission_denied",
    re.I,
)
OUTBOUND_AUTH = re.compile(r"headers\s*\[.Authorization|token\s+\{github", re.I)
INBOUND_AUTH = re.compile(
    r"get_current_user|HTTPBearer|OAuth2Password|verify_token|jwt\.decode|session\s*=\s*Request",
    re.I,
)
TLS_SERVER = re.compile(r"ListenAndServeTLS|ssl_context|HTTPSRedirect|uvicorn.*ssl", re.I)
HTTPS_URL = re.compile(r"https://[a-zA-Z0-9._/-]+")
ENCRYPT_REST = re.compile(r"Fernet|kms\.encrypt|encrypt_at_rest|sse-s3|sse-kms", re.I)
ALARM = re.compile(r"PagerDuty|sentry_sdk|Alertmanager|prometheus.*alert|create_alarm|CloudWatch Alarm", re.I)
LOGGER = re.compile(r"logger\.(info|error|exception|warning)|slog\.(Info|Error)|zap\.(Info|Error)")
INJECTION = re.compile(r"prompt[_ ]injection|injection[_ ]filter|sanitize_prompt|untrusted[_ ]content[_ ]fence", re.I)
PROMPT_ONLY = re.compile(r"Base answers ONLY|only use the provided", re.I)
PYDANTIC_API = re.compile(r"class\s+\w+\(BaseModel\)")
VALIDATOR = re.compile(r"field_validator|validator\(|Query\(|Body\(")
SECRET_SCAN = re.compile(r"gitleaks|detect-secrets|trufflehog|git-secrets")
GETENV_SECRET = re.compile(
    r"""(os\.getenv|os\.environ\.get|LookupEnv|Getenv)\(\s*['"][^'"]*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)""",
    re.I,
)
SECRET_LITERAL = re.compile(
    r"""(?:sk-[A-Za-z0-9]{20,})|(?:(?:password|api_key|secret_key)\s*=\s*['"][^'"]{8,}['"])""",
    re.I,
)
GETENV_ASSIGN = re.compile(r"(os\.getenv|os\.environ\.get)\(")
REFUSE_DEGRADE = re.compile(r"refuse_to_degrade\s*=\s*True|REFUSE_TO_DEGRADE\s*=\s*True")
TLS_DISABLED = re.compile(r"tls_disabled\s*=\s*True|allow_plaintext_listener\s*=\s*True")


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


def _hits(files, pattern, *, require=None) -> list[tuple[str, int, str]]:
    rows = []
    for rec in files:
        if _skip_file(rec.rel):
            continue
        for i, line in enumerate(rec.lines, 1):
            if _skip_line(line):
                continue
            if require and not require.search(line):
                continue
            if pattern.search(line):
                rows.append((rec.rel, i, line.strip()[:160]))
    return rows


FAMILY_EXPECTATION = {
    "QF-0001": "CEE-0001",
    "QF-0003": "CEE-0002",
    "QF-0005": "CEE-0003",
    "QF-0010": "CEE-0004",
    "QF-0012": "CEE-0005",
    "QF-0016": "CEE-0006",
    "QF-0017": "CEE-0007",
    "QF-0018": "CEE-0008",
    "QF-0019": "CEE-0009",
    "QF-0030": "CEE-0010",
    "QF-0032": "CEE-0011",
    "QF-0035": "CEE-0012",
}


def collect_control_observations(root: Path | str, *, repo: str = HACKERRANKATS_REPO) -> list[dict]:
    idx = walk_sources(Path(root))
    files = idx.files
    schema = load_schema(CONTROL_OBSERVATION_SCHEMA_PATH)
    specs = [
        ("QF-0001", "strong", EXPLICIT_TIMEOUT, OUTBOUND),
        ("QF-0001", "supporting", CANCEL, None),
        ("QF-0001", "contradiction", DISABLED_TIMEOUT, OUTBOUND),
        ("QF-0003", "strong", re.compile(r"def\s+\w*(failover|fallback)\w*", re.I), None),
        ("QF-0003", "supporting", FALLBACK, None),
        ("QF-0003", "supporting", EXCEPT_CONTINUE, None),
        ("QF-0003", "contradiction", REFUSE_DEGRADE, None),
        ("QF-0005", "strong", EVAL_GATE, None),
        ("QF-0005", "insufficient", RESUME_EVAL, None),
        ("QF-0010", "strong", AUTHORIZE, None),
        ("QF-0010", "insufficient", OUTBOUND_AUTH, None),
        ("QF-0012", "strong", INBOUND_AUTH, None),
        ("QF-0012", "insufficient", OUTBOUND_AUTH, None),
        ("QF-0016", "strong", TLS_SERVER, None),
        ("QF-0016", "supporting", HTTPS_URL, None),
        ("QF-0016", "contradiction", TLS_DISABLED, None),
        ("QF-0017", "strong", ENCRYPT_REST, None),
        ("QF-0018", "strong", ALARM, None),
        ("QF-0018", "insufficient", re.compile(r"logger\.error"), None),
        ("QF-0019", "strong", LOGGER, None),
        ("QF-0030", "strong", INJECTION, None),
        ("QF-0030", "insufficient", PROMPT_ONLY, None),
        ("QF-0032", "strong", PYDANTIC_API, None),
        ("QF-0032", "supporting", VALIDATOR, None),
        ("QF-0035", "strong", SECRET_SCAN, None),
        ("QF-0035", "supporting", GETENV_SECRET, None),
        ("QF-0035", "contradiction", SECRET_LITERAL, None),
    ]
    # Pydantic on API paths is stronger than internal models. Keep both as
    # strong only when the file looks like a serving surface.
    observations = []
    n = 0
    for family_id, strength, pattern, require in specs:
        expectation_id = FAMILY_EXPECTATION[family_id]
        for file, line, snippet in _hits(files, pattern, require=require):
            if family_id == "QF-0032" and strength == "strong":
                if not re.search(r"(^api/|/api/|main\.py$|app\.py$|routes)", file):
                    strength_use = "supporting"
                else:
                    strength_use = "strong"
            elif family_id == "QF-0035" and strength == "contradiction":
                if GETENV_ASSIGN.search(snippet):
                    continue
                if re.search(r"os\.getenv|os\.environ", snippet):
                    continue
                strength_use = strength
            else:
                strength_use = strength
            n += 1
            row = {
                "id": f"cobs_{n:04d}",
                "repo": repo,
                "expectation_id": expectation_id,
                "family_id": family_id,
                "strength": strength_use,
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


def write_control_observations(
    *,
    paths: dict[str, Path] | None = None,
    repo: Path | None = None,
    repo_id: str = HACKERRANKATS_REPO,
) -> dict:
    assert_control_locked(CONTROL_OBSERVE_LOCKED, "C2 control evidence observation")
    paths = paths or control_paths()
    refuse_overwrite(paths["observations"], "the C2 control observations")
    if repo is None:
        raise ControlError("C2 requires a repository root")
    rows = collect_control_observations(repo, repo=repo_id)
    stats = {
        "repo": repo_id,
        "observations": len(rows),
        "by_strength": {},
        "by_family": {},
        "status": "frozen",
        "note": "C2 only. Strength is assigned; assessment is C3.",
    }
    from collections import Counter

    stats["by_strength"] = dict(Counter(row["strength"] for row in rows))
    stats["by_family"] = dict(Counter(row["family_id"] for row in rows))
    write_jsonl(paths["observations"], rows)
    dump_json(paths["observation_stats"], stats)
    return stats
