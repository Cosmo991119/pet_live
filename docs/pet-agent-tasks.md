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
- [x] Clicking `桌面陪伴` opens a one-or-many pet picker instead of assuming one
  default pet.
- [x] Single-pet launch checks that pet's `profile.desktop_pet_manifest_url`.
- [x] Multi-pet launch starts every pet that already has desktop assets and
  leaves pets without assets in the Telegram group chat.
- [x] If no manifest is available, the bot asks the user to generate and
  confirm an avatar first.
- [x] If a manifest is available, the bot starts `launch_desktop_pet.py
  --pet-id {id} --offset-index {n}` as a local child process without blocking
  Telegram polling.
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
- [x] Current Qing Qing asset pack can publish already generated behavior pose
  sources as a partial manifest.

Implementation notes:

- `character_agent.py` now supplies `_generate_desktop_behavior_pose(...)` to
  `desktop_pet_assets.build_desktop_pet_assets(...)`.
- `desktop_pet_assets.py` now separates behavior pose generation from local GIF
  frame loops. Local frame loops provide only subtle motion around the generated
  pose.
- After user review, the main path was upgraded from one generated pose per
  behavior to one generated horizontal sprite strip per behavior. The confirmed
  pet image remains the locked identity reference, but each behavior now asks
  Poe for multiple equal-size frames showing actual action progression; local
  code splits those frames and composes the GIF instead of only floating one
  picture up/down.
- Default desktop companion generation is intentionally narrowed to the basic
  presence pack: `idle`, `relax`, `walk_right`, `walk_left`, `sleep`, and
  `happy`. The broader action set remains available for explicit future
  expansion, but is no longer generated by default.
- Regenerated
  `static/desktop_pet_assets/459356ff5ec64941a15d1884c16b97cf/manifest.json`;
  all listed animations and pose PNGs exist and have transparent GIF corners.
- Attempted to regenerate the actual pet-2 Qing Qing pack
  `static/desktop_pet_assets/e1f46dd64ca34f12aa7c739303bf25e9/`, but Poe
  returned `402 insufficient_quota` before all behavior poses completed. Its
  manifest intentionally remains the old `gif-first` pack until a complete run
  can finish.
- After the user accepted "use however many are available",
  `publish_existing_behavior_poses(...)` published a partial manifest with
  `idle`, `relax`, `walk_right`, `walk_left`, `sleep`, and `happy`.

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
- [x] A failed advanced action generation does not remove the basic desktop
  companion.
- [ ] Product copy frames the wait as progressive growth, not blocked access,
  for example: "小宠物先来桌面陪你啦，动作细节正在慢慢长出来。"
- [ ] The asset model leaves room for later user-created expressions, emotes,
  and action packs attached to the same pet identity.

Implementation notes:

- Suggested readiness states: `avatar_ready`, `desktop_basic_ready`,
  `actions_generating`, `actions_partial_ready`, `actions_full_ready`,
  `generation_failed`.
- Current Telegram profile bridge stores `desktop_pet_assets_status` as
  `generating`, `ready`, or `failed`; pet cards show failed background
  generation as "基础形象可用，动作素材生成失败" while preserving the basic
  avatar.
- Future user expression customization should reuse the manifest-first desktop
  pet asset system instead of creating a separate visual identity system.

## Slice 35: Telegram Pet Creation Onboarding

Type: Product UX / Telegram flow

Blocked by: Slice 21, Slice 27

What to build:

Move avatar customization out of the global menu and make it the next step after
the user creates a new pet. The creation flow should first collect durable pet
identity context, then offer targeted image customization for that exact pet.

Acceptance criteria:

- [x] Main Telegram menus expose `创建宠物` instead of a free-floating
  `定制形象` entry.
- [x] New-pet flow collects name, species, personality description, and feature
  description before persisting the pet.
- [x] Description fields are stored in the new pet profile JSON for later prompt
  reuse.
