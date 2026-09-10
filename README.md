# Production AI Readiness

Installable skill for **Cursor** and **Claude Code**. Mechanical scan of an AI application; the host model writes the customer review.

Requires Python 3.11+ and PyYAML.

```bash
pip3 install -r requirements.txt
```

## Install

Clone this repo as the skill folder (same tree works for both tools):

```bash
# Cursor
git clone <CLONE_URL> ~/.cursor/skills/production-ai-readiness

# Claude Code
git clone <CLONE_URL> ~/.claude/skills/production-ai-readiness
```

Or clone once and symlink:

```bash
git clone <CLONE_URL> ~/src/production-ai-readiness
ln -sfn ~/src/production-ai-readiness ~/.cursor/skills/production-ai-readiness
ln -sfn ~/src/production-ai-readiness ~/.claude/skills/production-ai-readiness
```

Then in the repo you want assessed, ask: **Assess production AI readiness**.

The scan command is:

```bash
python3 ~/.cursor/skills/production-ai-readiness/scripts/assess.py --repo "$PWD"
```

## What this package contains

- `SKILL.md` — host-agent instructions
- `scripts/assess.py` — entry point
- `pipeline/` — frozen 42-family analyzer (runtime modules only)
- `engineering-intelligence/schemas/` — validation schemas
- `engineering-intelligence/consolidation/` — frozen families, traits, detectors, catalog skills

It does **not** include the knowledge corpus, extractor prompts, tests, or sealed benchmark dests.

## Run without the agent

```bash
python3 scripts/assess.py --repo /path/to/your/app
python3 scripts/assess.py --repo /path/to/your/app --overwrite
```

Writes under `engineering-intelligence/consolidation/product_runs/<repo>/repo_analysis_integrated/`. Read `brief.json`; do not send `brief.md` to a customer.
