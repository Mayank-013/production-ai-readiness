"""Search hints for unverified (UNKNOWN) families.

Mechanical. The host model uses these to walk the user's repo.
Spotted files are clues, not SATISFIED. Missing files are not FAIL.
"""

from __future__ import annotations

PACK_LABELS: dict[str, str] = {
    "c1": "Core production controls",
    "p5_eval": "Quality checks",
    "p5_security": "Agent and supply-chain security",
    "p5_runtime": "Runtime behavior",
    "p5_rag": "Retrieval and data",
    "p5_ops": "Release and incidents",
    "p5_cost": "Cost and capacity",
}

# Directories and names that often hold this pack's evidence.
PACK_LOOK_IN: dict[str, list[str]] = {
    "c1": [".github/", "Dockerfile", "nginx", "middleware", "auth", "tests/"],
    "p5_eval": ["eval/", "evals/", "tests/", "golden/", "datasets/"],
    "p5_security": ["sandbox", "tools/", "permissions", "sbom", ".github/dependabot"],
    "p5_runtime": ["agent", "session", "retry", "timeout", "schema"],
    "p5_rag": ["retriev", "embed", "chunk", "prompt", "retention"],
    "p5_ops": [".github/workflows", "helm", "k8s", "runbook", "incident"],
    "p5_cost": ["quota", "budget", "cache", "token", "rate_limit"],
}