- [x] Successful creation returns a pet-specific `定制形象` action.
- [x] Avatar confirmation can bind desktop manifest/profile fields to that
  newly created pet id rather than always falling back to the default pet.
- [x] Focused Telegram flow regression tests cover menu placement, onboarding
  persistence, and targeted avatar routing.

## Slice 36: Directed Manual Pet Relationships V1

Type: Product UX / data model / group-chat behavior

Blocked by: Slice 35

What to build:

Add the smallest useful pet-to-pet relationship system for multi-pet group chat.
V1 relationships are owner-authored directed edges, not automatic inference.
They should let the owner describe how one pet tends to feel or act toward
another pet, then let group chat use that context lightly through scheduling and
occasional natural expression.

Out of scope for this slice:

- automatic relationship drift;
- relationship evidence tables;
- pending relationship change proposals;
- persisted expression cooldown;
- relationship graph visualization;
- numeric affinity editing.

Acceptance criteria:

- [x] Add a `pet_relationships` table with directed edge fields:
  `from_pet_id`, `to_pet_id`, `labels_json`, `note`, `muted`, `created_at`,
  and `updated_at`.
- [x] Enforce `UNIQUE(from_pet_id, to_pet_id)` and reject self-edges where
  `from_pet_id == to_pet_id`.
- [x] Add DB helpers to create/update, fetch, list, mute/unmute, and hard-delete
  directed relationship edges.
- [x] Telegram exposes relationship editing from the pet group chat surface.
- [x] After the owner creates a second pet, Telegram lightly offers to set how
  the pets relate to each other.
- [x] With three or more pets, Telegram first asks for the source pet, then the
  target pet, instead of showing all relationship edges at once.
- [x] Relationship setup uses multi-select buttons for V1 label keys:
  `often_replies_to_target`, `likes_staying_near_target`,
  `quiet_around_target`, `pulls_target_to_play`, and
  `keeps_distance_from_target`.
- [x] Relationship note prompts make direction explicit, for example: "How does
  Heimi usually feel or act toward Qing Qing?"
- [x] After saving one directed edge, Telegram offers to set the opposite
  direction, clearly saying it may be different and can be skipped.
- [x] Saved-relationship confirmation uses one light pet reaction plus a plain
  note that the relationship may lightly affect future group chat.
- [x] Group-chat scheduling considers saved directed edges among candidate
  speaking pets for the current turn only.
- [x] If both directions exist, the current speaking pet's outgoing edge is the
  primary relationship context and the reverse edge is secondary interaction
  context.
- [x] If only one direction exists, it may be used as weak context for the
  missing direction without inventing the missing pet's attitude.
- [x] If no relationship edge exists, group chat follows pet personality first
  and does not invent relationship context.
- [x] `muted` silences natural-language relationship expression while still
  allowing light scheduling influence.
- [x] Relationship expression cooldown is runtime-only in V1.
- [x] Tests cover DB constraints/helpers, Telegram relationship setup flow, and
  group-chat context selection/muting behavior.

Implementation notes:

- Relationship labels are LLM generation signals, not final dialogue scripts.
  Pass a structured relationship summary with guardrails rather than raw table
  rows or only freeform notes.
- The turn scheduler controls whether relationship context may be expressed
  before prompting the LLM. The LLM should express it only when the gate is
  open, and should do so lightly.
- Current implementation adds `build_relationship_context_for_candidates(...)`
  and `build_relationship_context_for_turn(...)` as tested relationship-context
  selection seams. The turn-level helper chooses the current speaker's outgoing
  edge as primary context, treats reverse/missing-direction edges as non-speaking
  context, and applies runtime-only cooldown before natural-language expression.
  Full speaker weighting should be wired when the project adds a real multi-pet
  LLM group-chat generator.
- Do not add `frozen`, `affinity`, `source`, `last_expressed_at`, or
  `evidence_summary` in V1. Future automatic drift can add a clearer owner-lock
  field and separate evidence/proposal/scheduling-state tables when needed.

