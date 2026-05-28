"""
Image style transfer service.

Takes one uploaded reference image plus a style instruction, then asks an
image-capable model to generate a new image that preserves the subject while
changing the requested visual style.
"""

import base64
from io import BytesIO
import os
import re
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from PIL import Image, UnidentifiedImageError
import requests

from diagnostics import log_event, log_exception, new_trace_id
from image_styles import get_style

load_dotenv()

GENERATED_DIR = Path("static/generated")
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 50 * 1024 * 1024
DEFAULT_IMAGE_MODEL = "gpt-image-1.5"
GPT_IMAGE_MODELS = ("gpt-image-", "chatgpt-image-")
TRANSPARENT_PNG_CONTRACT = """
Transparent PNG contract:
- The final file must be a PNG with a real alpha channel.
- The canvas must contain only the character pixels and transparent empty space.
- All four corners and the margin around the character must be fully transparent alpha 0.
- Do not use white, gray, checkerboard, matte, solid-color, gradient, scenic, or photographic
  background pixels.
- Do not add ground, floor, base, platform, shadow, glow, reflection, halo, border, frame, text, or
  watermark.
""".strip()
AVATAR_PIXEL_STYLE_REQUIREMENTS = """
Fixed style reference: refined chibi anime pixel-art sticker.

Use the uploaded image as the content reference and apply only this visual style:
Q-version anime pixel art, polished high-resolution pixel-art finish, crisp square pixel edges with
subtle anti-aliasing, big-head-small-body chibi proportions, expressive large eyes, delicate layered
pixel shading, detailed pixel clusters in hair and clothing, soft clean lighting, low-saturation
graphic shadows, modern cute but slightly cool temperament, and game character standing illustration
or sticker quality.

Style Transfer Scope: this is a style conversion, not a redesign. Preserve the uploaded image's
primary subject, pose logic, facing direction, body rhythm, hairstyle silhouette, outfit silhouette,
dominant colors, makeup cues, held objects, accessories, and companion plush or object if it is part
of the intended subject. Do not invent animal species, appendages, mascot traits, extra costumes, or
details from older examples unless the user's current text explicitly asks for them.

Subject Selection: if the uploaded image contains multiple people, characters, pets, or toys, create
the main subject named by the user's text. If the user does not specify one, use the most prominent
foreground subject and include a held plush/object when it is clearly being carried. Do not merge
identity features from unrelated background subjects.

Composition: create exactly one clean standalone character illustration, full body or three-quarter
body when the source crop requires it, centered with generous transparent margin. Keep the pose and
held-object placement close to the source image, but simplify forms so the result reads clearly as a
single chibi pixel-art avatar.

Pixel Detail: use clean hand-placed sprite clusters, controlled thin dark outlines, blocky hair and
clothing highlights, small bright eye and cheek highlights, separated color regions, and readable
accessory details. Prefer hard-edged pixel clusters and nearest-neighbor-like clarity over painterly
blending. Avoid photorealism, smooth illustration, fuzzy haze, noisy dithering, muddy texture, dirty
smudges, heavy black borders, and low-contrast color wash.

Background: transparent PNG only. Only the character may be visible. No beach, room, scenery, floor,
ground plane, base, cast shadow, contact shadow, mirror reflection, glossy floor reflection, frame,
UI, text, label, or watermark. Do not fake transparency with a white, gray, checkerboard, or solid
matte background.
""".strip()


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("缺少 OPENAI_API_KEY，请先在 .env 中配置。")
    return OpenAI(api_key=api_key)


