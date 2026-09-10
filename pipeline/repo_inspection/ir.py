"""Language-neutral repository evidence."""

from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA_VERSION = "repo-ir-0.1"
KINDS = (
    "file",
    "symbol",
    "import",
    "call",
    "reference",
    "entry_point",
    "config_link",
)
LANGUAGES = (
    "python",
    "go",
    "java",
    "c",
    "cpp",
    "javascript",
    "typescript",
    "config",
    "unknown",
)
EFFECTS = (
    "outbound_wait",
    "listen",
    "persist",
    "cache",
    "generate",
    "retrieve",
    "secret_read",
    "log",
    "auth_session",
    "job_consume",
    "train",
    "none",
)


def node(
    *,
    kind: str,
    language: str,
    file: str,
    start_line: int,
    end_line: int | None = None,
    name: str | None = None,
    callee: str | None = None,
    module: str | None = None,
    effect: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "kind": kind,
        "language": language,
        "file": file,
        "start_line": start_line,
        "end_line": end_line or start_line,
        "schema_version": SCHEMA_VERSION,
    }
    if name:
        row["name"] = name
    if callee:
        row["callee"] = callee
    if module:
        row["module"] = module
    if effect and effect != "none":
        row["effect"] = effect
    return row


def evidence_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "nodes": len(rows),
        "kinds": dict(Counter(row["kind"] for row in rows)),
        "languages": dict(Counter(row["language"] for row in rows)),
        "effects": dict(Counter(row.get("effect") or "none" for row in rows)),
        "outbound_wait": sum(1 for row in rows if row.get("effect") == "outbound_wait"),
        "schema_version": SCHEMA_VERSION,
    }
