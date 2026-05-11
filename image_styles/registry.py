"""Registry for independent image style prompts."""

from dataclasses import dataclass

from image_styles.animal_pixel_2d import PROMPT as ANIMAL_PIXEL_2D_PROMPT
from image_styles.character_pixel_2d import PROMPT as CHARACTER_PIXEL_2D_PROMPT
from image_styles.figurine_3d import PROMPT as FIGURINE_3D_PROMPT


@dataclass(frozen=True)
class ImageStyle:
    id: str
    label: str
    prompt: str


_STYLES = {
    "figurine_3d": ImageStyle(
        id="figurine_3d",
        label="3D Pixel Figurine",
        prompt=FIGURINE_3D_PROMPT,
    ),
    "character_pixel_2d": ImageStyle(
        id="character_pixel_2d",
        label="2D Pixel Character",
        prompt=CHARACTER_PIXEL_2D_PROMPT,
    ),
    "animal_pixel_2d": ImageStyle(
        id="animal_pixel_2d",
        label="2D Pixel Animal",
        prompt=ANIMAL_PIXEL_2D_PROMPT,
    ),
}


def get_style(style_id: str) -> ImageStyle:
    if style_id not in _STYLES:
        supported = ", ".join(sorted(_STYLES))
        raise ValueError(f"不支持的风格模式：{style_id}。可选：{supported}")
    return _STYLES[style_id]


def list_styles() -> list[ImageStyle]:
    return list(_STYLES.values())
