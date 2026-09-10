"""Extract language-neutral evidence from source files.

Parsers are language-specific. The emitted nodes are not.
A Python requests.get and a Go http.Get both become a call with
effect outbound_wait. Frozen detectors should later consume that
effect, not a per-language detector fork.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, Iterable

from pipeline.repo_inspection.ir import node

if TYPE_CHECKING:
    from pipeline.repo_inspection.index import SourceFile

OUTBOUND_WAIT = {
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "httpx.get",
    "httpx.post",
    "http.Get",
    "http.Post",
    "http.Head",
    "client.Do",
    "Client.Do",
    "http.Client.Do",
    "HttpClient.send",
    "OkHttpClient.newCall",
    "curl_easy_perform",
    "fetch",
    "axios.get",
    "axios.post",
    "grpc.Dial",
    "grpc.NewClient",
    "CreateChannel",
}
LISTEN = {
    "ListenAndServe",
    "ListenAndServeTLS",
    "http.ListenAndServe",
    "app.listen",
    "FastAPI",
    "http.HandleFunc",
    "gin.Default",
    "echo.New",
    "SpringApplication.run",
}
PERSIST = {
    "write_text",
    "write_bytes",
    "os.WriteFile",
    "os.Create",
    "sql.Open",
    "sql.Exec",
    "PutObject",
    "putItem",
}
CACHE = {
    "redis.get",
    "redis.set",
    "redis.Get",
    "redis.Set",
}
GENERATE = {
    "chat.completions.create",
    "completions.create",
    "responses.create",
    "ChatCompletion.create",
    "generate_content",
    "provider.chat",
}
RETRIEVE = {
    "similarity_search",
    "as_retriever",
    "get_relevant_documents",
    "amax_marginal_relevance_search",
}
SECRET_READ = {
    "os.getenv",
    "os.environ.get",
    "os.LookupEnv",
    "Getenv",
}
LOG = {
    "logger.info",
    "logger.error",
    "zap.Info",
    "zap.Error",
    "slog.Info",
    "logrus.Info",
}
AUTH = {
    "SetCookie",
    "set_cookie",
    "jwt.encode",
    "jwt.decode",
}
JOB = {
    "celery.shared_task",
    "StartConsumer",
    "RegisterConsumer",
}
TRAIN = {
    "fine_tune",
    "create_fine_tune",
}
CONFIG_DEP_FILES = {
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "cargo.toml",
    "cmakelists.txt",
}

GO_IMPORT_RE = re.compile(r'^\s*(?:[\w.]+)?\s*"(?P<mod>[^"]+)"', re.M)
GO_FUNC_RE = re.compile(r"^\s*func\s+(?:\([^)]+\)\s+)?(?P<name>[A-Za-z_]\w*)\s*\(", re.M)
GO_CALL_RE = re.compile(r"(?P<callee>(?:[A-Za-z_]\w*\.)+[A-Za-z_]\w*)\s*\(")
JAVA_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?(?P<mod>[\w.]+)\s*;", re.M)
JAVA_CLASS_RE = re.compile(r"^\s*(?:public\s+|protected\s+|private\s+)?(?:final\s+)?class\s+(?P<name>\w+)", re.M)
JAVA_METHOD_RE = re.compile(
    r"^\s*(?:public|protected|private|static|\s)+[\w.<>,\[\]]+\s+(?P<name>\w+)\s*\(",
    re.M,
)
JAVA_CALL_RE = re.compile(r"(?P<callee>(?:[A-Za-z_]\w*\.)+[A-Za-z_]\w*)\s*\(")
C_INCLUDE_RE = re.compile(r"^\s*#\s*include\s+[<\"](?P<mod>[^>\"]+)[>\"]", re.M)
C_FUNC_RE = re.compile(r"^(?P<name>[A-Za-z_]\w*)\s*\([^;]*\)\s*\{", re.M)
C_CALL_RE = re.compile(r"(?P<callee>[A-Za-z_]\w*)\s*\(")
JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[\w*{}\s,]+\s+from\s+)?|require\(\s*)['"](?P<mod>[^'"]+)['"]""",
)
JS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)", re.M)
JS_CALL_RE = re.compile(r"(?P<callee>(?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)\s*\(")
C_CALL_SKIP = {
    "if",
    "for",
    "while",
    "switch",
    "return",
    "sizeof",
    "defined",
}


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _effect_for(callee: str) -> str | None:
    tables = (
        (OUTBOUND_WAIT, "outbound_wait"),
        (LISTEN, "listen"),
        (PERSIST, "persist"),
        (CACHE, "cache"),
        (GENERATE, "generate"),
        (RETRIEVE, "retrieve"),
        (SECRET_READ, "secret_read"),
        (LOG, "log"),
        (AUTH, "auth_session"),
        (JOB, "job_consume"),
        (TRAIN, "train"),
    )
    for names, effect in tables:
        if callee in names:
            return effect
    if callee.endswith("completions.create") or callee.endswith("generate_content") or callee.endswith("provider.chat"):
        return "generate"
    if callee.endswith("similarity_search") or callee.endswith("as_retriever") or callee.endswith("get_relevant_documents"):
        return "retrieve"
    if callee.endswith("ListenAndServe") or callee.endswith("ListenAndServeTLS"):
        return "listen"
    return None


