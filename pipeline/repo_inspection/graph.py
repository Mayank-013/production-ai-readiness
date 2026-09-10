"""Cross-file reasoning over language-neutral evidence."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable


DOC_SUFFIXES = {".md", ".rst", ".txt"}
NON_RUNTIME_PARTS = {
    "docs",
    "documentation",
    "website",
    "site",
    "tests",
    "test",
    "__tests__",
    "examples",
    "example",
    "fixtures",
    "testdata",
}


def is_runtime_path(rel: str) -> bool:
    lower = rel.lower()
    name = lower.rsplit("/", 1)[-1]
    if name.startswith("test_") or name.endswith("_test.py") or name.endswith("_test.go"):
        return False
    parts = set(lower.split("/"))
    if parts & NON_RUNTIME_PARTS:
        return False
    if any(lower.endswith(suf) for suf in DOC_SUFFIXES):
        return False
    return True


def effects_by_file(evidence: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in evidence:
        effect = row.get("effect")
        if effect:
            out[row["file"]].add(effect)
    return dict(out)


def files_with_effect(evidence: list[dict], effect: str, *, runtime_only: bool = True) -> list[dict]:
    rows = []
    for row in evidence:
        if row.get("effect") != effect:
            continue
        if runtime_only and not is_runtime_path(row["file"]):
            continue
        rows.append(row)
    return rows


def file_has_effects(evidence: list[dict], *wanted: str, runtime_only: bool = True) -> list[str]:
    by_file = effects_by_file(evidence)
    hits = []
    need = set(wanted)
    for rel, have in by_file.items():
        if runtime_only and not is_runtime_path(rel):
            continue
        if need <= have:
            hits.append(rel)
    return hits


def connected_flow(evidence: list[dict], *wanted: str) -> list[str]:
    """Same-file or import-linked files that jointly cover the effects."""
    same = file_has_effects(evidence, *wanted)
    if same:
        return same
    by_file = effects_by_file(evidence)
    imports_of: dict[str, set[str]] = defaultdict(set)
    for row in evidence:
        if row["kind"] == "import" and row.get("module"):
            imports_of[row["file"]].add(row["module"])
    symbols: dict[str, set[str]] = defaultdict(set)
    for row in evidence:
        if row["kind"] == "symbol" and row.get("name"):
            symbols[row["name"]].add(row["file"])
    calls_to: dict[str, set[str]] = defaultdict(set)
    for row in evidence:
        if row["kind"] == "call" and row.get("callee"):
            name = row["callee"].rsplit(".", 1)[-1]
            calls_to[row["file"]].update(symbols.get(name, ()))
    need = set(wanted)
    for rel, peers in calls_to.items():
        if not is_runtime_path(rel):
            continue
        have = set(by_file.get(rel, ()))
        for peer in peers:
            if is_runtime_path(peer):
                have |= by_file.get(peer, set())
        if need <= have:
            return [rel]
    return []


def first_runtime(rows: Iterable[dict]) -> dict | None:
    for row in rows:
        if is_runtime_path(row["file"]):
            return row
    return None
