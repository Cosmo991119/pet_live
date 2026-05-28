**Current Objective**

Commit the local project work since last night, including desktop pet behavior, Wan animation assets, and generation workflow changes.

**Latest Change**

- Updated walking generation so `walk_left` is produced by mirroring `walk_right` frames in `desktop_pet_assets.build_desktop_pet_assets(...)`.
- Added regression coverage proving frame sequence generation only calls the provider for `walk_right`, then writes `walk_left` as the mirrored sequence with `pose_sources.walk_left.source = "mirrored_from_walk_right"`.
- Also updated future walking prompts so soft-bodied mollusks crawl/glide with arms/tentacles and fish use tail-fin swimming instead of legs.

**Current Desktop Pet Behavior**

- `desktop_pet_mac.swift` supports right-click `陪玩`: shows a small non-interactive lure overlay and makes the pet follow the mouse for about 18 seconds.
- While chasing, it emits `walk_left` / `walk_right`; `PetView.tick(...)` maps those actions to the walking GIFs.
- Sleep and idle manifest entries for Qing Qing use unique Wan full-video GIF filenames to avoid stale cache confusion.

**Verification**

- Ran `python3 -m unittest tests.test_desktop_pet_assets tests.test_character_sticker_pack tests.test_wan_video_agent`; passed, 27 tests.
- Ran `PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache python3 -m py_compile desktop_pet_assets.py character_agent.py wan_video_agent.py`; passed.
- Earlier Swift checks for `desktop_pet_mac.swift` passed with both `swiftc -parse` and full compile to `/private/tmp/desktop_pet_mac_check`.

**Working Tree Plan**

User asked to commit local code after last night. Stage the current worktree and create one local commit on `main` unless redirected.
