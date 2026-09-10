# Production AI Readiness

A Cursor and Claude Code skill that scans an AI app for production gaps. The scanner scores the repo; the host model writes the review from your files.

You need Python 3.11+ and PyYAML.

```bash
pip3 install -r requirements.txt
```

## Install

Clone this repo into the skill folder. One tree works for both tools.

```bash
# Cursor
git clone https://github.com/Mayank-013/production-ai-readiness.git ~/.cursor/skills/production-ai-readiness

# Claude Code
git clone https://github.com/Mayank-013/production-ai-readiness.git ~/.claude/skills/production-ai-readiness
```

Or clone once and symlink:

```bash
git clone https://github.com/Mayank-013/production-ai-readiness.git ~/src/production-ai-readiness
ln -sfn ~/src/production-ai-readiness ~/.cursor/skills/production-ai-readiness
ln -sfn ~/src/production-ai-readiness ~/.claude/skills/production-ai-readiness
```

Hook the slash command so `/production-ai-readiness` shows up in the chat:

```bash
mkdir -p ~/.cursor/commands ~/.claude/commands
ln -sfn ~/.cursor/skills/production-ai-readiness/commands/production-ai-readiness.md \
  ~/.cursor/commands/production-ai-readiness.md
ln -sfn ~/.claude/skills/production-ai-readiness/commands/production-ai-readiness.md \
  ~/.claude/commands/production-ai-readiness.md
```

If you used the single-clone + symlink install, point both command files at that clone's `commands/production-ai-readiness.md`.

Open the app you want assessed. Type `/production-ai-readiness` in the chat. You can also say "assess production AI readiness".

To run the scan yourself:

```bash
python3 ~/.cursor/skills/production-ai-readiness/scripts/assess.py --repo "$PWD"
```

## What's in here

- `SKILL.md` — what the host agent should do
- `commands/production-ai-readiness.md` — `/production-ai-readiness` in the chat
- `scripts/assess.py` — the command that runs the scan
- `pipeline/` — the 42-family analyzer
- `engineering-intelligence/schemas/` — validation schemas
- `engineering-intelligence/consolidation/` — frozen families, traits, detectors, and catalog skills

You won't find the knowledge corpus, extractor prompts, tests, or sealed benchmark dests here.

## Run without the agent

```bash
python3 scripts/assess.py --repo /path/to/your/app
python3 scripts/assess.py --repo /path/to/your/app --overwrite
```

Results land in `engineering-intelligence/consolidation/product_runs/<repo>/repo_analysis_integrated/`. Read `brief.json`. Don't send `brief.md` to the customer.