## Slice 37: GPT Multi-Pet Group Chat Entry Point

Type: Product UX / Telegram LLM integration

Blocked by: Slice 36

What to build:

Turn the Telegram pet group chat surface into a real GPT-backed reply path. Once
the user has opened the pet group chat, ordinary text should be treated as a
message to the pets. The bot should choose the current interaction pet as the
speaker, include the other pets as group context, pass directed relationship
context through the Slice 36 gate, and ask GPT for one natural speaker reply.

Acceptance criteria:

- [x] The Telegram chat box itself is the pet group-chat entry point; ordinary
  free text calls the GPT LLM path instead of falling through silently.
- [x] The persistent reply keyboard does not include a dedicated `宠物群聊`
  trigger. Relationship editing remains a control surface through `宠物关系`.
- [x] GPT prompt includes the owner message, the selected speaker pet, all pets
  in the group, and the gated `relationship_context`.
- [x] A responder-planning layer decides who should answer before response
  generation. Direct pet-name mentions are routed to the mentioned pet; otherwise
  GPT can choose 1-2 responders from the group.
- [x] Relationship context is generated through
  `build_relationship_context_for_turn(...)` so muted edges, reverse edges, weak
  incoming edges, and runtime cooldowns are respected.
- [x] The bot sends the returned text as `宠物名：回复`.
- [x] Existing pending flows for pet creation, relationship notes, settings, and
  avatar customization still take precedence over free group-chat text.
- [x] Unknown text outside an active group chat still does not emit the old
  generic button hint.

Implementation notes:

- This is now a planner-driven integration. It can choose up to two responders,
  but each responder still speaks through the single-speaker generation prompt.
  Richer speaker weighting, turn history, and short reaction formatting remain a
  future slice.
- GPT is already integrated through `llm_openai.openai_llm_call`; this slice adds
  the missing Telegram multi-pet group-chat product path that uses it.
- Relationship labels remain prompt signals, not dialogue scripts. The prompt
  tells GPT to express only relationships with `allow_natural_expression=true`
  and to keep other edges as light context.

## Slice 38: Follow-Up Reaction Gate

Type: Product UX / Telegram multi-pet chat behavior

Blocked by: Slice 37

What to build:

After the primary pet reply is generated, decide whether another pet should
briefly接话. This keeps the Telegram chat feeling like a real group chat without
turning every owner message into multiple full pet monologues.

Acceptance criteria:

- [x] Group chat generates one primary pet reply first.
- [x] A follow-up reaction behavior layer evaluates whether each other candidate
  pet may briefly接话 using the owner message, primary pet, primary reply,
  candidate reactors, and directed relationship context.
- [x] If the owner explicitly addressed one pet by name, other pets do not
  insert a follow-up reaction by default.
- [x] Candidate reactors must have an allowed outgoing relationship context
  toward the primary speaker, so muted, blocked, missing, reverse-only, or
  cooldown relationships do not naturally接话.
- [x] A gate decline does not consume relationship expression cooldown.
- [x] When a short reaction is generated, the relationship expression cooldown is
  recorded only after the reaction is actually sent.
- [x] Reaction generation uses the same single-speaker prompt with
  `short_reaction=true`, keeping the second message short and non-dominating.
- [x] Group chat remembers recent pet speakers per Telegram chat. When the owner
  asks about "other/another/remaining" pets, responder planning excludes recent
  speakers first so the same pet does not answer for everyone.
- [x] If the responder planner chooses two pets for a turn, Telegram emits both
  primary replies instead of silently using only the first responder.

Implementation notes:

- `choose_followup_reactors(...)` is the tested seam for reaction gating.
- `build_relationship_context_for_turn(..., record_expression=False)` is used
  while evaluating possible reactors; cooldown is recorded after a reaction is
  emitted.
- The gate may return multiple follow-up reactors, but each one still gets only
  a short `short_reaction=true` response. Richer turn history and more nuanced
  interruption policy remain future work.
