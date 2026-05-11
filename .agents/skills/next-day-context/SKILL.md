---
name: next-day-context
description: Automatically report context usage when available, prepare a compact project-scoped context handoff, and let a fresh session restore that context from a simple user command.
---

# Next-Day Context

Use this skill automatically at the beginning of a new or resumed long-running project session when there is enough prior context to compact. Also use it when the user asks to continue a project in a new session, reduce context bloat, create a handoff summary, asks about context usage or token spend, or asks for "继续", "继续项目", "接着来", "加载上下文", "第二天继续", "总结必要上下文", "清理冗余", "上下文花费", "context usage", "token 用量", "开新会话继续任务", "清除旧会话", "new session", "fresh session", or similar.

## Automatic Trigger

Before answering the user's first substantive request in a new or resumed project session, apply this skill when any of these signals are present:

- The session starts in a project that has prior docs, notes, task files, memory context, or conversation handoff material.
- The conversation has been compacted, resumed, or reopened after a meaningful time gap.
- The user says they are continuing work, returning the next day, picking up where they left off, or wants context cleaned up.
- The user asks about context usage, context spend, token usage, context budget, or whether context should be compacted.
- A user-configured context threshold is known and the current context usage is at or above that threshold.
- The user asks to open a new session, clear the old session, avoid wasting tokens on old context, or restore context from a handoff.
- Local project instructions mention this skill or ask for context handoff behavior.

This trigger is part of the skill itself. Individual projects may add domain-specific preservation rules in `AGENTS.md` or docs, but they do not need to restate the generic trigger.

Keep the automatic pass lightweight. Build only the context needed to answer the user's current request; do not turn every first message into a full repository audit.

## Context Usage Guard

When this skill is active, do not proactively report context status at the start of each substantive response. Mention context usage only when the user asks about it, when context management is directly relevant, or when a compression threshold must be evaluated. If exact usage is unavailable in those cases, say that exact usage is not exposed and provide a short qualitative status based only on observable signals such as recent compaction, visible conversation volume, and whether durable handoff files exist. Do not invent exact token counts or percentages.

User-configured thresholds may come from current user instructions, `AGENTS.md`, `.agents/context-handoff.md`, or another project-local settings file. If no threshold is configured, use this default policy:

- `report`: only mention exact context usage when the user asks, when context management is directly relevant, or when a compression threshold must be evaluated.
- `warn`: warn when usage appears high or exact usage is unavailable but the visible conversation is clearly large.
- `compact`: automatically run this skill's compression workflow when exact usage is available and is at or above 80% of the context window, or when the user explicitly asks to reduce context bloat.
- `fresh_session`: after compaction, the old session should provide a short restore command for a new session. In the new session, that command should make the agent read `.agents/context-handoff.md` and continue from it.

When usage meets or exceeds the configured compact threshold:

1. State the observed usage or clearly state that only qualitative status is available.
2. Run the compression workflow before taking on new non-urgent work.
3. Persist or update `.agents/context-handoff.md` when the compacted context will be useful for future turns.
4. Prefer a fresh-session restore command so old context stops consuming tokens.
5. Continue answering the user's current request using the compacted handoff only if the user chooses to stay in the current session.

If exact usage is unavailable, do not claim that a numeric threshold has been crossed. Instead, compact automatically only when the user requested compaction, the conversation has been compacted/resumed, the session is clearly long-running, or project instructions explicitly require a handoff.

## Fresh Session Restore

The preferred way to reclaim context-window tokens is to start a fresh session and send one short restore command. The new session should use that command to load `.agents/context-handoff.md` as the compact source of truth, instead of requiring the user to paste a long summary.

When preparing to leave an old session:

1. Update `.agents/context-handoff.md` with only durable project state, artifact trail, constraints, and next step.
2. Tell the user to open a new session in the same project root.
3. Give the shortest useful restore command.
4. Do not require the user to paste the full handoff unless file access is unavailable.
5. Do not claim that old context has been cleared until the user is actually in a new session or the platform performs compaction.

Recommended restore command:

```text
继续
```