def _python(rec: SourceFile) -> Iterable[dict]:
    try:
        tree = ast.parse(rec.text)
    except SyntaxError:
        return
    for child in ast.walk(tree):
        if isinstance(child, ast.FunctionDef) or isinstance(child, ast.AsyncFunctionDef):
            start = getattr(child, "lineno", 1)
            end = getattr(child, "end_lineno", start)
            yield node(
                kind="symbol",
                language="python",
                file=rec.rel,
                start_line=start,
                end_line=end,
                name=child.name,
            )
            if child.name == "main":
                yield node(
                    kind="entry_point",
                    language="python",
                    file=rec.rel,
                    start_line=start,
                    end_line=end,
                    name="main",
                )
        elif isinstance(child, ast.ClassDef):
            start = getattr(child, "lineno", 1)
            yield node(
                kind="symbol",
                language="python",
                file=rec.rel,
                start_line=start,
                end_line=getattr(child, "end_lineno", start),
                name=child.name,
            )
        elif isinstance(child, ast.Import):
            for alias in child.names:
                yield node(
                    kind="import",
                    language="python",
                    file=rec.rel,
                    start_line=child.lineno,
                    module=alias.name,
                )
        elif isinstance(child, ast.ImportFrom) and child.module:
            yield node(
                kind="import",
                language="python",
                file=rec.rel,
                start_line=child.lineno,
                module=child.module,
            )
        elif isinstance(child, ast.Call):
            callee = _py_callee(child.func)
            if not callee:
                continue
            yield node(
                kind="call",
                language="python",
                file=rec.rel,
                start_line=getattr(child, "lineno", 1),
                callee=callee,
                effect=_effect_for(callee),
            )


