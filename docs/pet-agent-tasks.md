# Pet Agent Task Group

This task group breaks `docs/pet-agent-prd.md` into small vertical slices. Each slice should leave the project in a demoable or verifiable state.

## Slice 1: SQLite Fact Store

Type: AFK

Blocked by: None

What to build:

Create the local SQLite schema for pets, raw events, behavior sessions, sleep sessions, event messages, summaries, and anomalies. Add a small initialization function that can create the database from scratch.

Acceptance criteria:

- [x] Running the database module creates `pet_agent.db`.
- [x] All PRD tables exist.
- [x] The schema uses foreign keys where relationships are clear.
- [x] The implementation uses Python standard library `sqlite3`.

## Slice 2: Pet Setup Path

Type: AFK

Blocked by: Slice 1

What to build:

Add functions to create and list pets, including `name`, `species`, `personality`, `owner_call_name`, and optional `profile_json`.

Acceptance criteria:

- [x] A default pet can be created from code.
- [x] Multiple pets can exist in the database.
- [x] Pet personality is limited to the first version preset list.
- [x] Pet records can be queried for later event handling.

## Slice 3: Raw Event Ingestion

Type: AFK

Blocked by: Slice 1, Slice 2

What to build:

Add a function to accept a structured behavior event, validate it, and store it in `events`.

Acceptance criteria:

- [x] Supports `eat`, `drink`, `poop`, `sleep_start`, and `sleep_end`.
- [x] Stores `raw_payload`.
- [x] Applies the `confidence >= 0.7` rule.
- [x] Low-confidence events are stored but do not trigger message generation.

## Slice 4: Behavior Session Aggregation

Type: AFK

Blocked by: Slice 3

What to build:

Aggregate `eat`, `drink`, and `poop` raw events into behavior sessions using per-behavior time windows.

Acceptance criteria:

- [x] New events create a session when no active session exists.
- [x] Events inside the session window update the existing session.
- [x] `raw_event_count`, `start_time`, and `end_time` are tracked.
- [x] Statistics count sessions, not raw repeated events.

## Slice 5: Sleep Session State Machine

Type: AFK

Blocked by: Slice 3

What to build:

Handle `sleep_start` and `sleep_end` using rule-based state logic.

Acceptance criteria:

- [x] A valid start/end pair creates a completed sleep session.
- [x] Duplicate `sleep_start` records an anomaly.
- [x] Orphan `sleep_end` records an anomaly.
- [x] Sleep duration is calculated in minutes.

## Slice 6: Stats API

Type: AFK

Blocked by: Slice 4, Slice 5

What to build:

Add daily, weekly, and monthly stats queries that return JSON-ready dictionaries.

Acceptance criteria:

- [x] Stats include eat, drink, poop session counts.
- [x] Stats include sleep minutes.
- [x] Supports `day`, `week`, and `month` ranges.
- [x] Does not require LLM calls.
- [x] Exposes `GET /pets/{pet_id}/stats` over HTTP.

## Slice 7: Event Message Agent

Type: AFK

Blocked by: Slice 4, Slice 6

What to build:

Generate structured pet-style event messages using current session, today stats, historical baseline, pet personality, and owner call name.

Acceptance criteria:

- [x] LLM returns `message`, `severity`, `facts_used`, and `internal_signal`.
- [x] Message output defaults to pet-like wording and avoids direct numbers.
- [x] Output is saved in `event_messages`.
- [x] A fallback template returns the same structure if the LLM fails.

## Slice 8: Console Notification

Type: AFK

Blocked by: Slice 7

What to build:

Add a notifier interface and `ConsoleNotifier` implementation.

Acceptance criteria:

- [x] Event messages are printed to the command line.
- [x] Notification logic is separate from message generation.
- [x] Telegram can be added later without rewriting event handling.

## Slice 9: FastAPI Event Endpoint

Type: AFK

Blocked by: Slice 3, Slice 4, Slice 5, Slice 7, Slice 8

