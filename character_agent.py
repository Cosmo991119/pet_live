"""Confirmed character identity and event image generation."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from openai import OpenAIError

from image_style_agent import (
    generate_image_from_reference,
)

CHARACTER_STORE = Path("characters/characters.json")
STATIC_PREFIX = "/static/"
STATIC_DIR = Path("static")


def _load_characters() -> list[dict]:
    if not CHARACTER_STORE.exists():
        return []
    return json.loads(CHARACTER_STORE.read_text(encoding="utf-8"))


def _save_characters(characters: list[dict]) -> None:
    CHARACTER_STORE.parent.mkdir(parents=True, exist_ok=True)
    CHARACTER_STORE.write_text(
        json.dumps(characters, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _image_url_to_path(image_url: str) -> Path:
    clean_url = image_url.split("?", 1)[0]
    if not clean_url.startswith(STATIC_PREFIX):
        raise ValueError("只能确认本地生成的 /static/ 图片。")

    relative = clean_url.removeprefix(STATIC_PREFIX)
    image_path = (STATIC_DIR / relative).resolve()
    static_root = STATIC_DIR.resolve()
    if static_root not in image_path.parents:
        raise ValueError("图片路径不合法。")
    if not image_path.exists():
        raise ValueError("确认的角色图片不存在。")
    return image_path


def _static_url_for_path(path: Path) -> str:
    resolved = path.resolve()
    static_root = STATIC_DIR.resolve()
    if resolved != static_root and static_root not in resolved.parents:
        raise ValueError("生成的参考图必须位于 /static/ 目录下。")
    return f"{STATIC_PREFIX}{resolved.relative_to(static_root).as_posix()}"


def _content_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def list_characters() -> list[dict]:
    return _load_characters()


def create_character(
    image_url: str,
    style_mode: str,
    description: str,
) -> dict:
    image_path = _image_url_to_path(image_url)
    walking_reference_image_url = _generate_walking_reference_image(
        image_path=image_path,
        style_mode=style_mode,
        description=description,
    )
    characters = _load_characters()
    character = {
        "id": uuid.uuid4().hex,
        "image_url": image_url.split("?", 1)[0],
        "walking_reference_image_url": walking_reference_image_url,
        "style_mode": style_mode,
        "description": description.strip() or "confirmed character",
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    characters.append(character)
    _save_characters(characters)
    return character


def _walking_reference_prompt(style_mode: str, description: str) -> str:
    style_note = (
        "Use the same refined chibi 2D pixel-art sprite style: thick clean pixel outline, crisp square "
        "pixels, flat readable colors, cute expressive proportions, and polished game-sprite finish."
    )
    if style_mode == "figurine_3d":
        style_note = "Use the same 3D voxel pixel-block figurine style and simplified toy-like parts."

    return f"""
Use the uploaded confirmed character image as the locked identity reference.
Generate one standalone species-accurate locomotion reference image for later desktop-pet walk animation.

Character notes:
{description.strip() or "confirmed character"}

Pose requirement:
- Change the pose into a normal movement-ready pose that fits this character's species and body structure.
- Do not preserve the reference image's sitting pose, curled pose, object-holding pose, or hand position.
- The first readable impression must be: this character is ready to move in its natural way.
- Do not force an animal, octopus, slime, fish, or non-humanoid creature into a human standing pose.
- Do not invent human legs, human feet, human arms, shoes, or hands for a creature that does not naturally have them.
- If the character has humanoid arms, arms hang naturally downward and can swing slightly.
- If the character is a four-legged animal, use a natural four-legged walking-ready pose.
- If the character is an octopus, squid, fish, jellyfish, seahorse, dolphin, shrimp, crab, turtle, or other
  marine or aquatic creature, use a swimming-ready pose instead of walking or crawling.
- For marine/aquatic creatures, keep the body floating and use fins, tail, tentacles, or body undulation
  as the movement cue; do not show ground contact, crawling, planted feet, or a walking stride.
