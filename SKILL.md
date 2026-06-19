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

## Hard Rules

### 1. Plan Mode is Mandatory for ALL Fixes

Whether the repo is specified by the user or auto-discovered, you MUST enter plan mode and get user approval before writing any code. The only exception is the Pre-Fix Checklist itself (reading commits/PRs/issue threads does not require a plan).

### 2. Follow the Target Repo's Rules — No Exceptions

**Before writing a single line of code**, read the target repo's own guidelines. If the repo has a `CONTRIBUTING.md`, `CLAUDE.md`, `DEVELOPMENT.md`, or any other governance file, you MUST comply with every requirement in it. This is not optional — you are a guest in their project.

Specifically:
- **PR template** — if `.github/pull_request_template.md` exists, use its exact structure
- **Commit format** — follow the repo's convention, not yours; if `CONTRIBUTING.md` specifies a format, use it
- **Testing requirements** — if they require tests, add them; if they require `doctest` for every function, do it
- **Code style** — match their linter config, not your preferences
- **Branch naming** — if they specify a naming convention, follow it; otherwise use `fix/<issue-number>-<short-description>`
- **Sign-off / DCO** — if the repo requires `Signed-off-by`, include it

If you skip reading their guidelines and submit a non-compliant PR, you are wasting the maintainers' time. Read first, code second.

### 3. No AI-Generated Markers in Commits or PRs — Zero Tolerance

**Never** include any of the following in commit messages, PR titles, or PR bodies:

- `Co-Authored-By: Claude`
- `Generated with Claude Code`
- `🤖 Generated with...`
- Any mention of Claude, Anthropic, AI, or LLM assistance

This applies to **every PR, every repo, no exceptions**. Even if the target repo does not explicitly ban AI content, these markers will cause maintainers to dismiss your contribution without review. Write commit messages and PR bodies naturally — the code is judged on its own merit, not its origin.

Use natural language: `docs: add docstrings to helper functions` not `claude added docstrings`.

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

Find **3 low-effort, unaddressed issues** from trending repos and let the user pick.

#### Phase 1: Source Trending Repos

Query GitHub trending repos with recent pushes:
```bash
gh api -X GET search/repositories \
  -f q='pushed:>$(date -d "7 days ago" +%Y-%m-%d) stars:>100' \
  -f sort=stars -f order=desc -f per_page=10 \
  --jq '.items[] | {full_name, stars: .stargazers_count, pushed_at, language}'
```

**Repo filters:**
- Stars: ≥ 100, pushed within 7 days
- Has open issues with recent activity
- Has a license file (skip unlicensed repos)
- Prefer repos with `CONTRIBUTING.md` or `CLAUDE.md`

#### Phase 2: Issue Triage

For each trending repo, walk issues **from newest to oldest**, running this pipeline on each. Stop scanning once you have **3 qualified candidates** across all repos.

##### Issue Evaluation Pipeline

Run each check in order. If any fails, skip and move to the next issue.

**Step 1 — Already addressed in commits?**
```bash
git log --all --oneline --grep="#<N>" --since="<issue.created_at>"
git log --all --oneline --grep="<key terms>" --since="<issue.created_at>"
```
If a commit references the issue or describes the fix → SKIP

**Step 2 — Already addressed in PRs?**
```bash
gh pr list --repo <owner/repo> --state all --search "<keywords>" --json number,title,state
gh pr list --repo <owner/repo> --state merged --search "#<N>" --json number,title
```
Check closed PRs — fixes may have merged without auto-closing. Also search for "Fixes #<N>" / "Closes #<N>" in PR bodies. If found → SKIP

**Step 3 — Still reproducible on default branch?**
If the repo is cloneable and buildable, quickly verify the bug still exists on the default branch.
If the described behavior is already gone → SKIP (fixed without referencing the issue)

**Step 4 — Workload classification:**

| Effort  | Criteria                                    | Keep? |
|---------|----------------------------------------------|-------|
| trivial | Typo, dead link, comment fix, single-line    | ✓     |
| small   | ≤3 files, ≤30 lines, single function/logic   | ✓     |
| medium  | 3–8 files, new endpoint, DB migration        | ✗     |
| large   | API change, multi-service, design discussion | ✗     |

Only keep **trivial** and **small**. Drop medium/large.

**Step 5 — Effort estimate:**
Record files affected, lines of change, testing needed, any dependency risks.

**Step 6 — Issue quality check:**
- Clear reproduction steps or acceptance criteria?
- Has a maintainer responded? What direction?
- Is someone else already assigned or visibly working on it?
Drop underspecified or already-claimed issues.

**Priority labels to favor:**

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

#### Phase 3: Present 3 Candidates

1. **Enter plan mode.** Present exactly **3 candidates**. For each, include:
   - Repo name, issue number, issue title (linked)
   - Workload + estimate (e.g., "small, ~3 files, ~20 lines, 15 min")
   - Whether the repo has its own guidelines or will use fallback
   - One-line summary of the fix approach

2. Let the user choose one (or reject all). Do not start until user approves.

3. If **fewer than 3** candidates survive across all trending repos, expand the search:
   - Lower star threshold (100 → 50 → 30)
   - Broaden date range (7d → 14d → 30d)
   - If still not enough, report what was found and ask for direction.

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

### PR Template — Mandatory

Always check `.github/pull_request_template.md` before opening a PR. If the repo has a template:
- Copy its structure into your PR body
- Fill every applicable checkbox — bots WILL close PRs with unchecked boxes
- If the template asks for a description, screenshot, or changelog entry, provide it

### Before Asking for Confirmation

Verify:
- All tests pass
- Lint passes (if the repo has linting)
- Commit messages follow the repo's convention
- The branch contains only fix commits — check with `git diff origin/<default-branch>...HEAD --stat`
- PR template is filled out completely
- No AI-generated markers in PR body

---

## Pre-Fix Checklist (Mandatory for Every Issue)

0. **Read the repo's contribution rules first** — before anything else, find and read `CONTRIBUTING.md`, `CLAUDE.md`, `DEVELOPMENT.md`, `.github/pull_request_template.md`, and any linter config. If the repo tells you how to do something, you follow that rule. No exceptions.

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