What to build:

Add `api.py` with `POST /events` for real-time event ingestion.

Acceptance criteria:

- [x] Endpoint accepts structured event JSON.
- [x] Endpoint stores the event and updates sessions.
- [x] Endpoint returns event id, session id when applicable, and message result.
- [x] Low-confidence events return a clear no-notification reason.

## Slice 10: Summary Agent

Type: AFK

Blocked by: Slice 6

What to build:

Generate structured daily, weekly, and monthly summaries from aggregated stats.

Acceptance criteria:

- [x] LLM receives aggregated stats, not raw events.
- [x] Returns `summary`, `alerts`, and `suggestions`.
- [x] Output is saved in `summaries`.
- [x] Medical diagnosis and treatment advice are forbidden.

## Slice 11: Minimal Chart View

Type: AFK

Blocked by: Slice 6

What to build:

Add a minimal chart view or static frontend that consumes the stats API.

Acceptance criteria:

- [x] Shows eat, drink, poop, play, and sleep totals.
- [x] Works with one focused pet.
- [x] Uses backend stats rather than recomputing in the browser.
- [x] Shows virtual pet state and owner action controls.

## Slice 12: Telegram Notification

Type: HITL

Blocked by: Slice 8, Slice 9

What to build:

Replace or extend `ConsoleNotifier` with `TelegramNotifier`.

Acceptance criteria:

- [x] Telegram bot token and chat id are configured outside code.
- [x] Real-time event messages can be sent to Telegram.
- [x] Console mode remains available for local debugging.

Implementation notes:

- `TelegramNotifier` sends generated pet messages through Telegram Bot API.
- `PET_AGENT_NOTIFIER=telegram` switches API event notifications from console to Telegram.
- `telegram_bot.py` is a separate polling process for interactive commands such as `/set`.
- `.env.example` documents the local configuration keys.

## Slice 13: Data Growth Optimization

Type: AFK

Blocked by: Slice 6, Slice 10

What to build:

Add database growth controls after the main behavior and summary flows are working. This is intentionally postponed from V1 so the first implementation can teach raw events, sessions, and direct stats queries clearly.

Acceptance criteria:

- [x] Define raw event retention rules.
- [x] Add an archive or cleanup strategy for old raw events.
- [x] Add a `daily_stats` pre-aggregation table if stats queries become expensive.
- [x] Document the future migration path from local SQLite to server PostgreSQL.

Implementation notes:

- Raw event retention is documented in `docs/pet-agent-data-growth.md`.
- `pet_db.archive_raw_events_before(...)` archives old unreferenced raw events
  into `archived_events` before deleting them from `events`.
- `daily_stats` is intentionally deferred because current stats read from
  session tables over day/week/month windows; the document defines when to add it
  and the expected table shape.
- The SQLite-to-PostgreSQL migration path is documented.

## Recommended Build Order

1. SQLite Fact Store
2. Pet Setup Path
3. Raw Event Ingestion
4. Behavior Session Aggregation
5. Sleep Session State Machine
6. Stats API
7. Event Message Agent
8. Console Notification
9. FastAPI Event Endpoint
10. Summary Agent
11. Minimal Chart View
12. Telegram Notification
13. Data Growth Optimization

## Slice 14: Virtual Pet Simulator V1

Type: AFK

Blocked by: Slice 9

What to build:

Add a local virtual pet simulator for pets with `pet_mode = virtual`. The simulator should maintain internal state and generate structured events from rules, probabilities, personality, time rhythm, and owner actions.

Acceptance criteria:

- [x] Virtual pets have state values for hunger, thirst, energy, mood, cleanliness, and affection.
- [x] Supports owner actions such as feed, refill, play, clean, pet, and lullaby.
- [x] Adds `play` as a supported virtual behavior.
- [x] Generates structured events without relying on the LLM for random simulation.
- [x] Can run locally before being wired to HTTP.

## Slice 15: Virtual Pet State Persistence + Actions API