def _build_prompt(style_instruction: str, style_mode: str) -> str:
    image_style = get_style(style_mode)
    extra_rules = ""
    if style_mode in {"character_pixel_2d", "animal_pixel_2d"}:
        extra_rules = f"""
Fixed pixel avatar style override:
When these rules conflict with the generic pixel-style rules above, follow this section. The desired
result is the fixed chibi pixel style only. Transfer the visual style, not an older pet, animal,
mascot, pose, or background concept.

{AVATAR_PIXEL_STYLE_REQUIREMENTS}

{TRANSPARENT_PNG_CONTRACT}

Desktop pet source image contract:
- Final output must be exactly one clean, complete character-style cutout.
- Use a transparent PNG background with a real alpha channel.
- Keep the full body visible with clear empty margin, centered on a square canvas.
- Preserve the source image's pose, gesture, facing direction, body rhythm, and held-object placement.
  Do not force a seated pose, standing pose, or body arrangement from the style reference.
- Preserve the source image's lower-body design and pose logic. If the source has distinctive legs,
  feet, paws, tail, fins, dress shape, or non-human appendages, keep that concept instead of replacing
  it with generic legs or anatomy from another example.
- Preserve important source accessories and hand/arm pose logic when present, such as a phone, bag,
  bow, collar, jewelry, or held object. Do not drop the accessory unless it conflicts with a clean
  desktop-pet silhouette.
- If the source shows a human hand or arm holding an object, keep it as a hand or arm with simplified
  readable fingers/palm and the same skin tone. Do not replace it with a tentacle, paw, fin, or generic
  noodle limb unless the current user request explicitly asks for that.
- Do not crop the head, hair, ears, tail, appendages, feet, or any major body part. Do not zoom in so
  much that the character fills the whole canvas.
- Feet/base should sit near the lower edge so the asset builder can anchor it as a desktop pet.
- Keep the avatar clean and cutout-friendly. Avoid obvious floor reflections, mirror reflections,
  glossy floor scenes, heavy cast shadows, dirty halos, or complex background scenes.
- Do not make a sheet, collage, contact sheet, expression grid, turn-around, multiple poses, duplicate
  characters, decorative scene, caption, label, UI, frame, speech bubble, or prop showcase.
- Do not add a leash, rope, lead, harness line, hand holding the pet, or tether unless the user's
  requirements explicitly ask for one.
- Prioritize a clean silhouette and readable 256x256 desktop-pet conversion over illustration polish.
""".rstrip()

    return (
        f"{image_style.prompt}\n\n"
        f"{extra_rules}\n\n"
        "Additional user requirements:\n"
        f"{style_instruction.strip()}"
    )


def _to_data_url(image_bytes: bytes, content_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _message_content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(getattr(block, "text", "") or getattr(block, "content", "")))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _extract_image_reference(text: str) -> str:
    data_url_match = re.search(r"data:image/[^;\s)]+;base64,[A-Za-z0-9+/=]+", text)
    if data_url_match:
        return data_url_match.group(0)

    markdown_match = re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text)
    if markdown_match:
        return markdown_match.group(1)

    url_match = re.search(r"https?://[^\s)]+", text)
    if url_match:
        return url_match.group(0)

    raise ValueError(f"图片模型没有返回可识别的图片链接。原始返回：{text[:300]}")


def _extension_from_content_type(content_type: str) -> str:
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/webp":
        return ".webp"
    return ".png"


def _extension_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".png"


def _save_generated_image(image_reference: str) -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    if image_reference.startswith("data:image/"):
        header, encoded = image_reference.split(",", 1)
        content_type = header.removeprefix("data:").split(";", 1)[0]
        output_name = f"{uuid.uuid4().hex}{_extension_from_content_type(content_type)}"
        (GENERATED_DIR / output_name).write_bytes(base64.b64decode(encoded))
        return output_name

    try:
        response = requests.get(image_reference, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"下载 OpenAI 返回的图片失败：{exc}") from exc
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    extension = _extension_from_content_type(content_type)
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        extension = _extension_from_url(image_reference)

    output_name = f"{uuid.uuid4().hex}{extension}"
    (GENERATED_DIR / output_name).write_bytes(response.content)
    return output_name


def _save_generated_image_data(encoded_image: str, extension: str = ".png") -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output_name = f"{uuid.uuid4().hex}{extension}"
    (GENERATED_DIR / output_name).write_bytes(base64.b64decode(encoded_image))
    return output_name


