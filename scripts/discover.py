#!/usr/bin/env python3
"""
Phase 1 + Phase 2 (mechanical checks) for issue-fixer skill.
Outputs structured JSON of surviving candidates for Claude to evaluate.

Usage:
    python discover.py [--min-stars 100] [--max-days 7] [--count 10]

Output: JSON array of candidate issues that passed all mechanical checks.
Each candidate includes repo metadata and issue details for Claude to classify.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone


def run(cmd, **kwargs):
    """Run a command, return stdout or empty string on failure.
    If *cmd* is a list, run without shell; if a string, use shell=True."""
    try:
        shell = isinstance(cmd, str)
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=kwargs.get("timeout", 30), shell=shell,
        )
        return (result.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return ""


def run_json(cmd, **kwargs):
    """Run a command expecting JSON output. Accepts list or string."""
    stdout = run(cmd, **kwargs)
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


# ── Labels that indicate low-effort issues ──────────────────────────
PRIORITY_LABELS = {
    "bug", "fix", "enhancement", "feature", "good first issue", "good-first-issue",
    "help wanted", "documentation", "docs", "test", "testing", "coverage",
    "typo", "chore", "style", "dependencies", "ux", "error-handling",
    "cleanup", "refactor", "config", "ci", "accessibility", "a11y",
}


def get_trending_repos(min_stars=100, max_days=7, count=10):
    """Phase 1: Search GitHub for trending repos with recent pushes."""
    since = (datetime.now(timezone.utc) - timedelta(days=max_days)).strftime("%Y-%m-%d")
    query = f"pushed:>{since} stars:>{min_stars}"
    jq_filter = "[.items[] | {full_name, stars: .stargazers_count, pushed_at, language, has_issues, license: .license.key}]"
    result = run_json(
        ["gh", "api", "-X", "GET", "search/repositories",
         "-f", f"q={query}", "-f", "sort=stars", "-f", "order=desc", "-f", f"per_page={count}",
         "--jq", jq_filter],
        timeout=15,
    )
    if not result:
        return []
    return [r for r in result if r.get("has_issues") and r.get("license")]


def get_recent_issues(repo_full_name, limit=8):
    """Get open issues for a repo, sorted newest first."""
    issues = run_json(
        ["gh", "issue", "list", "--repo", repo_full_name, "--limit", str(limit),
         "--state", "open", "--json", "number,title,updatedAt,createdAt,labels",
         "--jq", "sort_by(.createdAt) | reverse"],
        timeout=15,
    )
    return issues or []


def issue_matches_scope(issue):
    """Filter: skip issues that have labels but none are priority labels.
    Issues with no labels at all pass through (unlabeled but potentially relevant)."""
    labels = issue.get("labels", [])
    if not labels:
        return True  # unlabeled issues are still candidates
    label_names = {(l.get("name", "") or "").lower() for l in labels}
    return bool(label_names & PRIORITY_LABELS)


def check_commits_for_issue(repo_dir, issue_number, created_at):
    """Step 1: Search commits referencing this issue number."""
    since = created_at[:10] if created_at else "2026-01-01"
    stdout = run(
        ["git", "-C", repo_dir, "log", "--all", "--oneline",
         f"--grep=#{issue_number}", f"--since={since}"],
        timeout=10,
    )
    return bool(stdout)


def check_prs_for_issue(repo_full_name, issue_number):
    """Step 2: Search open/closed PRs referencing this issue."""
    prs = run_json(
        ["gh", "pr", "list", "--repo", repo_full_name, "--state", "all",
         "--search", f"#{issue_number}", "--json", "number,title,state"],
        timeout=15,
    )
    return bool(prs)


def check_linked_prs(issue_json):
    """Step 3: Check if issue already has linked closing PRs."""
    # The issue list JSON from `gh issue list` doesn't include linked PRs.
    # We need to query each issue individually for closedByPullRequestsReferences.
    # Since we're checking multiple issues, we batch by reading the field.
    number = issue_json["number"]
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    # Can't easily get repo from within the issue JSON — skip this check here,
    # it'll be done per-issue in the main loop with gh issue view.
    return False  # placeholder; checked separately


def clone_repo_shallow(repo_full_name):
    """Shallow-clone a repo for commit searching. Returns path or None."""
    clone_dir = tempfile.mkdtemp(prefix="ifx_")
    url = f"https://github.com/{repo_full_name}.git"
    run(
        ["git", "clone", "--depth", "50", url, clone_dir],
        timeout=60,
    )
    if os.path.isdir(os.path.join(clone_dir, ".git")):
        return clone_dir
    return None


def discover_candidates(min_stars=100, max_days=7, repo_count=10, issue_limit=8, max_candidates=5):
    """Main discovery pipeline. Returns list of candidate dicts."""

    repos = get_trending_repos(min_stars, max_days, repo_count)
    if not repos:
        print("ERROR: No trending repos found.", file=sys.stderr)
        return []

    candidates = []

    for repo in repos:
        if len(candidates) >= max_candidates:
            break

        full_name = repo["full_name"]
        print(f"Scanning {full_name}...", file=sys.stderr)

        issues = get_recent_issues(full_name, issue_limit)
        if not issues:
            continue

        # Clone once per repo for commit searching
        clone_dir = None

        for issue in issues:
            if len(candidates) >= max_candidates:
                break

            number = issue["number"]
            title = issue["title"]

            # Quick filter: skip issues with non-priority labels only
            if not issue_matches_scope(issue):
                continue

            # ── Step 1: Check commits ──
            clone_dir = clone_dir or clone_repo_shallow(full_name)
            if clone_dir and check_commits_for_issue(clone_dir, number, issue.get("createdAt", "")):
                print(f"  #{number} — SKIP (commit references found)", file=sys.stderr)
                continue

            # ── Step 2: Check PRs ──
            if check_prs_for_issue(full_name, number):
                print(f"  #{number} — SKIP (PR references found)", file=sys.stderr)
                continue

            # ── Step 3: Check linked PRs on issue ──
            linked = run_json(
                ["gh", "issue", "view", str(number), "--repo", full_name,
                 "--json", "closedByPullRequestsReferences",
                 "--jq", ".closedByPullRequestsReferences | length"],
                timeout=10,
            )
            if linked and linked > 0:
                print(f"  #{number} — SKIP ({linked} linked PRs)", file=sys.stderr)
                continue

            # ── Get issue body for Claude's evaluation ──
            detail = run_json(
                ["gh", "issue", "view", str(number), "--repo", full_name,
                 "--json", "title,body,createdAt,labels,assignees"],
                timeout=10,
            )
            if not detail:
                continue

            # Check assignees
            assignees = detail.get("assignees", []) or []
            if assignees:
                print(f"  #{number} — SKIP (assigned to {assignees[0].get('login', '?')})", file=sys.stderr)
                continue

            # ── Check for repo guidelines ──
            has_contributing = False
            has_claude_md = False
            if clone_dir:
                has_contributing = os.path.isfile(os.path.join(clone_dir, "CONTRIBUTING.md"))
                has_claude_md = os.path.isfile(os.path.join(clone_dir, "CLAUDE.md"))

            labels = [l.get("name", "") for l in (detail.get("labels", []) or [])]

            candidates.append({
                "repo": full_name,
                "repo_stars": repo["stars"],
                "repo_language": repo.get("language"),
                "repo_license": repo.get("license"),
                "repo_has_contributing": has_contributing,
                "repo_has_claude_md": has_claude_md,
                "issue_number": number,
                "issue_title": title,
                "issue_url": f"https://github.com/{full_name}/issues/{number}",
                "issue_body": (detail.get("body", "") or "")[:2000],
                "issue_created": detail.get("createdAt", ""),
                "issue_labels": labels,
            })

            print(f"  #{number} — CANDIDATE ✓", file=sys.stderr)

        # Cleanup clone dir
        if clone_dir:
            run(f'rm -rf "{clone_dir}"', timeout=5)

    return candidates


def main():
    # Fix Unicode output on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Discover fixable GitHub issues")
    parser.add_argument("--min-stars", type=int, default=100)
    parser.add_argument("--max-days", type=int, default=7)
    parser.add_argument("--repo-count", type=int, default=10)
    parser.add_argument("--issue-limit", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--json-only", action="store_true", help="Suppress stderr, output only JSON")
    args = parser.parse_args()

    if args.json_only:
        sys.stderr = open(os.devnull, "w")

    candidates = discover_candidates(
        min_stars=args.min_stars,
        max_days=args.max_days,
        repo_count=args.repo_count,
        issue_limit=args.issue_limit,
        max_candidates=args.max_candidates,
    )

    if not candidates:
        print(json.dumps({"error": "no candidates found", "candidates": []}))
        sys.exit(1)

    print(json.dumps({"candidates": candidates}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
