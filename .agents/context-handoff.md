**User Goal**

Continue `/Users/cosmos/agent-demo`, a Chinese ReAct/RAG demo evolving into a desktop AI pet assistant. Current priority: Telegram button launches a native macOS desktop companion whose manifest assets match real behaviors, not just mechanical transforms of one standing image.

**Current State**

- Main app: `api.py` on FastAPI, static UI at `http://127.0.0.1:8000`.
- Unified local runner exists: `run_pet_agent.py` starts FastAPI and Telegram together.
- Telegram UX must be button-first. Slash commands are debug/bootstrap only.
- Desktop runtime: `launch_desktop_pet.py` -> `desktop_pet_mac.swift`, using `profile.desktop_pet_manifest_url`.
- Current default pet id `2` is Qing Qing. Its profile currently binds character `e1f46dd64ca34f12aa7c739303bf25e9` and manifest `/static/desktop_pet_assets/e1f46dd64ca34f12aa7c739303bf25e9/manifest.json`.

**Do Not Lose**

- Generated character images are identity sources, not the final desktop pet runtime.
- Desktop presence should work early; high-quality behavior poses can be progressive, but the product must clearly report generation state/errors.
- Do not store secrets in handoff files. `.env` may contain Telegram/Poe keys.
- Keep handoff compact; use `docs/pet-agent-tasks.md` for detailed slice history.

**Recent Change**

- Fixed the core asset architecture so desktop action GIFs are built from behavior-specific pose images.
- `desktop_pet_assets.py` now has `ANIMATION_SPECS` for `idle`, `relax`, `walk_right`, `walk_left`, `sleep`, `happy`, `work`, `alert`, `feed`, `refill`, `play`, `pet`, `clean`, and `lullaby`.
- `character_agent.py` now passes `_generate_desktop_behavior_pose(...)` into `build_desktop_pet_assets(...)`, causing the image model to generate one pose source per behavior before local GIF loops are created.
- `desktop_pet_mac.swift` can map more action names to manifest animations instead of collapsing most actions to `happy` or `idle`.
- Current old test character pack `459356ff5ec64941a15d1884c16b97cf` was regenerated successfully and visually checked. Preview at `/private/tmp/desktop_pet_pose_preview.jpg` showed behavior-matched poses.

**Current Blocker**

- Actual Qing Qing pack `e1f46dd64ca34f12aa7c739303bf25e9` did **not** complete regeneration because Poe returned `402 insufficient_quota` while generating behavior poses. Some partial pose files exist, but its manifest remains old `gif-first` with 7 animations, intentionally not upgraded until a full run succeeds.
- Error text: `You've used up your points! ... insufficient_quota`.

**Changed Files**

- `desktop_pet_assets.py`
- `character_agent.py`
- `desktop_pet_mac.swift`
- `tests/test_desktop_pet_assets.py`
- `docs/pet-agent-tasks.md`
- `.agents/context-handoff.md`

**Verification**

- `python3 -m unittest tests.test_desktop_pet_assets tests.test_pet_runtime_controller` passed.
- `PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache python3 -m py_compile desktop_pet_assets.py character_agent.py pet_runtime_controller.py telegram_bot.py` passed.
- `swiftc -module-cache-path /private/tmp/codex-swift-module-cache desktop_pet_mac.swift -o /private/tmp/desktop_pet_mac_check` passed.

**Next Step**

After Poe quota is replenished or a different image provider/key is configured, rerun:

`python3 -c "from character_agent import build_character_desktop_assets; print(build_character_desktop_assets('e1f46dd64ca34f12aa7c739303bf25e9'))"`

Then verify the manifest format is `behavior-pose-gif` and relaunch via the Telegram `桌面陪伴` button.
