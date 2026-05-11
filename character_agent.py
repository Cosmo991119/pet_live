"""Confirmed character identity and event image generation."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAIError

from image_style_agent import (
    _client,
    _extract_image_reference,
    _message_content_to_text,
    _save_generated_image,
    _to_data_url,
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
    _image_url_to_path(image_url)
    characters = _load_characters()
    character = {
        "id": uuid.uuid4().hex,
        "image_url": image_url.split("?", 1)[0],
        "style_mode": style_mode,
        "description": description.strip() or "confirmed character",
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    characters.append(character)
    _save_characters(characters)
    return character


def build_character_desktop_assets(character_id: str) -> dict:
    from desktop_pet_assets import build_desktop_pet_assets

    characters = _load_characters()
    for character in characters:
        if character["id"] == character_id:
            assets = build_desktop_pet_assets(
                character,
                pose_image_generator=_generate_desktop_behavior_pose,
            )
            character.update(assets)
            _save_characters(characters)
            return character
    raise ValueError("角色不存在。")


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


def _desktop_pose_prompt(character: dict, action_prompt: str) -> str:
    return f"""
Use the uploaded confirmed desktop pet character as the identity reference.
Generate exactly one 2D pixel-art sprite pose for this desktop-pet behavior:
{action_prompt.strip()}

Keep the same character identity, proportions, face, colors, markings, outfit, animal traits, and
overall style. The pose must be physically different when the behavior requires it: sleeping should be
a real sleeping/lying pose, walking should be a real walking/stepping pose, eating should include an
eating posture, and relaxed/idle should look calm rather than like an action pose.

Character notes:
{character.get("description", "")}

Desktop sprite contract:
- One complete character only, centered on a square canvas.
- Transparent background if possible; otherwise one plain removable solid background.
- Full body or full readable sleeping/lying silhouette visible with clean empty margin.
- Thick pixel outline, clean flat colors, crisp square-pixel 2D game-sprite style.
- No character sheet, pose grid, duplicate characters, captions, UI, speech bubbles, frames, or scene
  background.
""".strip()


def _generate_desktop_behavior_pose(character: dict, spec: Any, output_dir: Path) -> Path:
    image_path = _image_url_to_path(character["image_url"])
    try:
        response = _client().chat.completions.create(
            model=os.getenv("POE_IMAGE_MODEL", "gpt-image-1.5"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _desktop_pose_prompt(character, spec.prompt)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _to_data_url(
                                    image_path.read_bytes(),
                                    _content_type_for_path(image_path),
                                )
                            },
                        },
                    ],
                }
            ],
            stream=False,
            extra_body={
                "aspect": os.getenv("POE_IMAGE_ASPECT", "1:1"),
                "quality": os.getenv("POE_IMAGE_QUALITY", "high"),
            },
        )
    except OpenAIError as exc:
        raise ValueError(f"Poe 图片模型生成 {spec.name} 姿态失败：{exc}") from exc

    if not response.choices:
        raise ValueError(f"图片模型没有返回 {spec.name} 姿态结果。")

    response_text = _message_content_to_text(response.choices[0].message.content)
    generated_name = _save_generated_image(_extract_image_reference(response_text))
    generated_path = (STATIC_DIR / "generated" / generated_name).resolve()
    pose_path = output_dir / f"{spec.pose_name}_model_pose{generated_path.suffix.lower() or '.png'}"
    pose_path.write_bytes(generated_path.read_bytes())
    return pose_path


def generate_character_event(character_id: str, event_prompt: str) -> dict:
    if not event_prompt.strip():
        raise ValueError("请输入事件或表情包内容。")

    character = _find_character(character_id)
    image_path = _image_url_to_path(character["image_url"])
    try:
        response = _client().chat.completions.create(
            model=os.getenv("POE_IMAGE_MODEL", "gpt-image-1.5"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _event_prompt(character, event_prompt)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _to_data_url(
                                    image_path.read_bytes(),
                                    _content_type_for_path(image_path),
                                )
                            },
                        },
                    ],
                }
            ],
            stream=False,
            extra_body={
                "aspect": os.getenv("POE_IMAGE_ASPECT", "1:1"),
                "quality": os.getenv("POE_IMAGE_QUALITY", "high"),
            },
        )
    except OpenAIError as exc:
        raise ValueError(f"Poe 图片模型调用失败：{exc}") from exc

    if not response.choices:
        raise ValueError("图片模型没有返回结果。")

    response_text = _message_content_to_text(response.choices[0].message.content)
    output_name = _save_generated_image(_extract_image_reference(response_text))
    return {
        "image_url": f"/static/generated/{output_name}",
        "filename": output_name,
        "character_id": character_id,
        "prompt": event_prompt.strip(),
    }
