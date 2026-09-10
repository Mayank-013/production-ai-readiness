"""Control evidence contract (C1–C4).

Mirrors the trait system:

    C1  what counts as control evidence
    C2  observe control evidence
    C3  assess control
    C4  benchmark

Absence of evidence is UNKNOWN, not FAIL.
FAIL requires contradiction / unsafe implementation evidence.

Do not emit one expectation per CPF object.
Do not retune trait detectors or overwrite B4 dests.
Skills and validation stay locked.

Contract: docs/control-evidence.md
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL_DOC = "docs/control-evidence.md"
SCHEMA_DIR = ROOT / "engineering-intelligence" / "schemas"
CONTROL_EXPECTATION_SCHEMA_PATH = SCHEMA_DIR / "control_evidence_expectation.json"
CONTROL_OBSERVATION_SCHEMA_PATH = SCHEMA_DIR / "control_evidence_observation.json"
CONTROL_ASSESSMENT_SCHEMA_PATH = SCHEMA_DIR / "control_assessment.json"
CONTROL_REFERENCE_SCHEMA_PATH = SCHEMA_DIR / "control_benchmark_reference.json"
CONTROL_COMPARISON_SCHEMA_PATH = SCHEMA_DIR / "control_benchmark_comparison.json"
ENGINEERING_QUESTION_SCHEMA_PATH = SCHEMA_DIR / "engineering_question.json"
RECOMMENDATION_SCHEMA_PATH = SCHEMA_DIR / "recommendation.json"
PLAYBOOK_SCHEMA_PATH = SCHEMA_DIR / "gap_playbook.json"
PLAYBOOK_VALIDATION_SCHEMA_PATH = SCHEMA_DIR / "playbook_validation.json"
SKILL_SCHEMA_PATH = SCHEMA_DIR / "implementation_skill.json"
VALIDATION_METHOD_SCHEMA_PATH = SCHEMA_DIR / "validation_method.json"
SKILL_APPLICATION_SCHEMA_PATH = SCHEMA_DIR / "skill_application.json"
SKILL_VALIDATION_SCHEMA_PATH = SCHEMA_DIR / "skill_validation.json"

SCHEMA_VERSION = "control-0.1"
PLAYBOOK_SCHEMA_VERSION = "playbook-0.1"
PLAYBOOK_DOC = "docs/gap-playbooks.md"
ABSENCE_POLICY_UNKNOWN = "unknown"
CONTROL_STAGES = ("C1", "C2", "C3", "C4")

STATES = ("SATISFIED", "PARTIAL", "UNKNOWN", "FAIL")
STRENGTHS = ("strong", "supporting", "insufficient", "contradiction")
EVIDENCE_SOURCES = (
    "code",
    "config",
    "dependencies",
    "architecture",
    "tests",
    "ci",
    "deployment",
    "ops",
)

EXPECTED_EXPECTATIONS = 12
EXPECTED_C4_REPOS = 1
EXPECTED_C4_ROWS = 12
C4_REPO = "HackerRankATS"

# Dest refuse-overwrite is the write lock. These flags block a second construction pass.
CONTROL_EVIDENCE_LOCKED = False
CONTROL_OBSERVE_LOCKED = False
CONTROL_ASSESS_LOCKED = False
CONTROL_BENCHMARK_LOCKED = False
CONTROL_QUESTIONS_LOCKED = False
CONTROL_RECOMMENDATIONS_LOCKED = False
CONTROL_LAYER_LOCKED = False
PLAYBOOK_LOCKED = False
PLAYBOOK_VALIDATION_LOCKED = False
SKILLS_LOCKED = True
VALIDATION_LOCKED = True
SKILL_LAYER_LOCKED = False
REPO_ANALYSIS_LOCKED = False
SKILL_SCHEMA_VERSION = "skill-0.1"
SKILL_DOC = "docs/implementation-skills.md"
EXPECTED_SKILLS = 6
EXPECTED_IMPLEMENTED_SKILLS = 1

TRAIT_BENCHMARK_V2_FREEZE_LOCKED = True


class ControlError(RuntimeError):
    pass


def control_locked_message(stage: str) -> str:
    return (
        f"{stage} stays locked. "
        "Do not overwrite the control-evidence dests. "
        "Do not expand toward one expectation per CPF. "
        f"Contract: {CONTROL_DOC}."
    )


def skills_locked_message() -> str:
    return (
        "Frozen recommendation dests do not receive skill_id. "
        "The skill layer writes its own dest. "
        f"Contract: {SKILL_DOC}."
    )


def repo_analysis_locked_message() -> str:
    return (
        "Repo analysis dest already exists; refusing to overwrite. "
        "Agent skills stay locked. "
        f"Contract: {PLAYBOOK_DOC}."
    )


def skills_stay_locked_message() -> str:
    return (
        "Implementation skills stay locked. "
        "The repo-analysis MVP emits finding playbooks, not skill_id agent playbooks. "
        f"Contract: {PLAYBOOK_DOC}."
    )


def assert_control_locked(flag: bool, stage: str) -> None:
    if flag:
        raise ControlError(control_locked_message(stage))


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_row(row: dict, schema: dict, *, label: str) -> None:
    missing = [key for key in schema["required"] if key not in row]
    if missing:
        raise ControlError(f"{label}: missing required fields {missing}")
    extra = set(row) - set(schema["properties"])
    if extra:
        raise ControlError(f"{label}: unknown fields {sorted(extra)}")


def refuse_overwrite(path: Path, label: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        raise ControlError(f"{path.name} already exists; refusing to overwrite {label}")
