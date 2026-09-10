"""C1 control evidence expectations.

A representative Production AI Readiness pack. Not 333 controls.
Not 53 families. One expectation per selected family, citing one
canonical control as the representative object.

Absence of evidence is UNKNOWN, not FAIL.
"""

from __future__ import annotations

EXPECTATION_SPECS: list[dict] = [
    {
        "family_id": "QF-0001",
        "control_id": "CTRL-0056",
        "diagnostic_job": "bound_work",
        "strong": [
            "An explicit client deadline or timeout is set on a runtime remote call.",
            "A request timeout and a connection timeout are configured on the client that performs the wait.",
        ],
        "supporting": [
            "Cancellation or deadline context is propagated into that client call.",
            "A timeout configuration value is wired to the same client instance.",
        ],
        "insufficient_alone": [
            "A timeout constant exists in a settings file and is unused at the call site.",
            "The HTTP library default timeout is relied on with no explicit bound.",
            "Retry configuration is present without an elapsed-time or attempt ceiling on the wait.",
        ],
        "contradiction": [
            "A runtime remote call sets timeout to zero, none, or disabled on the call site.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "The bound is on the wait. Retry pacing is a different family.",
    },
    {
        "family_id": "QF-0003",
        "control_id": "CTRL-0002",
        "diagnostic_job": "degrade_path",
        "strong": [
            "A named failover or fallback path continues the operation when a primary dependency is unavailable.",
            "An alternate resource is selected after a dependency health or availability check fails.",
        ],
        "supporting": [
            "The caller catches a dependency failure and continues with a default or reduced result.",
            "Provider selection falls back to an alternate backend when a key or endpoint is missing.",
        ],
        "insufficient_alone": [
            "An except block only logs and re-raises.",
            "A comment describes failover that is not implemented.",
        ],
        "contradiction": [
            "The only handling of an unavailable dependency is a hard crash with no alternate path and an explicit refuse-to-degrade flag.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Unavailable / failover. Slow-or-erroring cutoffs are slow_cutoff.",
    },
    {
        "family_id": "QF-0005",
        "control_id": "CTRL-0016",
        "diagnostic_job": "eval_gate",
        "strong": [
            "An automated evaluation must pass a documented quality threshold before a behavior change is released.",
            "CI or release config blocks production when eval scores fall below a stated gate.",
        ],
        "supporting": [
            "An eval harness is invoked as a required check on the release path.",
        ],
        "insufficient_alone": [
            "A product feature scores resumes, documents, or users and is named evaluation.",
            "Unit tests exist without a behavior-quality threshold.",
            "An evals folder exists with no gate that can fail a release.",
        ],
        "contradiction": [
            "Release config deploys model or prompt changes while skipping the documented eval gate.",
        ],
        "evidence_sources": ["tests", "ci", "code"],
        "notes": "Pre-production gate for shipped behavior. Product scoring is not this family.",
    },
    {
        "family_id": "QF-0010",
        "control_id": "CTRL-0003",
        "diagnostic_job": "permission_boundary",
        "strong": [
            "A request handler or tool checks an authorization policy before performing the action.",
            "Role, scope, or permission guardrails limit what a principal may do.",
        ],
        "supporting": [
            "An authorization middleware or decorator is attached to inbound routes.",
        ],
        "insufficient_alone": [
            "An outbound Authorization header authenticates this service to a dependency.",
            "A permission field exists in a schema and is unused at runtime.",
        ],
        "contradiction": [
            "An inbound privileged action is explicitly marked as skipping authorization.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Authorization. Identity is authentication.",
    },
    {
        "family_id": "QF-0012",
        "control_id": "CTRL-0023",
        "diagnostic_job": "authentication",
        "strong": [
            "The inbound caller is identified before authorization, via session, token, or workload identity.",
            "A request dependency verifies a human or workload credential on the serving path.",
        ],
        "supporting": [
            "Session or JWT verification is present on inbound routes.",
        ],
        "insufficient_alone": [
            "An outbound token is attached when this service calls GitHub or a model vendor.",
            "An auth library is listed as a dependency and unused on the request path.",
        ],
        "contradiction": [
            "An inbound route that mutates state is marked as skipping caller identification.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Authn only. Outbound vendor tokens are not caller identity.",
    },
    {
        "family_id": "QF-0016",
        "control_id": "CTRL-0126",
        "diagnostic_job": "encrypt_transit",
        "strong": [
            "The serving path requires TLS, HTTPS redirect, or a TLS listener for API traffic.",
            "Client and server are configured to refuse plaintext for the in-scope channel.",
        ],
        "supporting": [
            "Outbound dependency URLs use https on the runtime call.",
        ],
        "insufficient_alone": [
            "An HTTP client library is installed.",
            "Documentation mentions TLS with no runtime or listener config.",
        ],
        "contradiction": [
            "A public listener is configured to serve the API over plaintext HTTP with TLS disabled.",
        ],
        "evidence_sources": ["code", "config", "deployment"],
        "notes": "In-transit only. A client https URL is supporting, not a TLS-enforced server.",
    },
    {
        "family_id": "QF-0017",
        "control_id": "CTRL-0064",
        "diagnostic_job": "encrypt_rest",
        "strong": [
            "Data that outlives a request is encrypted before it is written to the store or volume.",
            "A KMS, application cipher, or encrypted volume is applied to the persisted payload.",
        ],
        "supporting": [
            "Store or volume configuration enables encryption at rest for the data path.",
        ],
        "insufficient_alone": [
            "A database or file store is used with no encryption setting.",
            "HTTPS on the wire is treated as at-rest encryption.",
        ],
        "contradiction": [
            "Persisted secrets or user data are written in cleartext with encryption explicitly disabled.",
        ],
        "evidence_sources": ["code", "config", "deployment"],
        "notes": "At-rest only. Transit TLS does not satisfy this family.",
    },
    {
        "family_id": "QF-0018",
        "control_id": "CTRL-0013",
        "diagnostic_job": "unhealthy_detect",
        "strong": [
            "Remote calls or model endpoints are monitored and an alarm fires on persistent timeout or error.",
            "An SLO, alert rule, or pager path is configured for unhealthy dependency behavior.",
        ],
        "supporting": [
            "Metrics or traces of dependency errors are exported to an alerting backend.",
        ],
        "insufficient_alone": [
            "logger.error or print records a failure with no alarm.",
            "A healthz route exists that does not watch the dependency.",
        ],
        "contradiction": [
            "Alerting for the dependency is explicitly disabled on the production path.",
        ],
        "evidence_sources": ["code", "config", "ops"],
        "notes": "Detection and alarm. Presence of logs is telemetry_exist.",
    },
    {
        "family_id": "QF-0019",
        "control_id": "CTRL-0001",
        "diagnostic_job": "telemetry_exist",
        "strong": [
            "A named logger, tracer, or metrics client records the request or model operation path.",
            "Logs or traces are stored and can be queried for that operation.",
        ],
        "supporting": [
            "Structured logging is configured for the service process.",
        ],
        "insufficient_alone": [
            "The logging package is imported and unused.",
            "print is used only in a one-shot script.",
        ],
        "contradiction": [
            "Telemetry for the operation path is explicitly disabled.",
        ],
        "evidence_sources": ["code", "config"],
        "notes": "Telemetry presence. Alarms on that telemetry are unhealthy_detect.",
    },
    {
        "family_id": "QF-0030",
        "control_id": "CTRL-0070",
        "diagnostic_job": "prompt_injection",
        "strong": [
            "Untrusted retrieved, web, or user content is filtered or fenced before it can change instructions or tool use.",
            "A prompt-injection control treats indirect content with the same rigor as direct user input.",
        ],
        "supporting": [
            "Untrusted content is labeled or isolated from system instructions before the model call.",
        ],
        "insufficient_alone": [
            "A prompt tells the model to use only the provided context.",
            "Input length limits exist with no instruction-hijack control.",
        ],
        "contradiction": [
            "Untrusted documents are concatenated into the system prompt with injection defenses disabled.",
        ],
        "evidence_sources": ["code"],
        "notes": "Instruction or tool hijack. Generic input validation is a different family.",
    },
    {
        "family_id": "QF-0032",
        "control_id": "CTRL-0008",
        "diagnostic_job": "input_validation",
        "strong": [
            "Inbound request or user input is schema-validated before the handler acts on it.",
            "A validator rejects malformed or out-of-range fields on the serving path.",
        ],
        "supporting": [
            "Typed request models are declared for inbound API payloads.",
        ],
        "insufficient_alone": [
            "Internal data classes exist for stored records and are not used on inbound requests.",
            "A type hint is present with no runtime check.",
        ],
        "contradiction": [
            "Inbound payloads are parsed as raw objects with validation explicitly skipped.",
        ],
        "evidence_sources": ["code"],
        "notes": "Input and request checks. Prompt-injection filtering is a different family.",
    },
    {
        "family_id": "QF-0035",
        "control_id": "CTRL-0094",
        "diagnostic_job": "hardcoded_secrets",
        "strong": [
            "An automated secret scanner or policy identifies hardcoded credentials in the tree or runtime.",
            "Credentials are loaded from a secret manager rather than the source tree.",
        ],
        "supporting": [
            "API keys and tokens are read from the environment or a secrets file that is not committed.",
        ],
        "insufficient_alone": [
            "A comment says not to commit secrets.",
            "An empty default string is passed to getenv.",
        ],
        "contradiction": [
            "A live credential, private key, or password literal is embedded in source.",
        ],
        "evidence_sources": ["code", "config", "ci"],
        "notes": "Where credentials are embedded. Env reads are supporting, not a scanner.",
    },
]