- If the character is an octopus, squid, or tentacled sea creature, use a swimming drift pose:
  keep the body suspended and gliding through water while the arms/tentacles open, gather, and ripple
  like soft ribbons, with some tentacles sweeping gently backward for propulsion.
  Do not let tentacles stick to the ground or alternate like feet.
- If the character is another animal or creature without arms, use its natural locomotion posture and do not add arms.
- Preserve the same identity, colors, outfit, markings, face, species/creature traits, and proportions as much as possible.

Style rules:
{style_note}

Output contract:
- Transparent PNG only, with a real alpha channel.
- One complete character only, centered on a square canvas.
- Full body or full readable silhouette visible with clean empty transparent margin.
- No background, scene, floor, shadow, reflection, glow, text, labels, UI, duplicate character, or sprite sheet.
""".strip()


def _generate_walking_reference_image(
    *,
    image_path: Path,
    style_mode: str,
    description: str,
) -> str:
    try:
        generated_name = generate_image_from_reference(
            image_bytes=image_path.read_bytes(),
            filename=image_path.name,
            content_type=_content_type_for_path(image_path),
            prompt=_walking_reference_prompt(style_mode, description),
            size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
            require_transparent_png=True,
        )
    except OpenAIError as exc:
        raise ValueError(f"GPT 生成站立行走参考图失败：{exc}") from exc
    return f"{STATIC_PREFIX}generated/{generated_name}"


def build_character_desktop_assets(
    character_id: str,
    animation_names: Optional[Sequence[str]] = None,
    provider: Optional[str] = None,
) -> dict:
    from desktop_pet_assets import build_desktop_pet_assets, publish_existing_behavior_assets

    asset_provider = (provider or os.getenv("DESKTOP_PET_ASSET_PROVIDER", "wan")).strip().lower()
    if asset_provider not in {"wan", "gpt"}:
        raise ValueError("桌宠动作素材 provider 只能是 wan 或 gpt。")
    frame_generator = (
        _generate_wan_desktop_behavior_frames
        if asset_provider == "wan"
        else _generate_desktop_behavior_frames
    )

    characters = _load_characters()
    for character in characters:
        if character["id"] == character_id:
            if asset_provider == "wan" and _needs_walking_reference(animation_names) and not character.get(
                "walking_reference_image_url"
            ):
                image_path = _image_url_to_path(character["image_url"])
                character["walking_reference_image_url"] = _generate_walking_reference_image(
                    image_path=image_path,
                    style_mode=character.get("style_mode", ""),
                    description=character.get("description", ""),
                )
            build_desktop_pet_assets(
                character,
                frame_sequence_generator=frame_generator,
                animation_names=animation_names,
            )
            assets = publish_existing_behavior_assets(character)
            assets["desktop_pet_asset_provider"] = asset_provider
            character.update(assets)
            _save_characters(characters)
            return character
    raise ValueError("角色不存在。")


def _needs_walking_reference(animation_names: Optional[Sequence[str]]) -> bool:
    if animation_names is None:
        return True
    return bool({"walk_left", "walk_right"} & set(animation_names))


def _find_character(character_id: str) -> dict:
    for character in _load_characters():
        if character["id"] == character_id:
            return character
    raise ValueError("角色不存在。")


def _event_prompt(character: dict, event_prompt: str) -> str:
    style_mode = character.get("style_mode", "")
    style_note = (
        "Use a 2D pixel sticker / meme / event-photo style with thick pixel outlines, "
        "clean flat colors, expressive cute face, simple readable action, and a clean background."
    )
    if style_mode == "figurine_3d":
        style_note = (
            "Use the same 3D voxel pixel-block figurine style, plastic toy material, clean blocks, "
            "and printable simplified parts."
        )
    elif style_mode == "character_pixel_2d":
        style_note = (
            "Use the same 2D pixel character sheet / game sprite style with thick outlines, flat "
            "colors, and clean readable shapes."
        )

    return f"""
Use the uploaded confirmed character image as the identity reference.
Keep the same character identity, proportions, face, colors, markings, outfit, animal traits,
and overall style. Do not redesign the character into a different character.

Generate a new event image or meme based on this request:
{event_prompt.strip()}

