"""
Image style transfer service.

Takes one uploaded reference image plus a style instruction, then asks an
image-capable model to generate a new image that preserves the subject while
changing the requested visual style.
"""

import base64
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
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
POE_BASE_URL = "https://api.poe.com/v1"


def _client() -> OpenAI:
    api_key = os.getenv("POE_API_KEY")
    if not api_key:
        raise ValueError("缺少 POE_API_KEY，请先在 .env 中配置。")
    return OpenAI(api_key=api_key, base_url=POE_BASE_URL)


def _build_prompt(style_instruction: str, style_mode: str) -> str:
    image_style = get_style(style_mode)
    extra_rules = ""
    if style_mode in {"character_pixel_2d", "animal_pixel_2d"}:
        extra_rules = """

Desktop pet source image contract:
- Final output must be exactly one complete, upright, grounded character.
- Use a transparent background if possible; otherwise use one plain removable solid background.
- Keep the full body visible with clear empty margin, centered on a square canvas.
- Feet/base should sit near the lower edge so the asset builder can anchor it as a desktop pet.
- Do not make a sheet, collage, contact sheet, expression grid, turn-around, multiple poses, duplicate
  characters, decorative scene, caption, label, UI, frame, speech bubble, or prop showcase.
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
        raise ValueError(f"下载 Poe 返回的图片失败：{exc}") from exc
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    extension = _extension_from_content_type(content_type)
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        extension = _extension_from_url(image_reference)

    output_name = f"{uuid.uuid4().hex}{extension}"
    (GENERATED_DIR / output_name).write_bytes(response.content)
    return output_name


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
        response = _client().chat.completions.create(
            model=os.getenv("POE_IMAGE_MODEL", "gpt-image-1.5"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _build_prompt(style_instruction, style_mode)},
                        {
                            "type": "image_url",
                            "image_url": {"url": _to_data_url(image_bytes, content_type)},
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
        log_exception("image_style_model_call_failed", trace_id, exc)
        raise ValueError(f"Poe 图片模型调用失败：{exc}") from exc

    if not response.choices:
        log_event("image_style_empty_model_response", trace_id)
        raise ValueError("图片模型没有返回结果。")

    response_text = _message_content_to_text(response.choices[0].message.content)
    try:
        image_reference = _extract_image_reference(response_text)
        output_name = _save_generated_image(image_reference)
    except ValueError as exc:
        log_exception(
            "image_style_output_parse_or_save_failed",
            trace_id,
            exc,
            response_preview=response_text[:500],
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