- `PET_GROUP_LAST_SPEAKER_IDS` stores a small runtime-only speaker memory per
  chat. It is used for turn wording such as "其他两个呢？" and is intentionally
  separate from `CURRENT_PET_IDS`, which only drives care/action buttons.

## Slice 39: Per-Pet Natural Profile Settings

Type: Product UX / Telegram profile management / LLM context

Blocked by: Slice 37

What to build:

Move profile editing out of the global Telegram reply keyboard and into each pet
card. Let the owner naturally add personality, habits, and behavior notes for a
specific pet, then inject those notes into group-chat GPT prompts.

Acceptance criteria:

- [x] The persistent reply keyboard no longer includes a global `设置资料`
  button.
- [x] Each pet card in `宠物列表` exposes a `设置资料` action for that pet.
- [x] Pet-specific settings menu can update basic fields such as name, owner
  call name, species, and mode.
- [x] Speaking style is configured through owner-authored free text instead of
  only four preset personality labels. The text is stored as
  `profile.speaking_style_prompt`.
- [x] Species setting accepts free text instead of limiting the owner to cat/dog
  buttons. Because the current DB enum supports `cat/dog/other`, arbitrary
  species text is persisted as `species=other` plus `profile.custom_species`.
- [x] Pet-specific settings menu includes `补充性格/行为`.
- [x] `补充性格/行为` accepts natural language and appends it to
  `profile.personality_behavior_notes` without overwriting existing notes.
- [x] Pet cards show recent personality/behavior notes.
- [x] Group-chat prompt context includes `personality_behavior_notes` so GPT can
  generate replies using the pet's owner-authored personality and behavior
  details.
- [x] Group-chat prompt context includes `speaking_style_prompt` so GPT can
  generate replies in the owner's described tone.

Implementation notes:

- `personality_behavior_notes` is intentionally owner-authored profile context,
  not inferred relationship evidence.
- `speaking_style_prompt` is owner-authored LLM guidance for voice/tone, not a
  replacement for the coarse persisted `personality` field.
- Keep the notes short and additive for V1. Future work can add editing/removal
  and summarization if the list gets long.

## Slice 40: One-Time Manual Sticker Pack Generation

Type: Product UX / Image generation / Telegram customization

Blocked by: Confirmed character image generation

What to build:

After a pet has a confirmed generated character image, let the owner manually
trigger one 12-image chat sticker pack. Keep this separate from the default
desktop GIF generation, which remains limited to `idle`, `relax`, `walk_right`,
`walk_left`, `sleep`, and `happy`.

Acceptance criteria:

- [x] A pet card with `profile.character_id` exposes `生成表情包`.
- [x] Triggering the action marks the pet profile as
  `sticker_pack_status=generating` and starts background generation.
- [x] The backend exposes `POST /characters/{character_id}/sticker-pack`.
- [x] The generated pack contains exactly 12 sticker images.
- [x] Successful generation stores `sticker_pack_status=ready`,
  `sticker_pack_character_id`, `sticker_pack_urls`, and
  `sticker_pack_theme` in the pet profile.
- [x] A ready pack is not regenerated by the Telegram button.
- [x] The generated sticker metadata is also stored on the character record.

Implementation notes:

- The sticker prompts are fixed in `character_agent.STICKER_PACK_PROMPTS` for
  V1 so the pack has a stable, predictable emotional range.
- Generation is synchronous at the FastAPI endpoint but called from a Telegram
  background thread because 12 image edits can take a long time.
- If generation fails, the pet profile is marked
  `sticker_pack_status=failed`; the owner can retry from the pet card.

## Slice 41: Persistent Pet-Owner Memories V1

Type: Product UX / data model / Telegram LLM context

Blocked by: Slice 37

What to build:

Add the first durable pet-owner memory store. This is separate from raw behavior
events, summaries, browser `localStorage`, pet profile notes, and pet-to-pet
relationships. It stores remembered companionship moments with explicit memory
type, source, participating pets, and recall guidance.

