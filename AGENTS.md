<claude-mem-context>
# Memory Context

# [agent-demo] recent context, 2026-05-28 8:58pm GMT+8

No previous sessions found.
</claude-mem-context>

<next-day-context-default>
The generic automatic trigger for `next-day-context` lives in the skill itself.
For this project, when that skill runs:

1. Build a compact handoff from available project files, docs, and current
   conversation context.
2. Keep only durable context needed to continue the task: user goal, product
   decisions, implemented features, important files, current services/config,
   constraints, and the next recommended step.
3. Track the artifact trail separately: files created, files modified, and
   important files read without changes.
4. Remove repeated confirmations, teaching chatter, obsolete options, raw logs,
   secrets, and context from unrelated projects.
5. Use the compact context to answer the user's request. Do not make the user
   manually ask for context cleanup.
6. Do not proactively report context usage at the start of each substantive
   response. Only mention usage when the user asks about it, when context
   management is directly relevant, or when a compression threshold must be
   evaluated. If exact usage is unavailable, say so briefly instead of
   inventing a number.
7. Automatically run the skill's compression workflow when exact context usage
   reaches the user's configured threshold. For this project, use 80% as the
   default threshold unless the user sets a different value.
8. After every substantive project conversation that creates, changes,
   verifies, rejects, or clarifies a task, update `.agents/context-handoff.md`
   before finishing the turn. Record the current task state, decisions,
   changed/read files, verification results, blockers, and the next recommended
   step. Tiny one-off answers that do not affect future work can skip this.
9. Keep long-project handoffs aggressively concise:
   - Target 250-500 words; hard cap 700 words unless the user explicitly asks
     for a fuller archive.
   - Preserve only the current objective, current state, active constraints,
     latest meaningful change, exact files/commands needed next, blockers, and
     one next step.
   - Collapse completed historical slices into references to their source docs
     instead of restating them. Prefer `docs/pet-agent-tasks.md` and code as
     the archive for old implementation detail.
   - Treat `.agents/context-handoff.md` as a routing index plus current state,
     not the detail store. Put fine-grained implementation notes, decisions, and
     task history in named docs with clear section anchors, then read those docs
     only when the current task needs them.
   - Keep an artifact trail only for files that are newly changed/read in the
     latest substantive turn or are essential entry points. Do not accumulate a
     full session log in the handoff.
   - Replace stale details instead of appending by default. Use a short
     "Recent Change" section only for the latest 1-3 durable updates.
10. When compression is meant to save tokens, prefer a simple fresh-session
   restore: update `.agents/context-handoff.md`; in a new session, the user can
   type `继续`, `继续项目`, `接着来`, or `加载上下文` and the agent should read
   `AGENTS.md` plus `.agents/context-handoff.md` before continuing.

Project-specific facts must come from this repository's files and current
conversation, not from the generic skill. If this repository's direction changes,
use the latest local docs or user instructions as the source of truth.
</next-day-context-default>

<codex-development-workflow>
# Mandatory Development Workflow

For this project, Codex must not treat code writing as complete until review
and verification have been performed or explicitly reported as blocked.
Use the project-local `disciplined-dev-workflow` skill when available; it
packages the routing, review, verification, and final reporting contract below.

## Skill Routing

1. Use `tdd` for feature work, behavior changes, refactors with observable
   behavior, and bug fixes where a useful test seam exists.
   - Work in vertical slices: one behavior test, minimal implementation, then
     repeat.
   - Prefer integration-style tests through public interfaces over tests of
     private implementation details.
2. Use `diagnose` for bugs, exceptions, failing tests, regressions,
   nondeterministic behavior, or performance problems.
   - Build or identify a pass/fail feedback loop before hypothesizing.
   - Reproduce first, then minimize, hypothesize, instrument, fix, and
     regression-test.
3. Use an installed code-review skill, preferably `code-reviewer`, after code
   changes. If no external code-review skill is available in the current
   session, perform the same review manually.

## Completion Gate

After any code change, before the final response:

1. Inspect the diff for correctness, regressions, edge cases, secrets,
   unnecessary churn, consistency with local patterns, and missing tests.
2. Run the narrowest useful verification available for the change, such as
   targeted tests, `py_compile`, lint, typecheck, an HTTP smoke test, or a
   focused manual/browser check.
3. If verification cannot be run, state the exact blocker and residual risk.
4. Do not present the task as done unless the review and verification result
   has been reported.

## Final Response Contract

For every substantive code task, the final response must include:

- Changed files.
- Self-review result, including any notable risk found or ruled out.
- Verification command(s) and result(s), or why they could not run.
- Remaining blocker or next recommended step, if any.
</codex-development-workflow>