def _py_callee(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parent = _py_callee(func.value)
        return f"{parent}.{func.attr}" if parent else func.attr
    return None


def _regex_nodes(rec: SourceFile, *, import_re, symbol_re, call_re, call_skip=frozenset()) -> Iterable[dict]:
    for match in import_re.finditer(rec.text):
        yield node(
            kind="import",
            language=rec.language,
            file=rec.rel,
            start_line=_line_of(rec.text, match.start()),
            module=match.group("mod"),
        )
    for match in symbol_re.finditer(rec.text):
        name = match.group("name")
        kind = "entry_point" if name == "main" else "symbol"
        yield node(
            kind=kind,
            language=rec.language,
            file=rec.rel,
            start_line=_line_of(rec.text, match.start()),
            name=name,
        )
        if kind == "entry_point":
            yield node(
                kind="symbol",
                language=rec.language,
                file=rec.rel,
                start_line=_line_of(rec.text, match.start()),
                name=name,
            )
    for match in call_re.finditer(rec.text):
        callee = match.group("callee")
        if callee in call_skip:
            continue
        yield node(
            kind="call",
            language=rec.language,
            file=rec.rel,
            start_line=_line_of(rec.text, match.start()),
            callee=callee,
            effect=_effect_for(callee),
        )


def _config(rec: SourceFile) -> Iterable[dict]:
    name = rec.rel.rsplit("/", 1)[-1].lower()
    if name not in CONFIG_DEP_FILES and rec.rel.lower() not in CONFIG_DEP_FILES:
        return
    yield node(
        kind="config_link",
        language="config",
        file=rec.rel,
        start_line=1,
        end_line=max(1, len(rec.lines)),
        name=name,
    )


def extract_evidence(files: list[SourceFile]) -> list[dict]:
    rows: list[dict] = []
    for rec in files:
        rows.append(
            node(
                kind="file",
                language=rec.language,
                file=rec.rel,
                start_line=1,
                end_line=max(1, len(rec.lines)),
                name=rec.rel.rsplit("/", 1)[-1],
            )
        )
        if rec.language == "python":
            rows.extend(_python(rec))
        elif rec.language == "go":
            rows.extend(_regex_nodes(rec, import_re=GO_IMPORT_RE, symbol_re=GO_FUNC_RE, call_re=GO_CALL_RE))
        elif rec.language == "java":
            java_rows = list(_regex_nodes(rec, import_re=JAVA_IMPORT_RE, symbol_re=JAVA_CLASS_RE, call_re=JAVA_CALL_RE))
            http_client = any(
                row.get("module") in {"java.net.http.HttpClient", "okhttp3.OkHttpClient"}
                for row in java_rows
            )
            if http_client:
                for row in java_rows:
                    if row["kind"] == "call" and str(row.get("callee", "")).endswith(".send"):
                        row["effect"] = "outbound_wait"
                        row["callee"] = "HttpClient.send"
            rows.extend(java_rows)
            for match in JAVA_METHOD_RE.finditer(rec.text):
                name = match.group("name")
                if name in {"if", "for", "while", "switch", "class"}:
                    continue
                kind = "entry_point" if name == "main" else "symbol"
                rows.append(
                    node(
                        kind=kind,
                        language="java",
                        file=rec.rel,
                        start_line=_line_of(rec.text, match.start()),
                        name=name,
                    )
                )
        elif rec.language in {"c", "cpp"}:
            call_re = C_CALL_RE if len(rec.text) < 80_000 else re.compile(r"(?P<callee>curl_easy_perform)\s*\(")
            rows.extend(
                _regex_nodes(
                    rec,
                    import_re=C_INCLUDE_RE,
                    symbol_re=C_FUNC_RE,
                    call_re=call_re,
                    call_skip=C_CALL_SKIP,
                )
            )
        elif rec.language in {"javascript", "typescript"}:
            rows.extend(_regex_nodes(rec, import_re=JS_IMPORT_RE, symbol_re=JS_FUNC_RE, call_re=JS_CALL_RE))
        elif rec.language == "config":
            rows.extend(_config(rec))
        rows.extend(_needle_effects(rec))
    return rows


NEEDLE_EFFECTS = (
    ("chat.completions.create", "generate"),
    ("ListenAndServe", "listen"),
    ("FastAPI(", "listen"),
    ("similarity_search", "retrieve"),
    ("curl_easy_perform", "outbound_wait"),
    ("os.WriteFile", "persist"),
)


def _needle_effects(rec: SourceFile) -> list[dict]:
    rows = []
    for needle, effect in NEEDLE_EFFECTS:
        idx = rec.text.find(needle)
        if idx < 0:
            continue
        rows.append(
            node(
                kind="call",
                language=rec.language,
                file=rec.rel,
                start_line=_line_of(rec.text, idx),
                callee=needle,
                effect=effect,
            )
        )
    return rows
