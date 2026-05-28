**User Goal**

Continue `/Users/cosmos/agent-demo`, a Chinese Telegram + desktop AI pet companion. Current active discussion: locate and understand the project’s current prompts for GPT-generated desktop-pet walking images and GIF walking animation.

**Current State**

- Desktop pet character images are confirmed in `characters/characters.json`; current relevant character `8bb2abb559984f83812153d08feede54` is the small octopus (`左边的小章鱼`) with `desktop_pet_asset_provider: "wan"` and `walking_reference_image_url: /static/generated/04df50041e0d4714b6562d02b21afff6.png`.
- GPT walking-reference image generation is built in `character_agent._walking_reference_prompt(...)`, then called by `_generate_walking_reference_image(...)` during `create_character(...)` or before Wan walking asset generation when missing.
- GPT desktop-pet behavior frame generation is built in `character_agent._desktop_frame_prompt(...)`; it receives the action short prompt from `desktop_pet_assets.ANIMATION_SPECS`.
- The current GPT walk action snippets are in `desktop_pet_assets.py`:
  - `walk_right`: `walking in place while facing right, one foot forward, lively step-cycle pose, full body visible`
  - `walk_left`: `walking in place while facing left, one foot forward, lively step-cycle pose, full body visible`
- Current default asset provider is Wan (`DESKTOP_PET_ASSET_PROVIDER` defaults to `wan`). For walk actions, `character_agent._generate_wan_desktop_behavior_frames(...)` uses the GPT walking reference image as Wan’s source image.
- Wan’s walk GIF motion prompt is in `wan_video_agent.wan_prompt_for_animation(...)`; it includes species-aware rules for octopus/squid/soft-bodied mollusks: preserve tentacles, avoid human/mammal gait, and use alternating tentacle support, crawling, ground-hugging motion, or gentle gliding.

**Recent Change**

- Read the prompt pipeline and current generated manifest for the octopus desktop pet. No runtime/code changes were made.
- Refreshed this handoff to make the walking prompt pipeline the current task context; older group-chat memory product rules remain archived in `CONTEXT.md`.

**Artifact Trail**

- Modified: `.agents/context-handoff.md`.
- Important read-only context: `character_agent.py`, `desktop_pet_assets.py`, `wan_video_agent.py`, `image_style_agent.py`, `image_styles/animal_pixel_2d.py`, `image_styles/character_pixel_2d.py`, `characters/characters.json`, `static/desktop_pet_assets/8bb2abb559984f83812153d08feede54/manifest.json`.

**Verification**

- Read-only prompt inspection plus handoff update; no tests run because no application behavior changed.

**Next Recommended Step**

If the desired walking style is octopus-like GPT crawling, update `desktop_pet_assets.ANIMATION_SPECS` walk prompts and/or `character_agent._desktop_frame_prompt(...)` walking-specific guidance to explicitly describe tentacle-supported crawling instead of generic `one foot forward` stepping.
