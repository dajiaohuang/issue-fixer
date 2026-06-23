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

## Operating Modes

This skill has two modes. The user chooses by how they phrase the request.

### Confirm Mode (default)

When the user says "帮我找 issue" or "修这个 issue", work in confirm mode:
- Enter plan mode before writing code
- Present candidates, let user pick
- Wait for user approval before opening PRs

### Autonomous Mode

When the user says **"自动"**, **"不停"**, **"一直"**, **"autonomous"**, **"auto"**, or **"持续"**, switch to autonomous mode:

**No plan mode.** Discover → filter → fix → test → commit → PR → track → repeat. Never stop unless:
- 3 consecutive discovery rounds find zero actionable candidates (all unactionable SKIPs count as empty)
- The user interrupts

In autonomous mode, do NOT ask for confirmation. Work each candidate directly:

```
discover.py → candidate JSON
  → for each actionable candidate:
      → gh repo fork + git clone
      → read code, apply fix
      → run tests (if available)
      → git commit + push
      → gh pr create (fill PR template if exists)
      → pr_tracker.py add
      → clean up clone dir
  → repeat
```

**If 3 consecutive discovery rounds return zero actionable candidates**, improve the search (broader params, new query types, scan known repos) and keep going.

---

## Hard Rules (apply to BOTH modes)

### 1. Plan Mode is Mandatory

Whether the repo is specified by the user or auto-discovered, you MUST enter plan mode and get user approval before writing any code. The only exception is the Pre-Fix Checklist itself (reading commits/PRs/issue threads does not require a plan).

> **Autonomous mode override:** When the user says "自动"/"不停"/"auto"/"autonomous", plan mode is skipped. All other rules still apply.

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

#### Step 1: Run the Discovery Script

Use `scripts/discover.py` to automate all mechanical checks. Uses two strategies:

**Strategy A — Trending repos** (stars > 100, pushed within 7 days)
**Strategy B — Domain keyword sampling** (random keyword, stars 30–2000, pushed within 14 days)

```bash
# Trending only (fast)
python scripts/discover.py --min-stars 100 --max-days 7 --repo-count 10

# Trending + keyword (broader coverage)
python scripts/discover.py --min-stars 100 --max-days 7 --keyword
```

Parameters:
- `--min-stars` — minimum trending stars (default 100, lower to 50 if no results)
- `--max-days` — last push within N days (default 7, expand to 14 or 30)
- `--repo-count` — repos to scan per strategy (default 10)
- `--keyword` — enable Strategy B (domain keyword sampling)
- `--kw-min-stars` / `--kw-max-stars` — star range for keyword search (default 30–2000)
- `--max-candidates` — max issues to return (default 5)

The script outputs a JSON array of candidates that passed all checks. It handles Steps 1-3 of the pipeline automatically:
- Searches commits for issue references
- Searches open/closed/merged PRs
- Checks `closedByPullRequestsReferences` on the issue
- Filters out assigned issues

#### Step 2: Classify & Present

Read the JSON output. For each candidate, apply your judgment:

**Workload classification:**

| Effort  | Criteria                                    |
|---------|----------------------------------------------|
| trivial | Typo, dead link, comment fix, single-line    |
| small   | ≤3 files, ≤30 lines, single function/logic   |
| medium  | 3–8 files, new endpoint, DB migration        |
| large   | API change, multi-service, design discussion |

**Issue quality check:**
- Clear reproduction steps or acceptance criteria?
- Has a maintainer responded? What direction?
- Underspecified or already claimed?

#### Step 3: Present All Candidates as a Table

Present a table with **all** candidates that passed mechanical checks. Let the user pick.

