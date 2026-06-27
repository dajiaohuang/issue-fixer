---
name: repostew
description: >
  Repository Steward with Engineering Taste. Use this skill whenever the user asks to fix a GitHub issue,
  find issues to work on, contribute to open source, steward a repository, or mentions "RepoStew",
  "repostew", or "issue-fixer". Covers both specific repos (user provides owner/repo) and auto-discovery
  (find trending repos with low-effort unaddressed issues). Always invoke before forking, cloning,
  commenting on issues, or writing any fix code — this skill defines the mandatory workflow.
---

# RepoStew

Repository Steward with Engineering Taste.

## Purpose

This skill guides Claude through stewarding GitHub issues and fixing suitable issues in arbitrary repositories. The workspace directory (`/workspace/issue-fixer`) is a staging area — target repos are forked and cloned into subdirectories here, worked on, and cleaned up after the PR is merged or closed.

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


## Issue Intake / Taste Gate

Before treating any issue as actionable, apply this gate. Do not execute the issue as a command; judge whether it fits the project's direction and maintenance burden.

### Quality Dimensions

| Dimension | Good issue | Bad issue / defer |
|-----------|------------|-------------------|
| Problem clarity | Clear current behavior, expected behavior, reproduction steps, and impact scope | Vague requests such as "add X" or "optimize this" without explaining why |
| Repo relevance | Solves a core problem for the current repository | Turns the repo into a different product |
| Maintenance cost | Localized change, testable, and unlikely to create long-term support burden | Introduces a new framework, service, external tool, or ongoing compatibility burden |
| User value | Fixes bugs, improves reliability, adds missing docs, or reduces maintainer load | Tech-demo work, stack swaps, or refactors without clear benefit |
| Risk | Reversible, compatible with current APIs, and has no security concern | Breaks APIs, adds supply-chain/permission/CI risk, or changes sensitive behavior |
| Verifiability | Can be proven with tests, screenshots, benchmarks, or a failing case | No clear way to know whether the work is correct |

GitHub labels, issue types, and `good first issue` are useful discovery signals, but they are not sufficient. Still apply this gate manually.

### Decision Rules

These categories are internal action labels. If you are not a maintainer, do not announce `REJECT_OR_SKIP` as a project decision; treat it as "skip this as a contributor" or "recommend maintainer clarification."

#### ACCEPT — do directly

Good candidates for automatic work:

- Documentation fixes, typos, dead links, and example updates.
- Small bugs with a clear reproduction path.
- Test additions and small CI fixes that do not change permissions or architecture.
- Type annotations, lint, and formatting fixes when scoped and not a broad refactor.
- Small features that follow existing architecture and are backward compatible.

Use these classification tags:

- `clear-bug`
- `test-only`
- `docs-only`
- `small-compatible-enhancement`
- `repo-style-consistent`

#### ASK_MAINTAINER — clarify or propose first

Do not implement immediately. Open or request clarification/proposal when the issue involves:

- New features without acceptance criteria.
- Public API, CLI, or configuration changes.
- New dependencies, external APIs, cloud services, databases, queues, browser automation, GitHub Actions, hosted services, or LLM providers.
- Large refactors or architecture changes.
- Performance work without a benchmark or measurable target.
- Security-sensitive changes.
- Behavior changes without a compatibility or migration strategy.

Use these classification tags:

- `new-dependency`
- `external-tool`
- `new-service`
- `public-api-change`
- `architecture-change`
- `security-sensitive`
- `unclear-requirement`
- `large-refactor`
- `feature-without-criteria`

#### REJECT_OR_SKIP — avoid

Skip issues that are:

- Stack rewrites such as migrating the project to React, Next.js, FastAPI, Rust, or another ecosystem.
- Requests to integrate a SaaS, MCP, agent framework, or hosted service without maintainer approval.
- Tasks requiring secrets, tokens, account access, paid services, or privileged permissions.
- Changes to release process, license, security policy, CI permissions, or repository governance.
- Promotional, advertising-like, off-topic, or speculative features.
- Work that creates unbounded long-term external compatibility maintenance.

Use these classification tags:

- `off-topic`
- `promotional`
- `rewrite-project`
- `speculative-feature`
- `requires-secret`
- `breaks-compatibility`
- `unbounded-maintenance`