Acceptance criteria:

- [x] Add a `pet_memories` table for durable memory records.
- [x] Add a `pet_memory_participants` table so each memory can name the exact
  pet participants and preserve foreign-key checks.
- [x] Support V1 memory types: `owner_shared`, `co_experienced`,
  `pet_milestone`, and `work_companion`.
- [x] Store source, title, content, emotional tone, importance, visibility,
  recall policy, use class, and metadata JSON.
- [x] Support per-pet memory participant roles. V1 roles include
  `participant`, `shared_with`, and `mentioned_only`, while preserving existing
  internal roles such as `subject` and `helper`.
- [x] `owner_shared` memories carry guidance that pets may recall the owner
  shared the moment, but must not claim physical presence.
- [x] `co_experienced` memories carry guidance that only participant pets may
  recall them as lived shared experiences.
- [x] Expose `POST /pet-memories` and `GET /pet-memories` for Telegram,
  desktop, and future assistant flows.
- [x] Telegram group-chat prompts include recent durable memory context with
  recall guidance.
- [x] Non-participant pets do not receive `co_experienced` memories as lived
  memory context.
- [x] Deleting a pet removes its memory participant rows and deletes memories
  that have no remaining participants.
- [x] Tests cover DB creation/query/deletion, API pass-through, and Telegram
  prompt injection boundaries.

Implementation notes:

- `pet_db.create_pet_memory(...)`, `get_pet_memory(...)`, and
  `list_pet_memories(...)` own the durable memory store.
- API endpoints live at `POST /pet-memories` and `GET /pet-memories`.
- `telegram_bot.build_pet_memory_context_for_prompt(...)` prepares compact
  prompt context and filters co-experienced memories for non-participants.
- Automatic memory extraction from free-form Telegram photos/text, desktop
  actions, behavior milestones, and work-helper sessions remains future product
  work; this slice provides the persistence and recall substrate.

## Slice 42: Telegram Photo-To-Shared-Memory V1

Type: Product UX / Telegram memory capture

Blocked by: Slice 41

What to build:

Let the owner send a photo into Telegram, then have the pet ask what happened.
The owner's next explanation is evaluated as a possible co-experienced memory.
If it describes a shared moment, write it into `pet_memories` as
`co_experienced`.

Acceptance criteria:

- [x] Avatar customization photo handling still takes priority when an avatar
  flow is waiting for a reference image.
- [x] A normal photo outside avatar customization creates a pending memory-photo
  flow instead of failing with an avatar setup hint.
- [x] The pet asks neutrally what happened and which pets are in the memory
  before writing any memory.
- [x] A caption is stored as metadata but does not immediately write memory;
  the owner explanation after the photo drives memory creation.
- [x] The next owner text is checked for shared-experience signals.
- [x] Shared-experience text creates a `co_experienced` memory through
  `POST /pet-memories` only when participant pets are named or confirmed.
- [x] If shared-experience text does not name pets, the bot asks which pets
  participated instead of defaulting to every pet in the home.
- [x] Sensitive shared-experience text asks for explicit long-term memory
  confirmation before saving.
- [x] Confirmed sensitive photo memories are saved with `visibility=private`
  and `recall_policy=owner_asked_only`.
- [x] Owner cancel text such as "不要记住" clears the pending flow without
  writing a memory.
- [x] Pending photo-memory flows expire after a short window.
- [x] Memory metadata keeps the Telegram photo file id, original message id,
  and caption if present.
- [x] Non-matching explanation text clears the pending flow without writing a
  memory.
- [x] Tests cover photo prompt, caption behavior, and text-after-photo memory
  creation.

Implementation notes:

- `PENDING_MEMORY_PHOTO_FLOWS` stores one pending photo per chat.
- `handle_memory_photo(...)` owns the photo-to-question step.
- `handle_memory_photo_text(...)` owns the explanation-to-memory step.
- V1 uses lightweight deterministic Chinese phrase checks for shared-experience
  detection. A later slice can replace or augment this with GPT classification
  once enough examples exist.
