# RepoStew

Repository Steward with Engineering Taste — a [Claude Code](https://claude.ai/code) skill that turns Claude into an autonomous open-source contributor. Point it at a specific issue, or let it discover trending repos with low-effort, unaddressed issues — it handles the full lifecycle from discovery to PR submission.

## Quick Install

```bash
# Install from the Claude skills registry
claude skills install dajiaohuang/issue-fixer
```

Or manually:

```bash
git clone https://github.com/dajiaohuang/issue-fixer.git ~/.claude/skills/issue-fixer
```

**Prerequisites:** Python 3, `gh` CLI (authenticated with GitHub), `git`, `claude` CLI.

## Full Lifecycle

| Step | What Happens |
|------|-------------|
| **Discover** | Finds trending repos or uses one you specify; scans open issues with 3 search strategies |
| **Verify** | Checks commits and PRs to confirm the issue isn't already fixed or claimed |
| **Assess** | Classifies workload (trivial→large), applies a **taste gate** to filter out bad fits |
| **Plan** | Enters plan mode with affected files, approach, and estimate — waits for your approval |
| **Implement** | Forks the repo, clones it, writes the fix following the repo's own conventions |
| **Submit** | Commits, pushes, and opens a PR (only after your explicit confirmation in confirm mode) |
| **Track** | Records all PRs in `pr_tracker.json`; monitors CI status, reviews, and comments |
| **Cleanup** | Deletes local clone after merge; fork can be kept or removed |

## Three Ways to Use

### 1. Fix a Specific Issue

Triggered by: providing a full issue URL or `owner/repo#N`.

```
"Fix https://github.com/owner/repo/issues/42"
```

Claude forks, runs the pre-fix checklist (commits/PRs for prior fixes), enters plan mode, and implements with your approval.

### 2. Scan a Repo for Fixable Issues

Triggered by: providing a repo without an issue number ("扫一下 owner/repo", "看看这个仓库有什么能做的").

Walks the repo's open issues **from newest to oldest**, applying the taste gate and pre-fix checklist to each one. Stops when it finds enough actionable candidates — doesn't blindly scan the entire backlog. Presents a table of candidates for you to choose from, then proceeds to the standard fix workflow.

Stop conditions (whichever comes first):
- 5 actionable candidates found
- 50 issues walked
- Reached issues older than 90 days with at least 1 candidate
- In autonomous mode: 1 actionable candidate → fix immediately, then resume scan

### 3. Auto-Discover Across GitHub

Triggered by: "帮我找 issue", "find me issues to fix".

Uses `scripts/discover.py` with three strategies (trending repos, domain keywords, direct issue search) to find low-effort, unaddressed issues across all of GitHub. Presents 3–5 candidates from diverse ecosystems.

## Two Operating Modes

### Confirm Mode (default)

Triggered by: "帮我找 issue", "修这个 issue", "扫一下 owner/repo", or any fix request without autonomous keywords.

```
You pick → Claude plans → You approve → Claude implements → You approve PR → Submit
```

- Plan mode is mandatory before any code is written
- Candidates presented as a table for you to choose from
- PR submitted only after your explicit confirmation

### Autonomous Mode

Triggered by: **"自动"**, **"不停"**, **"一直"**, **"auto"**, **"autonomous"**, **"持续"**

```
Discover → Filter → Fix → Test → Commit → PR → Track → Repeat
```

- No plan mode, no confirmation prompts
- Runs continuously: discovers, fixes, submits PRs, tracks them, and loops
- Exits only after 3 consecutive discovery rounds find zero actionable candidates, or you interrupt

## Discovery — Three Strategies

The `scripts/discover.py` engine uses three search strategies to avoid always landing in the same JS/Python repos:

| Strategy | How It Works |
|----------|-------------|
| **A — Trending repos** | Searches GitHub for repos pushed recently with minimum star threshold |
| **B — Domain keywords** | Randomly samples from 100+ keywords (golang, kubernetes, postgresql, cli tool, llm, wasm...) to find repos across diverse ecosystems |
| **C — Direct issue search** | Searches GitHub issues directly with quality signals: reactions, labels, body keywords, and issue age |

Each candidate is mechanically verified: checks commits for issue references, checks open/closed/merged PRs, checks `closedByPullRequestsReferences`, filters assigned issues, and deduplicates against `seen_issues.json`.

```bash
# Trending repos only (fast scan)
python scripts/discover.py --min-stars 100 --max-days 7 --repo-count 10

# All three strategies combined (broadest coverage)
python scripts/discover.py --direct --keyword --kw-min-stars 5 --max-days 120 --max-candidates 5
```

If discovery comes up empty, parameters auto-expand: `--min-stars` drops (100→50→30→5→1), `--max-days` widens (7→14→30→120), and `scan_known_repos.py` re-visits repos from previous contributions.

## The Taste Gate

Before any issue is touched, it passes through a quality gate. Not every open issue is worth fixing.

**ACCEPT** (do directly): clear bugs, docs fixes, test additions, small backward-compatible enhancements, style-consistent changes.

**ASK_MAINTAINER** (clarify first): new dependencies, external tools, public API changes, architecture changes, security-sensitive work, unclear requirements.

**REJECT_OR_SKIP** (avoid): stack rewrites, speculative features, tasks requiring secrets/paid services, off-topic or promotional issues, unbounded maintenance work.

A hard **external dependency gate** also applies: any new dependency, service, CLI tool, GitHub Action, or cloud resource requires maintainer approval — period.

## Hard Rules

These apply in **both** modes, every repo, no exceptions:

1. **Plan mode is mandatory** (confirm mode) — no code without your approval
2. **Follow the target repo's rules first** — read `CONTRIBUTING.md`, `CLAUDE.md`, PR template, and linter config before writing a single line. Be a good guest.
3. **Zero AI-generated markers** — never include "Co-Authored-By: Claude", "🤖 Generated with Claude Code", or any mention of Claude/Anthropic/AI/LLM in commits or PRs. The code is judged on its own merit.
4. **Minimal diffs** — smallest change that fixes the issue; no drive-by refactors, no style rewrites
5. **Contributor mode by default** — unless explicitly given maintainer authority, never reject issues, close issues, or speak on behalf of maintainers

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/discover.py` | Issue discovery engine (3 strategies, mechanical verification, JSON output) |
| `scripts/auto_fix.py` | Autonomous pipeline: chains discovery → fork → fix → PR → track via `claude -p` |
| `scripts/auto_fix.sh` | Bash equivalent of `auto_fix.py` |
| `scripts/loop.py` | Continuous autonomous loop with 3-dry-round exit and automatic parameter expansion |
| `scripts/pr_tracker.py` | PR lifecycle tracker: `add`, `check` (CI/reviews/comments), `list` |
| `scripts/scan_known_repos.py` | Re-visits repos from `pr_tracker.json` to find new open issues |

### PR Tracking

```bash
python scripts/pr_tracker.py add <pr-url> <issue-url> [--repo owner/repo]
python scripts/pr_tracker.py check [--repo owner/repo]   # CI status, reviews, new comments
python scripts/pr_tracker.py list
```

### Autonomous Pipeline

```bash
python scripts/auto_fix.py [--loop] [--max 5]
python scripts/loop.py          # Infinite loop, never stops until 3 dry rounds
```

## Safety Design

- **Plan mode is mandatory** — no code is written until you approve the plan (confirm mode)
- **Commit + PR dual check** — verifies issues aren't already fixed, including merged PRs that didn't auto-close the issue
- **Repo guidelines first** — follows the target repo's own `CLAUDE.md`/`CONTRIBUTING.md` when available; falls back to general best practices only when none exist
- **PR confirmation required** — never opens a PR without your explicit go-ahead (confirm mode)
- **Minimal diffs** — makes the smallest change that resolves the issue
- **Review permission model** — acts as a contributor unless maintainer authority is confirmed; never oversteps
- **Seen-issue deduplication** — `seen_issues.json` prevents re-processing the same issues across rounds

## Target Issue Types

Prioritizes low-effort, high-value issues across categories:

bug fixes · small features · documentation · test improvements · typos/formatting
dependency updates · error messages · dead code removal · configuration · accessibility

Work priority: **Bug fix > regression test > docs > small enhancement > feature-flag-guarded feature > large feature proposal**

## Self-Maintaining

This skill maintains itself. The RepoStew repository is stewarded by RepoStew — it discovers its own issues, fixes them, and continuously improves its own SKILL.md and scripts through the same workflow it provides to other repos.