def _validate_transparent_png(path: Path) -> None:
    if path.suffix.lower() != ".png":
        raise ValueError("图片模型必须返回透明 PNG，不能返回 JPG/WebP 或其他格式。")
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"无法读取生成的 PNG：{exc}") from exc

    alpha = rgba.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()
    if alpha_min > 0 or alpha_max == 0:
        raise ValueError("图片模型没有返回真实透明背景：PNG alpha 通道不包含透明区域。")

    width, height = rgba.size
    corner_points = [
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
    ]
    if any(alpha.getpixel(point) > 0 for point in corner_points):
        raise ValueError("图片模型返回的 PNG 四角不是透明的，背景没有被严格移除。")

    margin = max(2, min(width, height) // 64)
    edge_samples = []
    for x in range(width):
        for y in range(margin):
            edge_samples.append(alpha.getpixel((x, y)))
            edge_samples.append(alpha.getpixel((x, height - 1 - y)))
    for y in range(height):
        for x in range(margin):
            edge_samples.append(alpha.getpixel((x, y)))
            edge_samples.append(alpha.getpixel((width - 1 - x, y)))
    if edge_samples and max(edge_samples) > 0:
        raise ValueError("图片模型返回的角色或背景贴到画布边缘，缺少透明留白。")


def _response_data_value(item, key: str):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _image_model_supports_response_format(model: str) -> bool:
    return model.startswith("dall-e-")


def _is_gpt_image_model(model: str) -> bool:
    return model.startswith(GPT_IMAGE_MODELS)


def generate_image_from_reference(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    prompt: str,
    *,
    size: Optional[str] = None,
    require_transparent_png: bool = False,
) -> str:
    image_file = BytesIO(image_bytes)
    image_file.name = filename or f"input{SUPPORTED_IMAGE_TYPES.get(content_type, '.png')}"

    model = os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
    request_kwargs = {
        "model": model,
        "image": image_file,
        "prompt": f"{prompt}\n\n{TRANSPARENT_PNG_CONTRACT}" if require_transparent_png else prompt,
        "size": size or os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
        "quality": os.getenv("OPENAI_IMAGE_QUALITY", "high"),
        "background": "transparent",
    }
    if _is_gpt_image_model(model):
        request_kwargs["output_format"] = "png"
        request_kwargs["input_fidelity"] = os.getenv("OPENAI_IMAGE_INPUT_FIDELITY", "high")
    if _image_model_supports_response_format(model):
        request_kwargs["response_format"] = "b64_json"

    response = _client().images.edit(**request_kwargs)

    if not response.data:
        raise ValueError("图片模型没有返回结果。")

    first_image = response.data[0]
    encoded_image = _response_data_value(first_image, "b64_json")
    if encoded_image:
        output_name = _save_generated_image_data(encoded_image, ".png")
        if require_transparent_png:
            _validate_transparent_png(GENERATED_DIR / output_name)
        return output_name

    image_url = _response_data_value(first_image, "url")
    if image_url:
        output_name = _save_generated_image(image_url)
        if require_transparent_png:
            _validate_transparent_png(GENERATED_DIR / output_name)
        return output_name

    raise ValueError("图片模型没有返回可保存的图片数据。")


def transform_image_style(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    style_instruction: str,
    style_mode: str = "figurine_3d",
) -> dict:
    trace_id = new_trace_id("image")
    log_event(
        "image_style_request_started",
        trace_id,
        filename=filename,
        content_type=content_type,
        bytes=len(image_bytes),
        style_mode=style_mode,
        style_length=len(style_instruction.strip()),
    )
    if content_type not in SUPPORTED_IMAGE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_TYPES))
        log_event(
            "image_style_unsupported_content_type",
            trace_id,
            content_type=content_type,
            supported=supported,
        )
        raise ValueError(f"只支持这些图片类型：{supported}")

    if not image_bytes:
        raise ValueError("上传的图片为空。")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能超过 50MB。")

    if not style_instruction.strip():
        raise ValueError("请输入想要转换成的图片风格。")

    try:
        output_name = generate_image_from_reference(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
            prompt=_build_prompt(style_instruction, style_mode),
            require_transparent_png=style_mode in {"character_pixel_2d", "animal_pixel_2d"},
        )
    except OpenAIError as exc:
        log_exception("image_style_model_call_failed", trace_id, exc)
        raise ValueError(f"OpenAI 图片模型调用失败：{exc}") from exc
    except ValueError as exc:
        log_exception(
            "image_style_output_parse_or_save_failed",
            trace_id,
            exc,
        )
        raise
    log_event(
        "image_style_request_succeeded",
        trace_id,
        output_name=output_name,
    )
    return {
        "image_url": f"/static/generated/{output_name}",
        "filename": output_name,
        "style_instruction": style_instruction.strip(),
        "style_mode": style_mode,
        "trace_id": trace_id,
    }