Type: AFK

Blocked by: Slice 14

What to build:

Persist virtual pet state in SQLite and expose API/service functions for ticking time forward and applying owner actions.

Acceptance criteria:

- [x] Adds `virtual_pet_states` storage.
- [x] Restores simulator state across requests.
- [x] Supports `GET /virtual-pets/{pet_id}`.
- [x] Supports `POST /virtual-pets/{pet_id}/tick`.
- [x] Supports `POST /virtual-pets/{pet_id}/actions`.
- [x] Generated virtual events are passed into the existing event processing flow.

## Slice 16: Virtual Pet Interaction Simulator

Type: AFK

Blocked by: Slice 15

What to build:

Add a client-side demo script that simulates owner interactions with the virtual pet through HTTP.

Acceptance criteria:

- [x] Adds `simulate_virtual_pet.py`.
- [x] Calls virtual pet status, action, and tick endpoints through HTTP.
- [x] Demonstrates owner actions such as pet, play, feed, and lullaby.
- [x] Keeps this separate from `simulate_events.py`, which represents real device events.

## Slice 17: Pet Profile Update API for Telegram `/set`

Type: AFK

Blocked by: Slice 2, Slice 9

What to build:

Add the backend profile update path that future Telegram `/set` commands will call.
This keeps Telegram command parsing separate from the core pet profile write logic.

Acceptance criteria:

- [x] Adds a reusable `update_pet` database helper.
- [x] Supports partial updates for name, species, personality, owner call name, pet mode, and profile JSON.
- [x] Validates enum fields before writing to SQLite.
- [x] Exposes `PATCH /pets/{pet_id}`.
- [x] Keeps `/set` as a command design target without coupling the database layer to Telegram.

## Slice 18: Telegram Bot `/set` Command V1

Type: HITL

Blocked by: Slice 12, Slice 17

What to build:

Add a minimal Telegram polling bot that receives commands and calls the local FastAPI backend.

Acceptance criteria:

- [x] Adds `telegram_bot.py` as a separate process.
- [x] Supports `/start`.
- [x] Supports `/pets`.
- [x] Supports `/set name`, `/set personality`, `/set owner_call`, `/set mode`, and `/set species`.
- [x] Keeps `/set avatar` as a placeholder for the image customization agent.
- [x] Uses `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PET_AGENT_API_URL`, and `PET_AGENT_DEFAULT_PET_ID` from environment variables.

Status:

Superseded by Slice 21 and Slice 22. The backend profile update API remains, but daily Telegram usage moved from `/set` text commands to button-driven settings.

## Slice 19: Event-Triggered Telegram Push V1

Type: HITL

Blocked by: Slice 7, Slice 8, Slice 12

What to build:

When structured pet events enter the backend, push a pet-like Telegram message only when the event opens a new behavior session. Repeated raw events inside the same short session should update the database without spamming the owner.

Acceptance criteria:

- [x] FastAPI event ingestion reads notifier configuration from `.env`.
- [x] `PET_AGENT_NOTIFIER=telegram` sends generated event messages to Telegram.
- [x] New behavior sessions trigger one Telegram push.
- [x] Repeated behavior events inside the same session are recorded but do not push again.
- [x] Notification delivery failure does not roll back event/session storage.
- [x] API responses expose whether a notification was sent or suppressed.

## Slice 20: Telegram `/status` Command V1

Type: HITL

Blocked by: Slice 15, Slice 18

What to build:

Add a read-only Telegram command that summarizes the default virtual pet's current state and today's behavior stats.

Acceptance criteria:

- [x] Adds a reusable status formatting service outside Telegram-specific code.
- [x] `/status` reads the default pet id from environment configuration.
- [x] `/status` combines virtual pet snapshot data with daily stats.
- [x] `/status` replies in Telegram with a compact pet status message.
- [x] Non-virtual pets get a clear unsupported-state response.

Status:

Superseded by Slice 22 for daily Telegram usage. The status formatting service remains and is now triggered by the persistent "查看状态" button.