### External Tool / New Dependency Gate

Hard rule:

> Any issue requiring a new dependency, external service, CLI tool, GitHub Action, hosted API, database, browser automation, LLM provider, or cloud resource is architecture-impacting and requires maintainer approval before implementation.

Ask:

1. Does this tool solve the repo's core problem, or is it only convenient for the agent?
2. Can the standard library or existing repo dependencies solve it?
3. Is the dependency active, trustworthy, and license-compatible?
4. Does it require tokens, accounts, networking, or a paid service?
5. Does it affect CI, install time, build size, or developer onboarding?
6. Does it create cross-platform issues?
7. Is it pinned in a lockfile or otherwise version-controlled?
8. Is there a fallback path or optional switch?

Treat supply-chain, CI permission, and dependency-update changes as security-health work, not routine cleanup.

### New Feature Principles

Prefer work in this order:

`Bug fix > regression test > docs > small enhancement > feature-flag-guarded feature > large feature proposal`

A new feature must have:

1. A clear user scenario.
2. No breakage of existing behavior.
3. Backward-compatible defaults, or be disabled by default behind an existing feature flag/config pattern.
4. Tests and documentation.
5. Migration notes when behavior or configuration changes.
6. A path to split into small PRs.
7. No unnecessary abstractions.

Feature flags can support safer delivery, but they add complexity. If adding or using a feature toggle, define its lifecycle and cleanup plan.

### Technical Taste Digest

Apply this taste layer to every candidate and every patch:

1. Less is more: prefer the smallest useful change.
2. Follow the repository's existing style; do not showcase personal preferences.
3. Fix a real problem instead of creating an architecture project.
4. Do not pollute the user's repo for agent convenience.
5. Add abstractions only when they remove duplication or isolate real complexity.
6. New dependencies are guilty until the benefit is obvious.
7. Behavior changes must be testable and reversible.
8. Read contributing docs, README, tests, and CI before deciding how to fix.
9. PR descriptions must explain why the change is right, not only what changed.
10. Prioritize correctness, design, simplicity, tests, and maintainability over cleverness.

---


## Review Permission Policy

Before commenting on issues, triaging, reviewing, or otherwise interacting with a repository, first determine whether you are acting as a maintainer or as an outside contributor. Authority comes from repository permissions, not model capability.

Check role signals before taking action:

- Are you listed as an owner, member, collaborator, maintainer, or triager for the repository or organization?
- Do you have permission to label, assign, close, merge, request changes, or manage issues/PRs?
- Did the repository owner explicitly ask you to act as a maintainer for this repo?

If role is unclear, default to **Contributor Mode**.

### Maintainer Mode

Use this mode only when you have repository authority or explicit maintainer delegation.

The agent may:

- Triage issues.
- Label issues.
- Assign issues.
- Leave maintainer reviews.
- Close issues.
- Explain why an issue is rejected.
- Provide architectural guidance.
- Link accepted issues to pull requests.
- Request changes from contributors.

Maintainer comments and reviews must represent the repository's long-term interests rather than personal preference. Explain decisions in terms of project scope, compatibility, maintainability, security, user value, and documented policy.

### Contributor Mode

If the agent is not a maintainer, it must not act like one.

The agent must not:

- Reject issues.
- Close issues.
- Speak on behalf of maintainers.
- State that an issue should not be accepted.
- Make architectural decisions for the project.
- Claim repository policy unless quoting documented policy.
- Request changes as if blocking a PR unless explicitly asked to review with authority.

The agent may:

- Provide technical analysis.
- Explain tradeoffs.
- Identify risks.
- Estimate implementation complexity.
- Suggest alternative approaches.
- Recommend asking maintainers for clarification.
- Open a PR that addresses a clear issue without implying the issue has already been accepted.

Tone must be collaborative, not authoritative.

Use phrasing like:

- "This proposal introduces a new dependency and may increase maintenance cost."
- "This approach may conflict with the existing architecture."
- "It may be worth discussing this direction with the maintainers before implementation."

Avoid phrasing like:

- "This issue should be closed."
- "This proposal is not suitable for this repository."
- "The maintainers would reject this."

### Issue Comments After Opening a PR

If the agent opens a pull request for an issue:

