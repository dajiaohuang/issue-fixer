#!/usr/bin/env python3
"""
Autonomous issue-fixing loop.
Runs discovery, fixes candidates, opens PRs — no confirmation needed.

Usage:
    python auto_fix.py [--rounds 5] [--max-candidates 3]
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = r"D:\repo\issue-fixer"
DISCOVER = os.path.join(SKILL_DIR, "scripts", "discover.py")
TRACKER = os.path.join(SKILL_DIR, "scripts", "pr_tracker.py")


def run(cmd, **kwargs):
    try:
        shell = isinstance(cmd, str)
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=kwargs.get("timeout", 60), shell=shell, cwd=kwargs.get("cwd"),
        )
        return (result.stdout or "").strip(), (result.stderr or "").strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1


def discover(max_candidates=3, use_direct=True, use_keyword=True, min_stars=5, max_days=21):
    """Run discovery script, return candidate list."""
    args = [
        sys.executable, DISCOVER,
        "--max-candidates", str(max_candidates),
        "--min-stars", str(min_stars),
        "--max-days", str(max_days),
    ]
    if use_direct:
        args.append("--direct")
    if use_keyword:
        args.append("--keyword")
        args.extend(["--kw-min-stars", "5"])

    stdout, stderr, rc = run(args, timeout=300)
    if rc != 0 or not stdout:
        return []
    try:
        data = json.loads(stdout)
        return data.get("candidates", [])
    except json.JSONDecodeError:
        return []


def fix_and_pr(candidate):
    """Fork, clone, fix, push, create PR for one candidate. Returns PR URL or None."""
    repo = candidate["repo"]
    number = candidate["issue_number"]
    title = candidate["issue_title"]
    body = candidate.get("issue_body", "")
    url = candidate["issue_url"]

    owner, repo_name = repo.split("/")
    fork_url = f"https://github.com/dajiaohuang/{repo_name}.git"
    clone_dir = os.path.join(WORKSPACE, f"{owner}-{repo_name}")

    print(f"  Fixing {repo}#{number}: {title[:80]}")

    # Fork
    run(f"gh repo fork {repo} --clone=false", timeout=30)

    # Clone (remove if exists)
    if os.path.isdir(clone_dir):
        run(f'rm -rf "{clone_dir}"', timeout=10)
    stdout, stderr, rc = run(
        f'git clone --depth 50 "{fork_url}" "{clone_dir}"',
        timeout=120,
    )
    if rc != 0:
        print(f"    Clone failed: {stderr[:200]}")
        return None

    # ── Determine fix strategy from issue body ──
    # This is where Claude would normally plan. For autonomous mode we
    # handle simple categories: dead code, typo, error message, link/list add.
    # Complex fixes (new features, API changes, multi-file refactors) are skipped.

    # For now, this script is a framework — the actual fix logic is delegated
    # back to the main session. We just log the candidate for manual fixing.
    print(f"    Candidate logged: {url}")
    print(f"    Clone at: {clone_dir}")

    # Placeholder — return None to indicate "needs manual fix"
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--max-candidates", type=int, default=3)
    args = p.parse_args()

    total_fixed = 0
    for rnd in range(1, args.rounds + 1):
        print(f"\n{'='*60}")
        print(f"Round {rnd}/{args.rounds}")
        print(f"{'='*60}")

        candidates = discover(max_candidates=args.max_candidates)
        if not candidates:
            print("  No candidates found. Expanding search...")
            # Expand: lower stars, longer date range
            candidates = discover(min_stars=3, max_days=30)
        if not candidates:
            print("  Still nothing. Skipping round.")
            continue

        print(f"  Found {len(candidates)} candidate(s):")
        for c in candidates:
            print(f"    {c['repo']}#{c['issue_number']} — {c['issue_title'][:100]}")
            print(f"      {c['repo_stars']}★ | {c['repo_license']} | labels: {c.get('issue_labels', [])}")

        # In autonomous mode, each candidate needs to be fixed manually
        # for now — the auto_fix is a discovery+log tool.
        # Full autonomous fixing requires the main Claude session.
    print(f"\nDone {args.rounds} rounds.")


if __name__ == "__main__":
    main()