Character notes:
{character.get("description", "")}

Style rules:
{style_note}
Make the action immediately readable, funny or charming, and suitable as a small social sticker or
event photo. Avoid adding unrelated characters unless requested. Avoid text unless the user explicitly
asks for text.
""".strip()


STICKER_PACK_PROMPTS = [
    "开心打招呼，适合说你好",
    "害羞贴贴，适合表达喜欢",
    "震惊睁大眼，适合表达不可思议",
    "委屈快哭了，适合撒娇",
    "生气鼓脸，适合表达小脾气",
    "困到打哈欠，适合说想睡了",
    "认真点头，适合表示收到",
    "疑惑歪头，适合表达不懂",
    "加油挥拳，适合鼓励主人",
    "瘫倒休息，适合表达累了",
    "抱着爱心，适合表达感谢和喜欢",
    "偷偷探头，适合轻轻出现或围观",
]


def _sticker_prompt(character: dict, sticker_prompt: str, theme: str) -> str:
    theme_note = theme.strip() or "日常聊天表情包"
    return _event_prompt(
        character,
        (
            f"生成一张宠物聊天表情包：{sticker_prompt}。\n"
            f"表情包主题：{theme_note}。\n"
            "单张贴纸构图，角色占主体，动作和表情清晰，适合 Telegram 聊天中发送。"
        ),
    )


def _desktop_pose_prompt(character: dict, action_prompt: str) -> str:
    return f"""
Use the uploaded confirmed desktop pet character as the identity reference.
Generate exactly one 2D pixel-art sprite pose for this desktop-pet behavior:
{action_prompt.strip()}

Keep the same character identity, proportions, face, colors, markings, outfit, animal traits, and
overall style. The pose must be physically different when the behavior requires it: sleeping should be
a real sleeping/lying pose, walking should use species-accurate locomotion rather than a generic
human step, eating should include an eating posture, and relaxed/idle should look calm rather than
like an action pose.

Character notes:
{character.get("description", "")}

Desktop sprite contract:
- One complete character only, centered on a square canvas.
- Transparent PNG only, with a real alpha channel. Only the character may be visible.
- All four corners and the margin around the character must be fully transparent.
- Full body or full readable sleeping/lying silhouette visible with clean empty margin.
- Thick pixel outline, clean flat colors, crisp square-pixel 2D game-sprite style.
- No white/gray/checkerboard/solid matte background, character sheet, pose grid, duplicate characters,
  captions, UI, speech bubbles, frames, scene background, ground, shadow, glow, reflection, or halo.
""".strip()


def _desktop_frame_prompt(character: dict, spec: Any, frame_index: int) -> str:
    frame_direction = ""
    if spec.name == "idle":
        idle_moments = {
            1: "tilt the upper body gently toward the left",
            2: "ease the upper body back toward the center as a transition frame",
            3: "tilt the upper body gently toward the right",
            4: "ease the upper body back toward the center as a transition frame",
        }
        detail = idle_moments.get(frame_index, "keep the seated idle sway subtle")
        frame_direction = (
            f"\nIdle frame detail: draw the character sitting. Keep the seated lower body/base fixed. "
            f"In this frame, {detail}. "
            "Do not move the character's position on the canvas."
        )
    elif spec.name in {"walk_right", "walk_left"}:
        direction = "right" if spec.name == "walk_right" else "left"
        walk_moments = {
            1: (
                "the floating body leans slightly into the swim direction while tentacles open like "
                "soft ribbons, or fins, tail, and body segments begin a soft propulsion wave"
            ),
            2: "tentacles gather and sweep backward in swimming drift, or fins, tail, and body undulation push through water",
            3: "the body follows the wave with a gentle floating bend while the canvas anchor stays fixed",
            4: "the appendages drift back into a loop-ready swimming drift pose",
        }
        detail = walk_moments.get(frame_index, "show a clear loop-ready swimming locomotion pose")
        frame_direction = (
            f"\nWalking frame detail: face {direction} and use species-accurate locomotion. "
            "If the pet is humanoid, use a natural in-place step. If the pet is a four-legged animal, "
            "use a natural four-legged gait. If the pet is an octopus, squid, fish, jellyfish, seahorse, "
            "dolphin, shrimp, crab, turtle, or other marine/aquatic creature, do not add human legs, feet, "
            "shoes, or human hands: keep the body in a swimming posture with a floating body. In this frame, "
            f"{detail}. "
            "For octopus, squid, or tentacled sea pets, the movement must read as swimming drift: "
            "the body stays suspended and glides while tentacles open, gather, and ripple like soft ribbons. "
            "For other aquatic pets, the movement should read as swimming through water: tentacles, fins, tail, "
            "or body undulation create propulsion while the character stays centered in the sprite frame. "
            "Do not show ground contact, crawling, planted feet, or suction-cup floor contact. "
            "Keep the character's visual anchor fixed on the canvas."
        )

    return f"""
