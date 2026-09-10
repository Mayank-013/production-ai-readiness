"""Implementation skills attached to PARTIAL/FAIL findings.

P4.1  contract + finding compatibility
P4.2  one implemented skill (secret scanner)
P4.3  apply that skill to one development finding
P4.4  re-run affected C2/C3 detectors
P4.5  before-vs-after validation
P4.6  expand the catalog to the six playbook evidence classes

A skill attaches to family + state + evidence_class, not to a family
in the abstract. UNKNOWN and SATISFIED receive no skill.
Frozen C4 recommendations do not receive skill_id.

Contract: docs/implementation-skills.md
"""

from __future__ import annotations

import shutil
from hashlib import sha256
from pathlib import Path

from pipeline.common import CONSOLIDATION, ROOT, dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_assess import assess_controls
from pipeline.control_evidence_contract import (
    EXPECTED_IMPLEMENTED_SKILLS,
    EXPECTED_SKILLS,
    SKILL_APPLICATION_SCHEMA_PATH,
    SKILL_DOC,
    SKILL_LAYER_LOCKED,
    SKILL_SCHEMA_PATH,
    SKILL_SCHEMA_VERSION,
    SKILL_VALIDATION_SCHEMA_PATH,
    VALIDATION_METHOD_SCHEMA_PATH,
    ControlError,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.control_evidence_observe import collect_control_observations
from pipeline.repo_analysis import classify_evidence_class
from pipeline.system_trait import trait_paths

DEV_FINDING_FIXTURE = ROOT / "pipeline" / "fixtures" / "control_evidence_v1"
APPLIED_SKILL_ID = "SKL-0001"
PROTECTED_CONTROL = (
    "recommendations",
    "playbooks",
    "playbook_freeze",
    "assessments",
    "questions",
    "freeze",
)
PROTECTED_ANALYSIS = ("report", "findings", "freeze")
PROTECTED_TRAIT = ("trait_conclusions", "trait_benchmark_v2_freeze")

SKILL_SPECS: list[dict] = [
    {
        "id": "SKL-0001",
        "name": "Add secret scanning for env-only credentials",
        "family_id": "QF-0035",
        "assessment_state": "PARTIAL",
        "evidence_class": "getenv_no_scanner",
        "apply_status": "implemented",
        "inputs": ["source tree", "existing getenv call sites", "CI or pre-commit hook"],
        "steps": [
            "Add a secret scanner configuration that can fail the merge path.",
            "Wire the scanner in pre-commit or CI so a planted credential is caught.",
            "Keep runtime secrets in the environment; do not move them into source.",
            "Document how to rotate a credential if the scanner finds one.",
        ],
        "constraints": [
            "Do not commit a live credential, even as a test fixture.",
            "Do not rewrite application getenv call sites.",
            "Do not treat a comment that says not to commit secrets as the control.",
        ],
        "artifacts": [
            {"path": ".gitleaks.toml", "purpose": "Scanner configuration C2 can observe."},
            {"path": ".pre-commit-config.yaml", "purpose": "Merge-path gate that can fail on secrets."},
            {"path": "docs/secret-rotation.md", "purpose": "Rotation path after a detected leak."},
        ],
        "validation_id": "VAL-0001",
    },
    {
        "id": "SKL-0002",
        "name": "Remove a live credential literal from source",
        "family_id": "QF-0035",
        "assessment_state": "FAIL",
        "evidence_class": "live_literal_in_source",
        "apply_status": "catalog",
        "inputs": ["offending file", "credential owner", "secret manager"],
        "steps": [
            "Remove the live literal from the default branch.",
            "Rotate the exposed credential immediately.",
            "Load the replacement from the environment or a secret manager.",
            "Add a scanner so the same class of literal cannot merge again.",
        ],
        "constraints": [
            "Do not leave the old credential valid after the patch.",
            "Do not replace the literal with another committed secret.",
        ],
        "artifacts": [
            {"path": ".gitleaks.toml", "purpose": "Scanner that would have caught the literal."},
        ],
        "validation_id": "VAL-0002",
    },
    {
        "id": "SKL-0003",
        "name": "Name the degrade path for a down dependency",
        "family_id": "QF-0003",
        "assessment_state": "PARTIAL",
        "evidence_class": "supporting_fallback_no_named_failover",
        "apply_status": "catalog",
        "inputs": ["primary dependency", "existing except or missing-key fallback"],
        "steps": [
            "Name the branch taken when the primary dependency times out or is down.",
            "Return a reduced or unavailable result instead of only logging.",
            "Add a test that fails the dependency and expects that result.",
            "Emit a log or metric when the degrade path activates.",
        ],
        "constraints": [
            "Do not treat a missing API key fallback as the outage path.",
            "Do not crash the serving path to prove fail-fast unless the product contract requires it.",
        ],
        "artifacts": [
            {"path": "tests/test_dependency_down.py", "purpose": "Dependency-failure test."},
        ],
        "validation_id": "VAL-0003",
    },
    {
        "id": "SKL-0004",
        "name": "Replace refuse-to-degrade with a named unavailable result",
        "family_id": "QF-0003",
        "assessment_state": "FAIL",
        "evidence_class": "refuse_to_degrade",
        "apply_status": "catalog",
        "inputs": ["crash site", "product unavailable contract"],
        "steps": [
            "Remove the refuse-to-degrade flag or crash-only handler from the serving path.",
            "Return a documented unavailable or fallback payload.",
            "Keep fail-fast only where the product contract requires it.",
        ],
        "constraints": [
            "Do not hide the outage as a successful empty result without a named state.",
        ],
        "artifacts": [
            {"path": "tests/test_dependency_down.py", "purpose": "Proves the serving path no longer crashes."},
        ],
        "validation_id": "VAL-0004",
    },
    {
        "id": "SKL-0005",
        "name": "Enforce TLS on the serving surface",
        "family_id": "QF-0016",
        "assessment_state": "PARTIAL",
        "evidence_class": "outbound_https_no_serving_tls",
        "apply_status": "catalog",
        "inputs": ["serving host", "proxy or ingress", "certificate source"],
        "steps": [
            "Decide where TLS terminates: process, reverse proxy, or ingress.",
            "Refuse or redirect plaintext on the advertised serving path.",
            "Keep certificates outside the source tree.",
            "Probe the reachable path over HTTP and expect reject or redirect.",
        ],
        "constraints": [
            "Do not treat outbound https:// client URLs as serving-path TLS.",
            "Do not commit private keys.",
        ],
        "artifacts": [
            {"path": "deploy/tls.yaml", "purpose": "TLS listener, proxy, or ingress config."},
        ],
        "validation_id": "VAL-0005",
    },
    {
        "id": "SKL-0006",
        "name": "Disable an intentional plaintext listener",
        "family_id": "QF-0016",
        "assessment_state": "FAIL",
        "evidence_class": "plaintext_listener_tls_disabled",
        "apply_status": "catalog",
        "inputs": ["plaintext port", "TLS terminator"],
        "steps": [
            "Remove or bind the plaintext public listener to localhost.",
            "Require TLS on the advertised serving path.",
            "Fail deploy if TLS is off for an internet-reachable surface.",
        ],
        "constraints": [
            "Do not leave the previous plaintext port serving the API.",
        ],
        "artifacts": [
            {"path": "deploy/tls.yaml", "purpose": "TLS required on the advertised path."},
        ],
        "validation_id": "VAL-0006",
    },
]

VALIDATION_SPECS: list[dict] = [
    {
        "id": "VAL-0001",
        "skill_id": "SKL-0001",
        "family_id": "QF-0035",
        "kind": "detector-rerun",
        "before_state": "PARTIAL",
        "after_state_required": "SATISFIED",
        "checks": [
            "Re-run C2/C3 for QF-0035 on the patched worktree.",
            "A gitleaks or detect-secrets observation is present.",
            "Assessment state is SATISFIED, not PARTIAL.",
        ],
    },
    {
        "id": "VAL-0002",
        "skill_id": "SKL-0002",
        "family_id": "QF-0035",
        "kind": "detector-rerun",
        "before_state": "FAIL",
        "after_state_required": "PARTIAL",
        "checks": [
            "Re-run C2/C3 for QF-0035.",
            "The live literal contradiction is gone.",
            "State is no longer FAIL.",
        ],
    },
    {
        "id": "VAL-0003",
        "skill_id": "SKL-0003",
        "family_id": "QF-0003",
        "kind": "detector-rerun",
        "before_state": "PARTIAL",
        "after_state_required": "SATISFIED",
        "checks": [
            "Re-run C2/C3 for QF-0003.",
            "A named failover or fallback function is present.",
            "Assessment state is SATISFIED.",
        ],
    },
    {
        "id": "VAL-0004",
        "skill_id": "SKL-0004",
        "family_id": "QF-0003",
        "kind": "detector-rerun",
        "before_state": "FAIL",
        "after_state_required": "PARTIAL",
        "checks": [
            "Re-run C2/C3 for QF-0003.",
            "Refuse-to-degrade contradiction is gone.",
            "State is no longer FAIL.",
        ],
    },
    {
        "id": "VAL-0005",
        "skill_id": "SKL-0005",
        "family_id": "QF-0016",
        "kind": "detector-rerun",
        "before_state": "PARTIAL",
        "after_state_required": "SATISFIED",
        "checks": [
            "Re-run C2/C3 for QF-0016.",
            "A TLS listener, HTTPS redirect, or ingress config is present.",
            "Assessment state is SATISFIED.",
        ],
    },
    {
        "id": "VAL-0006",
        "skill_id": "SKL-0006",
        "family_id": "QF-0016",
        "kind": "detector-rerun",
        "before_state": "FAIL",
        "after_state_required": "PARTIAL",
        "checks": [
            "Re-run C2/C3 for QF-0016.",
            "The plaintext listener contradiction is gone.",
            "State is no longer FAIL.",
        ],
    },
]

SKL0001_ARTIFACTS = {
    ".gitleaks.toml": (
        'title = "gitleaks"\n'
        "\n"
        "[extend]\n"
        "useDefault = true\n"
    ),
    ".pre-commit-config.yaml": (
        "repos:\n"
        "  - repo: https://github.com/gitleaks/gitleaks\n"
        "    rev: v8.18.4\n"
        "    hooks:\n"
        "      - id: gitleaks\n"
    ),
    "docs/secret-rotation.md": (
        "If a scanner finds a credential in this tree, revoke it, issue a\n"
        "replacement from the secret manager or environment, and re-run the\n"
        "gitleaks gate before merging.\n"
    ),
}


def skill_paths(*, root: Path | None = None) -> dict[str, Path]:
    dest = (root or CONSOLIDATION) / "skills"
    applied = dest / "applied"
    return {
        "dir": dest,
        "skills": dest / "skills.jsonl",
        "validations": dest / "validation_methods.jsonl",
        "attachments": dest / "attachments.jsonl",
        "compatibility_stats": dest / "compatibility_stats.json",
        "application": applied / "application.json",
        "worktree": applied / "worktree",
        "before": applied / "before_assessments.jsonl",
        "after": applied / "after_assessments.jsonl",
        "validation": applied / "validation.json",
        "stats": dest / "stats.json",
        "freeze": dest / "freeze.json",
    }


def _hashes(paths: dict[str, Path], keys: tuple[str, ...]) -> dict[str, str]:
    out = {}
    for key in keys:
        path = paths.get(key)
        if path is None or not path.exists():
            continue
        out[key] = sha256(path.read_bytes()).hexdigest()
    return out


def skill_compatible(skill: dict, finding: dict) -> bool:
    """Finding compatibility. Family alone is not enough."""
    state = finding.get("assessment_state") or finding.get("state")
    if state not in {"PARTIAL", "FAIL"}:
        return False
    if finding.get("family_id") != skill["family_id"]:
        return False
    if state != skill["assessment_state"]:
        return False
    evidence_class = finding.get("evidence_class")
    if not evidence_class or evidence_class != skill["evidence_class"]:
        return False
    return True


def attach_skills(findings: list[dict], skills: list[dict] | None = None) -> list[dict]:
    skills = skills or SKILL_SPECS
    rows = []
    for finding in findings:
        state = finding.get("assessment_state") or finding.get("state")
        if state in {"UNKNOWN", "SATISFIED"}:
            continue
        matches = [skill for skill in skills if skill_compatible(skill, finding)]
        if len(matches) > 1:
            raise ControlError(
                f"multiple skills match {finding.get('family_id')} {state} "
                f"{finding.get('evidence_class')}"
            )
        if not matches:
            continue
        skill = matches[0]
        rows.append(
            {
                "finding_id": finding.get("id") or f"{finding['family_id']}:{state}",
                "family_id": finding["family_id"],
                "assessment_state": state,
                "evidence_class": finding["evidence_class"],
                "skill_id": skill["id"],
                "validation_id": skill["validation_id"],
                "apply_status": skill["apply_status"],
                "repo": finding.get("repo"),
            }
        )
    return rows


def _skill_row(spec: dict) -> dict:
    schema = load_schema(SKILL_SCHEMA_PATH)
    row = {
        "id": spec["id"],
        "name": spec["name"],
        "family_id": spec["family_id"],
        "assessment_state": spec["assessment_state"],
        "evidence_class": spec["evidence_class"],
        "apply_status": spec["apply_status"],
        "inputs": list(spec["inputs"]),
        "steps": list(spec["steps"]),
        "constraints": list(spec["constraints"]),
        "artifacts": [dict(item) for item in spec["artifacts"]],
        "validation_id": spec["validation_id"],
        "schema_version": SKILL_SCHEMA_VERSION,
        "status": "frozen",
    }
    validate_row(row, schema, label=row["id"])
    return row


def _validation_row(spec: dict) -> dict:
    schema = load_schema(VALIDATION_METHOD_SCHEMA_PATH)
    row = {
        **spec,
        "schema_version": SKILL_SCHEMA_VERSION,
        "status": "frozen",
    }
    validate_row(row, schema, label=row["id"])
    return row


def write_skill_catalog(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(SKILL_LAYER_LOCKED, "Implementation skill catalog")
    paths = paths or skill_paths()
    refuse_overwrite(paths["skills"], "the implementation skill catalog")
    skills = [_skill_row(spec) for spec in SKILL_SPECS]
    validations = [_validation_row(spec) for spec in VALIDATION_SPECS]
    if len(skills) != EXPECTED_SKILLS:
        raise ControlError(f"expected {EXPECTED_SKILLS} skills, got {len(skills)}")
    implemented = [row for row in skills if row["apply_status"] == "implemented"]
    if len(implemented) != EXPECTED_IMPLEMENTED_SKILLS:
        raise ControlError(f"expected {EXPECTED_IMPLEMENTED_SKILLS} implemented skill")
    keys = {(row["family_id"], row["assessment_state"], row["evidence_class"]) for row in skills}
    if len(keys) != len(skills):
        raise ControlError("skills must be unique on family + state + evidence_class")
    families = {row["family_id"] for row in skills}
    for family in families:
        partial = next(row for row in skills if row["family_id"] == family and row["assessment_state"] == "PARTIAL")
        fail = next(row for row in skills if row["family_id"] == family and row["assessment_state"] == "FAIL")
        if partial["steps"] == fail["steps"]:
            raise ControlError(f"{family}: PARTIAL and FAIL skills are identical")
    paths["dir"].mkdir(parents=True, exist_ok=True)
    write_jsonl(paths["skills"], skills)
    write_jsonl(paths["validations"], validations)
    return {
        "skills": len(skills),
        "implemented": len(implemented),
        "catalog": len(skills) - len(implemented),
        "validation_methods": len(validations),
    }


def write_skill_attachments(
    *,
    paths: dict[str, Path] | None = None,
    findings_path: Path | None = None,
) -> list[dict]:
    paths = paths or skill_paths()
    findings_path = findings_path or (CONSOLIDATION / "repo_analysis" / "findings.jsonl")
    if not findings_path.exists():
        return []
    findings = read_jsonl(findings_path)
    rows = attach_skills(findings)
    write_jsonl(paths["attachments"], rows)
    dump_json(
        paths["compatibility_stats"],
        {
            "findings": len(findings),
            "attached": len(rows),
            "unknown_skills": 0,
            "family_blind": False,
            "note": "Skills attach to findings, not families.",
        },
    )
    return rows


def assess_repo(repo: Path, *, repo_id: str) -> list[dict]:
    observations = collect_control_observations(repo, repo=repo_id)
    return assess_controls(observations, repo=repo_id)


def finding_from_assessments(assessments: list[dict], observations: list[dict]) -> dict | None:
    by_family = {row["family_id"]: row for row in assessments}
    target = by_family.get("QF-0035")
    if target is None or target["state"] != "PARTIAL":
        return None
    evidence_class = classify_evidence_class("QF-0035", "PARTIAL", observations)
    return {
        "id": "find:QF-0035:PARTIAL",
        "family_id": "QF-0035",
        "assessment_state": "PARTIAL",
        "evidence_class": evidence_class,
        "repo": target["repo"],
    }


def apply_skill(
    *,
    skill_id: str = APPLIED_SKILL_ID,
    source: Path | None = None,
    paths: dict[str, Path] | None = None,
) -> dict:
    assert_control_locked(SKILL_LAYER_LOCKED, "Skill apply")
    if skill_id != APPLIED_SKILL_ID:
        raise ControlError(f"{skill_id} is catalog-only; only {APPLIED_SKILL_ID} is implemented")
    source = Path(source or DEV_FINDING_FIXTURE).resolve()
    if source == Path("/Users/mauryans/Projects/HackerRankATS").resolve():
        raise ControlError("do not apply skills to HackerRankATS")
    paths = paths or skill_paths()
    refuse_overwrite(paths["application"], "the skill application dest")
    worktree = paths["worktree"]
    if worktree.exists() and any(worktree.iterdir()):
        raise ControlError("skill worktree already exists; refusing to overwrite")
    if not source.is_dir():
        raise ControlError(f"development finding fixture is missing: {source}")

    shutil.copytree(source, worktree, dirs_exist_ok=True)
    observations = collect_control_observations(worktree, repo="skill_dev")
    assessments = assess_controls(observations, repo="skill_dev")
    finding = finding_from_assessments(assessments, observations)
    if finding is None:
        raise ControlError("development fixture must have a QF-0035 PARTIAL finding")
    skill = next(row for row in SKILL_SPECS if row["id"] == skill_id)
    if not skill_compatible(skill, finding):
        raise ControlError("SKL-0001 is not compatible with the development finding")

    written = []
    for rel, body in SKL0001_ARTIFACTS.items():
        dest = worktree / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        written.append(rel)
    application = {
        "id": "apply:SKL-0001:01",
        "skill_id": skill_id,
        "family_id": "QF-0035",
        "assessment_state": "PARTIAL",
        "evidence_class": finding["evidence_class"],
        "source_repo": str(source),
        "worktree": str(worktree),
        "files_written": written,
        "schema_version": SKILL_SCHEMA_VERSION,
        "status": "frozen",
    }
    validate_row(application, load_schema(SKILL_APPLICATION_SCHEMA_PATH), label=application["id"])
    paths["application"].parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(paths["before"], assessments)
    dump_json(paths["application"], application)
    if (DEV_FINDING_FIXTURE / ".gitleaks.toml").exists():
        raise ControlError("apply mutated the source fixture")
    return application


def compare_assessments(
    before: list[dict],
    after: list[dict],
    *,
    skill: dict,
    method: dict,
) -> dict:
    before_by = {row["family_id"]: row["state"] for row in before}
    after_by = {row["family_id"]: row["state"] for row in after}
    family = skill["family_id"]
    before_state = before_by[family]
    after_state = after_by[family]
    closed = after_state == method["after_state_required"]
    demoted = False
    for fid, state in before_by.items():
        if fid == family:
            continue
        if state == "SATISFIED" and after_by.get(fid) != "SATISFIED":
            demoted = True
    decision = "accept" if closed and not demoted else "revise"
    row = {
        "skill_id": skill["id"],
        "validation_id": method["id"],
        "family_id": family,
        "before_state": before_state,
        "after_state": after_state,
        "required_after": method["after_state_required"],
        "closed": closed,
        "other_families_demoted": demoted,
        "decision": decision,
        "schema_version": SKILL_SCHEMA_VERSION,
        "status": "frozen",
    }
    if decision != "accept":
        row["notes"] = "target family did not close or another SATISFIED family was demoted"
    validate_row(row, load_schema(SKILL_VALIDATION_SCHEMA_PATH), label=skill["id"])
    return row


def validate_applied_skill(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(SKILL_LAYER_LOCKED, "Skill validation")
    paths = paths or skill_paths()
    refuse_overwrite(paths["validation"], "the skill validation dest")
    worktree = paths["worktree"]
    if not worktree.is_dir():
        raise ControlError("apply the implemented skill before validating")
    before = read_jsonl(paths["before"])
    after = assess_repo(worktree, repo_id="skill_dev")
    skill = next(row for row in SKILL_SPECS if row["id"] == APPLIED_SKILL_ID)
    method = next(row for row in VALIDATION_SPECS if row["id"] == skill["validation_id"])
    review = compare_assessments(before, after, skill=skill, method=method)
    if review["decision"] != "accept":
        raise ControlError("skill validation did not accept the applied finding")
    write_jsonl(paths["after"], after)
    dump_json(paths["validation"], review)
    return review


def write_skill_layer(*, paths: dict[str, Path] | None = None) -> dict:
    assert_control_locked(SKILL_LAYER_LOCKED, "Skill layer")
    paths = paths or skill_paths()
    control = control_paths()
    traits = trait_paths()
    refuse_overwrite(paths["freeze"], "the skill layer dest")
    before_control = _hashes(control, PROTECTED_CONTROL)
    before_trait = _hashes(traits, PROTECTED_TRAIT)
    analysis = {
        "report": CONSOLIDATION / "repo_analysis" / "report.json",
        "findings": CONSOLIDATION / "repo_analysis" / "findings.jsonl",
        "freeze": CONSOLIDATION / "repo_analysis" / "freeze.json",
    }
    before_analysis = _hashes(analysis, PROTECTED_ANALYSIS)

    catalog = write_skill_catalog(paths=paths)
    attachments = write_skill_attachments(paths=paths)
    application = apply_skill(paths=paths)
    review = validate_applied_skill(paths=paths)

    if _hashes(control, PROTECTED_CONTROL) != before_control:
        raise ControlError("skill layer mutated a control-evidence dest")
    if _hashes(traits, PROTECTED_TRAIT) != before_trait:
        raise ControlError("skill layer mutated a trait dest")
    if _hashes(analysis, PROTECTED_ANALYSIS) != before_analysis:
        raise ControlError("skill layer mutated the repo-analysis dest")

    stats = {
        "skills": catalog["skills"],
        "implemented": catalog["implemented"],
        "catalog": catalog["catalog"],
        "attachments": len(attachments),
        "applied_skill": application["skill_id"],
        "applied_family": application["family_id"],
        "before_state": review["before_state"],
        "after_state": review["after_state"],
        "closed": review["closed"],
        "validation_decision": review["decision"],
        "unknown_skills": 0,
        "family_blind": False,
        "recommendations_mutated": False,
        "repo_analysis_mutated": False,
        "hackerrankats_mutated": False,
        "status": "frozen",
        "next_gate": "remaining_catalog_apply",
        "note": (
            "Skill layer written. One implemented skill applied to a development "
            "finding and closed by detector re-run. "
            f"Contract: {SKILL_DOC}."
        ),
    }
    freeze = {
        "skills": catalog["skills"],
        "implemented": catalog["implemented"],
        "applied_skill": application["skill_id"],
        "closed": review["closed"],
        "validation_decision": review["decision"],
        "recommendations_mutated": False,
        "repo_analysis_mutated": False,
        "status": "frozen",
        "next_gate": "remaining_catalog_apply",
        "note": stats["note"],
    }
    dump_json(paths["stats"], stats)
    dump_json(paths["freeze"], freeze)
    stats["freeze"] = str(paths["freeze"])
    return stats
