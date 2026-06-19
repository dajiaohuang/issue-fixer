# Issue Fixer

A [Claude Code](https://claude.ai/code) skill for automatically fixing GitHub issues across any open-source repository — whether you point it at a specific issue or let it discover trending repos with low-effort, unaddressed issues.

## Quick Install

```bash
# Install the skill from the registry
claude skills install dajiaohuang/issue-fixer
```

Or manually:
```bash
git clone https://github.com/dajiaohuang/issue-fixer.git ~/.claude/skills/issue-fixer
```

## What It Does

Issue Fixer turns Claude Code into an autonomous open-source contributor. It handles the full lifecycle:

| Step | What Happens |
|------|-------------|
| **Discover** | Finds trending repos (or uses one you specify), scans open issues from newest to oldest |
| **Verify** | Checks commits and PRs to confirm the issue isn't already fixed or claimed |
| **Assess** | Classifies workload (trivial/small → keep, medium/large → skip) and estimates effort |
| **Plan** | Enters plan mode with affected files, approach, and time estimate — waits for your approval |
| **Implement** | Forks the repo, clones it, writes the fix following the repo's own conventions |
| **Submit** | Commits, pushes, and opens a PR (only after your explicit confirmation) |
| **Cleanup** | Deletes the local clone after merge; fork can be kept or removed |

## Two Modes

### Mode A — You Pick the Issue
```
"Fix https://github.com/owner/repo/issues/42"
```
Claude forks, checks commits/PRs for prior fixes, enters plan mode, and implements with your approval.

### Mode B — Auto-Discover
```
"Find me some issues to fix"
```
Claude searches trending repos **and** random domain keywords (to avoid always landing in the same JS/Python repos), walks issues newest-to-oldest, filters to low-effort/unaddressed, and presents 3–5 candidates for you to choose from.

## Safety Design

- **Plan mode is mandatory** — no code is written until you approve the plan
- **Commit + PR dual check** — verifies issues aren't already fixed (including merged PRs that didn't auto-close the issue)
- **Repo guidelines first** — follows the target repo's own `CLAUDE.md`/`CONTRIBUTING.md` when available; only falls back to general best practices when none exist
- **PR confirmation required** — never opens a PR without your explicit go-ahead
- **Minimal diffs** — makes the smallest change that resolves the issue, no drive-by refactors

## Target Issue Types

Prioritizes low-effort issues across 10 categories:

bug fixes · small features · documentation · test improvements · typos/formatting
dependency updates · error messages · dead code removal · configuration · accessibility