## Slice 21: Telegram Button Menu V1

Type: HITL

Blocked by: Slice 18, Slice 20

What to build:

Replace command-first usage with Telegram inline keyboards for common actions and pet settings.

Acceptance criteria:

- [x] `/start` shows the button-first interface.
- [x] Main menu includes status, pet list, settings, avatar, and interaction placeholders.
- [x] Settings menu includes name, owner call name, personality, mode, species, and avatar options.
- [x] Free-text settings use a pending input flow after the user taps a button.
- [x] Preset settings update the default pet directly through the existing profile API.
- [x] Old text command paths were removed after the persistent keyboard became the primary interface.

## Slice 22: Telegram Persistent Keyboard V1

Type: HITL

Blocked by: Slice 21

What to build:

Make the Telegram interface button-first by showing a persistent keyboard in the chat input area, instead of requiring users to remember `/start`, `/menu`, or other slash commands.

Acceptance criteria:

- [x] Adds a persistent reply keyboard for core actions.
- [x] Chinese button labels trigger the product handlers directly.
- [x] `/start` remains only as Telegram's first-open bootstrap entry point.
- [x] Bot command suggestions are cleared with `deleteMyCommands`.
- [x] Settings continue to use the existing settings menu and pending text flow.

## Slice 23: Telegram Virtual Pet Actions V1

Type: HITL

Blocked by: Slice 15, Slice 22

What to build:

Connect the persistent Telegram action buttons to the existing virtual pet action API.

Acceptance criteria:

- [x] "喂饭" calls `feed`.
- [x] "加水" calls `refill`.
- [x] "陪玩" calls `play`.
- [x] "摸摸" calls `pet`.
- [x] "清洁" calls `clean`.
- [x] "哄睡" calls `lullaby`.
- [x] Telegram replies with action completion and the latest status.
- [x] Actions continue to use `POST /virtual-pets/{pet_id}/actions`.

## Slice 24: Pet-Like Action Replies V1

Type: HITL

Blocked by: Slice 23

What to build:

Replace numeric status-bar replies after owner actions with short pet-like responses that preserve personality.

Acceptance criteria:

- [x] Action buttons no longer reply with full status bars by default.
- [x] Replies vary by action.
- [x] Replies vary by pet personality.
- [x] Existing event-generated messages are reused when an action emits an event.
- [x] The detailed status view remains available through the "查看状态" button.

## Slice 25: Desktop Pet Shell V1

Type: AFK

Blocked by: Slice 15, Slice 24

What to build:

Turn the local web console into the first desktop pet product shell. The page
should make the pet visibly present, connect owner actions to existing virtual
pet APIs, treat custom character images as persistent pet identity, show recent
shared moments, and expose a small work-helper entry point.

Acceptance criteria:

- [x] The first screen shows a visible pet stage rather than a plain dashboard.
- [x] The pet has lightweight idle movement and state-driven positioning/copy.
- [x] Existing virtual pet actions still call `/virtual-pets/{pet_id}/actions`.
- [x] Confirmed/generated character images can be attached to the selected pet
  profile and reused as the stage avatar.
- [x] Recent actions and generated moments appear in a local companionship memory
  panel.
- [x] A first work-helper entry point supports text summarization and todo
  extraction through a structured backend endpoint.
- [x] Stats and image customization remain available without becoming the main
  product surface.

Implementation notes:

- `static/index.html` is now the Desktop Pet Shell V1 surface.
- `pet_work_assistant.py` implements deterministic local helper actions.
- `POST /assistant/text` exposes the work-helper endpoint.
- Memory V1 uses browser `localStorage`; persistent cross-device memory should
  become a later slice.

## Slice 26: Floating Desktop Pet V1

Type: HITL

Blocked by: Slice 25

What to build:

Add the QQ-pet-style runtime surface: a separate floating desktop pet process.
The web UI remains the management/customization page, but the pet itself should
appear as a small always-on-top companion on the user's system desktop.

