#!/usr/bin/env python3
"""
PR tracker for issue-fixer skill.
- Records PRs after creation
- Checks status of all tracked PRs
- Detects CI failures, review requests, new comments

Usage:
    python pr_tracker.py add <pr-url> <issue-url> [--repo <owner/repo>]
    python pr_tracker.py check [--repo <owner/repo>]
    python pr_tracker.py list
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

TRACKER_FILE = os.path.join(os.path.dirname(__file__), "..", "pr_tracker.json")


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

def load():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save(data):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def cmd_add(args):
    """Add a PR to the tracker."""
    # Parse PR URL: https://github.com/owner/repo/pull/N
    url = args.pr_url.rstrip("/")
    parts = url.split("/")
    if len(parts) < 7 or parts[5] != "pull":
        print(f"ERROR: invalid PR URL: {url}", file=sys.stderr)
        sys.exit(1)
    owner, repo, number = parts[3], parts[4], parts[6]
    full_name = f"{owner}/{repo}"

    # Get current PR status
    pr = run_json(
        ["gh", "pr", "view", number, "--repo", full_name,
         "--json", "state,createdAt,mergedAt,closedAt,statusCheckRollup"],
        timeout=15,
    )
    if not pr:
        print(f"ERROR: could not fetch PR {url}", file=sys.stderr)
        sys.exit(1)

    entry = {
        "repo": full_name,
        "pr_number": int(number),
        "pr_url": url,
        "issue_url": args.issue_url,
        "state": pr.get("state"),
        "created_at": pr.get("createdAt"),
        "merged_at": pr.get("mergedAt"),
        "closed_at": pr.get("closedAt"),
        "ci_status": _summarize_checks(pr.get("statusCheckRollup", [])),
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }

    data = load()
    # Replace if exists
    data = [d for d in data if not (d["repo"] == full_name and d["pr_number"] == int(number))]
    data.append(entry)
    save(data)
    print(f"Tracked: {full_name}#{number} ({pr.get('state')})")


def cmd_check(args):
    """Check status of tracked PRs."""
    data = load()
    if not data:
        print("No tracked PRs.")
        return

    updated = []
    for entry in data:
        full_name = entry["repo"]
        number = entry["pr_number"]
        print(f"\n{'='*60}")
        print(f"{full_name}#{number}  {entry['pr_url']}")
        print(f"Issue: {entry.get('issue_url', '?')}")

        pr = run_json(
            ["gh", "pr", "view", str(number), "--repo", full_name,
             "--json", "state,createdAt,mergedAt,closedAt,statusCheckRollup,reviews,comments"],
            timeout=15,
        )
        if not pr:
            print("  [ERROR] Could not fetch PR status")
            entry["last_checked"] = datetime.now(timezone.utc).isoformat()
            updated.append(entry)
            continue

        old_state = entry.get("state")
        new_state = pr.get("state")
        state_icon = {"OPEN": "🟢", "MERGED": "🟣", "CLOSED": "🔴"}.get(new_state, "⚪")
        print(f"  State: {old_state} → {state_icon} {new_state}")

        # CI status
        checks = pr.get("statusCheckRollup", [])
        ci = _summarize_checks(checks)
        print(f"  CI: {_format_ci(ci)}")

        # Reviews
        reviews = pr.get("reviews", []) or []
        if reviews:
            for r in reviews:
                state = r.get("state", "")
                author = r.get("author", {}).get("login", "?")
                icon = {"APPROVED": "✅", "CHANGES_REQUESTED": "❌", "COMMENTED": "💬"}.get(state, "")
                print(f"  Review: {icon} {author} ({state})")

        # Comments since last check
        comments = pr.get("comments", []) or []
        new_comments = 0
        for c in comments:
            created = c.get("createdAt", "")
            if created and (not entry.get("last_checked") or created > entry["last_checked"]):
                new_comments += 1
        if new_comments:
            # Show latest comment
            sorted_comments = sorted(comments, key=lambda c: c.get("createdAt", ""), reverse=True)
            latest = sorted_comments[0]
            author = latest.get("author", {}).get("login", "?")
            body = (latest.get("body", "") or "")[:400]
            print(f"  🔔 New comments: {new_comments}")
            print(f"     Latest by {author}: {body}")

        entry["state"] = new_state
        entry["merged_at"] = pr.get("mergedAt")
        entry["closed_at"] = pr.get("closedAt")
        entry["ci_status"] = ci
        entry["last_checked"] = datetime.now(timezone.utc).isoformat()
        updated.append(entry)

    save(updated)
    print(f"\n{'='*60}")
    print(f"Checked {len(updated)} PRs.")


def cmd_list(args):
    """List tracked PRs."""
    data = load()
    if not data:
        print("No tracked PRs.")
        return

    print(f"{'Repo':<35} {'PR':<6} {'State':<12} {'CI':<15} Issue")
    print("-" * 100)
    for entry in data:
        full_name = entry["repo"]
        number = entry["pr_number"]
        state = entry.get("state", "?")
        ci = _format_ci(entry.get("ci_status", {}))
        issue = entry.get("issue_url", "")
        print(f"{full_name:<35} #{number:<5} {state:<12} {ci:<15} {issue}")


def _summarize_checks(checks):
    """Summarize CI check results."""
    result = {"total": 0, "success": 0, "failure": 0, "skipped": 0, "pending": 0}
    for c in (checks or []):
        result["total"] = result.get("total", 0) + 1
        conclusion = (c.get("conclusion") or "").lower()
        if conclusion == "success":
            result["success"] = result.get("success", 0) + 1
        elif conclusion == "failure":
            result["failure"] = result.get("failure", 0) + 1
        elif conclusion == "skipped":
            result["skipped"] = result.get("skipped", 0) + 1
        else:
            result["pending"] = result.get("pending", 0) + 1
    return result

def _format_ci(ci):
    """Format CI summary."""
    if not ci or ci.get("total", 0) == 0:
        return "no CI"
    parts = []
    if ci.get("failure", 0) > 0:
        parts.append(f"❌{ci['failure']}")
    if ci.get("success", 0) > 0:
        parts.append(f"✅{ci['success']}")
    if ci.get("pending", 0) > 0:
        parts.append(f"⏳{ci['pending']}")
    return "/".join(parts) if parts else "?"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="PR tracker for issue-fixer")
    sp = p.add_subparsers(dest="cmd")

    add_p = sp.add_parser("add")
    add_p.add_argument("pr_url")
    add_p.add_argument("issue_url")

    sp.add_parser("check")
    sp.add_parser("list")

    args = p.parse_args()
    if args.cmd == "add":
        cmd_add(args)
    elif args.cmd == "check":
        cmd_check(args)
    elif args.cmd == "list":
        cmd_list(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