Use the uploaded confirmed desktop pet character as a locked identity reference.
Generate frame {frame_index} of {spec.frame_count} as a standalone complete transparent PNG for this desktop-pet behavior:
{spec.prompt.strip()}
{frame_direction}

The pet identity is fixed. This single frame must keep the same species, face, silhouette, body
proportions, fur shape, colors, markings, accessories, and overall 2D pixel-art style as the reference
image. Do not redesign, recolor, simplify into a different animal, add new clothing, or change the
pet's age.

Animation requirements:
- This is one complete frame in a {spec.frame_count}-frame action sequence.
- Show the frame-specific moment for frame {frame_index}: keep scale, visual/base anchor, and character
  size consistent with the other frames.
- The desktop host app moves the Swift window across the screen. Do not simulate travel by shifting
  the pet left or right inside the PNG frames.
- Keep the pet's center point and bottom/visual anchor fixed in the same canvas position for
  every frame. Walking frames must be an in-place movement loop, not a traveling sprite.
- Do not create a sprite sheet, strip, collage, grid, multiple frames, or multiple copies.
- For idle/relax, use a small breathing or posture variation.
- For idle specifically, use four frames total: all frames are seated; frame 1 tilts the upper body
  gently left, frame 2 transitions back toward center, frame 3 tilts the upper body gently right,
  frame 4 transitions back toward center, and the seated base anchor stays fixed.
- For walking, use a readable species-accurate locomotion pose for this frame.
- For happy/play/feed/refill/pet/clean/lullaby/work/alert/sleep, make this frame's behavior readable
  through body pose and expression while staying consistent with the other frames.

Character notes:
{character.get("description", "")}

Single-frame contract:
- Family-friendly, non-sexualized desktop mascot sprite. Preserve the outfit as a cute costume, but
  avoid revealing, suggestive, romantic, or adult framing.
- Output exactly one complete pet, centered with clean empty margin.
- Transparent PNG only, with a real alpha channel. Only the pet pixels may be visible.
- All four corners and the margin around the pet must be fully transparent.
- Thick pixel outline, clean flat colors, crisp square-pixel 2D game-sprite style.
- No white/gray/checkerboard/solid matte background, character sheet labels, captions, UI, speech
  bubbles, decorative scene background, ground, shadow, glow, reflection, halo, extra characters, or
  duplicate pets.