Acceptance criteria:

- [x] Adds a standalone desktop pet launcher outside the browser page.
- [x] Uses the selected pet's confirmed `profile.avatar_image_url` when present.
- [x] Falls back to a built-in simple pet drawing when no avatar is configured.
- [x] Opens as a borderless always-on-top desktop companion window.
- [x] Supports basic movement, dragging, double-click petting, and right-click
  quick actions.
- [x] Reads virtual pet state and can trigger existing virtual pet actions.

Implementation notes:

- `desktop_pet.py` implements the floating desktop pet using standard-library
- Tkinter, but the system Python/Tk build can fail on some macOS versions.
- `desktop_pet_mac.swift` plus `launch_desktop_pet.py` implements the preferred
  native macOS AppKit floating pet.
- Run with `python3 launch_desktop_pet.py --pet-id 2`, or omit `--pet-id` to use
  the first virtual pet.
- GUI launch requires the user's approval in sandboxed environments.

## Slice 27: Manifest-First Desktop Pet Assets V1

Type: AFK

Blocked by: Slice 26

What to build:

Change character confirmation from "use this generated picture directly" to
"derive a desktop pet asset pack from this character identity." The desktop pet
runtime should read a manifest and play animation assets instead of guessing how
to crop or animate a raw generated image.

Acceptance criteria:

- [x] Confirmed characters generate a `manifest.json` desktop pet asset pack.
- [x] Asset pack includes `avatar.png`.
- [x] Asset pack includes GIF-first animations for idle, walk left/right, sleep,
  happy, work, and alert states.
- [x] Pet profile stores the desktop pet manifest URL when a character is bound.
- [x] Native desktop pet launcher prefers the manifest over raw image URLs.
- [x] Native desktop pet runtime can switch animation states from the manifest.

Implementation notes:

- `desktop_pet_assets.py` builds the first local asset pack from a confirmed
  character image using Pillow.
- Asset packs are written under `static/desktop_pet_assets/{character_id}/`.
- `desktop_pet_mac.swift` reads `--manifest` and displays GIF animations through
  `NSImageView`.
- This is GIF-first for fast product feel, but manifest-first so sprite sheets or
  frame sequences can be added later without redesigning the launcher.

## Slice 28: Telegram Avatar Customization Flow V1

Type: HITL

Blocked by: Slice 27

What to build:

Move pet appearance customization into Telegram. The web UI is deprecated as a
daily product surface and should remain only as a local debug/admin page.
Customization must be explicit and user-confirmed: generate a preview first,
then create desktop pet assets only after the user confirms.

Acceptance criteria:

- [x] Telegram "定制形象" starts an avatar customization flow.
- [x] User sends a reference image in Telegram.
- [x] Bot asks for desired pet style after receiving the image.
- [x] Bot generates an image preview through the backend without creating
  desktop pet assets yet.
- [x] Bot sends the preview back with explicit confirm/cancel buttons.
- [x] Only after confirmation does the backend create a character, generate the
  desktop pet asset pack, and bind the manifest to the default pet profile.
- [x] Web UI displays a deprecation/debug-only notice.

Implementation notes:

- `telegram_bot.py` owns the new `PENDING_AVATAR_FLOWS` state machine.
- Telegram avatar customization now offers preset style buttons after the
  reference image, while still allowing free-form text.
- Pixel desktop-pet styles add a backend prompt contract requiring one complete
  upright character on a transparent/plain background, avoiding sheets,
  collages, duplicate poses, text, and decorative scenes.
- Backend flow is split:
  - `POST /image-style` only generates preview.
  - `POST /characters` confirms the character record.
  - `POST /characters/{character_id}/desktop-assets` generates GIF-first assets.
  - `PATCH /pets/{pet_id}` binds manifest/profile data.
- Web customization is retained for debugging but is no longer the intended
  product path.
