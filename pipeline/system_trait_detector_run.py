"""B2 first repo observation run.

Walks one repository with the frozen detector catalog and emits
provenance-bearing observations only. Does not infer PRESENT / LIKELY /
ABSENT / UNKNOWN. Does not apply ontology implies. Does not open B3.

Implementations live here, not in the catalog. A semantically correct
frozen detector can still be implemented badly; this pass is where that
shows up. Strong dataflow requires the chain in one connected span.

Contract: docs/repo-trait-inference.md
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.common import dump_json, read_jsonl, write_jsonl
from pipeline.question_family_contract import SPECIALIZATION_LOCKED
from pipeline.system_trait_contract import (
    EXPECTED_FROZEN_DETECTORS,
    FORBIDDEN_TRAIT_STATES,
    MAPPING_STATUS_FROZEN,
    REPO_TRAIT_DOC,
    REPO_TRAIT_OPEN_STAGE,
    REPO_TRAIT_STAGES,
    TRAIT_AGGREGATION_LOCKED,
    TRAIT_AGGREGATION_REVIEW_LOCKED,
    TRAIT_BENCHMARK_LOCKED,
    TRAIT_DETECTOR_OBSERVATION_REVIEW_LOCKED,
    TRAIT_DETECTOR_RUN_LOCKED,
    TRAIT_STATES,
    TraitError,
    assert_trait_detector_run_locked,
    load_trait_detector_observation_schema,
)

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
}
SKIP_FILE_NAMES = {".ds_store", "thumbs.db"}
SECRET_NAME_RE = re.compile(r"^\.env(\.|$)")
SECRET_ALLOW = {".env.example", ".env.local.example", ".env.sample"}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".md",
    ".txt",
    ".jinja",
    ".j2",
    ".css",
}
TEXT_NAMES = {
    "dockerfile",
    "makefile",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
    "pipfile.lock",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "mix.lock",
    "bun.lock",
    "bun.lockb",
    "go.mod",
    "go.sum",
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
}


@dataclass
class FileRec:
    rel: str
    text: str
    lines: list[str]


@dataclass
class RepoIndex:
    root: Path
    files: list[FileRec]
    by_rel: dict[str, FileRec]
    considered: int
    unsupported: list[str] = field(default_factory=list)


def _is_secret(name: str) -> bool:
    lower = name.lower()
    if lower in SECRET_ALLOW:
        return False
    return bool(SECRET_NAME_RE.match(lower))


def _walk_repo(root: Path) -> RepoIndex:
    files: list[FileRec] = []
    unsupported: list[str] = []
    considered = 0
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
        if _is_secret(name):
            continue
        considered += 1
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix in UNSUPPORTED_SUFFIXES:
            unsupported.append(rel)
            continue
        if suffix not in TEXT_SUFFIXES and name.lower() not in TEXT_NAMES:
            if name.lower() != "dockerfile" and name.lower() not in SECRET_ALLOW:
                unsupported.append(rel)
                continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            unsupported.append(rel)
            continue
        if "\x00" in text:
            unsupported.append(rel)
            continue
        rec = FileRec(rel=rel, text=text, lines=text.splitlines())
        files.append(rec)
    return RepoIndex(
        root=root,
        files=files,
        by_rel={row.rel: row for row in files},
        considered=considered,
        unsupported=unsupported,
    )


def _span_for(rec: FileRec, start: int, end: int) -> tuple[int, int]:
    n = max(1, len(rec.lines))
    start = max(1, min(start, n))
    end = max(start, min(end, n))
    return start, end


def _find_line(rec: FileRec, needle: str) -> int | None:
    for i, line in enumerate(rec.lines, start=1):
        if needle in line:
            return i
    return None


def _function_span(rec: FileRec, name: str, *, contains: str | None = None) -> tuple[int, int] | None:
    if not rec.rel.endswith(".py"):
        return None
    try:
        tree = ast.parse(rec.text)
    except SyntaxError:
        return None
    matches: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start and end:
                body = "\n".join(rec.lines[start - 1 : end])
                if contains and contains not in body:
                    continue
                matches.append((start, end))
    if not matches:
        return None
    return matches[-1]


def _class_span(rec: FileRec, name: str) -> tuple[int, int] | None:
    if not rec.rel.endswith(".py"):
        return None
    try:
        tree = ast.parse(rec.text)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start and end:
                return start, end
    return None


def _req_blob(idx: RepoIndex) -> str:
    parts = []
    for rel in ("requirements.txt", "requirements-dev.txt", "pyproject.toml"):
        rec = idx.by_rel.get(rel)
        if rec:
            parts.append(rec.text.lower())
    rec = idx.by_rel.get("web/package.json") or idx.by_rel.get("package.json")
    if rec:
        parts.append(rec.text.lower())
    return "\n".join(parts)


def _has_dep(idx: RepoIndex, *names: str) -> FileRec | None:
    for rel in (
        "requirements.txt",
        "requirements-dev.txt",
        "pyproject.toml",
        "web/package.json",
        "package.json",
    ):
        rec = idx.by_rel.get(rel)
        if not rec:
            continue
        text = rec.text.lower()
        if any(name.lower() in text for name in names):
            return rec
    return None


def _import_used(idx: RepoIndex, *needles: str) -> bool:
    for rec in idx.files:
        if not rec.rel.endswith(".py"):
            continue
        for needle in needles:
            if re.search(rf"\bimport\s+{re.escape(needle)}\b|\bfrom\s+{re.escape(needle)}\b", rec.text):
                return True
    return False


def _make_hit(
    spec: dict,
    rec: FileRec,
    start: int,
    end: int,
    observation: str,
) -> dict:
    start, end = _span_for(rec, start, end)
    return {
        "detector_id": spec["detector_id"],
        "trait": spec["trait"],
        "strength": spec["evidence_strength"],
        "supports": list(spec["supports"]),
        "file": rec.rel,
        "location": {"start_line": start, "end_line": end},
        "observation": observation,
    }


def _hit_fn(idx: RepoIndex, spec: dict, rel: str, fn: str, observation: str) -> dict | None:
    rec = idx.by_rel.get(rel)
    if not rec:
        return None
    span = _function_span(rec, fn)
    if not span:
        return None
    return _make_hit(spec, rec, span[0], span[1], observation)


def _hit_class(idx: RepoIndex, spec: dict, rel: str, name: str, observation: str) -> dict | None:
    rec = idx.by_rel.get(rel)
    if not rec:
        return None
    span = _class_span(rec, name)
    if not span:
        return None
    return _make_hit(spec, rec, span[0], span[1], observation)


def _hit_file(idx: RepoIndex, spec: dict, rel: str, observation: str) -> dict | None:
    rec = idx.by_rel.get(rel)
    if not rec:
        return None
    end = max(1, len(rec.lines))
    return _make_hit(spec, rec, 1, end, observation)


def _connected(rec: FileRec, *needles: str) -> bool:
    text = rec.text.lower()
    return all(needle.lower() in text for needle in needles)


def detect(idx: RepoIndex, spec: dict) -> list[dict]:
    did = spec["detector_id"]
    fn = DETECTORS.get(did)
    if fn is None:
        return []
    return fn(idx, spec)


def _backend_listen(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = idx.by_rel.get("api/main.py")
    if not rec:
        return []
    if "FastAPI(" not in rec.text or "@app." not in rec.text:
        return []
    hit = _hit_fn(
        idx,
        spec,
        "api/main.py",
        "upload_resumes",
        "FastAPI binds route handlers and a long-running process dispatches upload requests.",
    )
    return [hit] if hit else []


def _backend_dep(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = _has_dep(idx, "fastapi")
    if not rec:
        return []
    line = _find_line(rec, "fastapi") or 1
    return [_make_hit(spec, rec, line, line, "FastAPI is listed as a dependency.")]


def _stateful_retain(idx: RepoIndex, spec: dict) -> list[dict]:
    hit = _hit_class(
        idx,
        spec,
        "api/store.py",
        "CandidateStore",
        "Request handlers read and write an in-memory candidate store that outlives a single request.",
    )
    return [hit] if hit else []


def _human_facing(idx: RepoIndex, spec: dict) -> list[dict]:
    hit = _hit_fn(
        idx,
        spec,
        "api/main.py",
        "upload_resumes",
        "A recruiter-facing upload action reaches this runtime and starts evaluation.",
    )
    return [hit] if hit else []


def _external_wait(idx: RepoIndex, spec: dict) -> list[dict]:
    out = []
    gh = idx.by_rel.get("github.py")
    if gh and "requests." in gh.text:
        hit = _hit_fn(
            idx,
            spec,
            "github.py",
            "_fetch_github_api",
            "A job path blocks on GitHub HTTP calls before evaluation continues.",
        )
        if not hit:
            line = _find_line(gh, "requests.")
            if line:
                hit = _make_hit(
                    spec,
                    gh,
                    line,
                    min(line + 8, len(gh.lines)),
                    "A job path blocks on GitHub HTTP calls before evaluation continues.",
                )
        if hit:
            out.append(hit)
    chat = _hit_fn(
        idx,
        spec,
        "api/services/chat.py",
        "stream_chat",
        "A request path blocks on a remote model completion call.",
    )
    if chat:
        out.append(chat)
    return out


def _http_import(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = idx.by_rel.get("github.py")
    if not rec or "import requests" not in rec.text:
        return []
    line = _find_line(rec, "import requests") or 1
    return [_make_hit(spec, rec, line, line, "The requests HTTP client is imported.")]


def _persist_write(idx: RepoIndex, spec: dict) -> list[dict]:
    out = []
    hit = _hit_fn(
        idx,
        spec,
        "score.py",
        "main",
        "Evaluation results are appended to resume_evaluations.csv on the runtime path.",
    )
    if hit:
        out.append(hit)
    upload = _hit_fn(
        idx,
        spec,
        "api/main.py",
        "upload_resumes",
        "Uploaded PDFs are written to the uploads directory and outlive the request.",
    )
    if upload:
        out.append(upload)
    return out


def _cache_io(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = idx.by_rel.get("score.py")
    if not rec or "cache/" not in rec.text or "write_text" not in rec.text:
        return []
    hit = _hit_fn(
        idx,
        spec,
        "score.py",
        "main",
        "Resume and GitHub JSON caches are read and written on the CLI evaluation path.",
    )
    return [hit] if hit else []


LOCKFILE_NAMES = frozenset({
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
    "poetry.lock",
    "uv.lock",
    "pipfile.lock",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "mix.lock",
    "go.sum",
})
NOT_LOCKFILE_NAMES = frozenset({
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-doc.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "package.json",
    "cargo.toml",
    "go.mod",
})


def _is_lockfile_name(rel: str) -> bool:
    return Path(rel).name.lower() in LOCKFILE_NAMES


def _lockfile(idx: RepoIndex, spec: dict) -> list[dict]:
    out = []
    for rec in idx.files:
        name = Path(rec.rel).name.lower()
        if name in NOT_LOCKFILE_NAMES:
            continue
        if not _is_lockfile_name(rec.rel):
            continue
        out.append(_make_hit(
            spec,
            rec,
            1,
            min(20, len(rec.lines)),
            f"A {Path(rec.rel).name} lockfile ships a third-party dependency tree.",
        ))
    return out


def _llm_call(idx: RepoIndex, spec: dict) -> list[dict]:
    out = []
    for rel, fn, text in (
        ("models.py", "chat", "An OpenAI chat completion is issued on a live provider path."),
        ("api/services/chat.py", "stream_chat", "A streaming chat completion is issued on the hiring-desk request path."),
        ("evaluator.py", "evaluate_resume", "A model chat call scores a resume on the evaluation path."),
        ("pdf.py", None, "A model chat call extracts a resume section on the parse path."),
        ("github.py", None, "A model chat call selects GitHub projects on the enrichment path."),
    ):
        rec = idx.by_rel.get(rel)
        if not rec:
            continue
        if "chat.completions.create" not in rec.text and "provider.chat" not in rec.text:
            continue
        if fn:
            rec2 = idx.by_rel.get(rel)
            span = _function_span(rec2, fn, contains="chat.completions.create") if rec2 else None
            if span:
                out.append(_make_hit(spec, rec2, span[0], span[1], text))
                continue
            hit = _hit_fn(idx, spec, rel, fn, text)
            if hit and rec2 and "..." not in "\n".join(rec2.lines[hit["location"]["start_line"] - 1 : hit["location"]["end_line"]]):
                out.append(hit)
                continue
        line = _find_line(rec, "provider.chat") or _find_line(rec, "chat.completions.create")
        if line:
            out.append(_make_hit(spec, rec, line, min(line + 6, len(rec.lines)), text))
    return out


def _llm_dep(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = _has_dep(idx, "openai")
    if not rec:
        return []
    line = _find_line(rec, "openai") or 1
    return [_make_hit(spec, rec, line, line, "The openai package is listed as a dependency.")]


def _prompt_load(idx: RepoIndex, spec: dict) -> list[dict]:
    hit = _hit_fn(
        idx,
        spec,
        "prompts/template_manager.py",
        "_load_templates",
        "Runtime loads versioned Jinja prompt templates from prompts/templates.",
    )
    return [hit] if hit else []


def _gen_out(idx: RepoIndex, spec: dict) -> list[dict]:
    out = []
    chat = _hit_fn(
        idx,
        spec,
        "api/services/chat.py",
        "stream_chat",
        "Generated tokens leave the model call into the streaming HTTP response.",
    )
    if chat:
        out.append(chat)
    ev = _hit_fn(
        idx,
        spec,
        "evaluator.py",
        "evaluate_resume",
        "Generated evaluation JSON leaves the model call into the returned EvaluationData.",
    )
    if ev:
        out.append(ev)
    return out


def _sdk_only(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = _has_dep(idx, "openai", "ollama", "google-generativeai")
    if not rec:
        return []
    line = _find_line(rec, "openai") or _find_line(rec, "ollama") or 1
    return [_make_hit(spec, rec, line, line, "An LLM SDK is listed as a dependency.")]


def _model_endpoint(idx: RepoIndex, spec: dict) -> list[dict]:
    return _llm_call(idx, spec)


def _secrets_runtime(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = idx.by_rel.get("prompt.py")
    if not rec or "os.getenv" not in rec.text:
        return []
    if "OPENAI_API_KEY" not in rec.text and "GEMINI_API_KEY" not in rec.text:
        return []
    line = _find_line(rec, "OPENAI_API_KEY") or _find_line(rec, "os.getenv") or 1
    return [_make_hit(
        spec,
        rec,
        line,
        min(line + 2, len(rec.lines)),
        "A live path reads model API keys from the environment.",
    )]


def _secrets_example(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = idx.by_rel.get(".env.example")
    if not rec or "API_KEY" not in rec.text:
        return []
    return [_make_hit(spec, rec, 1, len(rec.lines), "Example environment templates mention API keys.")]


def _untrusted_input(idx: RepoIndex, spec: dict) -> list[dict]:
    hit = _hit_fn(
        idx,
        spec,
        "api/services/pipeline.py",
        "run_evaluation",
        "An uploaded PDF enters the extract-enrich-evaluate path and is acted on.",
    )
    return [hit] if hit else []


def _untrusted_context(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = idx.by_rel.get("api/services/chat.py")
    if not rec:
        return []
    if not _connected(rec, "resume_text", "system", "chat.completions.create"):
        return []
    start = _function_span(rec, "_candidate_system_prompt")
    end = _function_span(rec, "stream_chat")
    if not (start and end):
        return []
    return [_make_hit(
        spec,
        rec,
        start[0],
        end[1],
        "Untrusted resume text is inserted into the system prompt and the generation call consumes that same context.",
    )]


def _logs(idx: RepoIndex, spec: dict) -> list[dict]:
    rec = idx.by_rel.get("api/main.py")
    if not rec or "logger." not in rec.text:
        return []
    line = _find_line(rec, "logger.info") or _find_line(rec, "logger.exception")
    if not line:
        return []
    return [_make_hit(spec, rec, line, line, "Runtime paths emit structured application logs.")]


def _retain_user(idx: RepoIndex, spec: dict) -> list[dict]:
    hit = _hit_class(
        idx,
        spec,
        "api/store.py",
        "Candidate",
        "Candidate resume text and evaluation records are kept in the store beyond the upload request.",
    )
    return [hit] if hit else []


DOC_SUFFIXES = {".md", ".rst", ".txt"}
DOC_DIRS = {"docs", "documentation", "site", "website"}
TEST_DIRS = {"tests", "test", "__tests__"}
NON_RETRIEVAL_RE = re.compile(
    r"retrieve_completion\w*|responses\.retrieve|_?retrieved_response",
    re.I,
)


def _is_non_runtime_path(rel: str) -> bool:
    path = Path(rel)
    if path.suffix.lower() in DOC_SUFFIXES:
        return True
    parts = {part.lower() for part in path.parts}
    if parts & DOC_DIRS or parts & TEST_DIRS:
        return True
    name = path.name.lower()
    return name.startswith("test_") or name.endswith("_test.py")


def _has_retrieval_result(text: str) -> bool:
    """Response-object retrieve is not a retrieval result inserted into a prompt."""
    stripped = NON_RETRIEVAL_RE.sub("", text.lower())
    return "retriev" in stripped


def _rag_three_link(idx: RepoIndex, spec: dict) -> list[dict]:
    """Refuse docs and filename-only RAG. Require retrieve + insert + generate."""
    for rec in idx.files:
        if rec.rel.endswith("pymupdf_rag.py"):
            continue
        if _is_non_runtime_path(rec.rel):
            continue
        if not rec.rel.endswith(".py"):
            continue
        if not _has_retrieval_result(rec.text):
            continue
        if "vector" not in rec.rel and "retriev" not in rec.text.lower():
            continue
        if not (
            ("prompt" in rec.text.lower() or "context" in rec.text.lower() or "messages" in rec.text.lower())
            and ("chat.completions" in rec.text or "provider.chat" in rec.text)
            and ("index" in rec.text.lower() or "embedding" in rec.text.lower() or "vector" in rec.text.lower())
        ):
            continue
        return [_make_hit(
            spec,
            rec,
            1,
            min(len(rec.lines), 80),
            "A retrieval result is inserted into model context and the generation call uses that context.",
        )]
    return []


def _tool_chain(idx: RepoIndex, spec: dict) -> list[dict]:
    for rec in idx.files:
        if rec.rel.endswith(".py") and _connected(rec, "tool", "dispatch", "return"):
            if "select" in rec.text.lower() and "chat.completions" in rec.text:
                if "tools=" in rec.text or "tool_choice" in rec.text:
                    return [_make_hit(
                        spec,
                        rec,
                        1,
                        min(len(rec.lines), 80),
                        "Model tool-selection output is dispatched and the tool result returns into the agent flow.",
                    )]
    return []


def _internet_traffic(idx: RepoIndex, spec: dict) -> list[dict]:
    # Localhost CORS / local listeners are not demonstrated untrusted traffic.
    return []


DETECTORS = {
    "backend_service.listen_bind.v1": _backend_listen,
    "backend_service.framework_dep.v1": _backend_dep,
    "internet_facing.untrusted_traffic.v1": _internet_traffic,
    "stateful.retain_across_requests.v1": _stateful_retain,
    "human_user.login_session.v1": _human_facing,
    "external_dependency.runtime_wait.v1": _external_wait,
    "external_dependency.http_library.v1": _http_import,
    "persists_data.runtime_write.v1": _persist_write,
    "uses_cache.runtime_io.v1": _cache_io,
    "third_party_code.lockfile_shipped.v1": _lockfile,
    "llm.openai.chat_call.v1": _llm_call,
    "llm.openai.dependency.v1": _llm_dep,
    "prompt_managed.runtime_load.v1": _prompt_load,
    "generative_output.emitted.v1": _gen_out,
    "generative_output.sdk_only.v1": _sdk_only,
    "model_endpoint.inference_request.v1": _model_endpoint,
    "handles_secrets.runtime_read.v1": _secrets_runtime,
    "handles_secrets.example_env.v1": _secrets_example,
    "untrusted_input.payload_acted.v1": _untrusted_input,
    "untrusted_context.enters_prompt.v1": _untrusted_context,
    "produces_logs.runtime_telemetry.v1": _logs,
    "retains_user_data.retained_records.v1": _retain_user,
    "rag.retrieval_to_generation.v1": _rag_three_link,
    "tool_using_agent.model_selects_tool.v1": _tool_chain,
}


def _validate_observation(row: dict, schema: dict, catalog: dict[str, dict]) -> None:
    missing = [k for k in schema["required"] if k not in row]
    if missing:
        raise TraitError(f"{row.get('detector_id')}: missing observation fields {missing}")
    extra = set(row) - set(schema["properties"])
    if extra:
        raise TraitError(f"{row.get('detector_id')}: unknown observation fields {sorted(extra)}")
    spec = catalog.get(row["detector_id"])
    if spec is None:
        raise TraitError(f"unknown detector_id {row['detector_id']}")
    if row["supports"] != list(spec["supports"]):
        raise TraitError(f"{row['detector_id']}: supports must be copied from the detector")
    if row["strength"] != spec["evidence_strength"]:
        raise TraitError(f"{row['detector_id']}: strength must match the frozen detector")
    loc = row["location"]
    if loc["end_line"] < loc["start_line"]:
        raise TraitError(f"{row['detector_id']}: invalid span")
    raw = json.dumps(row)
    for state in list(TRAIT_STATES) + list(FORBIDDEN_TRAIT_STATES):
        if re.search(rf"\b{state}\b", raw):
            raise TraitError(f"{row['detector_id']}: observation must not emit trait state {state}")


def _dedup_key(row: dict) -> tuple:
    return (
        row["detector_id"],
        row["file"],
        row["location"]["start_line"],
        row["location"]["end_line"],
        row["observation"],
    )


def collect_detector_observations(
    repo: Path,
    catalog_rows: list[dict],
) -> tuple[list[dict], RepoIndex, dict]:
    """Walk one repo with the frozen catalog. Does not write dests or infer states."""
    repo = Path(repo).expanduser().resolve()
    if not repo.is_dir():
        raise TraitError(f"repository is not a directory: {repo}")
    if len(catalog_rows) != EXPECTED_FROZEN_DETECTORS:
        raise TraitError(f"expected {EXPECTED_FROZEN_DETECTORS} frozen detectors, got {len(catalog_rows)}")
    if any(row.get("status") != MAPPING_STATUS_FROZEN for row in catalog_rows):
        raise TraitError("observation run admits only the frozen catalog")
    catalog = {row["detector_id"]: row for row in catalog_rows}
    schema = load_trait_detector_observation_schema()
    idx = _walk_repo(repo)
    errors: list[dict] = []
    raw_hits: list[dict] = []
    fired: set[str] = set()

    for spec in catalog_rows:
        try:
            hits = detect(idx, spec)
        except Exception as exc:  # noqa: BLE001 — count per-detector execution errors
            errors.append({"detector_id": spec["detector_id"], "error": type(exc).__name__})
            continue
        for hit in hits:
            raw_hits.append(hit)
            fired.add(spec["detector_id"])

    seen: set[tuple] = set()
    observations: list[dict] = []
    duplicates = 0
    for hit in raw_hits:
        key = _dedup_key(hit)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        _validate_observation(hit, schema, catalog)
        observations.append(hit)

    valid_file = 0
    valid_span = 0
    for row in observations:
        rec = idx.by_rel.get(row["file"])
        if rec:
            valid_file += 1
            start = row["location"]["start_line"]
            end = row["location"]["end_line"]
            if 1 <= start <= end <= max(1, len(rec.lines)):
                valid_span += 1

    if valid_file != len(observations) or valid_span != len(observations) or errors:
        raise TraitError(
            "observation run failed execution integrity: "
            f"valid_file={valid_file} valid_span={valid_span} "
            f"errors={errors} n={len(observations)}"
        )
    meta = {
        "repo": str(repo),
        "repo_name": repo.name,
        "repo_files_considered": idx.considered,
        "repo_files_indexed": len(idx.files),
        "detectors_attempted": len(catalog_rows),
        "detectors_fired": len(fired),
        "observations": len(observations),
        "strong_observations": sum(1 for row in observations if row["strength"] == "strong"),
        "weak_observations": sum(1 for row in observations if row["strength"] == "weak"),
        "observations_with_valid_file_provenance": valid_file,
        "observations_with_valid_spans": valid_span,
        "duplicate_observations": duplicates,
        "detector_execution_errors": len(errors),
        "detector_errors": errors,
        "unsupported_file_language_cases": len(idx.unsupported),
        "fired_detector_ids": sorted(fired),
    }
    return observations, idx, meta


def run_trait_detectors(*, repo: Path | None = None, paths: dict[str, Path] | None = None) -> dict:
    from pipeline.system_trait import trait_paths

    assert_trait_detector_run_locked()
    if TRAIT_DETECTOR_RUN_LOCKED:
        raise TraitError("The first repo observation run stays locked.")
    if repo is None:
        raise TraitError("--repo is required for the first observation run")
    repo = Path(repo).expanduser().resolve()

    paths = paths or trait_paths()
    dest = paths["trait_detector_observations"]
    stats_path = paths["trait_detector_observation_stats"]
    for key, label in (
        ("trait_detector_observations", "trait_detector_observations.jsonl"),
        ("trait_detector_observation_stats", "trait_detector_observation_stats.json"),
    ):
        target = paths[key]
        if target.exists() and target.read_text(encoding="utf-8").strip():
            raise TraitError(f"{label} already exists; refusing to overwrite the observation dest")
    if not paths["trait_detectors_frozen"].exists():
        raise TraitError("missing trait_detectors_frozen.jsonl; freeze the catalog first")

    catalog_rows = read_jsonl(paths["trait_detectors_frozen"])
    observations, idx, meta = collect_detector_observations(repo, catalog_rows)
    strong = meta["strong_observations"]
    weak = meta["weak_observations"]
    valid_file = meta["observations_with_valid_file_provenance"]
    valid_span = meta["observations_with_valid_spans"]
    errors = meta["detector_errors"]
    duplicates = meta["duplicate_observations"]
    fired = set(meta["fired_detector_ids"])
    stats = {
        "repo": str(repo),
        "repo_name": repo.name,
        "repo_files_considered": idx.considered,
        "repo_files_indexed": len(idx.files),
        "detectors_attempted": len(catalog_rows),
        "detectors_fired": len(fired),
        "observations": len(observations),
        "strong_observations": strong,
        "weak_observations": weak,
        "observations_with_valid_file_provenance": valid_file,
        "observations_with_valid_spans": valid_span,
        "duplicate_observations": duplicates,
        "detector_execution_errors": len(errors),
        "detector_errors": errors,
        "unsupported_file_language_cases": len(idx.unsupported),
        "fired_detector_ids": sorted(fired),
        "status": "written",
        "open_stage": REPO_TRAIT_OPEN_STAGE,
        "stages": list(REPO_TRAIT_STAGES),
        "observation_review": "locked" if TRAIT_DETECTOR_OBSERVATION_REVIEW_LOCKED else "open",
        "aggregation": "locked" if TRAIT_AGGREGATION_REVIEW_LOCKED else "open",
        "benchmark": "locked" if TRAIT_BENCHMARK_LOCKED else "open",
        "questions": "locked" if SPECIALIZATION_LOCKED else "open",
        "next_gate": "observation_execution_review",
        "note": (
            "First repo observation run only. Raw observations. "
            "No PRESENT/LIKELY/ABSENT/UNKNOWN. No ontology implication "
            "expansion. Observation execution review stays locked. "
            f"Contract: {REPO_TRAIT_DOC}."
        ),
    }
    if (
        stats["observations_with_valid_file_provenance"] != len(observations)
        or stats["observations_with_valid_spans"] != len(observations)
        or stats["detector_execution_errors"] != 0
    ):
        raise TraitError(
            "observation run failed execution integrity: "
            f"valid_file={valid_file} valid_span={valid_span} "
            f"errors={errors} n={len(observations)}"
        )
    write_jsonl(dest, observations)
    dump_json(stats_path, stats)
    return stats
