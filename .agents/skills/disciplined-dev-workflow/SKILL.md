---
name: disciplined-dev-workflow
description: Orchestrates feature work, bug diagnosis, code review, and verification into a mandatory completion gate. Use when writing or changing code, fixing bugs, refactoring, reviewing local changes, or when the user asks for a disciplined workflow, completion gate, TDD, diagnosis, testing, or post-change self-review.
---

# Disciplined Dev Workflow

## Quick Start

Before changing code, classify the task. After changing code, do not finish
until the completion gate is satisfied.

```text
Route -> Implement with feedback -> Review diff -> Verify -> Report
```

## Companion Skills

Use companion skills when they are installed:

- `tdd` for feature work, behavior changes, testable refactors, and bug fixes
  with a useful test seam.
- `diagnose` for bugs, exceptions, failing tests, regressions,
  nondeterministic behavior, and performance problems.
- `code-reviewer` for local diff or PR review after code changes.

If a companion skill is unavailable, follow the equivalent workflow described
here instead of skipping the step. If the user wants installation help, run
`scripts/check-companion-skills.sh` and install missing skills where a source is
known.

## Task Routing

1. Feature, behavior change, or refactor with observable behavior:
   use `tdd` or this fallback:
   - Name the public behavior to protect.
   - Add one focused behavior test or executable check.
   - Implement the smallest useful slice.
   - Repeat in vertical slices; avoid writing all tests first.
2. Bug, regression, flaky behavior, exception, or performance issue:
   use `diagnose` or this fallback:
   - Build a fast pass/fail feedback loop.
   - Reproduce the reported symptom.
   - Minimize the case.
   - List falsifiable hypotheses.
   - Instrument one variable at a time.
   - Fix and rerun the original loop plus regression check.
3. Small config, docs, or mechanical edits:
   use the lightest verification that can catch the likely failure.

## Completion Gate

After any code change and before the final response:

1. Inspect the diff for correctness, regressions, edge cases, secrets,
   unnecessary churn, local style, and missing tests.
2. Use `code-reviewer` if available; otherwise perform the same local review
   manually against the changed files.
3. Run the narrowest useful verification:
   - targeted unit or integration tests,
   - compile/import check such as `py_compile`,
   - lint/typecheck,
   - HTTP smoke test,
   - browser/manual check for UI,
   - reproduction loop for diagnosed bugs.
4. If verification cannot run, state the exact blocker and residual risk.
5. Do not call the task done unless review and verification are reported.

## Final Response Contract

For every substantive code task, include:

- Changed files.
- Review result, including notable risks found or ruled out.
- Verification command(s) and result(s), or why they could not run.
- Remaining blocker or next recommended step, if any.

## Dependency Check

From the skill directory:

```bash
./scripts/check-companion-skills.sh
```

The script only checks local availability and prints install guidance. It does
not install anything without the user taking action.