- The current parser only handles a small deterministic first pass. Richer
  mixed-role parsing for `shared_with` and `mentioned_only` in the same photo
  explanation should be implemented before the Memory Album UI.

## Slice 43: Multi-Owner Foundation V1

Type: Data model / Telegram access control

Blocked by: Cross-owner pet friendship design

What to build:

Introduce an explicit owner boundary before implementing pet friendships. In
Telegram V1, an owner is represented by a Telegram chat identity. Each pet
belongs to one owner, and Telegram pet list/create/update/delete/action surfaces
can be scoped to the current owner when the V1 allowlist is enabled.

Acceptance criteria:

- [x] Add an `owners` table keyed by Telegram chat id.
- [x] Add `pets.owner_id` and migrate existing global pets to an explicit
  default owner.
- [x] Add owner helpers for Telegram chat id lookup/creation.
- [x] `create_pet`, `get_pet`, `list_pets`, `update_pet`, and `delete_pet`
  support owner scoping.
- [x] API supports `POST /owners/telegram`, `owner_id` on pet creation, and
  owner-scoped `/pets` list/update/delete and virtual-pet action reads.
- [x] Telegram can use `TELEGRAM_ALLOWED_OWNER_CHAT_IDS` as the V1 static owner
  allowlist and passes `owner_id` to pet APIs when that allowlist is enabled.
- [x] Unapproved Telegram chats are rejected before normal bot flows.
- [x] Tests cover owner-scoped pet listing and Telegram owner-scoped pet list.

Implementation notes:

- `TELEGRAM_CHAT_ID` remains the legacy single-chat access limiter. It does not
  by itself enable multi-owner API scoping.
- `TELEGRAM_ALLOWED_OWNER_CHAT_IDS` enables V1 owner scoping. Leave it empty for
  local single-user demo behavior.
- Friendship invites, opportunistic friendship messages, owner-directed
  forwarding, and confirmed memory sharing now build on this owner boundary.

## Slice 44: Pet Friendship Invites V1

Type: Cross-owner social graph / Telegram UX

Blocked by: Slice 43

What to build:

Let one owner choose one of their pets and generate a short-lived friendship
invite. Another approved owner can open the invite, choose one of their own pets,
and accept. Only after acceptance does the system create an active cross-owner
`pet_friendships` row.

Acceptance criteria:

- [x] Add `pet_friendship_invites` for owner-mediated invite tokens.
- [x] Add `pet_friendships` for active cross-owner pet friendships with V1
  `affinity` defaulting to 50.
- [x] Reject invites for pets that do not belong to the inviter owner.
- [x] Reject accepting an invite with a pet from the same owner.
- [x] Accepting a pending invite creates or reuses an active friendship and
  marks the invite accepted.
- [x] API exposes create/get/accept invite endpoints and friendship listing.
- [x] Telegram exposes a `宠物好友` entry point for generating an invite from one
  of the owner's pets.
- [x] Telegram supports `/pet_friend_invite <token>` for the receiving owner to
  accept with one of their own pets.
- [x] Tests cover DB constraints, API pass-through, and Telegram invite
  generation/acceptance.

Implementation notes:

- Friendship invite tokens are generated server-side and expire after seven
  days by default.
- Telegram V1 shares the command `/pet_friend_invite <token>` as the invitation
  handoff; a true Telegram deep link can be added later.
- This slice creates the friendship graph. Slice 47 uses the accepted graph for
  owner-directed forwarding, low-frequency daily messages, and confirmed memory
  sharing.

## Slice 45: Cross-Platform Desktop Companion Client

Type: Desktop client / multi-owner remote companion

Blocked by: Slice 43, Slice 44

What to build:

Make true floating desktop companionship available to owners who are not running
the Telegram bot host machine. A Telegram bot cannot create a native floating
window on another owner's computer by itself; the remote owner must run a local
desktop client. The product direction is to provide an installable cross-platform
desktop companion rather than asking users to configure a Python script.

Technical decision:

- Use Tauri as the preferred desktop client framework for the installable
  companion.
- Tauri is preferred over Electron for this use case because the companion should
  be small, lightweight, always-on-top, and suitable for long-running desktop
  presence.
- The client should ship as normal installers/packages:
  - macOS: `.app` / `.dmg`
  - Windows: `.exe` / `.msi`
  - Linux: `AppImage` / `.deb`
- The client should support transparent, borderless, always-on-top windows,
  local asset cache, tray/menu controls, and later deep links such as
  `petagent://bind?...`.

Acceptance criteria:

- [ ] Telegram `桌面陪伴` distinguishes local-host launch from remote-owner
  launch.
- [ ] Remote owners receive a client download/bind flow instead of triggering
  `launch_desktop_pet.py` on the bot host machine.
- [ ] Server issues short-lived signed desktop bind tokens scoped to
  `{owner_id, pet_id}`.
- [ ] The desktop client can bind with a token, fetch only the bound pet config,
  and download the pet's manifest/GIF assets from HTTPS URLs.
- [ ] The client opens a native floating companion window on the owner's own
  machine.
- [ ] The client works on macOS, Windows, and Linux, or clearly reports platform
  support gaps during phased rollout.
- [ ] Tokens are not raw `owner_id` authorization; they are opaque/signed,
  expire, and can be revoked or made one-time use.

Implementation notes:

- The current macOS Swift runtime remains a local-host implementation. It opens
  the desktop pet on the machine running the bot and should not be treated as
  remote-owner support.
- A script-based prototype is acceptable for internal experiments, but the
  product path is an installable Tauri client so non-technical owners do not need
  to install Python dependencies or run terminal commands.
- Before this slice ships, multi-owner safety should ensure `全部有素材的一起上桌面`
  is owner-scoped or disabled for remote owners; the current runtime controller
  uses unscoped `list_pets(...)` for the group launch path.

## Slice 46: Telegram Proactive Virtual Pet Tick

Type: Product behavior / Telegram companionship

Blocked by: Slice 15, Slice 43

What to build:

Let virtual pets initiate Telegram updates without requiring the owner to press
an action button or manually call `/tick`. The Telegram bot owns the chat-specific
delivery loop; the backend remains responsible for ticking simulation state and
generating event messages.

Acceptance criteria:

- [x] Telegram bot starts a background proactive tick loop when it runs.
- [x] The loop targets `TELEGRAM_CHAT_ID`, allowed owner chats, and runtime
  chats that have selected a pet.
- [x] Each pass advances owner-scoped virtual pets through
  `POST /virtual-pets/{pet_id}/tick`.
- [x] Telegram bot calls tick with `notify=false` so backend global notifier
  does not duplicate chat-specific delivery.
- [x] Generated event messages are sent to the same owner chat.
- [x] No Telegram message is sent when a tick produces no generated event
  message.
- [x] `.env.example` documents enable/disable and cadence settings.
- [x] Tests cover notifier suppression and Telegram proactive delivery.

Implementation notes:

- Default cadence is every 600 seconds with `minutes=10`, so virtual time stays
  close to wall-clock time.
- `PET_AGENT_PROACTIVE_TICKS_ENABLED=false` disables the loop.
- `PET_AGENT_PROACTIVE_TICK_INTERVAL_SECONDS` and
  `PET_AGENT_PROACTIVE_TICK_MINUTES` tune runtime cadence.

## Slice 47: Pet Friendship Messages and Memory Share V1

Type: Cross-owner social messaging / Telegram UX

Blocked by: Slice 44

What to build:

Use accepted pet friendships as the only delivery graph for cross-owner social
messages. Owners can explicitly forward a message to a named friend owner, pets
can send low-frequency daily friendship messages, and saved memories can be
shared only after the source owner confirms.

