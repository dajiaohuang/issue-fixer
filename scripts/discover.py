#!/usr/bin/env python3
"""
Issue discovery pipeline for issue-fixer skill.
Three strategies → smart filter → output clean JSON for Claude.

Usage:
    python discover.py [--keyword] [--direct] [--max-candidates 5]
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone


# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

DOMAIN_KEYWORDS = [
    # Languages & frameworks
    "golang", "rustlang", "typeScript", "python3", "c++ library", "zig",
    # DevOps & infra
    "kubernetes", "docker", "terraform", "ansible", "prometheus", "grafana",
    "nginx", "envoy", "helm", "gitops", "ci cd",
    # Data & storage
    "postgresql", "sqlite", "redis", "mongodb", "elasticsearch", "kafka",
    "rabbitmq", "etcd", "clickhouse", "duckdb", "vector database",
    # App types
    "cli tool", "dashboard", "api gateway", "job scheduler", "image optimizer",
    "openapi", "websocket", "cron", "diff", "cache", "queue",
    "form builder", "csv parser", "pdf generator", "email client", "auth library",
    "i18n", "webhook", "proxy", "log", "monitor", "backup",
    "migrate", "scraper", "code formatter", "linter", "test runner",
    "package manager", "chat bot", "notification", "scheduler", "template engine",
    "rate limiter", "feature flag", "config parser", "data validator",
    # AI/ML
    "llm", "vector search", "rag", "embedding", "tokenizer",
    "image recognition", "speech recognition", "text to speech",
    # Web & mobile
    "react component", "vue component", "svelte", "wasm", "graphql",
    "rest api", "grpc", "swagger", "jwt", "oauth2",
    # Tools & utils
    "dotfiles", "dev tools", "productivity", "note taking",
    "terminal emulator", "file manager", "text editor plugin",
    "home automation", "iot", "raspberry pi", "arduino",
    # Misc active niches
    "game engine", "chess engine", "pomodoro", "markdown editor",
    "rss reader", "bookmark manager", "password manager",
    "music player", "video player", "image viewer",
    "weather app", "todo list", "calendar", "spreadsheet",
    "kanban board", "wiki engine", "blog engine", "static site",
    "cms", "headless cms", "ssg template", "css framework",
    "design system", "icon set", "font library", "color palette",
    "neovim plugin", "vscode extension", "tmux config",
    "zsh plugin", "fish shell", "git alias", "github action",
]

PRIORITY_LABELS = {
    "bug", "fix", "enhancement", "feature", "good first issue", "good-first-issue",
    "help wanted", "documentation", "docs", "test", "testing", "coverage",
    "typo", "chore", "style", "dependencies", "ux", "error-handling",
    "cleanup", "refactor", "config", "ci", "accessibility", "a11y",
}

DIRECT_SEARCH_LABELS = [
    "good-first-issue", "bug", "help-wanted", "good first issue",
]

# Repos whose full_name matches any of these patterns are excluded
EXCLUDED_REPO_PATTERNS = [
    r"/awesome$", r"/awesome-", r"/Awesome-", r"-awesome-",
    r"/public-apis$", r"/free-programming-books$",
    r"/Best-websites-a-programmer-should-visit$",
    r"/project-based-learning$", r"/build-your-own-x$",
    r"/coding-interview-university$", r"/system-design-primer$",
    r"/developer-roadmap$", r"/every-programmer-should-know$",
    r"/the-book-of-secret-knowledge$", r"/the-art-of-command-line$",
    r"/Front-End-Checklist$", r"/javascript-algorithms$",
    r"/30-seconds-of-", r"/You-Dont-Know-JS$",
]

# Words that, if they appear as the entire title, indicate spam
SPAM_TITLE_PATTERNS = [
    r"^[a-zA-Z0-9]{1,4}$",          # "A9", "lodka"
    r"^[a-zA-Z0-9]{1,6}\.py$",      # "main.py"
    r"^.*\.(py|js|ts|java|cpp|rs)$", # code files as titles
]


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def run(cmd, **kwargs):
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
    stdout = run(cmd, **kwargs)
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


# ═══════════════════════════════════════════════════════════════════════
# Smart Filters (applied to every candidate before output)
# ═══════════════════════════════════════════════════════════════════════

def is_spam_title(title):
    """Reject titles that are clearly spam/noise."""
    title = (title or "").strip()
    for pattern in SPAM_TITLE_PATTERNS:
        if re.match(pattern, title, re.IGNORECASE):
            return True
    # Title is just a code block
    if title.startswith("import ") or title.startswith("#include"):
        return True
    return False

def is_valid_body(body, min_chars=100):
    """Reject issues with no meaningful body."""
    body = (body or "").strip()
    if len(body) < min_chars:
        return False
    # Body is just a code dump with no English/Chinese text
    code_chars = sum(1 for c in body if c in "{}()[]<>;:=+-*/%&|!^~#@\\\"'`_.,\n\r\t ")
    if code_chars > len(body) * 0.85:
        return False
    return True

def is_stale_issue(created_at, comments_count=0, max_age_days=90):
    """Reject issues that are old and have zero engagement."""
    if not created_at:
        return True
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
    except (ValueError, TypeError):
        return False
    if age_days > max_age_days and comments_count <= 0:
        return True
    return False

def is_list_repo(full_name):
    """Exclude list/curation/awesome repos that attract spam."""
    for pattern in EXCLUDED_REPO_PATTERNS:
        if re.search(pattern, full_name):
            return True
    return False

def is_bad_license(license_key):
    """Reject repos with restrictive, unclear, or no license."""
    if not license_key:
        return True
    bad = {"other", "noassertion", "none", "unlicense"}
    if (license_key or "").lower() in bad:
        return True
    return False

def labels_ok(labels):
    """Issues with labels must include at least one priority label.
    Unlabeled issues pass (might still be good)."""
    if not labels:
        return True
    names = {(l.get("name", "") or "").lower() for l in labels}
    return bool(names & PRIORITY_LABELS)


# ═══════════════════════════════════════════════════════════════════════
# Mechanical Checks (commit grep, PR search, linked PR)
# ═══════════════════════════════════════════════════════════════════════

def check_commits_for_issue(repo_dir, issue_number, created_at):
    since = created_at[:10] if created_at else "2026-01-01"
    stdout = run(
        ["git", "-C", repo_dir, "log", "--all", "--oneline",
         f"--grep=#{issue_number}", f"--since={since}"],
        timeout=10,
    )
    return bool(stdout)

def check_prs_for_issue(repo_full_name, issue_number):
    prs = run_json(
        ["gh", "pr", "list", "--repo", repo_full_name, "--state", "all",
         "--search", f"#{issue_number}", "--json", "number,title,state"],
        timeout=15,
    )
    return bool(prs)

def check_linked_prs(repo_full_name, issue_number):
    linked = run_json(
        ["gh", "issue", "view", str(issue_number), "--repo", repo_full_name,
         "--json", "closedByPullRequestsReferences",
         "--jq", ".closedByPullRequestsReferences | length"],
        timeout=10,
    )
    return (linked or 0) > 0

def clone_repo_shallow(repo_full_name):
    clone_dir = tempfile.mkdtemp(prefix="ifx_")
    url = f"https://github.com/{repo_full_name}.git"
    run(["git", "clone", "--depth", "50", url, clone_dir], timeout=60)
    if os.path.isdir(os.path.join(clone_dir, ".git")):
        return clone_dir
    return None


# ═══════════════════════════════════════════════════════════════════════
# Strategy A: Trending repos
# ═══════════════════════════════════════════════════════════════════════

def get_trending_repos(min_stars=100, max_days=7, count=10):
    since = (datetime.now(timezone.utc) - timedelta(days=max_days)).strftime("%Y-%m-%d")
    query = f"pushed:>{since} stars:>{min_stars}"
    jq = "[.items[] | {full_name, stars: .stargazers_count, pushed_at, language, has_issues, license: .license.key}]"
    result = run_json(
        ["gh", "api", "-X", "GET", "search/repositories",
         "-f", f"q={query}", "-f", "sort=stars", "-f", "order=desc", "-f", f"per_page={count}",
         "--jq", jq], timeout=15,
    )
    if not result:
        return []
    return [r for r in result if r.get("has_issues") and r.get("license") and not is_list_repo(r["full_name"])]


# ═══════════════════════════════════════════════════════════════════════
# Strategy B: Domain keyword → repos
# ═══════════════════════════════════════════════════════════════════════

def get_keyword_repos(min_stars=10, max_stars=0, max_days=14, count=10):
    keyword = random.choice(DOMAIN_KEYWORDS)
    since = (datetime.now(timezone.utc) - timedelta(days=max_days)).strftime("%Y-%m-%d")
    if max_stars and max_stars > 0:
        query = f"{keyword} stars:{min_stars}..{max_stars} pushed:>{since}"
    else:
        query = f"{keyword} stars:>={min_stars} pushed:>{since}"
    jq = "[.items[] | {full_name, stars: .stargazers_count, pushed_at, language, has_issues, license: .license.key}]"
    result = run_json(
        ["gh", "api", "-X", "GET", "search/repositories",
         "-f", f"q={query}", "-f", "sort=updated", "-f", "order=desc", "-f", f"per_page={count}",
         "--jq", jq], timeout=15,
    )
    if not result:
        return []
    filtered = [
        r for r in result
        if r.get("has_issues") and r.get("license")
        and (r.get("stars", 0) or 0) >= min_stars
        and not is_list_repo(r["full_name"])
    ]
    label = f"≤{max_stars}" if max_stars else "no max"
    print(f"  [kw] '{keyword}' → {len(result)} total, {len(filtered)} stars ≥{min_stars} {label}", file=sys.stderr)
    return filtered


# ═══════════════════════════════════════════════════════════════════════
# Strategy C: Direct issue search (reverse check repo after finding issue)
# ═══════════════════════════════════════════════════════════════════════

def get_direct_issues(count=20):
    """Search issues directly by label, skip repo-first discovery."""
    all_issues = []
    for label in DIRECT_SEARCH_LABELS[:2]:
        result = run_json(
            ["gh", "search", "issues",
             "--label", label,
             "--state", "open",
             "--sort", "created",
             "--order", "desc",
             "--limit", str(count // 2),
             "--json", "number,title,body,createdAt,labels,repository,commentsCount,assignees"],
            timeout=30,
        )
        if result:
            for item in result:
                repo_data = item.get("repository", {})
                if not repo_data:
                    continue
                rn = repo_data.get("nameWithOwner", "")
                if not rn:
                    continue
                item["_repo_full_name"] = rn
                all_issues.append(item)
    # Deduplicate by (repo, number)
    seen = set()
    unique = []
    for iss in all_issues:
        key = (iss["_repo_full_name"], iss["number"])
        if key not in seen:
            seen.add(key)
            unique.append(iss)
    return unique


# ═══════════════════════════════════════════════════════════════════════
# Core pipeline: evaluate a single issue
# ═══════════════════════════════════════════════════════════════════════

def evaluate_issue(repo_full_name, repo_stars, repo_license_str, issue,
                   clone_dir=None):
    """Run all filters and mechanical checks on one issue.
    Returns a candidate dict or None if filtered out."""

    number = issue["number"]
    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    created_at = issue.get("createdAt", "")
    labels = issue.get("labels", [])
    assignees = issue.get("assignees", []) or []
    comments_count = (issue.get("commentsCount", None) or 0)

    # ── Smart filters ──

    if is_bad_license(repo_license_str):
        print(f"  #{number} — SKIP (bad license: {repo_license_str})", file=sys.stderr)
        return None

    if is_spam_title(title):
        print(f"  #{number} — SKIP (spam title: {title[:60]})", file=sys.stderr)
        return None

    if not is_valid_body(body):
        print(f"  #{number} — SKIP (body too short/noisy: {len(body)} chars)", file=sys.stderr)
        return None

    if is_stale_issue(created_at, comments_count):
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - created).days
        except Exception:
            age = "?"
        print(f"  #{number} — SKIP (stale: {age}d old, {comments_count} comments)", file=sys.stderr)
        return None

    if not labels_ok(labels):
        label_names = [l.get("name", "") for l in labels]
        print(f"  #{number} — SKIP (non-priority labels: {label_names})", file=sys.stderr)
        return None

    # ── Assignee check ──
    if assignees:
        print(f"  #{number} — SKIP (assigned: {assignees[0].get('login', '?')})", file=sys.stderr)
        return None

    # ── Mechanical checks ──
    if clone_dir and check_commits_for_issue(clone_dir, number, created_at):
        print(f"  #{number} — SKIP (commit refs)", file=sys.stderr)
        return None

    if check_prs_for_issue(repo_full_name, number):
        print(f"  #{number} — SKIP (PR refs)", file=sys.stderr)
        return None

    if check_linked_prs(repo_full_name, number):
        print(f"  #{number} — SKIP (linked PRs)", file=sys.stderr)
        return None

    # ── Repo guidelines ──
    has_contributing = False
    has_claude_md = False
    if clone_dir:
        has_contributing = os.path.isfile(os.path.join(clone_dir, "CONTRIBUTING.md"))
        has_claude_md = os.path.isfile(os.path.join(clone_dir, "CLAUDE.md"))

    label_names = [l.get("name", "") for l in labels]

    return {
        "repo": repo_full_name,
        "repo_stars": repo_stars,
        "repo_license": repo_license_str,
        "repo_has_contributing": has_contributing,
        "repo_has_claude_md": has_claude_md,
        "issue_number": number,
        "issue_title": title,
        "issue_url": f"https://github.com/{repo_full_name}/issues/{number}",
        "issue_body": body[:2000],
        "issue_created": created_at,
        "issue_labels": label_names,
    }


# ═══════════════════════════════════════════════════════════════════════
# Main orchestration
# ═══════════════════════════════════════════════════════════════════════

def discover_candidates(min_stars=100, max_days=7, repo_count=10, issue_limit=8,
                        max_candidates=5, use_keyword=False, use_direct=False,
                        kw_min_stars=10, kw_max_stars=0):
    candidates = []

    # ── Collect repos ──
    repos = []

    if not use_direct:
        repos = get_trending_repos(min_stars, max_days, repo_count)
    if use_keyword:
        kw_repos = get_keyword_repos(kw_min_stars, kw_max_stars, max_days, repo_count)
        seen = {r["full_name"] for r in repos}
        for r in kw_repos:
            if r["full_name"] not in seen:
                repos.append(r)
                seen.add(r["full_name"])

    # ── Strategy C: Direct issue search ──
    if use_direct:
        print("[direct] Searching issues directly...", file=sys.stderr)
        direct_issues = get_direct_issues(count=30)
        print(f"[direct] Found {len(direct_issues)} raw issues", file=sys.stderr)
        for iss in direct_issues:
            if len(candidates) >= max_candidates:
                break
            rn = iss["_repo_full_name"]
            if not rn or is_list_repo(rn):
                continue
            # Quick license check for direct issues
            license_key = "unknown"
            repo_info = run_json(
                ["gh", "api", f"repos/{rn}", "--jq", "{stars: .stargazers_count, license: .license.spdx_id}"],
                timeout=10,
            )
            if repo_info:
                license_key = repo_info.get("license", "unknown") or "unknown"
                stars = repo_info.get("stars", 0)
            else:
                stars = 0

            if stars <= 0:
                continue  # skip repos with no stars (likely test/template repos)

            result = evaluate_issue(
                rn, stars, license_key, iss, clone_dir=None,
            )
            if result:
                candidates.append(result)
                print(f"  #{iss['number']} — CANDIDATE ✓", file=sys.stderr)
        if len(candidates) >= max_candidates:
            return candidates

    if not use_direct and not repos:
        print("ERROR: No repos found.", file=sys.stderr)
        return []

    # ── Process repos (Strategy A + B) ──
    for repo in repos:
        if len(candidates) >= max_candidates:
            break

        full_name = repo["full_name"]
        if is_list_repo(full_name):
            continue

        print(f"Scanning {full_name}...", file=sys.stderr)
        issues = run_json(
            ["gh", "issue", "list", "--repo", full_name, "--limit", str(issue_limit),
             "--state", "open", "--json", "number,title,updatedAt,createdAt,labels",
             "--jq", "sort_by(.createdAt) | reverse"],
            timeout=15,
        ) or []
        if not issues:
            continue

        clone_dir = None
        for issue in issues:
            if len(candidates) >= max_candidates:
                break
            clone_dir = clone_dir or clone_repo_shallow(full_name)
            result = evaluate_issue(
                full_name, repo["stars"], repo.get("license", "unknown"),
                issue, clone_dir=clone_dir,
            )
            if result:
                candidates.append(result)
                print(f"  #{issue['number']} — CANDIDATE ✓", file=sys.stderr)

        if clone_dir:
            run(f'rm -rf "{clone_dir}"', timeout=5)

    return candidates


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="Discover fixable GitHub issues")
    p.add_argument("--min-stars", type=int, default=100)
    p.add_argument("--max-days", type=int, default=7)
    p.add_argument("--repo-count", type=int, default=10)
    p.add_argument("--issue-limit", type=int, default=8)
    p.add_argument("--max-candidates", type=int, default=5)
    p.add_argument("--keyword", action="store_true")
    p.add_argument("--direct", action="store_true", help="Use Strategy C: direct issue search")
    p.add_argument("--kw-min-stars", type=int, default=10)
    p.add_argument("--kw-max-stars", type=int, default=0)
    p.add_argument("--json-only", action="store_true")
    args = p.parse_args()

    if args.json_only:
        sys.stderr = open(os.devnull, "w")

    candidates = discover_candidates(
        min_stars=args.min_stars, max_days=args.max_days,
        repo_count=args.repo_count, issue_limit=args.issue_limit,
        max_candidates=args.max_candidates,
        use_keyword=args.keyword, use_direct=args.direct,
        kw_min_stars=args.kw_min_stars, kw_max_stars=args.kw_max_stars,
    )

    if not candidates:
        print(json.dumps({"error": "no candidates found", "candidates": []}))
        sys.exit(1)

    print(json.dumps({"candidates": candidates}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