""".strip()


def _generate_desktop_behavior_pose(character: dict, spec: Any, output_dir: Path) -> Path:
    image_path = _image_url_to_path(character["image_url"])
    try:
        generated_name = generate_image_from_reference(
            image_bytes=image_path.read_bytes(),
            filename=image_path.name,
            content_type=_content_type_for_path(image_path),
            prompt=_desktop_pose_prompt(character, spec.prompt),
            size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
            require_transparent_png=True,
        )
    except OpenAIError as exc:
        raise ValueError(f"OpenAI 图片模型生成 {spec.name} 姿态失败：{exc}") from exc

    generated_path = (STATIC_DIR / "generated" / generated_name).resolve()
    pose_path = output_dir / f"{spec.pose_name}_model_pose{generated_path.suffix.lower() or '.png'}"
    pose_path.write_bytes(generated_path.read_bytes())
    return pose_path


def _generate_desktop_behavior_frames(character: dict, spec: Any, output_dir: Path) -> list[Path]:
    image_path = _image_url_to_path(character["image_url"])
    frame_paths = []
    for frame_index in range(1, spec.frame_count + 1):
        try:
            generated_name = generate_image_from_reference(
                image_bytes=image_path.read_bytes(),
                filename=image_path.name,
                content_type=_content_type_for_path(image_path),
                prompt=_desktop_frame_prompt(character, spec, frame_index),
                size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
                require_transparent_png=True,
            )
        except OpenAIError as exc:
            raise ValueError(f"OpenAI 图片模型生成 {spec.name} 第 {frame_index} 帧失败：{exc}") from exc

        generated_path = (STATIC_DIR / "generated" / generated_name).resolve()
        frame_path = output_dir / f"{spec.pose_name}_model_frame_{frame_index}.png"
        frame_path.write_bytes(generated_path.read_bytes())
        frame_paths.append(frame_path)
    return frame_paths


def _generate_wan_desktop_behavior_frames(character: dict, spec: Any, output_dir: Path) -> list[Path]:
    from wan_video_agent import generate_wan_animation_gif

    image_url = character["image_url"]
    if spec.name in {"walk_left", "walk_right"}:
        image_url = character.get("walking_reference_image_url") or image_url
    elif spec.name == "sleep":
        sleep_reference_path = _generate_desktop_behavior_pose(character, spec, output_dir)
        image_url = _static_url_for_path(sleep_reference_path)

    try:
        return generate_wan_animation_gif(
            image_url=image_url,
            animation_name=spec.name,
            output_dir=output_dir,
            frame_count=spec.frame_count,
            duration_ms=spec.duration,
            target_duration_ms=int(os.getenv("WAN_GIF_DURATION_MS", "5000")),
        )
    except ValueError as exc:
        raise ValueError(f"Wan 图生视频生成 {spec.name} 动作 GIF 失败：{exc}") from exc


def generate_character_event(character_id: str, event_prompt: str) -> dict:
    if not event_prompt.strip():
        raise ValueError("请输入事件或表情包内容。")

    character = _find_character(character_id)
    image_path = _image_url_to_path(character["image_url"])
    try:
        output_name = generate_image_from_reference(
            image_bytes=image_path.read_bytes(),
            filename=image_path.name,
            content_type=_content_type_for_path(image_path),
            prompt=_event_prompt(character, event_prompt),
            size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
        )
    except OpenAIError as exc:
        raise ValueError(f"OpenAI 图片模型调用失败：{exc}") from exc

    return {
        "image_url": f"/static/generated/{output_name}",
        "filename": output_name,
        "character_id": character_id,
        "prompt": event_prompt.strip(),
    }


def generate_character_sticker_pack(character_id: str, theme: str = "") -> dict:
    character = _find_character(character_id)
    image_path = _image_url_to_path(character["image_url"])
    stickers = []
    for index, prompt in enumerate(STICKER_PACK_PROMPTS, start=1):
        try:
            output_name = generate_image_from_reference(
                image_bytes=image_path.read_bytes(),
                filename=image_path.name,
                content_type=_content_type_for_path(image_path),
                prompt=_sticker_prompt(character, prompt, theme),
                size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
            )
        except OpenAIError as exc:
            raise ValueError(f"OpenAI 图片模型生成第 {index} 张表情包失败：{exc}") from exc
        stickers.append(
            {
                "index": index,
                "image_url": f"/static/generated/{output_name}",
                "filename": output_name,
                "prompt": prompt,
            }
        )

    characters = _load_characters()
    for stored in characters:
        if stored["id"] == character_id:
            stored["sticker_pack"] = stickers
            stored["sticker_pack_theme"] = theme.strip() or "日常聊天表情包"
            stored["sticker_pack_created_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            _save_characters(characters)
            break

    return {
        "character_id": character_id,
        "theme": theme.strip() or "日常聊天表情包",
        "stickers": stickers,
    }