Acceptance criteria:

- [x] Friendship list rows expose both owners' Telegram chat ids for delivery.
- [x] Telegram handles `分享给XXX：...` by resolving `XXX` against the current
  pet's active friendships and forwarding the text to that friend's owner chat.
- [x] Telegram handles `分享记忆 9 给 XXX` by previewing the memory and requiring
  `确认分享` before sending it to the friend owner.
- [x] Explicit new memories may occasionally suggest a share command, with a
  cooldown, but never send without confirmation.
- [x] The bot opportunistically sends low-frequency daily friend messages from
  active pet friendships, weighted by affinity and protected by per-friendship
  cooldown.
- [x] Tests cover cross-owner forwarding, memory-share confirmation, daily
  friendship messages, and friendship delivery chat ids.

Implementation notes:

- V1 delivery is direct Telegram `sendMessage` to the friend owner's allowlisted
  chat id; there is no durable outbox yet.
- `PET_FRIEND_DAILY_MESSAGE_INTERVAL_SECONDS`,
  `PET_FRIEND_DAILY_MESSAGE_COOLDOWN_SECONDS`,
  `PET_FRIEND_DAILY_MESSAGE_CHANCE`, and
  `PET_FRIEND_DAILY_MESSAGE_MAX_PER_SCAN` tune the automatic daily-message
  budget.
- `PET_FRIEND_MEMORY_SHARE_SUGGESTION_CHANCE` and
  `PET_FRIEND_MEMORY_SHARE_SUGGESTION_COOLDOWN_SECONDS` tune how often new
  memories suggest, but do not automatically perform, a friend share.
- Memory sharing remains owner-consented: the owner must issue a share command
  and then confirm the preview before the friend owner sees the memory content.

## Slice 48: Simple Work-Form Lobster Tools V1

Type: Work assistant / Telegram + desktop utility

Blocked by: Slice 43

What to build:

Keep the first work-helper implementation deliberately small. The pet-avatar
lobster can enter work form to help with lightweight local utilities, without
turning into a broad productivity platform.

Acceptance criteria:

- [x] SQLite stores owner-scoped assistant items for `note`, `todo`, `alarm`,
  and `focus`.
- [x] FastAPI exposes create/list/complete endpoints for assistant items.
- [x] Telegram persistent keyboard exposes `小助手`.
- [x] Telegram accepts simple phrases such as `记一下 ...`, `待办 ...`,
  `提醒 10分钟后 ...`, `闹钟 16:30 ...`, and `番茄钟 25 ...`.
- [x] Telegram can list open notes/todos with `我的记事` / `我的待办`.
- [x] Telegram can complete an item with `完成 7`.
- [x] Telegram scans due `alarm` and `focus` items and sends a reminder back to
  the owner chat, then dismisses the item to avoid repeated reminders.
- [x] Native macOS desktop pet launcher passes API base URL, pet id, and owner
  id into the Swift runtime.
- [x] Floating desktop pet right-click menu can create note, todo, alarm, and
  focus items through the same `POST /assistant/items` endpoint.
- [x] Tests cover database persistence, API pass-through, command parsing, item
  creation, due reminder delivery, desktop launch context, and desktop menu
  wiring.

Implementation notes:

- This slice intentionally avoids calendar/email/deep project automation.
- `assistant_items` stores the durable lightweight work-helper facts.
- `PET_AGENT_ASSISTANT_DUE_SCAN_INTERVAL_SECONDS` controls Telegram due-item
  scan cadence.
- Entry principle: Telegram and the desktop pet should both be able to trigger
  the same assistant functions. Telegram is the away-from-computer/chat entry;
  the desktop pet is the immediate work-context entry.
- Current V1 implements the Telegram entry, shared backend, and a native macOS
  desktop right-click entry. Reminder delivery still happens through Telegram;
  future desktop work should add local reminder bubbles/animation-state changes
  for due items.
