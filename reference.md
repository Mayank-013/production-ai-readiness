# Production AI Readiness — reference

## Architecture

```
Repository
  → ForgeAI mechanical analyzer (no LLM)
  → brief.json (one hunt card per specialized question)
  → host Cursor model hunts each binding on the real path
  → customer review: only their files; misses stay silent
  → optional catalog patch
  → re-inspect proves closure
```

Judgment stays in ForgeAI. The host model walks every unverified area, then phrases. It does not re-score.

## Destinations

| Path | Role |
|---|---|
| `engineering-intelligence/consolidation/repo_analysis/` | Frozen 12-family HackerRankATS dest. Never overwrite. |
| `engineering-intelligence/consolidation/repo_analysis_integrated/` | Frozen first integrated dest. Never overwrite. |
| `engineering-intelligence/consolidation/product_runs/<repo>/repo_analysis_integrated/` | Live product runs. `--overwrite` allowed here only. |

CLI (from this skill folder):

```bash
python3 scripts/assess.py --repo /path/to/repo
python3 scripts/assess.py --repo /path/to/repo --overwrite
```

## Safety model

| State | Product meaning |
|---|---|
| SATISFIED | Evidenced. Count / mention. Do not ask. |
| PARTIAL / FAIL with `skill_id` | Actionable. Host may patch per catalog. |
| PARTIAL / FAIL without skill | Mention. Do not auto-patch. |
| UNKNOWN | Abstain. Host must hunt the repo, then narrate. Never a finding. Spotted ≠ SATISFIED. Missing ≠ FAIL. |

Absence of evidence is UNKNOWN, not FAIL. FAIL requires contradiction evidence.

## Catalog skills (frozen)

Compatible iff `family_id` + `assessment_state` + `evidence_class` match.

| Skill | Finding | Close signal |
|---|---|---|
| SKL-0001 | QF-0035 PARTIAL `getenv_no_scanner` | secret scanner present |
| SKL-0003 | QF-0003 PARTIAL `supporting_fallback_no_named_failover` | named fallback + down-path test |
| SKL-0005 | QF-0016 PARTIAL `outbound_https_no_serving_tls` | serving TLS / HTTPSRedirect — **not** outbound https URLs |
| SKL-0002 | QF-0035 FAIL `live_literal_in_source` | literal removed |
| SKL-0004 | QF-0003 FAIL `refuse_to_degrade` | flag gone + named fallback |
| SKL-0006 | QF-0016 FAIL `plaintext_listener_tls_disabled` | serving TLS present |

Source of truth: `engineering-intelligence/consolidation/skills/skills.jsonl`.

## User-facing language

`brief.md` / `brief.json` are **agent-only**. Do not send them to the customer.

The customer review keeps the pack groupings. Each bullet is a path in their repo plus what it does. Omit a topic if there is no file. Do not say “tree,” family counts, strength labels, or ForgeAI internals.

`skill_suggestions.apply_now` is catalog-only. Public skills are **not** seeded. The host writes a problem from this repo, web-searches a skill for that problem, and advertises it. Do not apply public skills. Do not show skill ids.

## Contract docs

- `docs/cursor-skill.md`
- `docs/repo-analysis.md`
- `docs/implementation-skills.md`
- `docs/control-evidence.md`
