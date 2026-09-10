---
name: production-ai-readiness
description: >-
  Assess Production AI Readiness for a repository using ForgeAI's frozen
  42-family analyzer. After the scan, hunt specialized questions on real
  paths, then write a customer review that only cites their code. Apply only
  catalog-compatible implementation skills. Use when the user types
  /production-ai-readiness or asks to assess production readiness, run
  ForgeAI, check AI app readiness, or fix a ForgeAI finding.
---

# Production AI Readiness

You are the host coding agent. ForgeAI scores. You search internally, then send the customer only what is about **their** code.

## Hard rules

1. **Never invent “done” or “broken.”** Only the mechanical analyzer assigns those.
2. **Missing evidence is not a failure.** Do not patch unverified areas. Do not treat absence as broken.
3. **Do not dump `report.md` or `brief.md` at the customer.** Those are for you. Rewrite a customer review.
4. **Customer text stays human and local.** No `QF-…`, `SKL-…`, `CEE-…`, `PARTIAL`, `SATISFIED`, `FAIL`, `UNKNOWN`. No family counts, no “N areas checked,” no “specialized questions,” no “Supporting” / “Insufficient” / “strong,” no “in this tree” / “not in this tree,” no “clue / passing score,” no mention of ForgeAI, briefs, or detectors.
5. **If you cannot name a file in their repo, do not mention the topic.** A miss is silent, not a bullet.
6. **Patch only findings that carry `skill_id` in `brief.json`.** Name the problem in English, not the skill id.
7. **Refuse HackerRankATS.** Sealed benchmark.
8. **Do not call external LLM APIs from ForgeAI.** Use this Cursor session's model.

## 1. Scan (always first)

This skill is self-contained. `scripts/assess.py` finds the folder that contains `pipeline/` and `SKILL.md`. You do not need `FORGEAI_ROOT` unless you installed a nested copy inside a ForgeAI checkout.

From the **user's** repo (or the path they name):

```bash
python3 "$HOME/.cursor/skills/production-ai-readiness/scripts/assess.py" --repo "$PWD"
```

Claude Code:

```bash
python3 "$HOME/.claude/skills/production-ai-readiness/scripts/assess.py" --repo "$PWD"
```

If this skill lives at another path, run that copy of `scripts/assess.py`. Optional: `export FORGEAI_ROOT=/path/to/this-skill`.

Re-inspect after a fix:

```bash
python3 "$HOME/.cursor/skills/production-ai-readiness/scripts/assess.py" --repo "$PWD" --overwrite
```

Then read `brief.json` (hunt cards + skill ids). Do not show `brief.md` to the customer.

## 2. Walk every specialized question (internal)

Do this **before** writing the customer review. The walk is for you, not for them.

For **each** row in `brief.json` → `unknown.questions` (skip none):

1. Read `prompt` and `binding`.
2. Find **that path** in the **user's repo**: entry → agent / tools / retriever / deploy.
3. Keep a private note: path + what it does, or “no file.”
4. Do not change the scan state. Do not patch unverified areas.

## 3. Customer review (required shape)

Keep the grouped walk. Only include a bullet when you found a file. Say what that file does. Never say “tree.”

```markdown
# Production readiness — <repo>

<one sentence: what this codebase is, using their product nouns>

## Needs work
- **<plain problem>** — `their/path`: what is wrong, what to do next
  (offer an automatic fix only when brief.json has skill_id)

## What can actually hurt you
- **<plain risk>** — `their/path`: what this code does today, and what goes wrong for their users

## In your code

### Core production controls
- **Limits on work — agent execution** — `app/services/agent.py`: 10 iterations, history trim, OpenAI 60–90s

### Quality checks
- **Faithful listing answers** — `system_prompts.py`: listing Q&A is told not to invent exact numbers

### Agent and supply-chain security
- **Tools this turn may call** — `app/services/agent.py`: `TOOL_DEFINITIONS` plus quote / lock / fallback subsets

### Runtime behavior
- **Slow dependency cutoff** — MarketCheck / J.D. Power clients: HTTP timeouts and three retries

### Retrieval and data
- **Listing answers tied to listings** — `system_prompts.py` plus `listingContext`

### Cost and capacity
- **Reuse payment-graph work** — `chat_graph/orchestrator.py`: skips nodes when session state already has the result

## What you should do now
1. …

## Skills worth adding
- **<plain name>** — I can apply this now, for `their/path` (only if brief.json apply_now has skill_id)
- **<plain name>** — [link](url): what it does for this repo. Install or run it only if they ask.
```

Use the brief’s `pack_label` headings. Skip a heading if that group has no files.

Rules:

- **Needs work** = scanner findings you can tie to their code. Skip if you have no path.
- **What can actually hurt you** = 3–5 weak paths that matter for this product.
- **In your code** = grouped findings that have a path. Important behavior only. No empty “we looked and found nothing” lines.
- Do **not** write “in this tree,” “not in this tree,” or “likely elsewhere.”
- Do **not** mention ForgeAI, briefs, detectors, families, scores, or how many checks ran.
- Do **not** use Supporting / Insufficient / strong / clue / passing score.
- No composite score. No `/100`.

## 4. Suggest skills (required, dynamic)

Do **not** pick from a canned list. Form the problem from **this** repo, then search.

1. From **Needs work**, **What can actually hurt you**, and weak paths under **In your code**, write 3–5 problem statements in plain English. Use their nouns and files.
   Examples of the *shape* (not a list to reuse): “deploy-beta.yml ships without running tests”; “`run_tools` can charge twice”; “this service file is 2k lines and mixes payments with prompts.”
2. For each problem, web-search a **current** skill or playbook that solves *that* problem (Cursor/`SKILL.md`, official docs, or a maintained high-star repo). Query the problem, not a family name.
3. Keep one best match per problem. Say why it fits this path. Link it.
4. If `brief.json` → `skill_suggestions.apply_now` has a row, also offer “I can apply this now” in English (no internal ids). Apply only if they ask.
5. Cap the public list at five. Do not install or run a public skill unless they ask. A public skill does not change the score.

## Fix workflow

When the user asks to fix something:

1. Confirm the matching finding in `brief.json` has `skill_id`.
2. Load catalog steps from this skill:
   `engineering-intelligence/consolidation/skills/skills.jsonl`
   Match that `skill_id`. Obey `steps` and `constraints`.
3. Apply the transform in the **user's repo** (not this skill's fixtures, not HackerRankATS).
4. Tell the user in plain English what you changed (e.g. “added HTTPS redirect on the serving path”).
5. Re-run assess with `--overwrite`.
6. Closed only if that area moved to fully evidenced and nothing previously evidenced got worse.
7. If still incomplete, say why in plain English — do not claim success.

## What you must not do

- Do not invent eval harnesses, sandboxes, or RAG gates from unverified areas.
- Do not “fix” TLS by adding another outbound `https://` URL.
- Do not use `pipeline/m3.py --apply-implementation-skill` on customer repos (fixture-only path).
- Do not overwrite `repo_analysis/` or the default `repo_analysis_integrated/` dest.
- Do not show internal IDs, counts, or hunt checklists in the customer review.
- Do not skip the internal walk; do not paste the walk.

## Reference

See [reference.md](reference.md) for dest rules, safety model, and the six catalog skills.