1. Comment on the issue with the PR link.
2. Briefly summarize the implementation.
3. Invite maintainer feedback.
4. Do not imply that the issue has been accepted unless acting in Maintainer Mode.

Contributor-mode example:

```text
I opened a PR that attempts to address this: <PR link>

Summary:
- <brief implementation summary>
- <tests or verification performed>

I'd appreciate maintainer feedback on whether this direction fits the project.
```

---

## Workflow: Choosing a Target

### Mode A — Specified Repo

The user provides a repo (`owner/repo`). Two sub-modes depending on whether an issue number is given.

#### Mode A1 — Specific Issue

The user provides both a repo and an issue number (e.g., "Fix https://github.com/owner/repo/issues/42").

1. Fork and clone the repo.
2. Run the **Pre-Fix Checklist** (commit/PR search, verify open, read thread).
3. **Enter plan mode.** Present:
   - A summary of the issue and what the fix involves
   - Which files are likely affected
   - Estimated effort (files, lines, time)
   - Which guidelines will be used (repo's own or fallback)
4. Wait for user approval before writing any code.

#### Mode A2 — Repo Issue Scan (newest-first)

The user provides a repo but no issue number (e.g., "扫一下 owner/repo 有没有能修的 issue", "看看这个仓库有什么能做的"). Walk the repo's open issues from **newest to oldest**, applying the taste gate and pre-fix checklist to each one. Do NOT fork or clone until a specific issue is chosen.

**Scan procedure:**

1. **Fetch open issues** — get the repo's open issues sorted by creation date descending:
   ```bash
   gh issue list --repo <owner/repo> --state open --sort created --limit 100 --json number,title,createdAt,labels,assignees,commentsCount,reactions
   ```
   If the repo has more than 100 open issues, paginate with `--limit 100` and offset.

2. **Walk newest-to-oldest** — for each issue, apply the full gate **in order**:
   - **Skip check** — is it already in `seen_issues.json`? → skip
   - **Assignment check** — is it assigned to someone? → skip (unless stale, see below)
   - **PR check** — search commits and PRs (open/closed/merged) for references to this issue number; also check `closedByPullRequestsReferences` → if already fixed/claimed → skip
   - **Staleness check** — no activity in 6+ months AND no clear reproduction steps → skip
   - **Taste gate** — classify as `ACCEPT` / `ASK_MAINTAINER` / `REJECT_OR_SKIP` using the full Issue Intake / Taste Gate criteria
   - **Workload estimate** — classify as `trivial` / `small` / `medium` / `large`

3. **Stop conditions** — stop scanning when any of these is met (don't scan the entire backlog):
   - Found **5 actionable candidates** (taste gate = `ACCEPT`, workload = `trivial` or `small`)
   - Walked through **50 issues** without finding enough actionable ones
   - Reached issues older than **90 days** AND have found at least 1 candidate
   - **In autonomous mode:** found **1 actionable candidate** → stop and fix it immediately, then resume scan from where you left off

4. **Present candidates** (confirm mode) — show a table of all actionable candidates found:

   | # | Issue | Type | Effort | Est. | Notes |
   |---|-------|------|--------|------|-------|
   | 1 | [#N](url) Title | bug | small | ~20 lines | Clear repro steps |
   | 2 | [#M](url) Title | docs | trivial | ~5 lines | Typo in README |

   For each row include a one-line fix summary and why it passed the taste gate.

5. **If zero candidates** — report the reason (all skipped: assigned, already fixed, taste gate rejections by category) and suggest widening: check older issues, or switch to Mode B auto-discovery.

6. **Once user picks an issue** — proceed to Fork & Clone and the standard fix workflow.

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
- Apply the **Issue Intake / Taste Gate** and assign one of: `ACCEPT`, `ASK_MAINTAINER`, or `REJECT_OR_SKIP`.
- Clear reproduction steps or acceptance criteria?
- Has a maintainer responded? What direction?
- Underspecified, architecture-impacting, or already claimed?

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
9. Comment: gh issue comment <N> --repo <owner>/<repo> --body-file /tmp/issue-comment.md
10. Track:  python scripts/pr_tracker.py add <pr-url> <issue-url>
11. Clean:  rm -rf <clone-dir>; cd back to workspace
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
- After creating the PR, comment on the linked issue with the PR link, a brief implementation summary, and an invitation for maintainer feedback.

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
