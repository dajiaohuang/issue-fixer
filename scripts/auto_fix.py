#!/usr/bin/env python3
"""
Autonomous issue-fixing pipeline using claude -p.
Usage: python auto_fix.py [--loop] [--max 5]
"""

import json, os, subprocess, sys, time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISCOVER = os.path.join(SKILL_DIR, "scripts", "discover.py")
TRACKER = os.path.join(SKILL_DIR, "scripts", "pr_tracker.py")
WORKSPACE = r"D:\repo\issue-fixer"

FIX_PROMPT = """You are an autonomous issue fixer. Fix this GitHub issue and open a PR.
Do NOT ask any questions. Do NOT enter plan mode. Work silently. Output only a summary at the end.

**Issue:** {repo}#{num} — {title}
**URL:** {url}
**Stars:** {stars} | **License:** {license} | **Labels:** {labels}

**Instructions:**
1. Read the issue: gh issue view {num} --repo {repo}
2. Fork: gh repo fork {repo} --clone=false
3. Clone: git clone https://github.com/dajiaohuang/{name}.git {workspace}\\{owner}-{name}
4. cd into clone, read relevant source files, understand the bug, apply the MINIMAL fix
5. If the repo has CONTRIBUTING.md, follow its rules. If PR template exists, fill it.
6. Run tests if available (pytest / npm test / cargo test / etc.)
7. Commit with conventional commit (fix: / docs: / feat:). NEVER include Co-Authored-By, Generated with Claude Code, or 🤖.
8. Check default branch: gh api repos/{repo} --jq .default_branch
9. Push to branch '{branch}' on origin
10. Create PR with title and body linking to the issue
11. cd back to the workspace root

**Output format:** When done, print exactly:
PR_URL=<pr_url>
"""


def run(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1


def discover(max_candidates=3):
    stdout, stderr, rc = run(
        f"{sys.executable} {DISCOVER} --direct --keyword --kw-min-stars 5 --max-days 120 --max-candidates {max_candidates}",
        timeout=300,
    )
    if rc != 0 or not stdout:
        return []
    try:
        return json.loads(stdout).get("candidates", [])
    except json.JSONDecodeError:
        return []


def fix_one(candidate):
    repo = candidate["repo"]
    owner, name = repo.split("/")
    num = candidate["issue_number"]
    title = candidate["issue_title"]
    url = candidate["issue_url"]
    stars = candidate.get("repo_stars", 0)
    license_key = candidate.get("repo_license", "?")
    labels = ",".join(candidate.get("issue_labels", []) or [])
    slug = "".join(c if c.isalnum() else "-" for c in title.lower()[:40]).strip("-")
    branch = f"fix/{num}-{slug}"

    prompt = FIX_PROMPT.format(
        repo=repo, owner=owner, name=name, num=num,
        title=title, url=url, stars=stars, license=license_key,
        labels=labels, branch=branch, workspace=WORKSPACE,
    )

    print(f"\n>>> Fixing {repo}#{num}: {title[:80]}")
    print(f"    Running: claude -p ...")

    stdout, stderr, rc = run(f'claude -p --permission-mode bypassPermissions "{prompt}"', timeout=600)
    print(stdout[:500] if stdout else "(no output)")

    if rc == 0:
        print(f"    ✓ {repo}#{num} done.")
        run(f"{sys.executable} {TRACKER} add {url} {url}", timeout=10)
    else:
        print(f"    ✗ {repo}#{num} failed (rc={rc})")
        if stderr:
            print(f"    stderr: {stderr[:200]}")


def main():
    loop = "--loop" in sys.argv
    max_candidates = 3
    for i, a in enumerate(sys.argv):
        if a == "--max" and i + 1 < len(sys.argv):
            max_candidates = int(sys.argv[i + 1])

    if loop:
        print("Autonomous loop started. Ctrl+C to stop.")
        while True:
            candidates = discover(max_candidates)
            if not candidates:
                print("No candidates. Sleeping 30s...")
                time.sleep(30)
                continue
            print(f"Found {len(candidates)} candidate(s).")
            for c in candidates:
                fix_one(c)
            time.sleep(5)
    else:
        candidates = discover(max_candidates)
        if not candidates:
            print("No candidates found.")
            return
        print(f"Found {len(candidates)} candidate(s).")
        for c in candidates:
            fix_one(c)


if __name__ == "__main__":
    main()
