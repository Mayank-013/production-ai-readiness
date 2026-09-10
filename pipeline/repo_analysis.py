"""Integrated repo-analysis: C1 plus Phase 5 packs.

    repo → traits → family applicability
      → original C1 pack
      → P5 eval / security / runtime / RAG / ops / cost
      → one assessment / report

Each pack keeps its sealed specs, detectors, and assessment rules.
The merge layer does not reinterpret C1–C4. A family is evaluated
at most once. Dropped families stay out. UNKNOWN is abstain.

The first 12-family dest stays frozen. This command writes
repo_analysis_integrated/.

Contract: docs/repo-analysis.md
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path

from pipeline.common import CONSOLIDATION, dump_json, read_jsonl, write_jsonl
from pipeline.control_evidence import control_paths
from pipeline.control_evidence_c1 import EXPECTATION_SPECS
from pipeline.control_evidence_contract import (
    REPO_ANALYSIS_LOCKED,
    SKILLS_LOCKED,
    ControlError,
    assert_control_locked,
    load_schema,
    refuse_overwrite,
    validate_row,
)
from pipeline.control_questions import load_specializations, specialize_pack
from pipeline.control_recommendations import build_recommendations
from pipeline.gap_playbook import (
    PLAYBOOK_SPECS,
    _row,
    _spec_key,
    catalog_playbooks_for_validation,
)
from pipeline.gap_playbook_validate import validate_playbooks
from pipeline.repo_analysis_packs import (
    DROPPED_FAMILIES,
    EXPECTED_INSTANTIATED,
    PACKS,
    applicable_pack_families,
    assert_pack_registry,
    build_pack_recommendations,
    c1_identity,
    classify_pack_evidence_class,
    finding_identity,
    stamp_assessment,
)
from pipeline.system_trait import trait_paths
from pipeline.system_trait_contract import (
    EXPECTED_FROZEN_DETECTORS,
    EXPECTED_TRAITS,
    HACKERRANKATS_REPO,
    TraitError,
    family_applies,
)
from pipeline.system_trait_detector_run import collect_detector_observations
from pipeline.system_trait_map import aggregate_trait_states

SCHEMA_VERSION = "repo-analysis-0.1"
REPO_ANALYSIS_DOC = "docs/repo-analysis.md"
REPORT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "engineering-intelligence"
    / "schemas"
    / "repo_analysis_report.json"
)
ASSESSMENT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "engineering-intelligence"
    / "schemas"
    / "repo_analysis_assessment.json"
)
BASELINE_DEST_NAME = "repo_analysis"
INTEGRATED_DEST_NAME = "repo_analysis_integrated"
PRODUCT_RUNS_DIR = "product_runs"
P5_DESTS = (
    "p5_eval",
    "p5_security",
    "p5_runtime",
    "p5_rag",
    "p5_ops",
    "p5_cost",
)
PROTECTED_CONTROL = (
    "expectations",
    "observations",
    "assessments",
    "questions",
    "recommendations",
    "freeze",
    "playbooks",
    "playbook_validation",
    "playbook_freeze",
)
PROTECTED_TRAIT = (
    "traits",
    "applicability",
    "trait_detectors_frozen",
    "trait_conclusions",
    "trait_benchmark_references",
    "trait_benchmark_v2_freeze",
)


def _dest_paths(dest: Path) -> dict[str, Path]:
    return {
        "dir": dest,
        "report": dest / "report.json",
        "report_md": dest / "report.md",
        "brief": dest / "brief.json",
        "brief_md": dest / "brief.md",
        "findings": dest / "findings.jsonl",
        "questions": dest / "questions.jsonl",
        "assessments": dest / "assessments.jsonl",
        "traits": dest / "traits.jsonl",
        "playbooks": dest / "playbooks.jsonl",
        "validation": dest / "validation.jsonl",
        "stats": dest / "stats.json",
        "freeze": dest / "freeze.json",
    }


def repo_analysis_baseline_paths(*, root: Path | None = None) -> dict[str, Path]:
    """Frozen 12-family HackerRankATS dest. Do not overwrite."""
    return _dest_paths((root or CONSOLIDATION) / BASELINE_DEST_NAME)


def repo_analysis_paths(*, root: Path | None = None) -> dict[str, Path]:
    """Integrated 42-family dest (C1 + Phase 5). Default dest stays frozen after write."""
    return _dest_paths((root or CONSOLIDATION) / INTEGRATED_DEST_NAME)


def product_run_paths(repo_name: str, *, root: Path | None = None) -> dict[str, Path]:
    """Per-repo product run under product_runs/. Safe for --overwrite."""
    return _dest_paths(
        (root or CONSOLIDATION) / PRODUCT_RUNS_DIR / repo_name / INTEGRATED_DEST_NAME
    )


def product_runs_root(*, root: Path | None = None) -> Path:
    return (root or CONSOLIDATION) / PRODUCT_RUNS_DIR


def is_product_run_dest(paths: dict[str, Path], *, root: Path | None = None) -> bool:
    dest = paths["dir"].resolve()
    runs = product_runs_root(root=root).resolve()
    try:
        dest.relative_to(runs)
        return True
    except ValueError:
        return False


def resolve_repo_analysis_paths(
    dest: Path | str | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Path]:
    """Resolve write paths. --dest DIR writes report.json under DIR."""
    if dest is None:
        return repo_analysis_paths(root=root)
    return _dest_paths(Path(dest).expanduser().resolve())


def sealed_guard_paths(*, root: Path | None = None) -> dict[str, Path]:
    cons = root or CONSOLIDATION
    paths = {
        "c1_expectations": cons / "control_evidence" / "expectations.jsonl",
        "c4_assessments": cons / "control_evidence" / "c4" / "assessments.jsonl",
        "c4_freeze": cons / "control_evidence" / "c4" / "freeze.json",
        "playbook_freeze": cons / "control_evidence" / "playbooks" / "freeze.json",
        "skill_freeze": cons / "skills" / "freeze.json",
        "baseline_freeze": cons / BASELINE_DEST_NAME / "freeze.json",
        "baseline_assessments": cons / BASELINE_DEST_NAME / "assessments.jsonl",
        "baseline_findings": cons / BASELINE_DEST_NAME / "findings.jsonl",
        "b4_v2_freeze": cons / "system_traits" / "b4_v2" / "freeze.json",
    }
    for name in P5_DESTS:
        paths[f"{name}_freeze"] = cons / "control_evidence" / name / "freeze.json"
    return paths


def _hashes(paths: dict[str, Path], keys: tuple[str, ...]) -> dict[str, str]:
    out = {}
    for key in keys:
        path = paths.get(key)
        if path is None or not path.exists():
            continue
        out[key] = sha256(path.read_bytes()).hexdigest()
    return out


def stamp_trait_observations(hits: list[dict]) -> list[dict]:
    rows = []
    for i, hit in enumerate(hits, start=1):
        rows.append(
            {
                "detector_id": hit["detector_id"],
                "trait": hit["trait"],
                "supports": list(hit["supports"]),
                "observation": hit["observation"],
                "strength": hit["strength"],
                "file": hit["file"],
                "location": dict(hit["location"]),
                "observation_index": i,
            }
        )
    return rows


def conclusions_for_repo(
    traits: list[dict],
    observations: list[dict],
    *,
    repo: str,
    contract: list[dict],
) -> list[dict]:
    rows = []
    for state_row in aggregate_trait_states(
        traits,
        observations,
        contract=contract,
        require_review=False,
    ):
        rows.append(
            {
                "repo": repo,
                "trait": state_row["trait"],
                "trait_id": state_row["trait_id"],
                "state": state_row["state"],
                "basis": state_row["basis"],
                "observation_ids": list(state_row["observation_ids"]),
                "implied_by": list(state_row["implied_by"]),
            }
        )
    return rows


def applicable_c1_families(
    present: set[str],
    traits: list[dict],
    applicability: list[dict],
) -> list[str]:
    app_by = {row["family_id"]: row for row in applicability}
    out = []
    for spec in EXPECTATION_SPECS:
        fid = spec["family_id"]
        mapping = app_by.get(fid)
        if mapping is None:
            raise ControlError(f"{fid} has no applicability rule")
        if family_applies(mapping, present, traits=traits) == "APPLY":
            out.append(fid)
    return out


def classify_evidence_class(
    family_id: str,
    state: str,
    observations: list[dict],
) -> str | None:
    """Map this finding's evidence to a playbook class. None = no playbook."""
    hits = [row for row in observations if row["family_id"] == family_id]
    strengths = {row["strength"] for row in hits}
    if family_id == "QF-0003":
        if state == "FAIL" and "contradiction" in strengths:
            return "refuse_to_degrade"
        if state == "PARTIAL" and "supporting" in strengths:
            return "supporting_fallback_no_named_failover"
    elif family_id == "QF-0016":
        if state == "FAIL" and "contradiction" in strengths:
            return "plaintext_listener_tls_disabled"
        if state == "PARTIAL" and "supporting" in strengths and "strong" not in strengths:
            return "outbound_https_no_serving_tls"
    elif family_id == "QF-0035":
        if state == "FAIL" and "contradiction" in strengths:
            return "live_literal_in_source"
        if state == "PARTIAL" and "supporting" in strengths and "strong" not in strengths:
            return "getenv_no_scanner"
    return None