In a fresh session, when the user says `继续`, `继续项目`, `接着来`, or `加载上下文`, read `AGENTS.md` and `.agents/context-handoff.md` from the current project root, summarize the loaded state in 3-6 bullets, and continue from `Next Step`.

## Goal

Produce a compact, project-scoped handoff that lets the next agent continue work without rereading the full conversation. Keep only context that affects future decisions or execution for the current project.

The skill must be portable across projects. Never carry product facts, file paths, goals, or decisions from one project into another unless they are present in the current project files, current conversation, or explicit user instructions.

## Workflow

1. Identify the current project root from the working directory and local project instructions.
2. Report exact context usage if exposed by the platform. If not exposed, state that briefly when the user asked about usage or when context management is relevant.
3. Read only the local context needed to understand the project: `AGENTS.md`, `README.md`, relevant docs, recent notes, task files, and current conversation. Do not import context from unrelated projects.
4. Check for an existing project handoff at `.agents/context-handoff.md` unless local instructions name a different file.
5. Separate durable context from conversation noise.
6. Build or update a project-scoped handoff. Prefer anchored iterative summarization: keep the existing durable summary if one is present, summarize only newly relevant context, then merge without regenerating everything from scratch.
7. Summarize current state, decisions, running services, key files, and next recommended work.
8. Persist the updated handoff to `.agents/context-handoff.md` when the user asks to prepare future context, when a meaningful handoff does not yet exist, when a configured context compact threshold is exceeded, when a fresh-session handoff is needed, or when the current work materially changes project state. If the user only asked a small question and no threshold was exceeded, an in-chat lightweight handoff is enough.
9. When compaction is meant to reduce token waste, follow the Fresh Session Restore protocol so future work can run without the old conversation context.
10. Preserve user preferences only when they are explicitly stated for the current project or clearly global working preferences. Mark global preferences as such.
11. Remove transient teaching turns, repeated confirmations, dead-end ideas, obsolete implementation details, raw logs, and secrets unless they explain a current decision.
12. If the user asks for a Skill, create or update a `SKILL.md` with this workflow instead of only writing a one-off summary.

## Project Scope Rules

- Treat each project root as a separate memory boundary.
- Project-specific context belongs in that project's `AGENTS.md`, docs, notes, or handoff summary, not in this general skill.
- If a repository has no clear product direction yet, say that it is unknown instead of borrowing one from another project.
- If multiple projects appear in the conversation, create separate handoff sections by absolute project path.
- Prefer local evidence over memory. When project files disagree with older conversation context, call out the conflict and keep the newer or better-supported source.

## Persistent Handoff File

By default, use `.agents/context-handoff.md` under the current project root as the durable project handoff.

Create or update it when:

- The user asks to continue tomorrow, open a new session, clean up context, or prepare a handoff.
- A new or resumed project session has useful durable context but no handoff file yet.
- Work has materially changed the project state: new features, changed architecture, important decisions, service/config changes, known failures, or next steps.
- Every substantive project conversation creates, changes, verifies, rejects, or clarifies a task.
  In that case, update the handoff before the final response so a next-day session can resume from
  the latest task state without depending on hidden chat history.

For task updates, record the active task, current status, decisions, files created/modified/read,
verification results, blockers, and the next recommended step. Keep this as an incremental merge:
append or revise only the durable task facts instead of rewriting the whole handoff.

Do not update it for tiny one-off answers that do not change future work. Do not store secrets. If `.agents/` does not exist and a handoff should be persisted, create it.

If the project already has a local convention such as `CONTEXT.md`, `docs/context.md`, `docs/adr/`, or another handoff file, follow that convention and mention the path used.

## Source Priority

When sources conflict, prefer them in this order:

1. Current explicit user instruction.
2. Current code, config, tests, and files in the project root.
3. Project-local instructions such as `AGENTS.md`.
4. Current project docs, ADRs, task files, and handoff files.
5. Recent conversation context for this project.
6. Older summaries or memory context.

If the conflict affects the next action, state the conflict briefly instead of silently merging incompatible facts.

## Compression Budget

Keep the handoff compact by default:

