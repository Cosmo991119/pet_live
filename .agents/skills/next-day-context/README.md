# next-day-context

## Quick Start / 快速使用

English: Install this skill as `next-day-context` in your agent skills folder or
inside a project's `.agents/skills/` directory. In a long-running project, ask
the agent to use it when you say `continue`, `new session`, `context usage`, or
similar. The skill reads local project instructions and writes a compact,
secret-free handoff to `.agents/context-handoff.md`. In a fresh session, type
`继续` or `load context`; the agent should read `AGENTS.md` plus the handoff,
summarize the restored state, and continue from `Next Step`.

中文：把本技能安装为 `next-day-context`，可放在全局 skills 目录或项目的
`.agents/skills/` 下。长项目里，当你说 `继续`、`加载上下文`、`上下文用量`
或类似请求时，技能会读取项目说明，并把必要上下文压缩到
`.agents/context-handoff.md`，不保存密钥。新会话中输入 `继续`，代理应读取
`AGENTS.md` 和 handoff，简要恢复状态，然后从 `Next Step` 接着做。每次实质任务
变更后也应更新 handoff。

`next-day-context` is a Codex/agent skill for monitoring context usage when the
runtime exposes it, preparing compact project handoffs, and restoring that
context in a fresh session from a short user command.

It is designed for projects where the user returns the next day and expects the
agent to automatically compress context before doing new work. The skill is
project-scoped: each repository should get its own handoff, and facts from one
project must not leak into another.

## What It Does

- Summarizes only durable project context.
- Removes repeated confirmations, teaching chatter, obsolete options, raw logs,
  and secrets.
- Preserves product decisions, implemented features, key files, constraints,
  running services, and the next recommended task.
- Tracks the artifact trail: files created, files modified, and important files
  read without changes.
- Uses anchored incremental summaries: keep durable context, merge only newly
  relevant context, and avoid regenerating everything from scratch.
- Persists durable handoffs by default at `.agents/context-handoff.md`, unless a
  project has its own convention.
- Defines source priority and compression budget rules so summaries stay useful
  as projects grow.
- Reports exact context usage only when asked, when context management is
  directly relevant, or when a compression threshold must be evaluated. It
  clearly says when exact usage is unavailable instead of inventing token
  counts.
- Automatically runs the compression workflow when a configured context
  threshold is exceeded, or by default when exact usage reaches 80% of the
  available context window.
- Writes a compact handoff so a fresh session can restore context from a short
  command such as `继续`.
- Updates the handoff after every substantive project conversation that creates,
  changes, verifies, rejects, or clarifies a task, so next-day sessions can
  resume from the latest task state.

## When To Use

Use it when starting or resuming a long project session, especially when the
conversation has become too long or noisy. Also use it when the user asks about
context spend, context usage, token usage, context budget, or whether the
conversation should be compacted, reset, cleared, or continued in a new session.
In a fresh session, simple commands such as `继续`, `继续项目`, `接着来`, or
`加载上下文` should trigger the skill to read `.agents/context-handoff.md`.

The generic trigger lives in the skill itself: before the first substantive
request in a new or resumed project session, the agent should do a lightweight
context handoff pass when prior docs, notes, memory context, task files, or
handoff material exist.

When a context usage value is available, the agent should not report it by
default. It should mention usage only when the user asks, when context
management is directly relevant, or when a compression threshold must be
evaluated. If a user-configured threshold is known, compact when usage meets or
exceeds that threshold. If no threshold is configured, the default compact
threshold is 80%. If exact usage is not exposed by the runtime, the agent should
say so only when usage needs to be discussed and use qualitative signals only;
it must not invent a numeric usage value.

To actually stop paying for old context, the preferred path is simple:
update `.agents/context-handoff.md`, open a fresh session in the same project,
and type `继续`. The new session should read `AGENTS.md` plus
`.agents/context-handoff.md`, summarize the restored state briefly, and continue
from `Next Step`.

Example prompt:

```text
使用 next-day-context，接上昨天的项目，先压缩必要上下文再继续。
```

In a project, `AGENTS.md` should only add domain-specific preservation rules.
Put project-specific product facts in that project's `AGENTS.md` or docs, not
in the general skill.

## Default Handoff File

When durable context should be saved, use:

```text
.agents/context-handoff.md
```

The file is created or updated when the user asks to continue later, when a
new/resumed session has useful context but no handoff exists, when work
materially changes the project state, or after any substantive task conversation
that changes what a future session needs to know. Tiny one-off questions do not
need a file update.

If a project already uses `CONTEXT.md`, `docs/context.md`, ADRs, or another
local convention, follow that instead.

## Compression Strategy

The handoff should usually stay around 400-900 words. Preserve current goal,
current state, changed files, decisions, constraints, commands, and next steps
before older background. Keep exact paths, function names, config keys, errors,
and URLs whenever future work may need them.

## Files

```text
next-day-context/
├── README.md
└── SKILL.md
```

## Safety

The skill explicitly avoids carrying secrets such as API keys, bot tokens,
passwords, and private credentials into the handoff summary.

It also avoids cross-project contamination: when the current repository has no
clear product direction yet, the handoff should say it is unknown instead of
borrowing a direction from another project.