def _live_evidence(family_id: str, observations: list[dict], strengths: set[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in observations:
        if row["family_id"] != family_id or row["strength"] not in strengths:
            continue
        snippet = " ".join((row.get("snippet") or "").split())
        if len(snippet) < 8 or snippet in seen:
            continue
        seen.add(snippet)
        out.append(snippet[:160])
        if len(out) >= 5:
            break
    return out


def attach_run_playbooks(
    recommendations: list[dict],
    observations: list[dict],
) -> list[dict]:
    """Finding playbooks only. Attached to this run's evidence, not the family."""
    by_key = {_spec_key(spec): spec for spec in PLAYBOOK_SPECS}
    rows = []
    n = 0
    for rec in recommendations:
        if rec["assessment_state"] not in {"PARTIAL", "FAIL"}:
            raise ControlError("playbooks attach only to PARTIAL or FAIL recommendations")
        evidence_class = classify_evidence_class(
            rec["family_id"],
            rec["assessment_state"],
            observations,
        )
        spec = by_key.get((rec["family_id"], rec["assessment_state"]))
        if spec is None or evidence_class is None or spec["evidence_class"] != evidence_class:
            continue
        found = _live_evidence(
            rec["family_id"],
            observations,
            {"supporting", "strong"} if rec["assessment_state"] == "PARTIAL" else {"contradiction"},
        )
        payload = {
            **spec,
            "kind": "finding",
            "evidence_class": evidence_class,
            "evidence_found": found or list(spec["evidence_found"]),
        }
        n += 1
        rows.append(_row(payload, n, recommendation=rec))
    return rows


def attach_pack_playbooks(
    recommendations: list[dict],
    observations: list[dict],
    *,
    specs: list[dict],
    start: int = 1001,
) -> list[dict]:
    """Phase 5 finding playbooks. Uses the pack's written class only."""
    by_key = {_spec_key(spec): spec for spec in specs}
    rows = []
    n = start - 1
    for rec in recommendations:
        if rec["assessment_state"] not in {"PARTIAL", "FAIL"}:
            raise ControlError("playbooks attach only to PARTIAL or FAIL recommendations")
        evidence_class = classify_pack_evidence_class(
            rec["family_id"],
            rec["assessment_state"],
            observations,
            specs=specs,
        )
        spec = by_key.get((rec["family_id"], rec["assessment_state"]))
        if spec is None or evidence_class is None or spec["evidence_class"] != evidence_class:
            continue
        found = _live_evidence(
            rec["family_id"],
            observations,
            {"supporting", "strong"} if rec["assessment_state"] == "PARTIAL" else {"contradiction"},
        )
        payload = {
            **spec,
            "kind": "finding",
            "evidence_class": evidence_class,
            "evidence_found": found or list(spec["evidence_found"]),
        }
        n += 1
        rows.append(_row(payload, n, recommendation=rec))
    return rows


def useful_questions(questions: list[dict]) -> list[dict]:
    """SATISFIED is already answered. Ask UNKNOWN, PARTIAL, and FAIL only."""
    return [row for row in questions if row.get("assessment_state") in {"UNKNOWN", "PARTIAL", "FAIL"}]


def render_report_md(report: dict, findings: list[dict], asked: list[dict], playbooks: list[dict]) -> str:
    by_id = {row["id"]: row for row in playbooks}
    c1_families = report.get("applicable_c1_families")
    if c1_families is None:
        c1_count = len(report["applicable_families"])
    else:
        c1_count = len(c1_families)
    lines = [
        f"# {report['repo']} readiness",
        "",
        "No composite score. UNKNOWN is abstain, not a failed check.",
        "",
        f"Present traits: {', '.join(report['traits_present']) or '(none)'}",
        f"Applicable families: {len(report['applicable_families'])} (C1 {c1_count})",
        "",
        f"SATISFIED  {report['by_state']['SATISFIED']}",
        f"PARTIAL    {report['by_state']['PARTIAL']}",
        f"UNKNOWN    {report['by_state']['UNKNOWN']}",
        f"FAIL       {report['by_state']['FAIL']}",
        "",
    ]
    if findings:
        lines.append("## Findings")
        lines.append("")
        for i, finding in enumerate(findings, start=1):
            lines.append(f"{i}. **{finding['family_id']} {finding['assessment_state']}** — {finding['title']}")
            pb = by_id.get(finding.get("playbook_id") or "")
            if pb:
                lines.append(f"   {pb['problem']}")
                lines.append(f"   Next: {pb['implementation_options'][0]}")
            elif finding.get("playbook_available") is False:
                lines.append("   Recommendation only; no finding-shaped playbook for this evidence class.")
            lines.append("")
    if asked:
        lines.append("## Ask next")
        lines.append("")
        for row in asked:
            if row.get("assessment_state") != "UNKNOWN":
                continue
            lines.append(f"- {row['family_id']}: {row['prompt']}")
        lines.append("")
    lines.append("Agent skills stay locked. A playbook is instructions for an engineer, not a coding-agent skill.")
    lines.append("")
    return "\n".join(lines)


def analyze_repository(
    repo: Path,
    *,
    control: dict[str, Path] | None = None,
    traits_paths: dict[str, Path] | None = None,
) -> dict:
    repo = Path(repo).expanduser().resolve()
    if not repo.is_dir():
        raise ControlError(f"repository is missing: {repo}")
    control = control or control_paths()
    traits_paths = traits_paths or trait_paths()
    repo_id = repo.name

    catalog = read_jsonl(traits_paths["trait_detectors_frozen"])
    if len(catalog) != EXPECTED_FROZEN_DETECTORS:
        raise TraitError(f"expected {EXPECTED_FROZEN_DETECTORS} frozen detectors")
    traits = read_jsonl(traits_paths["traits"])
    if len(traits) != EXPECTED_TRAITS:
        raise TraitError(f"expected {EXPECTED_TRAITS} traits")
    contract = read_jsonl(traits_paths["trait_aggregation"])
    applicability = read_jsonl(traits_paths["applicability"])

    hits, _idx, trait_meta = collect_detector_observations(repo, catalog)
    stamped = stamp_trait_observations(hits)
    conclusions = conclusions_for_repo(traits, stamped, repo=repo_id, contract=contract)
    present = {row["trait"] for row in conclusions if row["state"] == "PRESENT"}
    likely = {row["trait"] for row in conclusions if row["state"] == "LIKELY"}
    instantiated = assert_pack_registry()
    families = {row["id"]: row for row in read_jsonl(control["families"])}
    assessment_schema = load_schema(ASSESSMENT_SCHEMA_PATH)

    applicable: list[str] = []
    applicable_by_pack: dict[str, list[str]] = {}
    stamped: list[dict] = []
    c1_assessments: list[dict] = []
    c1_observations: list[dict] = []
    all_questions: list[dict] = []
    c1_recommendations: list[dict] = []
    p5_recommendations: list[dict] = []
    c1_playbooks: list[dict] = []
    p5_playbooks: list[dict] = []
    pack_observation_counts: dict[str, int] = {}
    seen_families: set[str] = set()

    for pack in PACKS:
        pack_applicable = applicable_pack_families(
            pack["specs"], present, traits, applicability
        )
        overlap = set(pack_applicable) & seen_families
        if overlap:
            raise ControlError(f"{sorted(overlap)} evaluated by more than one pack")
        leaked = set(pack_applicable) & DROPPED_FAMILIES
        if leaked:
            raise ControlError(f"dropped families reintroduced: {sorted(leaked)}")
        seen_families.update(pack_applicable)
        applicable.extend(pack_applicable)
        applicable_by_pack[pack["id"]] = pack_applicable

        observations = pack["collect"](repo, repo=repo_id)
        pack_observation_counts[pack["id"]] = len(observations)
        raw = [
            row
            for row in pack["assess"](observations, repo=repo_id)
            if row["family_id"] in set(pack_applicable)
        ]
        for row in raw:
            stamped_row = stamp_assessment(row, pack=pack["id"], observations=observations)
            validate_row(stamped_row, assessment_schema, label=f"{pack['id']}:{row['family_id']}")
            stamped.append(stamped_row)

        pack_questions = specialize_pack(
            present=present,
            traits=traits,
            applicability=applicability,
            specializations=load_specializations(control),
            families=families,
            assessments={row["family_id"]: row for row in raw},
            repo=repo_id,
            specs=pack["specs"],
        )
        all_questions.extend(pack_questions)
        if pack["c1"]:
            c1_assessments = raw
            c1_observations = observations
            c1_recommendations = build_recommendations(raw, pack_questions, repo=repo_id)
            c1_playbooks = attach_run_playbooks(c1_recommendations, observations)
        else:
            pack_recs = build_pack_recommendations(
                raw, pack_questions, pack["specs"], pack["actions"], repo=repo_id
            )
            p5_recommendations.extend(pack_recs)
            p5_playbooks.extend(
                attach_pack_playbooks(pack_recs, observations, specs=pack["playbooks"])
            )

    if any(fid in DROPPED_FAMILIES for fid in applicable):
        raise ControlError("dropped families must stay absent")
    recommendations = c1_recommendations + p5_recommendations
    if any(row.get("skill_id") for row in recommendations):
        raise ControlError("skill_id must stay omitted")
    playbooks = c1_playbooks + p5_playbooks
    asked = useful_questions(all_questions)
    by_rec = {row["recommendation_id"]: row for row in playbooks if row.get("recommendation_id")}
    pack_by_family = {row["family_id"]: row["pack"] for row in stamped}
    findings = []
    for rec in recommendations:
        pb = by_rec.get(rec["id"])
        findings.append(
            {
                "id": f"find:{rec['family_id']}:{rec['assessment_state']}",
                "family_id": rec["family_id"],
                "expectation_id": rec["expectation_id"],
                "question_id": rec["question_id"],
                "recommendation_id": rec["id"],
                "assessment_state": rec["assessment_state"],
                "title": rec["title"],
                "actions": list(rec["actions"]),
                "playbook_id": pb["id"] if pb else None,
                "playbook_available": pb is not None,
                "evidence_class": pb["evidence_class"] if pb else None,
                "pack": pack_by_family[rec["family_id"]],
                "repo": repo_id,
            }
        )
    validation_set = c1_playbooks + catalog_playbooks_for_validation(
        {(row["family_id"], row["assessment_state"]) for row in c1_playbooks}
    )
    reviews = validate_playbooks(validation_set, c1_recommendations, c1_assessments)
    finding_reviews = [row for row in reviews if not row["playbook_id"].startswith("PB-9")]
    if any(row["decision"] != "accept" for row in finding_reviews):
        raise ControlError("finding playbooks must validate")
    if any(row["assessment_state"] == "UNKNOWN" for row in findings):
        raise ControlError("UNKNOWN must not appear as a finding")
    unknown_families = [row["family_id"] for row in stamped if row["state"] == "UNKNOWN"]
    by_state = dict(Counter(row["state"] for row in stamped))
    for state in ("SATISFIED", "PARTIAL", "UNKNOWN", "FAIL"):
        by_state.setdefault(state, 0)
    by_pack_state = {}
    for pack in PACKS:
        counts = dict(
            Counter(row["state"] for row in stamped if row["pack"] == pack["id"])
        )
        for state in ("SATISFIED", "PARTIAL", "UNKNOWN", "FAIL"):
            counts.setdefault(state, 0)
        by_pack_state[pack["id"]] = counts
    not_applicable = [fid for fid in instantiated if fid not in set(applicable)]
    report = {
        "repo": repo_id,
        "repo_path": str(repo),
        "schema_version": SCHEMA_VERSION,
        "status": "frozen",
        "absence_is_unknown": True,
        "fail_requires_contradiction": True,
        "skills": "locked" if SKILLS_LOCKED else "open",
        "traits_present": sorted(present),
        "traits_likely": sorted(likely),
        "packs": [pack["id"] for pack in PACKS],
        "instantiated_families": instantiated,
        "applicable_families": applicable,
        "applicable_c1_families": applicable_by_pack.get("c1") or [],
        "applicable_by_pack": applicable_by_pack,
        "not_applicable_families": not_applicable,
        "by_state": {key: by_state[key] for key in ("SATISFIED", "PARTIAL", "UNKNOWN", "FAIL")},
        "by_pack": by_pack_state,
        "asked_questions": len(asked),
        "findings": len(findings),
        "unknown_families": unknown_families,
        "playbook_validation_accept": sum(1 for row in finding_reviews if row["decision"] == "accept"),
        "playbook_validation_revise": sum(1 for row in finding_reviews if row["decision"] == "revise"),
        "composite_score": None,
        "note": (
            "Integrated C1 + Phase 5 repo-analysis. UNKNOWN is abstain. "
            "Packs stay the source of truth for their families. "
            "Playbooks attach to findings, not families. "
            f"Skills stay locked. Contract: {REPO_ANALYSIS_DOC}."
        ),
    }
    validate_row(report, load_schema(REPORT_SCHEMA_PATH), label="report")
    return {
        "report": report,
        "report_md": render_report_md(report, findings, asked, playbooks),
        "findings": findings,
        "questions": asked,
        "assessments": stamped,
        "c1_assessments": c1_assessments,
        "traits": conclusions,
        "playbooks": playbooks,
        "c1_playbooks": c1_playbooks,
        "validation": finding_reviews,
        "trait_meta": trait_meta,
        "control_observations": pack_observation_counts.get("c1", 0),
        "pack_observations": pack_observation_counts,
        "all_questions": len(all_questions),
        "c1_questions": sum(1 for row in all_questions if row["family_id"] in set(applicable_by_pack.get("c1") or [])),
    }


def write_repo_analysis(
    *,
    repo: Path | None = None,
    paths: dict[str, Path] | None = None,
    control: dict[str, Path] | None = None,
    traits_paths: dict[str, Path] | None = None,
    overwrite: bool = False,
) -> dict:
    from pipeline.repo_analysis_brief import build_agent_brief, load_catalog_skills, render_brief_md

    assert_control_locked(REPO_ANALYSIS_LOCKED, "Repo analysis")
    if repo is None:
        raise ControlError("--repo is required for --repo-analysis")
    paths = paths or repo_analysis_paths()
    control = control or control_paths()
    traits_paths = traits_paths or trait_paths()
    baseline = repo_analysis_baseline_paths()
    if paths["dir"].resolve() == baseline["dir"].resolve():
        raise ControlError("the 12-family repo-analysis dest stays frozen")
    frozen_integrated = repo_analysis_paths()["dir"].resolve()
    if paths["dir"].resolve() == frozen_integrated and overwrite:
        raise ControlError("the integrated repo-analysis dest stays frozen; use product_runs/")
    if overwrite and not is_product_run_dest(paths):
        raise ControlError("--overwrite is allowed only under product_runs/")
    if not overwrite:
        for key in ("report", "findings", "stats", "freeze"):
            refuse_overwrite(paths[key], "the integrated repo-analysis dest")
    before_control = _hashes(control, PROTECTED_CONTROL)
    before_trait = _hashes(traits_paths, PROTECTED_TRAIT)
    guards = sealed_guard_paths()
    before_guards = {key: path.read_bytes() for key, path in guards.items() if path.exists()}

    bundle = analyze_repository(repo, control=control, traits_paths=traits_paths)
    brief = build_agent_brief(
        report=bundle["report"],
        findings=bundle["findings"],
        playbooks=bundle["playbooks"],
        questions=bundle["questions"],
        assessments=bundle["assessments"],
        skills=load_catalog_skills(),
    )
    brief_md = render_brief_md(brief)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    dump_json(paths["report"], bundle["report"])
    paths["report_md"].write_text(bundle["report_md"], encoding="utf-8")
    dump_json(paths["brief"], brief)
    paths["brief_md"].write_text(brief_md, encoding="utf-8")
    write_jsonl(paths["findings"], bundle["findings"])
    write_jsonl(paths["questions"], bundle["questions"])
    write_jsonl(paths["assessments"], bundle["assessments"])
    write_jsonl(paths["traits"], bundle["traits"])
    write_jsonl(paths["playbooks"], bundle["playbooks"])
    write_jsonl(paths["validation"], bundle["validation"])

    if _hashes(control, PROTECTED_CONTROL) != before_control:
        raise ControlError("repo analysis mutated a control-evidence dest")
    if _hashes(traits_paths, PROTECTED_TRAIT) != before_trait:
        raise ControlError("repo analysis mutated a trait dest")
    for key, blob in before_guards.items():
        if guards[key].read_bytes() != blob:
            raise ControlError(f"repo analysis mutated sealed dest {key}")

    c1_ids = set(bundle["report"]["applicable_c1_families"])
    c1_live = {row["family_id"]: row["state"] for row in bundle["c1_assessments"]}
    stats = {
        "repo": bundle["report"]["repo"],
        "repo_path": bundle["report"]["repo_path"],
        "traits_present": len(bundle["report"]["traits_present"]),
        "instantiated_families": EXPECTED_INSTANTIATED,
        "applicable_families": len(bundle["report"]["applicable_families"]),
        "applicable_c1_families": len(bundle["report"]["applicable_c1_families"]),
        "assessments": len(bundle["assessments"]),
        "by_state": bundle["report"]["by_state"],
        "by_pack": bundle["report"]["by_pack"],
        "asked_questions": bundle["report"]["asked_questions"],
        "all_pack_questions": bundle["all_questions"],
        "c1_pack_questions": bundle["c1_questions"],
        "findings": bundle["report"]["findings"],
        "finding_playbooks": len(bundle["playbooks"]),
        "c1_finding_playbooks": len(bundle["c1_playbooks"]),
        "unknown_playbooks": 0,
        "playbook_validation_accept": bundle["report"]["playbook_validation_accept"],
        "brief_unknown_questions": len(brief["unknown"]["questions"]),
        "catalog_skills_attached": len(brief["skills"]["catalog_skill_ids"]),
        "skills": "locked",
        "composite_score": None,
        "control_dests_mutated": False,
        "b4_dests_mutated": False,
        "p5_dests_mutated": False,
        "baseline_dest_mutated": False,
        "status": "frozen" if not is_product_run_dest(paths) else "product_run",
        "next_gate": "integrated_mvp_written",
        "note": bundle["report"]["note"],
    }
    if bundle["report"]["repo"] == HACKERRANKATS_REPO and control["assessments"].exists():
        sealed = {row["family_id"]: row["state"] for row in read_jsonl(control["assessments"])}
        stats["c4_comparable"] = all(
            fid in sealed and sealed[fid] == state for fid, state in c1_live.items()
        )
    if bundle["report"]["repo"] == HACKERRANKATS_REPO and baseline["assessments"].exists():
        baseline_assess = {
            row["family_id"]: c1_identity(row) for row in read_jsonl(baseline["assessments"])
        }
        live_c1 = {row["family_id"]: c1_identity(row) for row in bundle["c1_assessments"]}
        stats["c1_regression"] = live_c1 == baseline_assess
        if baseline["findings"].exists():
            baseline_findings = [
                finding_identity(row) for row in read_jsonl(baseline["findings"])
            ]
            live_c1_findings = [
                finding_identity(row) for row in bundle["findings"] if row["family_id"] in c1_ids
            ]
            stats["c1_findings_regression"] = live_c1_findings == baseline_findings
        if not stats["c1_regression"]:
            raise ControlError("integrated run drifted from the frozen 12-family C1 assessments")
        if stats.get("c1_findings_regression") is False:
            raise ControlError("integrated run drifted from the frozen 12-family C1 findings")
    freeze = {
        "repo": stats["repo"],
        "instantiated_families": EXPECTED_INSTANTIATED,
        "applicable_families": stats["applicable_families"],
        "applicable_c1_families": stats["applicable_c1_families"],
        "findings": stats["findings"],
        "asked_questions": stats["asked_questions"],
        "finding_playbooks": stats["finding_playbooks"],
        "unknown_playbooks": 0,
        "skills": "locked",
        "composite_score": None,
        "c1_regression": stats.get("c1_regression"),
        "c4_comparable": stats.get("c4_comparable"),
        "control_dests_mutated": False,
        "b4_dests_mutated": False,
        "p5_dests_mutated": False,
        "baseline_dest_mutated": False,
        "status": stats["status"],
        "next_gate": "integrated_mvp_written",
        "note": (
            "Integrated 42-family repo-analysis dest. "
            "The original 12-family dest stays frozen. "
            "Agent skills stay locked. "
            f"Contract: {REPO_ANALYSIS_DOC}."
        ),
    }
    dump_json(paths["stats"], stats)
    dump_json(paths["freeze"], freeze)
    stats["freeze"] = str(paths["freeze"])
    stats["report"] = str(paths["report"])
    stats["brief"] = str(paths["brief"])
    return stats