- Smoke-tested on 2026-05-11 with Telegram trace `avatar_2bcf330248`:
  Telegram photo download, MIME inference, backend preview generation, local
  character confirmation, desktop asset generation, and pet profile binding all
  succeeded. The new Qing Qing manifest is
  `/static/desktop_pet_assets/459356ff5ec64941a15d1884c16b97cf/manifest.json`.

## Slice 29: Telegram Desktop Companion Launch V1

Type: Local runtime

Blocked by: Slice 27

What to build:

Add a Telegram button that brings the confirmed desktop pet onto the owner's
local desktop using the currently bound manifest-first asset pack.

Acceptance criteria:

- [x] Persistent Telegram keyboard includes a `桌面陪伴` button.
- [x] Bot startup refreshes the configured chat with the persistent button
  keyboard, so users do not need slash commands to discover new actions.
- [x] Main menu also sends visible inline buttons under the Telegram message,
  with `桌面陪伴` as a first-row action, because persistent keyboards can be
  collapsed by some clients.
- [x] Clicking `桌面陪伴` checks the default pet's
  `profile.desktop_pet_manifest_url`.
- [x] If no manifest is available, the bot asks the user to run `定制形象`
  first.
- [x] If a manifest is available, the bot starts `launch_desktop_pet.py
  --pet-id {id}` as a local child process without blocking Telegram polling.
- [x] Repeated clicks do not spawn duplicate desktop pet processes while the
  previous one is still alive.
- [x] Launch attempts write diagnostics with `desktop_...` trace ids and child
  process output goes to `logs/desktop_pet_launch.log`.

Implementation notes:

- `telegram_bot.py` owns the button handler and local process lifecycle handle.
- Slash commands are debug/bootstrap fallbacks only; daily product usage should
  stay button-first.
- `send_main_menu(...)` sends both the bottom persistent keyboard and a visible
  inline action menu.
- The desktop pet still launches locally on the machine running the bot; this is
  intentionally not a remote Telegram/cloud action.

## Slice 30: One-Command Local Product Runtime V1

Type: Runtime reliability

Blocked by: Slice 29

What to build:

Make the local product loop smoother by replacing the "remember to start both
FastAPI and Telegram bot" workflow with one product command.

Acceptance criteria:

- [x] `python3 run_pet_agent.py` starts FastAPI and Telegram bot together.
- [x] FastAPI and Telegram logs are separated under `logs/`.
- [x] If either child process exits unexpectedly, the runner shuts down the
  companion process instead of leaving a half-working product loop.
- [x] `README.md` documents the one-command product entry and keeps separate
  process commands as debugging paths.

Implementation notes:

- `run_pet_agent.py` is intentionally small and local-dev oriented. It is not a
  production process manager, but it removes the current UX footgun.

## Slice 31: Runtime Control Plane V1

Type: Runtime architecture

Blocked by: Slice 30

What to build:

Move product runtime orchestration out of individual Telegram handlers and into
a unified local control plane. Telegram should request product actions; the
control plane should own service readiness, local state fallback, desktop pet
launching, duplicate suppression, logs, and stable error codes.

Acceptance criteria:

- [x] `pet_runtime_controller.py` exposes a small `PetRuntimeController`
  interface for launching desktop companionship.
- [x] The controller resolves the default pet from local SQLite, so desktop
  companionship is not blocked by FastAPI being offline.
- [x] The controller validates the bound manifest before launching the native
  desktop pet.
- [x] The controller prevents duplicate desktop pet launches while the previous
  process is still alive.
- [x] The controller returns structured `DesktopCompanionResult` values with
  stable product error codes.
- [x] `telegram_bot.py` delegates `桌面陪伴` to the controller instead of
  owning the orchestration itself.
- [x] Unit tests cover local-profile launch and missing-manifest error behavior.

Implementation notes:

- `run_pet_agent.py` remains the local product supervisor.
- `PetRuntimeController` is the product control plane seam. Future Telegram
  actions such as status and virtual-pet actions should move behind this seam
  so Telegram no longer coordinates backend details directly.

