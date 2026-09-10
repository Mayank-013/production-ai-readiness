"""Shared paths, glob matching, and source classification for Milestone 1."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "engineering-kb"
EI = ROOT / "engineering-intelligence"
CONFIGS = EI / "configs"
NORMALIZED = EI / "normalized"
PASSAGES = EI / "passages"
EXTRACTIONS = EI / "extractions"
PROMPTS = EI / "prompts"
SCHEMAS = EI / "schemas"
CONSOLIDATION = EI / "consolidation"

CLAIM_TYPES = (
    "principle",
    "control",
    "failure_mode",
    "anti_pattern",
    "tradeoff",
    "architectural_decision",
    "constraint",
    "verification_method",
    "operational_practice",
    "security_requirement",
    "evaluation_practice",
    "generalizable_incident_lesson",
)

SOURCE_TYPES = {
    "standard",
    "framework",
    "book",
    "documentation",
    "postmortem",
    "incident",
    "adr",
    "rfc",
    "kep",
    "research_paper",
    "engineering_blog",
    "issue",
    "pull_request",
    "source_code",
    "benchmark",
    "tutorial",
    "unknown",
}

SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".venv"}

BINARY_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".mp4",
    ".mp3",
    ".wav",
    ".zip",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".tar",
    ".so",
    ".dylib",
    ".o",
    ".a",
    ".class",
    ".jar",
    ".wasm",
    ".pyc",
    ".exe",
    ".bin",
    ".lock",
    ".parquet",
    ".idx",
    ".pack",
}

CODE_EXT = {
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".scala",
    ".ts",
    ".js",
    ".tsx",
    ".jsx",
    ".py",
    ".rb",
    ".swift",
    ".m",
    ".mm",
    ".s",
    ".S",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".php",
}

TEXT_EXT = {".html", ".htm", ".md", ".markdown", ".txt", ".rst", ".pdf"}
STRUCT_EXT = {".json", ".yaml", ".yml", ".toml"}

META_NAMES = {"index.md", "size.md", "readme.md"}


def posix(rel: str) -> str:
    return rel.replace("\\", "/")


def glob_match(path: str, pattern: str) -> bool:
    path = posix(path)
    pattern = posix(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    if "**/" in pattern:
        # prefix/**/rest → fnmatch after collapsing
        rx = (
            "^"
            + re.escape(pattern).replace(r"\*\*/", "(.*/)?").replace(r"\*", "[^/]*").replace(r"\?", ".")
            + "$"
        )
        return re.match(rx, path) is not None
    return fnmatch.fnmatch(path, pattern) or path == pattern


def any_glob(path: str, patterns: Iterable[str]) -> bool:
    return any(glob_match(path, p) for p in patterns)


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_source_rules() -> list[dict]:
    data = load_yaml(CONFIGS / "source_rules.yaml")
    return data.get("rules") or []


def load_gold_config() -> dict:
    return load_yaml(CONFIGS / "gold_sources.yaml")


def classify(rel: str, rules: list[dict]) -> dict:
    rel = posix(rel)
    for rule in rules:
        if glob_match(rel, rule["match"]):
            source_name = rule.get("source_name") or _default_source_name(rel)
            return {
                "source_type": rule["type"],
                "authority": float(rule.get("authority", 0.5)),
                "source_name": source_name,
            }
    return {
        "source_type": "unknown",
        "authority": 0.4,
        "source_name": _default_source_name(rel),
    }


def _default_source_name(rel: str) -> str:
    parts = posix(rel).split("/")
    if len(parts) >= 3:
        return parts[2]
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else "unknown"


def is_gold(rel: str, gold_cfg: dict) -> bool:
    rel = posix(rel)
    if any_glob(rel, gold_cfg.get("exclude") or []):
        return False
    return any_glob(rel, gold_cfg.get("include") or [])


def is_sidecar(path: Path) -> bool:
    name = path.name
    if name.endswith(".sourcedoc.json"):
        return True
    if name.endswith(".json"):
        stem = path.with_suffix("")
        # foo.html.json or foo.pdf.json
        if stem.exists() or any(Path(str(stem) + ext).exists() for ext in TEXT_EXT | STRUCT_EXT):
            return True
    return False


def processable_for(rel: str, ext: str, source_type: str, path: Path) -> tuple[bool, str]:
    name = path.name.lower()
    if name.startswith("."):
        return False, "dotfile"
    if is_sidecar(path):
        return False, "sidecar"
    if name in META_NAMES or name in {"size.md"}:
        return False, "index_or_size"
    if ext in BINARY_EXT:
        return False, "binary"
    if source_type == "source_code" or ext in CODE_EXT:
        return False, "source_code_catalog_only"
    if ext in TEXT_EXT or ext in STRUCT_EXT:
        return True, "ok"
    return False, "unsupported_extension"


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_kb_files(kb: Path = KB):
    """Yield files under engineering-kb. Skip .git; do not follow symlinks."""
    import os

    for dirpath, dirnames, filenames in os.walk(kb, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if path.is_symlink():
                continue
            yield path


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dumps_jsonl_line(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("\u2028", " ").replace("\u2029", " ") + "\n"


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
