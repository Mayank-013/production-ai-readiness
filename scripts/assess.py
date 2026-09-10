#!/usr/bin/env python3
"""Run Production AI Readiness into product_runs/ and print the agent brief path.

Usage:
  python3 scripts/assess.py --repo /path/to/repo
  python3 scripts/assess.py --repo /path/to/repo --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HACKERRANKATS = Path("/Users/mauryans/Projects/HackerRankATS")


def skill_root() -> Path:
    env = os.environ.get("FORGEAI_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "pipeline" / "repo_analysis.py").exists():
            return p
        raise SystemExit(f"FORGEAI_ROOT={p} has no pipeline/repo_analysis.py")

    here = Path(__file__).resolve()
    candidates: list[Path] = []
    if here.parent.name == "scripts":
        candidates.append(here.parents[1])
    if len(here.parents) >= 4:
        candidates.append(here.parents[3])
    candidates.append(Path("/Users/mauryans/Projects/ForgeAI"))
    for c in candidates:
        if (c / "pipeline" / "repo_analysis.py").exists():
            return c.resolve()
    raise SystemExit(
        "Could not locate the Production AI Readiness skill root "
        "(folder with pipeline/repo_analysis.py). "
        "Export FORGEAI_ROOT=/path/to/production-ai-readiness"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Production AI Readiness assess")
    parser.add_argument("--repo", required=True, help="Repository root to assess")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing product_runs dest (re-inspect after a fix)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print brief.json instead of the agent-only pointer",
    )
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"repository missing: {repo}", file=sys.stderr)
        return 2
    if repo.resolve() == HACKERRANKATS.resolve():
        print(
            "Refusing HackerRankATS. That sealed benchmark stays frozen.",
            file=sys.stderr,
        )
        return 2

    root = skill_root()
    sys.path.insert(0, str(root))
    from pipeline.control_evidence_contract import ControlError
    from pipeline.repo_analysis import product_run_paths, write_repo_analysis
    from pipeline.system_trait_contract import TraitError

    dest_paths = product_run_paths(repo.name)
    dest = dest_paths["dir"]
    try:
        stats = write_repo_analysis(repo=repo, paths=dest_paths, overwrite=args.overwrite)
    except (ControlError, TraitError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    brief_json = dest / "brief.json"
    brief_md = dest / "brief.md"
    if not brief_json.exists() or not brief_md.exists():
        print(f"brief missing after write: {brief_json}", file=sys.stderr)
        return 2

    print(f"dest={dest}", file=sys.stderr)
    if args.json:
        print(brief_json.read_text(encoding="utf-8"))
    else:
        print(
            "Agent-only brief written.\n"
            f"Read {brief_json}\n"
            "Do not send brief.md to the customer.\n"
            f"<!-- brief_json={brief_json} "
            f"skills={stats.get('catalog_skills_attached')} -->"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