## Slice 32: Transparent Desktop Pet Animation Assets

Type: Visual quality

Blocked by: Slice 27

What to build:

Ensure GIF-first desktop pet animation assets preserve transparent backgrounds.
The pet should appear as an overlay on the desktop, not inside a black rectangle.

Acceptance criteria:

- [x] GIF export reserves palette index `0` for transparent pixels.
- [x] Non-transparent pixels are remapped away from the transparent index.
- [x] Regression test verifies reopened GIF frames have transparent corners.
- [x] Current Qing Qing asset pack was regenerated and verified.

Implementation notes:

- `desktop_pet_assets.py` now converts RGBA frames to paletted GIF frames
  explicitly instead of relying on Pillow's default quantization.
- Verified all frames in
  `static/desktop_pet_assets/459356ff5ec64941a15d1884c16b97cf/` have
  transparent corners.

## Slice 33: Behavior-Matched Desktop Pet Pose Assets

Type: Visual quality / product correctness

Blocked by: Slice 27, Slice 32

What to build:

Desktop pet action animations must be based on behavior-specific generated
poses, not only transforms of the confirmed standing avatar. For example,
sleeping should use a generated sleeping/lying pose, walking should use a
generated walking pose, and owner commands should have matching action poses.

Acceptance criteria:

- [x] Asset generation has a single animation spec list for desktop behaviors.
- [x] Specs include idle, relax, walk left/right, sleep, happy, work, alert,
  feed, refill, play, pet, clean, and lullaby.
- [x] Character desktop asset generation calls the image model once per behavior
  pose and then creates GIFs from those pose images.
- [x] Manifest records pose sources and action-to-animation mapping.
- [x] Regression test verifies behavior poses are present and sleep uses a
  generated behavior pose instead of the avatar fallback.
- [x] Current Qing Qing asset pack was regenerated with behavior pose sources.

Implementation notes:

- `character_agent.py` now supplies `_generate_desktop_behavior_pose(...)` to
  `desktop_pet_assets.build_desktop_pet_assets(...)`.
- `desktop_pet_assets.py` now separates behavior pose generation from local GIF
  frame loops. Local frame loops provide only subtle motion around the generated
  pose.
- Regenerated
  `static/desktop_pet_assets/459356ff5ec64941a15d1884c16b97cf/manifest.json`;
  all listed animations and pose PNGs exist and have transparent GIF corners.

## Slice 34: Progressive Desktop Companion Readiness

Type: Product UX / asset pipeline

Blocked by: Slice 27, Slice 29, Slice 33

What to build:

Make customized desktop companionship available as soon as the user confirms a
character image. The first desktop experience only needs quiet/idle presence and
simple desktop wandering. Richer action animations and user-created emote packs
should be generated, unlocked, and replaced progressively after the pet is
already usable.

Acceptance criteria:

- [ ] Character confirmation can produce a minimal `desktop_basic_ready`
  manifest containing `avatar`, quiet/idle, and simple wandering assets.
- [ ] Telegram/local UI can launch desktop companionship when
  `desktop_basic_ready` is available, without waiting for every behavior pose.
- [ ] Full behavior poses continue generating asynchronously and update asset
  readiness as `actions_generating`, `actions_partial_ready`, or
  `actions_full_ready`.
- [ ] A failed advanced action generation does not remove the basic desktop
  companion.
- [ ] Product copy frames the wait as progressive growth, not blocked access,
  for example: "小宠物先来桌面陪你啦，动作细节正在慢慢长出来。"
- [ ] The asset model leaves room for later user-created expressions, emotes,
  and action packs attached to the same pet identity.

Implementation notes:

- Suggested readiness states: `avatar_ready`, `desktop_basic_ready`,
  `actions_generating`, `actions_partial_ready`, `actions_full_ready`,
  `generation_failed`.
- Future user expression customization should reuse the manifest-first desktop
  pet asset system instead of creating a separate visual identity system.
