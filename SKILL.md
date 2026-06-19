---
name: issue-fixer
description: >
  Fix GitHub issues across arbitrary repositories. Use this skill whenever the user asks to fix a GitHub issue,
  find issues to work on, contribute to open source, or mentions "issue-fixer". Covers both specific repos
  (user provides owner/repo) and auto-discovery (find trending repos with low-effort unaddressed issues).
  Always invoke before forking, cloning, or writing any fix code — this skill defines the mandatory workflow.
---

# Issue Fixer

## Purpose

This skill guides Claude through fixing GitHub issues in arbitrary repositories. The workspace directory (`D:\repo\issue-fixer`) is a staging area — target repos are forked and cloned into subdirectories here, worked on, and cleaned up after the PR is merged or closed.

## Hard Rule — Plan Mode is Mandatory for ALL Fixes

Whether the repo is specified by the user or auto-discovered, you MUST enter plan mode and get user approval before writing any code. The only exception is the Pre-Fix Checklist itself (reading commits/PRs/issue threads does not require a plan).

---

## Workflow: Choosing a Target

### Mode A — Specified Repo

The user provides a repo (`owner/repo`) and optionally an issue number.

1. Fork and clone the repo.
2. Run the **Pre-Fix Checklist** (commit/PR search, verify open, read thread).
3. **Enter plan mode.** Present:
   - A summary of the issue and what the fix involves
   - Which files are likely affected
   - Estimated effort (files, lines, time)
   - Which guidelines will be used (repo's own or fallback)
4. Wait for user approval before writing any code.

### Mode B — Auto-Discover

Find low-effort, unaddressed issues in active open-source repos. Three phases: repo sourcing → issue triage → candidate presentation.

#### Phase 1: Repo Sourcing

Use BOTH strategies to build a pool of 5–10 candidate repos.

**Strategy A — GitHub Trending**
```bash
gh api -X GET search/repositories \
  -f q='pushed:>$(date -d "7 days ago" +%Y-%m-%d) stars:>100' \
  -f sort=stars -f order=desc -f per_page=10 \
  --jq '.items[] | {full_name, stars: .stargazers_count, pushed_at, language, topics: .topics}'
```

**Strategy B — Domain Keyword Sampling**
Pick a random keyword from the pool below (rotate each session) to avoid always landing in the same trending repos:
```
"inventory management", "task runner", "static site generator", "markdown parser",
"cli tool", "dashboard", "api gateway", "job scheduler", "image optimizer",
"openapi", "websocket", "cron", "diff", "sqlite", "cache", "queue",
"form builder", "csv", "pdf", "email", "auth", "i18n", "theme",
"webhook", "proxy", "log", "monitor", "backup", "migrate", "scraper"
```
```bash
gh api -X GET search/repositories \
  -f q='KEYWORD stars:30..2000 pushed:>$(date -d "14 days ago" +%Y-%m-%d)' \
  -f sort=updated -f order=desc -f per_page=10 \
  --jq '.items[] | {full_name, stars: .stargazers_count, pushed_at, language}'
```

**Repo filtering criteria:**
- Stars: ≥ 30
- Last push: within 14 days
- Has open issues with activity in the last 30 days
- Has a license file (skip unlicensed repos)
- Prefer repos with `CONTRIBUTING.md` or `CLAUDE.md`

#### Phase 2: Issue Triage

Walk issues **from newest to oldest** in each candidate repo. Newer issues are less likely to already be fixed.

##### Issue Evaluation Pipeline (run per issue, in order)

**Step 1 — Already addressed in commits?**
```bash
git log --all --oneline --grep="#<N>" --since="<issue.created_at>"
git log --all --oneline --grep="<key terms>" --since="<issue.created_at>"
```
If a commit references the issue or describes the fix → SKIP

**Step 2 — Already addressed in PRs?**
```bash
gh pr list --repo <owner/repo> --state all --search "<keywords>" --json number,title,state,body
gh pr list --repo <owner/repo> --state merged --search "#<N>" --json number,title
```
Check closed PRs too — fixes may have merged without auto-closing the issue.
Look for "Fixes #<N>" or "Closes #<N>" in PR descriptions.
If a PR already addresses this issue → SKIP

**Step 3 — Still reproducible on default branch?**
If the repo is cloneable/buildable, quickly verify the bug still exists.
If not → SKIP (fixed without referencing the issue)

**Step 4 — Workload classification:**

| Effort  | Criteria                                    | Keep? |
|---------|----------------------------------------------|-------|
| trivial | Typo, dead link, comment fix, single-line    | ✓     |
| small   | ≤3 files, ≤30 lines, single function/logic   | ✓     |
| medium  | 3–8 files, new endpoint, DB migration        | ✗     |
| large   | API change, multi-service, design discussion | ✗     |

**Step 5 — Effort estimate:**
Record files affected, lines of change, testing needed, dependency risks.

**Step 6 — Issue quality check:**
- Clear reproduction steps or acceptance criteria?
- Maintainer response/direction?
- Someone else assigned or working on it?
Drop underspecified or already-claimed issues.

**Priority labels:**

| Category          | Labels                                          |
|-------------------|-------------------------------------------------|
| Bug fix           | `bug`, `fix`                                    |
| Small feature     | `enhancement`, `feature`, `good first issue`    |
| Documentation     | `documentation`, `docs`                         |
| Test improvement  | `test`, `testing`, `coverage`                   |
| Typo / formatting | `typo`, `chore`, `style`                        |
| Dependency update | `dependencies`                                  |
| Error message     | `ux`, `error-handling`                          |
| Dead code removal | `cleanup`, `refactor`                           |
| Configuration     | `config`, `ci`, `chore`                         |
| Accessibility     | `accessibility`, `a11y`                         |

#### Phase 3: Candidate Presentation

1. **Enter plan mode** for every candidate. Present each with:
   - Repo, issue number, title (linked)
   - Workload classification + estimate (e.g., "small, ~3 files, ~20 lines, 15 min")
   - Whether the repo has its own guidelines or will use fallback
   - One-line fix approach summary

2. Present the top 3–5 candidates. Do not start until user approves.

3. If zero candidates survive triage, expand the search:
   - Broaden date range (7d → 14d → 30d)
   - Lower the star threshold
   - Try a different domain keyword
   - Report back and ask for direction.

---

## Fork & Clone

Always fork before cloning — it's required to push a branch and open a PR.

```bash
gh repo fork <owner>/<repo> --clone=false
```
Then clone the fork into the workspace:
```bash
git clone https://github.com/<your-username>/<repo>.git <owner>-<repo>
```

**Branch naming:** `fix/<issue-number>-<short-description>` branched from the fork's default branch.

**Cleanup:** Delete the local clone after PR merge/closure. The fork can be kept or deleted.

## PR Rules

- **Never open a PR without explicit user confirmation.** After pushing, present a summary and wait for approval.
- Before asking for confirmation, verify:
  - All tests pass
  - Lint passes (if the repo has linting)
  - Commit messages follow the repo's convention
  - The branch contains only fix commits — check with `git diff origin/<default-branch>...HEAD --stat`

---

## Pre-Fix Checklist (Mandatory for Every Issue)

1. **Check commits** — search for the issue number and related keywords since the issue's creation date.
2. **Check PRs** — search open, closed, and merged PRs for references to the issue.
3. **Verify still open** — confirm via `gh issue view <number>`.
4. **Read the full thread** — understand maintainer direction, check if someone else is already working on it, and look for consensus on approach.

---

## Guideline Selection (Priority Order)

When working inside a cloned repo, check for these files in order. The first applicable one wins.

| Priority | File | What it covers |
|----------|------|---------------|
| 1 | `CLAUDE.md` | AI assistant instructions — follow exactly |
| 2 | `CONTRIBUTING.md` | PR process, commit style, testing requirements |
| 3 | `.github/pull_request_template.md` | Required PR checklist |
| 4 | `.github/ISSUE_TEMPLATE/*.md` | Issue structure conventions |
| 5 | `CODE_OF_CONDUCT.md` | Community norms |
| 6 | `DEVELOPMENT.md` / `BUILDING.md` | Local setup, build commands |
| 7 | `CODE_STYLE.md` / `.editorconfig` | Formatting rules |
| 8 | Lint config files (`.eslintrc*`, `.prettierrc*`, `pyproject.toml`, etc.) | Run the linter |
| 9 | `Makefile` / `justfile` / `package.json` scripts | Build/test/lint entry points |

If the target repo lacks all of the above, apply the **Fallback Maintenance Guidelines** below.

**Universal rules** (always apply):
- Match existing code style, naming, and patterns
- Run the existing test suite before making changes
- Make the smallest change that fixes the issue — no drive-by refactors

---

## Fallback Maintenance Guidelines

Apply when the target repo has no explicit CLAUDE.md, CONTRIBUTING.md, or equivalent.

### Before Writing Code
1. **Reproduce the bug** — run the project locally and confirm the bug exists. Deduce run instructions from `package.json`, `Makefile`, `Cargo.toml`, `go.mod`, etc.
2. **Find relevant code** — use `git log --follow` on affected files to understand recent changes that may have introduced the bug.

### Writing the Fix
1. **Match existing style** — follow indentation, quoting, naming, and comment conventions already in the file.
2. **Minimal diff** — avoid refactoring unrelated code, whitespace changes outside affected lines, dependency upgrades, or new abstractions.
3. **Consider edge cases** — null/undefined/empty inputs, boundary conditions, concurrency/race conditions, error states.

### Testing
1. Add a test that reproduces the bug and passes with the fix, following the project's test organization pattern.
2. Run the full test suite — do not submit until all pass.
3. If the project has no tests and the issue is sensitive (security, data loss), mention this in the PR description.

### Commit & PR
If the repo has no convention, use:
```
<type>: <short description>

<optional body — what was wrong, how it was fixed>

Fixes #<issue-number>
```
Types: `fix`, `feat`, `docs`, `test`, `refactor`, `chore`

PR description should include: what the issue was, root cause, how the fix works, how tested, screenshots/logs if relevant.

### After Submitting
- Respond to review feedback promptly. Each requested change either gets applied or gets a clear explanation.
- Clean up the local clone after merge or closure.

---

## Tooling Notes

- Use `gh` CLI for all GitHub operations (issues, PRs, comments, search).
- Prefer Git Bash (`Bash` tool) over PowerShell for cross-platform consistency with cloned repos.
