# disciplined-dev-workflow

`disciplined-dev-workflow` packages a strict coding Definition of Done for
agents: route the task, keep a feedback loop, review the diff, verify the
change, and report residual risk before saying the work is complete.

## What It Coordinates

- `tdd` for feature work, behavior changes, and testable refactors.
- `diagnose` for bugs, regressions, failing tests, flaky behavior, and
  performance problems.
- `code-reviewer` for local or PR review after code changes.

The skill remains usable when companion skills are missing: it includes fallback
workflows for TDD, diagnosis, and post-change review.

## Install

Copy this directory to one of your agent skill folders, for example:

```bash
~/.agents/skills/disciplined-dev-workflow
```

or project-local:

```bash
.agents/skills/disciplined-dev-workflow
```

Restart the agent after installing so the skill appears in the active skill
list.

## Recommended Companion Install

Install `code-reviewer` from the Gemini CLI skills package:

```bash
npx skills add https://github.com/google-gemini/gemini-cli --skill code-reviewer -g -y
```

If `tdd` or `diagnose` are not installed, use this skill's built-in fallback
workflow or install equivalent skills from your organization's trusted skill
source.

## Check Dependencies

```bash
./scripts/check-companion-skills.sh
```

The script prints which companion skills are present and gives install guidance
for missing ones.

## Example Prompts

```text
Use disciplined-dev-workflow to implement this feature.
```

```text
Use disciplined-dev-workflow to diagnose and fix this bug.
```

```text
Before final answer, run the completion gate.
```

