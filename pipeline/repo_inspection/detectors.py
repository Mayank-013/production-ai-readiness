"""Execute frozen detector semantics over common IR.

Does not rewrite observes, supports, or strength. Does not fork
detectors by language. Unused-weak detectors stay silent so a single
weak cannot become LIKELY. Strong high-FP traits require distinctive
runtime evidence.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.repo_inspection.graph import (
    connected_flow,
    files_with_effect,
    first_runtime,
    is_runtime_path,
)

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
    "gradle.lockfile",
})
SERVICE_FRAMEWORKS = (
    "fastapi",
    "gin-gonic/gin",
    "labstack/echo",
    "spring-boot",
    "springframework",
    "express",
    "koa",
    "actix-web",
    "axum",
)
STORE_DEPS = ("sqlalchemy", "psycopg", "sqlite3", "gorm", "jdbc", "hibernate", "redis", "mongodb")
HTTP_LIBS = ("requests", "httpx", "net/http", "okhttp", "java.net.http", "axios", "node-fetch", "curl/curl.h")
LLM_SDKS = ("openai", "anthropic", "google-generativeai", "ollama", "langchain_openai")
VECTOR_DEPS = ("faiss", "chromadb", "pinecone", "weaviate", "qdrant", "pgvector", "lunr")
AGENT_DEPS = ("langgraph", "langchain.agents", "openai-agents")
JOB_DEPS = ("celery", "rq", "sidekiq", "bullmq", "quartz")
CACHE_DEPS = ("redis", "memcached", "lettuce")
CI_NAMES = (
    ".github/workflows",
    ".gitlab-ci.yml",
    "jenkinsfile",
    "azure-pipelines.yml",
    "circle.yml",
    ".circleci",
    "buildkite",
    "cloudbuild.yaml",
)


def _hit(spec: dict, rec: dict, observation: str) -> dict:
    return {
        "detector_id": spec["detector_id"],
        "trait": spec["trait"],
        "strength": spec["evidence_strength"],
        "supports": list(spec["supports"]),
        "file": rec["file"],
        "location": {"start_line": rec["start_line"], "end_line": rec["end_line"]},
        "observation": observation,
    }


def _effect_hit(evidence: list[dict], spec: dict, effect: str, observation: str) -> list[dict]:
    rec = first_runtime(row for row in evidence if row.get("effect") == effect)
    if rec is None:
        return []
    return [_hit(spec, rec, observation)]


def _config_named(evidence: list[dict], *needles: str) -> dict | None:
    for row in evidence:
        rel = row["file"].lower()
        if any(needle in rel for needle in needles):
            return row
        if row.get("name") and any(needle in str(row["name"]).lower() for needle in needles):
            return row
    return None


def _import_named(evidence: list[dict], names: tuple[str, ...]) -> dict | None:
    lowered = tuple(name.lower() for name in names)
    for row in evidence:
        module = str(row.get("module") or "").lower()
        if not module:
            continue
        if any(name in module for name in lowered):
            if is_runtime_path(row["file"]) or row["language"] == "config":
                return row
    return None


def _lockfile(evidence: list[dict], spec: dict) -> list[dict]:
    for row in evidence:
        name = Path(row["file"]).name.lower()
        if name in LOCKFILE_NAMES:
            return [_hit(spec, row, "A lockfile ships a third-party dependency tree.")]
        if row["kind"] == "config_link" and name in LOCKFILE_NAMES:
            return [_hit(spec, row, "A lockfile ships a third-party dependency tree.")]
    return []


def _ci(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _config_named(evidence, *CI_NAMES)
    if rec is None:
        return []
    return [_hit(spec, rec, "A pipeline configuration compiles, tests, or releases this repository.")]


def _listen(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "listen",
        "A long-running process binds a port and dispatches request handlers.",
    )


def _outbound(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "outbound_wait",
        "A request or job path blocks on an out-of-process remote call.",
    )


def _persist(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "persist",
        "A store, volume, or database write is on the runtime path.",
    )


def _cache(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "cache",
        "A cache read or write is on the runtime path.",
    )


def _logs(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "log",
        "Runtime paths write structured telemetry.",
    )


def _secrets(evidence: list[dict], spec: dict) -> list[dict]:
    rec = first_runtime(row for row in evidence if row.get("effect") == "secret_read")
    if rec is None:
        return []
    return [_hit(spec, rec, "A live path reads a secret from config or the environment.")]


def _stateful(evidence: list[dict], spec: dict) -> list[dict]:
    for effect in ("persist", "cache"):
        hits = _effect_hit(
            evidence,
            spec,
            effect,
            "Request handling reads or writes stores or caches that outlive the request.",
        )
        if hits:
            return hits
    return []


def _job(evidence: list[dict], spec: dict) -> list[dict]:
    hits = _effect_hit(
        evidence,
        spec,
        "job_consume",
        "A worker, queue consumer, or scheduled job process executes this system's work.",
    )
    if hits:
        return hits
    rec = _import_named(evidence, JOB_DEPS)
    if rec is None:
        return []
    # Strong detector; an import alone is not a consumer process.
    return []


def _human(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "auth_session",
        "Login, a user session, or human-facing actions reach this runtime.",
    )


def _session(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "auth_session",
        "A session, cookie, or token binds subsequent requests to that principal.",
    )


def _generate(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "generate",
        "A completion, chat, or multimodal call is issued on a live request or job path.",
    )


def _gen_out(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "generate",
        "Generated content leaves the model call into a response or stored artifact.",
    )


def _retrieve(evidence: list[dict], spec: dict) -> list[dict]:
    return _effect_hit(
        evidence,
        spec,
        "retrieve",
        "A query path hits an index or knowledge store and returns retrieved items.",
    )


def _rag(evidence: list[dict], spec: dict) -> list[dict]:
    files = connected_flow(evidence, "retrieve", "generate")
    if not files:
        return []
    rec = first_runtime(row for row in evidence if row["file"] == files[0] and row.get("effect") in {"retrieve", "generate"})
    if rec is None:
        return []
    return [_hit(
        spec,
        rec,
        "A retrieval result is inserted into model context and a generation call uses that context.",
    )]


def _untrusted_context(evidence: list[dict], spec: dict) -> list[dict]:
    files = connected_flow(evidence, "retrieve", "generate")
    if not files:
        return []
    rec = first_runtime(row for row in evidence if row["file"] == files[0])
    if rec is None:
        return []
    return [_hit(
        spec,
        rec,
        "Untrusted retrieved or tool text is concatenated into a model prompt or messages array.",
    )]


def _agentic(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, ("langgraph",))
    gens = files_with_effect(evidence, "generate")
    if rec is None or not gens:
        return []
    # Framework import plus one generate is still only agentic-weak territory.
    # Strong control-loop needs more than one model step; require generate in two files.
    if len({row["file"] for row in gens}) < 2:
        return []
    return [_hit(spec, rec, "A live control loop issues more than one model step toward a goal.")]


def _tool_agent(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, ("bind_tools", "tool_choice", "langchain.tools", "create_tool_calling_agent"))
    if rec is None:
        return []
    if not files_with_effect(evidence, "generate"):
        return []
    return [_hit(
        spec,
        rec,
        "Model tool-selection output is dispatched by the runtime and the tool result returns into the flow.",
    )]


def _prompt_load(evidence: list[dict], spec: dict) -> list[dict]:
    for row in evidence:
        rel = row["file"].lower()
        if not is_runtime_path(rel):
            continue
        if "prompt" in rel and row["kind"] in {"file", "symbol"} and row["language"] == "python":
            if files_with_effect(evidence, "generate"):
                return [_hit(spec, row, "Runtime loads prompts from versioned files, config, or a prompt store.")]
    return []


def _http_import(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, HTTP_LIBS)
    if rec is None:
        return []
    return [_hit(spec, rec, "An HTTP client library is imported.")]


def _framework_dep(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, SERVICE_FRAMEWORKS)
    if rec is None:
        return []
    return [_hit(spec, rec, "A service framework is listed as a dependency.")]


def _store_dep(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, STORE_DEPS)
    if rec is None:
        return []
    return [_hit(spec, rec, "A database or cache library is listed as a dependency.")]


def _orm_dep(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, ("sqlalchemy", "gorm", "hibernate", "jdbc", "prisma", "django.db"))
    if rec is None:
        return []
    return [_hit(spec, rec, "An ORM or database driver is listed as a dependency.")]


def _redis_dep(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, CACHE_DEPS)
    if rec is None:
        return []
    return [_hit(spec, rec, "Redis is listed as a dependency.")]


def _llm_dep(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, LLM_SDKS)
    if rec is None:
        return []
    return [_hit(spec, rec, "An openai-family package is listed as a dependency.")]


def _vector_dep(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, VECTOR_DEPS)
    if rec is None:
        return []
    return [_hit(spec, rec, "A vector database or search library is listed as a dependency.")]


def _agent_dep(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, AGENT_DEPS)
    if rec is None:
        return []
    return [_hit(spec, rec, "An agent framework is listed as a dependency.")]


def _langgraph_import(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, ("langgraph",))
    if rec is None:
        return []
    return [_hit(spec, rec, "LangGraph is imported.")]


def _env_example(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _config_named(evidence, ".env.example", ".env.sample")
    if rec is None:
        return []
    return [_hit(spec, rec, "Example environment templates mention keys.")]


def _dockerfile_expose(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _config_named(evidence, "dockerfile")
    if rec is None:
        return []
    return []  # weak unused-style; keep silent unless EXPOSE is proven later


def _public_api(evidence: list[dict], spec: dict) -> list[dict]:
    # Versioned HTTP API in Go/Python/Java/TS only — not C++ proxy internals.
    rec = first_runtime(
        row for row in evidence
        if row.get("effect") == "listen" and row["language"] in {"python", "go", "java", "javascript", "typescript"}
    )
    if rec is None:
        return []
    return [_hit(spec, rec, "A versioned API is served to callers outside this deploy.")]


def _external_caller(evidence: list[dict], spec: dict) -> list[dict]:
    rec = first_runtime(row for row in evidence if row.get("effect") == "listen")
    if rec is None:
        return []
    return [_hit(spec, rec, "Untrusted or third-party callers actually invoke this runtime.")]


def _svc_identity(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _import_named(evidence, ("oauth2", "oidc", "mtls", "serviceaccount", "spiffe"))
    if rec is None:
        rec = first_runtime(row for row in evidence if row.get("effect") == "listen")
    if rec is None:
        return []
    if rec.get("effect") == "listen" and rec["language"] in {"go", "java", "cpp", "c"}:
        return [_hit(spec, rec, "Inbound callers present workload credentials rather than only human sessions.")]
    return []


def _untrusted_input(evidence: list[dict], spec: dict) -> list[dict]:
    rec = first_runtime(row for row in evidence if row.get("effect") == "listen")
    if rec is None:
        return []
    return [_hit(spec, rec, "Untrusted payloads enter a runtime path that acts on them.")]


def _retain_user(evidence: list[dict], spec: dict) -> list[dict]:
    rec = first_runtime(row for row in evidence if row.get("effect") == "persist")
    if rec is None:
        return []
    return [_hit(spec, rec, "User or telemetry records are written and kept beyond a request.")]


def _ships(evidence: list[dict], spec: dict) -> list[dict]:
    rec = _config_named(evidence, "dockerfile", "helm", "kustomization", "chart.yaml", "deploy")
    if rec is None:
        return []
    return [_hit(spec, rec, "A release path ships prompts, models, config, or code into a running system.")]


def _model_artifact(evidence: list[dict], spec: dict) -> list[dict]:
    for row in evidence:
        rel = row["file"].lower()
        if rel.endswith((".pt", ".pth", ".onnx", ".safetensors", ".bin")) and "example" not in rel:
            return [_hit(spec, row, "Runtime or release includes weight files or packaged model extras.")]
    return []


def _silent(_evidence: list[dict], _spec: dict) -> list[dict]:
    return []


HANDLERS = {
    "backend_service.listen_bind.v1": _listen,
    "backend_service.framework_dep.v1": _framework_dep,
    "internet_facing.untrusted_traffic.v1": _silent,
    "internet_facing.public_listener.v1": _silent,
    "internet_facing.dockerfile_expose.v1": _dockerfile_expose,
    "stateful.retain_across_requests.v1": _stateful,
    "stateful.store_dep.v1": _store_dep,
    "multi_tenant.tenant_on_path.v1": _silent,
    "multi_tenant.unused_customer_field.v1": _silent,
    "background_worker.consumer_process.v1": _job,
    "background_worker.job_framework_dep.v1": _silent,
    "on_device.local_runtime.v1": _silent,
    "on_device.sdk_unused.v1": _silent,
    "ci_pipeline.jobs_run.v1": _ci,
    "ci_pipeline.config_unused.v1": _silent,
    "serves_production.production_named.v1": _silent,
    "ships_behavior_change.release_path.v1": _ships,
    "ships_behavior_change.changelog_only.v1": _silent,
    "human_user.login_session.v1": _human,
    "human_user.unused_user_model.v1": _silent,
    "external_caller.inbound_trust.v1": _external_caller,
    "external_caller.cors_unused.v1": _silent,
    "service_to_service.workload_identity.v1": _svc_identity,
    "service_to_service.discovery_unused.v1": _silent,
    "external_dependency.runtime_wait.v1": _outbound,
    "external_dependency.http_library.v1": _http_import,
    "persists_data.runtime_write.v1": _persist,
    "persists_data.orm_dependency.v1": _orm_dep,
    "uses_cache.runtime_io.v1": _cache,
    "uses_cache.redis_dependency.v1": _redis_dep,
    "public_api.versioned_served.v1": _public_api,
    "public_api.openapi_examples.v1": _silent,
    "third_party_code.lockfile_shipped.v1": _lockfile,
    "third_party_code.package_manager_empty.v1": _silent,
    "llm.openai.chat_call.v1": _generate,
    "llm.openai.dependency.v1": _llm_dep,
    "prompt_managed.runtime_load.v1": _prompt_load,
    "prompt_managed.unused_dir.v1": _silent,
    "generative_output.emitted.v1": _gen_out,
    "generative_output.sdk_only.v1": _silent,
    "model_endpoint.inference_request.v1": _generate,
    "model_endpoint.sample_url.v1": _silent,
    "model_training.weight_update.v1": _silent,
    "model_training.unused_sdk.v1": _silent,
    "model_artifact.loads_weights.v1": _model_artifact,
    "model_artifact.sample_unused.v1": _silent,
    "retrieval_system.query_index.v1": _retrieve,
    "retrieval_system.vector_dependency.v1": _vector_dep,
    "rag.retrieval_to_generation.v1": _rag,
    "rag.vector_dependency.v1": _vector_dep,
    "agent_memory.later_turn_read.v1": _silent,
    "agent_memory.unused_sdk.v1": _silent,
    "agentic.control_loop.v1": _agentic,
    "agentic.framework_dep.v1": _agent_dep,
    "tool_using_agent.model_selects_tool.v1": _tool_agent,
    "tool_using_agent.langgraph_import.v1": _langgraph_import,
    "computer_use.ui_os_loop.v1": _silent,
    "computer_use.browser_lib.v1": _silent,
    "human_in_the_loop.approval_gate.v1": _silent,
    "human_in_the_loop.pr_template.v1": _silent,
    "eval_harness.scores_behavior.v1": _silent,
    "eval_harness.unused_dir.v1": _silent,
    "eval_datasets.loadable.v1": _silent,
    "eval_datasets.unused_gold.v1": _silent,
    "handles_secrets.runtime_read.v1": _secrets,
    "handles_secrets.example_env.v1": _env_example,
    "retains_user_data.retained_records.v1": _retain_user,
    "retains_user_data.unused_table.v1": _silent,
    "produces_logs.runtime_telemetry.v1": _logs,
    "produces_logs.unused_lib.v1": _silent,
    "untrusted_input.payload_acted.v1": _untrusted_input,
    "untrusted_input.unused_validation.v1": _silent,
    "untrusted_context.enters_prompt.v1": _untrusted_context,
    "untrusted_context.unused_tool.v1": _silent,
    "sessioned_auth.binds_requests.v1": _session,
    "sessioned_auth.unused_jwt.v1": _silent,
    "oncall_owned.paging_wired.v1": _silent,
    "oncall_owned.empty_runbooks.v1": _silent,
    "security_operations.telemetry_or_ir.v1": _silent,
    "security_operations.sast_only.v1": _silent,
    "metered_cost.budget_path.v1": _silent,
    "metered_cost.unused_billing.v1": _silent,
    "cloud_quota.throttling.v1": _silent,
    "cloud_quota.unused_sdk.v1": _silent,
}


def detect_from_ir(evidence: list[dict], spec: dict) -> list[dict]:
    fn = HANDLERS.get(spec["detector_id"], _silent)
    return fn(evidence, spec)
