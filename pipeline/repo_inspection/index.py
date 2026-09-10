"""Multilingual repository indexer.

This walker is the substrate, not the frozen B2 runner. Do not change
TEXT_SUFFIXES on the B4-era detector runner. Go / Java / C++ are first-class
here so the same IR can be produced across languages.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.repo_inspection.extract import extract_evidence
from pipeline.repo_inspection.ir import evidence_stats

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".turbo",
    "dist",
    "build",
    "coverage",
    ".cursor",
    "target",
    "vendor",
    "third_party",
    "third-party",
    "testdata",
    "testdata2",
    "testdata3",
    "bazel-bin",
    "bazel-out",
    "bazel-testlogs",
}
SKIP_FILE_NAMES = {".ds_store", "thumbs.db"}
LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".go": "go",
    ".java": "java",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}
CONFIG_SUFFIXES = {".json", ".yml", ".yaml", ".toml", ".xml", ".gradle", ".md", ".txt"}
MAX_FILE_BYTES = 512_000
MAX_SOURCE_FILES = 8_000
CONFIG_NAMES = {
    "dockerfile",
    "makefile",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "cargo.toml",
    "cargo.lock",
    "cmakelists.txt",
}
UNSUPPORTED_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
    ".pyc",
    ".so",
    ".dylib",
    ".bin",
    ".pt",
    ".onnx",
    ".class",
    ".jar",
    ".o",
}


@dataclass
class SourceFile:
    rel: str
    language: str
    text: str
    lines: list[str]


@dataclass
class RepoIndex:
    root: Path
    files: list[SourceFile] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    considered: int = 0
    unsupported: list[str] = field(default_factory=list)


def language_for(path: Path) -> str | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name in CONFIG_NAMES or suffix in CONFIG_SUFFIXES:
        return "config"
    return LANGUAGE_BY_SUFFIX.get(suffix)


def walk_sources(root: Path) -> RepoIndex:
    idx = RepoIndex(root=root)
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            found.append(Path(dirpath) / name)
    for path in sorted(found):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        name = path.name
        if name.lower() in SKIP_FILE_NAMES:
            continue
        idx.considered += 1
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix in UNSUPPORTED_SUFFIXES:
            idx.unsupported.append(rel)
            continue
        language = language_for(path)
        if language is None:
            idx.unsupported.append(rel)
            continue
        parts = {part.lower() for part in rel_parts}
        if parts & {"tests", "test", "__tests__", "docs", "documentation", "website", "site", "examples", "example"}:
            if language != "config":
                idx.unsupported.append(rel)
                continue
        if len(idx.files) >= MAX_SOURCE_FILES:
            idx.unsupported.append(rel)
            continue
        try:
            size = path.stat().st_size
        except OSError:
            idx.unsupported.append(rel)
            continue
        if size > MAX_FILE_BYTES:
            idx.unsupported.append(rel)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            idx.unsupported.append(rel)
            continue
        if "\x00" in text:
            idx.unsupported.append(rel)
            continue
        idx.files.append(SourceFile(rel=rel, language=language, text=text, lines=text.splitlines()))
    return idx


def index_repository(root: Path | str) -> dict:
    idx = walk_sources(Path(root))
    idx.evidence = extract_evidence(idx.files)
    stats = evidence_stats(idx.evidence)
    stats.update({
        "root": str(idx.root),
        "files": len(idx.files),
        "considered": idx.considered,
        "unsupported": len(idx.unsupported),
        "source_languages": sorted({rec.language for rec in idx.files if rec.language != "config"}),
        "b4_runner_unchanged": True,
        "language_specific_detectors": False,
        "questions_generated": False,
    })
    return {
        "stats": stats,
        "evidence": idx.evidence,
        "files": [{"file": rec.rel, "language": rec.language} for rec in idx.files],
    }
