#!/bin/bash
# auto_fix.sh — autonomous issue-fixing pipeline
# Usage: ./auto_fix.sh [--loop] [--max 5]
#
# Runs discover.py, then spawns a claude -p process for each candidate
# to fix it independently.  With --loop, keeps running forever.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DISCOVER="$SKILL_DIR/scripts/discover.py"
TRACKER="$SKILL_DIR/scripts/pr_tracker.py"
WORKSPACE="D:/repo/issue-fixer"
SEEN="$SKILL_DIR/seen_issues.json"

# ── helpers ────────────────────────────────────────────────────────────

fix_one() {
    local repo="$1" stars="$2" license="$3" num="$4" title="$5" url="$6" labels="$7"
    local owner="${repo%/*}"
    local name="${repo#*/}"
    local branch="fix/${num}-$(echo "$title" | tr ' ' '-' | tr -cd 'a-zA-Z0-9-' | cut -c1-30 | sed 's/-$//')"

    echo ">>> Fixing $repo#$num: $title"

    claude -p --permission-mode bypassPermissions --output-format text "
You are an autonomous issue fixer.  Fix this GitHub issue and open a PR.
Do NOT ask any questions.  Do NOT enter plan mode.  Work silently.

**Issue:** $repo#$num — $title
**URL:** $url
**Stars:** $stars | **License:** $license | **Labels:** $labels

**Instructions:**
1. Fork:  gh repo fork $repo --clone=false
2. Clone: git clone https://github.com/dajiaohuang/$name.git $WORKSPACE/${owner}-${name}
3. cd into the clone and read the issue at $url using 'gh issue view $num --repo $repo'
4. Read the relevant source files, understand the bug, apply the MINIMAL fix
5. If the repo has CONTRIBUTING.md, follow its rules.  If it has a PR template, fill it.
6. Run tests if available (pytest / npm test / cargo test / etc.)
7. Commit with a conventional commit message (fix: / docs: / feat:).  No 'Co-Authored-By' markers.
8. Push to branch '$branch' on origin
9. Create PR: gh pr create --repo $repo --head dajiaohuang:\$branch --title '...' --body '...'
   (check default branch first: gh api repos/$repo --jq '.default_branch')
10. cd back to workspace

**Hard rules:**
- Never include Co-Authored-By, Generated with Claude Code, or 🤖 in commits or PRs
- Follow the target repo's CONTRIBUTING.md if it exists
- Make the smallest change that fixes the issue
" 2>&1

    local rc=$?
    if [ $rc -eq 0 ]; then
        echo "    ✓ $repo#$num fixed."
        python "$TRACKER" add "$url" "$url" 2>/dev/null || true
    else
        echo "    ✗ $repo#$num failed (exit $rc)"
    fi
}

run_once() {
    local max="${1:-5}"
    echo "=== $(date -Iseconds)  Discovering issues... ==="

    local json
    json=$(python "$DISCOVER" --direct --keyword --kw-min-stars 5 --max-days 120 --max-candidates "$max" 2>/dev/null)

    local count
    count=$(echo "$json" | python -c "import json,sys; print(len(json.load(sys.stdin).get('candidates',[])))" 2>/dev/null || echo 0)

    if [ "$count" -eq 0 ]; then
        echo "No candidates found."
        return 1
    fi

    echo "Found $count candidate(s)."

    echo "$json" | python -c "
import json, sys, subprocess, os
data = json.load(sys.stdin)
for c in data.get('candidates', []):
    repo = c['repo']
    stars = c.get('repo_stars', 0)
    lic = c.get('repo_license', '?')
    num = c['issue_number']
    title = c['issue_title']
    url = c['issue_url']
    labels = ','.join(c.get('issue_labels', []))
    print(f'{repo}|{stars}|{lic}|{num}|{title}|{url}|{labels}')
" | while IFS='|' read -r repo stars license num title url labels; do
        fix_one "$repo" "$stars" "$license" "$num" "$title" "$url" "$labels"
    done

    return 0
}

# ── main ───────────────────────────────────────────────────────────────

LOOP=false
MAX=3

while [ $# -gt 0 ]; do
    case "$1" in
        --loop) LOOP=true; shift ;;
        --max)  MAX="$2"; shift 2 ;;
        *)      echo "Usage: $0 [--loop] [--max N]"; exit 1 ;;
    esac
done

if $LOOP; then
    echo "Autonomous loop started. Press Ctrl+C to stop."
    while true; do
        run_once "$MAX" || sleep 30
    done
else
    run_once "$MAX"
fi