- Target 250-500 words for an active long-running project.
- Use up to 700 words only when several active threads would otherwise become ambiguous.
- Use a longer archive only when the user explicitly asks for a fuller record.
- Keep `Next Step` to one clear recommendation unless there are true blockers.
- Prefer bullets with exact identifiers over paragraphs of background.
- Drop older background before dropping current state, modified files, constraints, or next steps.
- Replace stale handoff facts by default. Do not append a running chat log.
- Keep only the latest 1-3 durable updates in `Recent Change`; move older completed work to source docs, ADRs, task files, or code references.
- Treat the handoff as a routing index plus current state, not the detail store.
  Store fine-grained implementation notes, decisions, and task history in named
  docs with clear section anchors, then read those docs only when the active task
  needs them.
- Keep the artifact trail to files touched/read in the latest substantive turn plus essential entry points. Do not accumulate every file ever touched.

When the handoff is still too long, preserve information in this priority order:

1. Current user goal and active task.
2. Current project state and known failures.
3. Files created or modified, with exact paths.
4. Decisions, constraints, non-goals, and source-of-truth rules.
5. Running services, commands, local URLs, and config assumptions.
6. Next step and blocking questions.
7. Older background and rationale.

## Compression Method

Use a lightweight structured compression pass:

1. Extract: collect only facts that can change future execution.
2. Classify: group facts into goal, state, decisions, artifact trail, constraints, and next step.
3. Deduplicate: merge repeated facts and remove superseded options.
4. Anchor: preserve exact file paths, function/class names, commands, errors, URLs, and issue IDs.
5. Merge: update the existing handoff incrementally instead of replacing stable context wholesale.
6. Verify: run the compression quality check below.

## What To Keep

Keep:

- Project path, runtime environment, active services, and important local URLs.
- User's current objective and any explicitly relevant long-term objective.
- Product positioning and major design decisions.
- Implemented features and their key files.
- Files read but not changed when they affect future work.
- Files created or modified, with what changed at the module/function level when known.
- Current task progress from the latest substantive conversation, including completed, superseded,
  blocked, or newly discovered tasks.
- Specific identifiers that future work may need: function names, class names, config keys, commands, error messages, issue IDs, and local URLs.
- Current configuration assumptions, without exposing secrets.
- Current known constraints, non-goals, and "do not do" items.
- Recommended next step and why.
- Any pending question that blocks implementation.

## What To Remove

Remove:

- Repeated "OK", "yes", and confirmation turns.
- Long line-by-line teaching content unless a concept is needed later.
- Full command outputs unless they reveal current state.
- Old options that were rejected.
- Implementation details that have been superseded.
- Secret values such as API keys, bot tokens, passwords, or private URLs.
- Product facts, goals, or decisions from other projects.
- Tool schemas, command specifications, or API contracts rewritten in lossy prose when exact names are needed.

## Output Shape

Use concise headings:

```markdown
**User Goal**
...

**Project State**
...

**Product Decisions**
...

**Implemented / Changed**
...

**Important Files**
...

**Artifact Trail**
- Created:
- Modified:
- Read Only:

**Constraints / Preferences**
...

**Do Not Lose**
...

**Next Step**
...
```

Omit empty sections when they add no value, except keep `Next Step` whenever work is expected to continue.

## Quality Bar

The handoff should be:

- Short enough to paste at the start of a new session.
- Specific enough that the next agent can act immediately.
- Free of secrets.
- Clear about what is current versus superseded.
- Written in the user's language unless they ask otherwise.
- Project-scoped: no unrelated product direction, file path, or decision should leak in.
- Verifiable: preserve exact identifiers instead of paraphrasing them away.

## Compression Quality Check

Before considering the handoff complete, ask whether it can answer these probes:

- What is the user trying to accomplish in this project?
- Which files were created, modified, or read-only because they matter?
- What decisions or constraints must future agents preserve?
- What is the current state, including tests, services, or known failures?
- What is the single best next step?

If an answer is missing but the information exists in the current context, update the handoff. If the information is genuinely unknown, say so directly.

## Installing In A Project

For project-specific defaults, add them to the project's `AGENTS.md` or docs. This skill should stay generic; the project files should say what makes that project special.