# look_for: grep/glob terms. enough_when: what would count as "this exists here".
HUNT_HINTS: dict[str, dict[str, object]] = {
    "bound_work": {
        "look_for": ["timeout", "max_tokens", "deadline", "max_steps", "AbortController"],
        "enough_when": "A hard stop on duration, tokens, steps, or retries for a request or tool call.",
    },
    "degrade_path": {
        "look_for": ["fallback", "circuit_breaker", "degraded", "failover", "feature_flag"],
        "enough_when": "A named path when a dependency is down, not only a crash or generic retry.",
    },
    "eval_gate": {
        "look_for": ["eval", "quality_gate", "promptfoo", "pytest", "ci.yaml"],
        "enough_when": "A check that must pass before a model or prompt change ships.",
    },
    "permission_boundary": {
        "look_for": ["rbac", "authorize", "permission", "role", "ACL"],
        "enough_when": "Code or config that decides who may perform which action.",
    },
    "authentication": {
        "look_for": ["jwt", "oauth", "api_key", "Bearer", "Depends("],
        "enough_when": "Callers are identified before authorization runs.",
    },
    "encrypt_transit": {
        "look_for": ["HTTPSRedirect", "ssl", "tls", "https://", "uvicorn"],
        "enough_when": "The serving path itself requires TLS, not only outbound https URLs.",
    },
    "encrypt_rest": {
        "look_for": ["kms", "at_rest", "encryption", "AES", "encrypt("],
        "enough_when": "Stored data is encrypted, or a named store that encrypts by default.",
    },
    "unhealthy_detect": {
        "look_for": ["/health", "readiness", "liveness", "healthcheck", "unhealthy"],
        "enough_when": "A probe or check that marks the process or a dependency unhealthy.",
    },
    "telemetry_exist": {
        "look_for": ["logging", "structlog", "opentelemetry", "metrics", "logger."],
        "enough_when": "Request or job logs/metrics that operators can actually read.",
    },
    "prompt_injection": {
        "look_for": ["prompt_injection", "sanitize", "untrusted", "guardrail", "system_prompt"],
        "enough_when": "A control that treats user or retrieved text as untrusted in the prompt path.",
    },
    "input_validation": {
        "look_for": ["pydantic", "BaseModel", "zod", "jsonschema", "validate"],
        "enough_when": "Inbound payloads are schema-checked before work starts.",
    },
    "hardcoded_secrets": {
        "look_for": ["getenv", "SecretStr", "gitleaks", "trufflehog", "os.environ"],
        "enough_when": "Secrets come from env/secret store, and a scanner or review catches literals.",
    },
    "retrieval_eval": {
        "look_for": ["recall", "ndcg", "ragas", "retrieval_eval", "golden"],
        "enough_when": "A scored check that retrieved sources are relevant.",
    },
    "tool_selection_eval": {
        "look_for": ["tool_choice", "selected_tool", "tool_eval", "router"],
        "enough_when": "A scored check that the agent picked the right tool.",
    },
    "online_eval": {
        "look_for": ["online_eval", "shadow", "canary_eval", "production_eval", "sample_rate"],
        "enough_when": "Live or sampled production quality measurement after ship.",
    },
    "eval_dataset": {
        "look_for": ["golden", "eval_set", "labeled", "fixtures", "dataset"],
        "enough_when": "Labeled examples used to score behavior, not only unit tests.",
    },
    "grounding_eval": {
        "look_for": ["faithfulness", "groundedness", "citation", "hallucination", "attribution"],
        "enough_when": "A scored check that answers stay tied to retrieved evidence.",
    },
    "eval_leakage": {
        "look_for": ["leakage", "train_test_split", "contamination", "holdout"],
        "enough_when": "Train, eval, and retrieved corpora are kept from mixing.",
    },
    "agent_sec_assessment": {
        "look_for": ["threat_model", "agent_security", "abuse", "misuse", "STRIDE"],
        "enough_when": "A review aimed at agent misuse, not only generic app security.",
    },
    "sandbox_isolation": {
        "look_for": ["sandbox", "seccomp", "docker", "isolate", "nsjail"],
        "enough_when": "Tool execution is isolated from the control plane.",
    },
    "tool_catalog_scope": {
        "look_for": ["tools =", "allowed_tools", "tool_registry", "enable_tools"],
        "enough_when": "The set of tools for a turn is explicit and bounded.",
    },
    "sensitive_egress": {
        "look_for": ["redact", "pii", "dlp", "egress", "strip_secrets"],
        "enough_when": "Outputs are checked so secrets or PII do not leave.",
    },
    "red_team": {
        "look_for": ["red_team", "adversarial", "jailbreak", "attack_eval"],
        "enough_when": "Adversarial tests run against the shipped behavior.",
    },
    "dependency_integrity": {
        "look_for": ["sbom", "dependabot", "pip-audit", "npm audit", "lockfile"],
        "enough_when": "Third-party or generated deps are reviewed before they ship.",
    },
    "human_approval": {
        "look_for": ["approval", "human_in_the_loop", "confirm(", "require_review"],
        "enough_when": "A human must approve before a high-impact action runs.",
    },
    "idempotent_replay": {
        "look_for": ["idempoten", "dedup", "request_id", "exactly_once", "replay"],
        "enough_when": "Repeating the same operation does not double-apply side effects.",
    },
    "structured_output": {
        "look_for": ["response_format", "json_schema", "pydantic", "structured_output"],
        "enough_when": "Model output is forced into a machine-readable shape.",
    },
    "retry_classification": {
        "look_for": ["retry", "tenacity", "Retry-After", "transient", "idempotent"],
        "enough_when": "Retryable failures are separated from ones that must not retry.",
    },
    "session_binding": {
        "look_for": ["session_id", "conversation_id", "thread_id", "bind_session"],
        "enough_when": "Agent turns are bound to a session that cannot be mixed with another.",
    },
    "slow_cutoff": {
        "look_for": ["read_timeout", "deadline", "slow_request", "circuit", "bulkhead"],
        "enough_when": "A slow or error-prone dependency is cut off.",
    },
    "grounding": {
        "look_for": ["cite", "source", "context=", "ground", "retrieved"],
        "enough_when": "Generated text is required to use retrieved evidence.",
    },
    "query_reformulation": {
        "look_for": ["rewrite", "reformulat", "hyde", "expand_query", "retriever"],
        "enough_when": "Queries are rewritten so retrieval can match the index.",
    },
    "artifact_versioning": {
        "look_for": ["dvc", "mlflow", "prompt_version", "model_id", "dataset_version"],
        "enough_when": "Datasets, models, or prompts have versions that can be replayed.",
    },
    "data_retention": {
        "look_for": ["retention", "ttl", "gdpr", "delete_user", "expire"],
        "enough_when": "How long data is kept, and how it is deleted, is specified.",
    },
    "rollback_capability": {
        "look_for": ["rollback", "revert", "previous_version", "helm rollback"],
        "enough_when": "A bad release can be rolled back to a known good artifact.",
    },
    "rollout_strategy": {
        "look_for": ["canary", "blue_green", "percentage", "feature_flag", "progressive"],
        "enough_when": "Changes roll out in a controlled way, not only all-at-once.",
    },
    "incident_playbook": {
        "look_for": ["runbook", "incident", "oncall", "playbook", "SEVERITY"],
        "enough_when": "Operators have a written path for this system's incidents.",
    },
    "postmortem": {
        "look_for": ["postmortem", "incident_review", "rca", "blameless"],
        "enough_when": "Incidents produce a written learning record.",
    },
    "resource_bound": {
        "look_for": ["max_concurrency", "semaphore", "rate_limit", "memory_limit"],
        "enough_when": "Resources that can grow without limit have a cap.",
    },
    "quota_capacity": {
        "look_for": ["quota", "capacity", "budget", "tpm", "rate_limit"],
        "enough_when": "Capacity or vendor quota is planned, not only hoped for.",
    },
    "inference_cache": {
        "look_for": ["cache", "redis", "lru", "memoize", "prompt_cache"],
        "enough_when": "Stable equivalent work is reused instead of paid for twice.",
    },
    "quota_alarm": {
        "look_for": ["budget_alert", "quota_alarm", "pager", "spend", "cloudwatch"],
        "enough_when": "An alert fires before cost or quota blows.",
    },
}