| # | Repo | Issue | Type | Effort | Est. | Guidelines |
|---|------|-------|------|--------|------|------------|
| 1 | owner/repo | [#N](url) Title | bug | small | ~20 lines | CONTRIBUTING.md |
| 2 | ... | ... | ... | ... | ... | fallback |

For each row include a one-line fix summary. Only show `trivial` and `small` candidates — drop `medium`/`large`.

#### Fallback

If zero candidates, expand the search:
- Lower `--min-stars` (100 → 50 → 30 → 5 → 1)
- Broaden `--max-days` (7 → 14 → 30 → 120)
- Add new query types to `DIRECT_SEARCH_QUERIES`
- Run `scan_known_repos.py`
- In autonomous mode: keep expanding and retrying, never stop

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

## Autonomous Workflow

When in autonomous mode, run the full cycle without stopping:

### Step 1: Discover
```bash
python scripts/discover.py --direct --keyword --kw-min-stars 5 --max-days 120 --max-candidates 5
```

### Step 2: Scan known repos
```bash
python scripts/scan_known_repos.py
```

### Step 3: Fix each actionable candidate

For each candidate, execute directly (no plan mode, no confirmation):

```
1. Fork:     gh repo fork <owner>/<repo> --clone=false
2. Clone:    git clone https://github.com/dajiaohuang/<repo>.git <owner>-<repo>
3. Read:     Read relevant source files
4. Fix:     Apply the minimal change
5. Test:    Run tests (pytest / npm test / cargo test / etc.)
6. Commit:  git checkout -b fix/<N>-<slug> && git add -A && git commit
7. Push:    git push origin fix/<N>-<slug>
8. PR:      gh pr create --repo <owner>/<repo> --base <default-branch> --head dajiaohuang:fix/<N>-<slug>
9. Track:   python scripts/pr_tracker.py add <pr-url> <issue-url>
10. Clean:  rm -rf <clone-dir>; cd back to workspace
```

### Step 4: Handle failures

- **PR creation fails** (GraphQL error, wrong base branch): check `gh api repos/<owner>/<repo> --jq '.default_branch'`, retry with correct base
- **3 rounds empty**: expand `--min-stars` (5→3→1), `--max-days` (120→180→365), add new query types to `DIRECT_SEARCH_QUERIES`
- **Actionable but too complex** (needs full dev environment): skip, note reason

### Step 5: Loop

Back to Step 1. Never stop unless interrupted.

## PR Rules

### Confirm Mode
- Present summary, wait for user approval before `gh pr create`.

### Autonomous Mode
- Create PR immediately after push. No confirmation needed.

**PR Template — Mandatory**

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
2. **Check PRs** — search open, closed, and merged PRs for references to the issue. Also check the issue's linked PRs directly:
   ```bash
   gh issue view <N> --repo <owner/repo> --json closedByPullRequestsReferences --jq '.closedByPullRequestsReferences | length'
   ```
   If the returned count is > 0, the issue already has a linked PR that may close it. SKIP.
3. **Verify still open** — confirm via `gh issue view <number>`.
4. **Read the full thread** — understand maintainer direction, check if someone else is already working on it, and look for consensus on approach.

---

## Guideline Selection (Priority Order)

When working inside a cloned repo, check for these files in order. The first applicable one wins.

| Priority | File | What it covers |
|----------|------|---------------|
| 1 | `CLAUDE.md` | AI assistant instructions — follow exactly |
| 2 | `CONTRIBUTING.md` | PR process, commit style, testing requirements |
| 3 | `FAQ.md` | New contributor rules (introduction, AI policy, assignment) |
| 4 | `.github/pull_request_template.md` | Required PR checklist |
| 5 | `.github/ISSUE_TEMPLATE/*.md` | Issue structure conventions |
| 6 | `CODE_OF_CONDUCT.md` | Community norms |
| 7 | `DEVELOPMENT.md` / `BUILDING.md` | Local setup, build commands |
| 8 | `CODE_STYLE.md` / `.editorconfig` | Formatting rules |
| 9 | Lint config files (`.eslintrc*`, `.prettierrc*`, `pyproject.toml`, etc.) | Run the linter |
| 10 | `Makefile` / `justfile` / `package.json` scripts | Build/test/lint entry points |

If the target repo lacks all of the above, apply the **Fallback Maintenance Guidelines** below.

**Universal rules** (always apply):
- Match existing code style, naming, and patterns
- Run the existing test suite before making changes
- Make the smallest change that fixes the issue — no drive-by refactors
- **If FAQ.md requires self-introduction**, add a brief introduction in your PR body (who you are, why you're contributing)
- **If FAQ.md bans AI-generated content**, do NOT submit to that repo — skip it entirely

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
- **Register the PR in the tracker** after creation:
  ```bash
  python scripts/pr_tracker.py add <pr-url> <issue-url>
  ```

---

## PR Tracking

All submitted PRs are tracked in `pr_tracker.json`. Use `scripts/pr_tracker.py`:

```bash
# Add a PR after creating it
python scripts/pr_tracker.py add "https://github.com/owner/repo/pull/N" "https://github.com/owner/repo/issues/N"

# Check status of all tracked PRs (state changes, CI, reviews, new comments)
python scripts/pr_tracker.py check

# List all tracked PRs
python scripts/pr_tracker.py list
```

The `check` command reports:
- State changes (OPEN → MERGED / CLOSED)
- CI status (pass/fail/pending)
- New reviews (approved, changes requested, commented)
- New comments since last check

**When to check:**
- After every batch of new PRs is created
- When resuming a session to catch CI failures or review feedback
- Periodically for PRs that are awaiting merge

**When a check finds an issue** (CI failure, requested changes, review comment):
- Fix the problem immediately
- Push the fix to the same branch (PR updates automatically)
- Run `check` again to verify

---

## PR Review Response

After submitting a PR, bots (CodeRabbit, Greptile, Copilot, Qodo) and humans will leave review comments. Responding effectively requires triage — not every comment is a valid bug.

### Step 1: Collect All Comments

```bash
gh pr view <N> --repo <owner/repo> --comments --json comments --jq '.comments[] | "\(.author.login): \(.body)"'
```

Read every comment before acting.  Bots often flag the same issue from different angles — fix once, not N times.

### Step 2: Triage into Three Buckets

| Bucket | Criteria | Action |
|--------|----------|--------|
| 🔴 **Real bugs** | Crash, `NameError`, data loss, race condition, security hole | Fix immediately |
| 🟡 **Valid concerns** | Missing validation, unclear error messages, hardening gaps | Fix |
| ⚪ **Skip** | False positives, design choices, stale reviews (from before latest push), pre-existing issues not caused by the PR | Explain why, don't fix |

**Common false positives to recognize:**

| Signal | Why it's safe to skip |
|--------|----------------------|
| `codecov/patch` or `codecov/project` failure on fork PR | Fork CI doesn't upload coverage flags — not a real drop |
| Stale review from a bot referencing old line numbers | Check if the commit hash in the review is outdated; compare against `git log` |
| "Docstring coverage too low" (e.g. 35% vs 80% threshold) | Read the project's actual docstring convention; many projects don't enforce this |
| Bot suggests adding a parameter that's already there | The bot may have reviewed an intermediate commit — check current HEAD |

### Step 3: Fix in Order of Severity

1. **Blocking bugs first** (crash, `NameError`, race) — these need one commit
2. **Medium issues** (error handling, hardening) — can be one or more commits
3. **Skip bucket** — note in a single PR comment which items were intentionally skipped and why

### Step 4: Handle Remote Conflicts

If bots or maintainers push to your branch between your commits:

```bash
# Check what remote has
git fetch origin <branch>
git log --oneline origin/<branch> -5

# Pull with rebase
git pull --rebase origin <branch>

# If conflicts: check if remote already fixed the same things
# If remote fix is incomplete → abort, reset to remote, re-apply remaining fixes
git rebase --abort
git reset --hard origin/<branch>
# ... edit files to apply what's still missing ...
git add -A && git commit && git push
```

### Step 5: Check CI

```bash
gh pr checks <N> --repo <owner/repo>
```

Filter failures:

| Looks bad | Actually bad? |
|-----------|---------------|
| `test-core` / `test-windows` / `smoke` ❌ | 🔴 Yes — real test failure, investigate logs |
| `codecov/*` ❌ on fork PR | ⚪ No — fork doesn't upload coverage flags |
| `review` ❌ from bot | ⚪ Check the commit hash — if stale, ignore |

### Step 6: Comment After Every Push

Post a concise summary on the PR after each fix push:

```
gh pr comment <N> --repo <owner/repo> -F /tmp/msg.txt
```

Use `-F <file>` (not `--body`) to avoid shell escaping problems with backticks, quotes, and parentheses.

Include:
- What was fixed (with file names)
- What was intentionally skipped (with reasons)
- CI status assessment (which failures are real vs false positives)

---

## Tooling Notes

- Use `gh` CLI for all GitHub operations (issues, PRs, comments, search).
- Prefer Git Bash (`Bash` tool) over PowerShell for cross-platform consistency with cloned repos.
