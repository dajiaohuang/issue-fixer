#!/usr/bin/env python3
"""
Scan open issues from repos we've already contributed to.
Skips seen issues, outputs fresh candidates as JSON.
"""

import json, os, subprocess, sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKER = os.path.join(SKILL_DIR, "pr_tracker.json")
SEEN = os.path.join(SKILL_DIR, "seen_issues.json")

DISCOVER_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DISCOVER_DIR)
from discover import (
    run, run_json, _load_seen, _mark_seen, _is_seen,
    is_list_repo, is_bad_license, is_spam_title, is_valid_body,
    is_stale_issue, labels_ok, check_prs_for_issue, check_linked_prs,
    evaluate_issue, clone_repo_shallow,
)


def get_known_repos():
    """Extract unique repo list from PR tracker."""
    if not os.path.exists(TRACKER):
        return []
    with open(TRACKER) as f:
        prs = json.load(f)
    return list(dict.fromkeys(p["repo"] for p in prs))


def main():
    repos = get_known_repos()
    print(f"Known repos: {len(repos)}", file=sys.stderr)

    candidates = []
    max_candidates = 10

    for full_name in repos:
        if len(candidates) >= max_candidates:
            break

        print(f"\nScanning {full_name}...", file=sys.stderr)

        # Quick license check
        repo_info = run_json(
            ["gh", "api", f"repos/{full_name}",
             "--jq", "{stars: .stargazers_count, license: .license.spdx_id, has_issues}"],
            timeout=10,
        )
        if not repo_info or not repo_info.get("has_issues"):
            continue
        if is_bad_license(repo_info.get("license", "")):
            continue
        if is_list_repo(full_name):
            continue

        stars = repo_info.get("stars", 0)
        license_key = repo_info.get("license", "")

        issues = run_json(
            ["gh", "issue", "list", "--repo", full_name, "--limit", "15",
             "--state", "open", "--json", "number,title,createdAt,labels",
             "--jq", "sort_by(.createdAt) | reverse"],
            timeout=15,
        ) or []

        clone_dir = None
        for issue in issues:
            if len(candidates) >= max_candidates:
                break

            num = issue["number"]
            if _is_seen(full_name, num):
                continue
            _mark_seen(full_name, num)

            # Get full detail
            detail = run_json(
                ["gh", "issue", "view", str(num), "--repo", full_name,
                 "--json", "number,title,body,createdAt,labels,assignees,commentsCount"],
                timeout=10,
            )
            if not detail:
                continue

            # Quick filters
            if not labels_ok(detail.get("labels", [])):
                continue
            if detail.get("assignees"):
                continue
            if is_spam_title(detail.get("title", "")):
                continue
            if not is_valid_body(detail.get("body", "")):
                continue
            if is_stale_issue(detail.get("createdAt", ""), detail.get("commentsCount", 0)):
                continue

            # Mechanical checks
            clone_dir = clone_dir or clone_repo_shallow(full_name)
            if clone_dir:
                from discover import check_commits_for_issue
                if check_commits_for_issue(clone_dir, num, detail.get("createdAt", "")):
                    print(f"  #{num} — SKIP (commit refs)", file=sys.stderr)
                    continue

            if check_prs_for_issue(full_name, num):
                print(f"  #{num} — SKIP (PR refs)", file=sys.stderr)
                continue

            if check_linked_prs(full_name, num):
                print(f"  #{num} — SKIP (linked PRs)", file=sys.stderr)
                continue

            label_names = [l.get("name", "") for l in (detail.get("labels", []) or [])]
            candidates.append({
                "repo": full_name,
                "repo_stars": stars,
                "repo_license": license_key,
                "issue_number": num,
                "issue_title": detail.get("title", ""),
                "issue_url": f"https://github.com/{full_name}/issues/{num}",
                "issue_body": (detail.get("body", "") or "")[:2000],
                "issue_created": detail.get("createdAt", ""),
                "issue_labels": label_names,
            })
            print(f"  #{num} — CANDIDATE ✓", file=sys.stderr)

        if clone_dir:
            import shutil
            shutil.rmtree(clone_dir, ignore_errors=True)

    if not candidates:
        print(json.dumps({"candidates": []}))
        return

    print(json.dumps({"candidates": candidates}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