_DEFAULT_HINT = {
    "look_for": ["README", "docs/", "tests/", ".github/"],
    "enough_when": "Named config, test, or doc that implements this area.",
}


def pack_label(pack: str | None) -> str:
    if not pack or pack == "other":
        return "Other"
    return PACK_LABELS.get(pack, pack.replace("_", " "))


# Extra globs when a specialization names a noun.
BINDING_LOOK_IN: dict[str, list[str]] = {
    "tool invocation": ["tools/", "tool_", "function_call"],
    "tool": ["tools/", "tool_"],
    "tool output": ["tools/", "tool_"],
    "tool result": ["tools/", "tool_"],
    "retrieval request": ["retriev", "embed", "vector"],
    "retrieved documents": ["retriev", "embed", "chunk"],
    "retrieved evidence": ["retriev", "cite", "context"],
    "RAG retrieval": ["retriev", "rag", "embed"],
    "index retrieval": ["retriev", "index", "embed"],
    "agent execution": ["agent", "graph", "orchestr"],
    "inference request": ["openai", "anthropic", "completion"],
    "remote call": ["httpx", "requests", "aiohttp"],
    "background job": ["celery", "worker", "queue"],
    "model endpoint": ["openai", "anthropic", "llm"],
    "retrieval index": ["retriev", "vector", "index"],
}


def hunt_hint(diagnostic_job: str) -> dict[str, object]:
    row = HUNT_HINTS.get(diagnostic_job) or _DEFAULT_HINT
    return {
        "look_for": list(row["look_for"]),
        "enough_when": str(row["enough_when"]),
    }


def binding_noun(bindings: dict | None) -> str:
    if not bindings:
        return ""
    for key in (
        "operation",
        "dependency",
        "principal",
        "surface",
        "channel",
        "state",
        "artifact",
    ):
        value = bindings.get(key)
        if value:
            return str(value)
    return str(next(iter(bindings.values())))


def binding_look_in(bindings: dict | None) -> list[str]:
    noun = binding_noun(bindings)
    return list(BINDING_LOOK_IN.get(noun, []))


def hunt_label(diagnostic_job: str, bindings: dict | None, *, job_label_fn) -> str:
    base = job_label_fn(diagnostic_job)
    noun = binding_noun(bindings)
    if noun:
        return f"{base} — {noun}"
    return base
