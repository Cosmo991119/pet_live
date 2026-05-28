"""Build manifest-first desktop pet assets from a confirmed character image."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from PIL import Image, ImageEnhance, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"
ASSET_ROOT = STATIC_DIR / "desktop_pet_assets"
CANVAS_SIZE = 256


@dataclass(frozen=True)
class AnimationSpec:
    name: str
    pose_name: str
    duration: int
    prompt: str
    frame_count: int = 4


PoseImageGenerator = Callable[[dict[str, Any], AnimationSpec, Path], Path]
FrameSheetGenerator = Callable[[dict[str, Any], AnimationSpec, Path], Path]
FrameSequenceGenerator = Callable[[dict[str, Any], AnimationSpec, Path], list[Path]]

BASIC_DESKTOP_ANIMATION_NAMES = (
    "idle",
    "walk_right",
    "walk_left",
    "sleep",
    "happy",
)


ANIMATION_SPECS = [
    AnimationSpec(
        name="idle",
        pose_name="idle",
        duration=440,
        prompt=(
            "sitting calmly in a relaxed idle pose, upper body gently swaying in place, "
            "full seated body visible"
        ),
        frame_count=4,
    ),
    AnimationSpec(
        name="relax",
        pose_name="relax",
        duration=260,
        prompt="lounging lazily in a cozy relaxed pose, peaceful and idle, full body visible",
    ),
    AnimationSpec(
        name="walk_right",
        pose_name="walk_right",
        duration=140,
        prompt=(
            "walking in place while facing right, one foot forward, lively step-cycle pose, "
            "full body visible"
        ),
    ),
    AnimationSpec(
        name="walk_left",
        pose_name="walk_left",
        duration=140,
        prompt=(
            "walking in place while facing left, one foot forward, lively step-cycle pose, "
            "full body visible"
        ),
    ),
    AnimationSpec(
        name="sleep",
        pose_name="sleep",
        duration=420,
        prompt="sleeping curled up or lying down comfortably, eyes closed, unmistakable sleep pose",
    ),
    AnimationSpec(
        name="happy",
        pose_name="happy",
        duration=130,
        prompt="very happy celebratory pose, smiling brightly, excited cute expression",
    ),
    AnimationSpec(
        name="work",
        pose_name="work",
        duration=180,
        prompt="focused work-helper pose, concentrating with a tiny laptop or notebook prop",
    ),
    AnimationSpec(
        name="alert",
        pose_name="alert",
        duration=110,
        prompt="alert attention pose, surprised eyes, ready to notify the owner",
    ),
    AnimationSpec(
        name="feed",
        pose_name="feed",
        duration=170,
        prompt="eating happily from a small bowl, food action immediately readable",
    ),
    AnimationSpec(
        name="refill",
        pose_name="refill",
        duration=170,
        prompt="drinking water or reaching toward a small water bowl, thirst action immediately readable",
    ),
    AnimationSpec(
        name="play",
        pose_name="play",
        duration=130,
        prompt="playing energetically with a small toy, playful motion pose, full body visible",
    ),
    AnimationSpec(
        name="pet",
        pose_name="pet",
        duration=150,
        prompt="being petted and enjoying it, affectionate happy pose, full body visible",
    ),
    AnimationSpec(
        name="clean",
        pose_name="clean",
        duration=170,
        prompt="getting cleaned or sparkling after cleaning, fresh tidy pose, full body visible",
    ),
    AnimationSpec(
        name="lullaby",
        pose_name="lullaby",
        duration=320,
        prompt="drowsy and being soothed to sleep, sleepy eyes, cozy bedtime pose",
    ),
]


def animation_specs_for(names: Sequence[str] | None = None) -> list[AnimationSpec]:
    if names is None:
        names = BASIC_DESKTOP_ANIMATION_NAMES
    requested = set(names)
    return [spec for spec in ANIMATION_SPECS if spec.name in requested]


def _static_url_to_path(image_url: str) -> Path:
    clean = image_url.split("?", 1)[0]
    if not clean.startswith("/static/"):
        raise ValueError("desktop pet assets require a local /static/ image")
    path = (PROJECT_ROOT / clean.removeprefix("/")).resolve()
    static_root = STATIC_DIR.resolve()
    if static_root not in path.parents:
        raise ValueError("image path is outside static")
    if not path.exists():
        raise ValueError("source image does not exist")
    return path


def _remove_flat_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()
    if alpha_min < 255 and alpha_max > 0:
        return rgba

    pixels = rgba.load()
    width, height = rgba.size
    corner_colors = [
        rgba.getpixel((0, 0)),
        rgba.getpixel((width - 1, 0)),
        rgba.getpixel((0, height - 1)),
        rgba.getpixel((width - 1, height - 1)),
    ]
    bg = max(set(corner_colors), key=corner_colors.count)

    tolerance = 38
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if (
                abs(r - bg[0]) <= tolerance
                and abs(g - bg[1]) <= tolerance
                and abs(b - bg[2]) <= tolerance
            ):
                pixels[x, y] = (r, g, b, 0)
            else:
                pixels[x, y] = (r, g, b, a)
    return rgba


def _largest_subject(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return image

    # If the generated image is a sticker sheet, prefer the biggest connected
    # non-background area. This keeps a single pet instead of the whole sheet.
    mask = alpha.point(lambda value: 255 if value > 16 else 0)
    visited = set()
    width, height = mask.size
    mask_pixels = mask.load()
    best: tuple[int, tuple[int, int, int, int]] | None = None

    for start_y in range(0, height, 3):
        for start_x in range(0, width, 3):
            if mask_pixels[start_x, start_y] == 0 or (start_x, start_y) in visited:
                continue
            stack = [(start_x, start_y)]
            visited.add((start_x, start_y))
            count = 0
            min_x = max_x = start_x
            min_y = max_y = start_y
            while stack:
                x, y = stack.pop()
                count += 1
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                for nx, ny in ((x + 3, y), (x - 3, y), (x, y + 3), (x, y - 3)):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and (nx, ny) not in visited
                        and mask_pixels[nx, ny] > 0
                    ):
                        visited.add((nx, ny))
                        stack.append((nx, ny))
            if best is None or count > best[0]:
                pad = 24
                best = (
                    count,
                    (
                        max(0, min_x - pad),
                        max(0, min_y - pad),
                        min(width, max_x + pad),
                        min(height, max_y + pad),
                    ),
                )

    crop_box = best[1] if best else bbox
    return image.crop(crop_box)


def _fit_canvas(subject: Image.Image) -> Image.Image:
    subject = subject.convert("RGBA")
    subject.thumbnail((210, 210), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    x = (CANVAS_SIZE - subject.width) // 2
    y = CANVAS_SIZE - subject.height - 28
    canvas.alpha_composite(subject, (x, y))
    return canvas


def _prepare_pose_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return _prepare_pose_image_from_image(image)


def _prepare_pose_image_from_image(image: Image.Image) -> Image.Image:
    subject = _largest_subject(_remove_flat_background(image))
    return _fit_canvas(subject)


def _frames_from_sheet(path: Path, frame_count: int) -> list[Image.Image]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        if frame_count <= 1 or width < frame_count:
            return [_prepare_pose_image_from_image(rgba)]
        frame_width = width // frame_count
        frames = []
        for index in range(frame_count):
            left = index * frame_width
            right = width if index == frame_count - 1 else (index + 1) * frame_width
            frame = rgba.crop((left, 0, right, height))
            frames.append(_prepare_pose_image_from_image(frame))
        return frames


def _save_frame_sequence(output_dir: Path, name: str, frames: list[Image.Image]) -> list[str]:
    frame_names = []
    for index, frame in enumerate(frames, start=1):
        frame_name = f"{name}_frame_{index}.png"
        frame.save(output_dir / frame_name)
        frame_names.append(frame_name)
    return frame_names


def _frame(base: Image.Image, dx: int = 0, dy: int = 0, scale_y: float = 1.0) -> Image.Image:
    canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
    image = base
    if scale_y != 1.0:
        image = base.resize(
            (base.width, max(1, int(base.height * scale_y))),
            Image.Resampling.BICUBIC,
        )
    canvas.alpha_composite(image, (dx, dy + base.height - image.height))
    return canvas


def _brightness_frame(base: Image.Image, factor: float) -> Image.Image:
    rgba = base.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = ImageEnhance.Brightness(rgba.convert("RGB")).enhance(factor)
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    output.paste(rgb)
    output.putalpha(alpha)
    return output


def _frames_for_animation(name: str, pose: Image.Image) -> list[Image.Image]:
    if name == "idle":
        return [_frame(pose), _brightness_frame(pose, 0.97)]
    frame_count = 4 if name in {"walk_right", "walk_left", "feed", "refill", "play", "pet", "clean"} else 3
    return [_frame(pose) for _ in range(frame_count)]


def _save_gif(path: Path, frames: list[Image.Image], duration: int = 160) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    paletted_frames = [_gif_frame(frame) for frame in frames]
    paletted_frames[0].save(
        path,
        save_all=True,
        append_images=paletted_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        transparency=0,
        optimize=False,
    )


def _gif_frame(frame: Image.Image) -> Image.Image:
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    quantized = rgba.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT)

    output = Image.new("P", rgba.size, 0)
    palette = [0, 0, 0] + quantized.getpalette()[: 255 * 3]
    palette.extend([0] * (768 - len(palette)))
    output.putpalette(palette)

    alpha_data = list(alpha.getdata())
    color_data = list(quantized.getdata())
    output.putdata(
        [
            0 if transparent <= 16 else min(255, color_index + 1)
            for transparent, color_index in zip(alpha_data, color_data)
        ]
    )
    output.info["transparency"] = 0
    return output


def build_desktop_pet_assets(
    character: dict[str, Any],
    pose_image_generator: PoseImageGenerator | None = None,
    frame_sequence_generator: FrameSequenceGenerator | None = None,
    frame_sheet_generator: FrameSheetGenerator | None = None,
    animation_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Create a desktop-pet asset pack and return manifest metadata."""
    character_id = character["id"]
    source_path = _static_url_to_path(character["image_url"])
    output_dir = ASSET_ROOT / character_id
    output_dir.mkdir(parents=True, exist_ok=True)

    avatar = _prepare_pose_image(source_path)
    avatar_path = output_dir / "avatar.png"
    avatar.save(avatar_path)

    animations: dict[str, dict[str, str]] = {}
    pose_sources: dict[str, dict[str, str]] = {
        "avatar": {"src": "avatar.png", "source": "confirmed_character"}
    }
    generated_poses: dict[str, Image.Image] = {}
    generated_frames: dict[str, list[Image.Image]] = {}

    selected_specs = animation_specs_for(animation_names)

    def source_frames_for_spec(spec: AnimationSpec) -> tuple[list[Image.Image], str, Path]:
        pose_path = output_dir / f"{spec.pose_name}_pose.png"
        if frame_sequence_generator:
            frame_paths = frame_sequence_generator(character, spec, output_dir)
            return [_prepare_pose_image(path) for path in frame_paths], "generated_behavior_frame_sequence", pose_path
        if frame_sheet_generator:
            sheet_path = frame_sheet_generator(character, spec, output_dir)
            return _frames_from_sheet(sheet_path, spec.frame_count), "generated_behavior_frames", pose_path
        if pose_image_generator:
            pose_path = pose_image_generator(character, spec, output_dir)
            pose = _prepare_pose_image(pose_path) if pose_path.exists() else avatar.copy()
            return _frames_for_animation(spec.name, pose), "generated_behavior_pose", pose_path

        pose = _prepare_pose_image(pose_path) if pose_path.exists() else avatar.copy()
        if spec.name == "walk_left" and "walk_right" in generated_poses:
            pose = ImageOps.mirror(generated_poses["walk_right"])
        return _frames_for_animation(spec.name, pose), "confirmed_character_fallback", pose_path

    for spec in selected_specs:
        pose_path = output_dir / f"{spec.pose_name}_pose.png"
        source_label = "confirmed_character_fallback"
        frame_names: list[str] = []
        generated_gif_path = output_dir / f"{spec.name}.gif"
        generated_gif_stat = generated_gif_path.stat() if generated_gif_path.exists() else None

        if spec.name == "walk_left":
            if "walk_right" not in generated_frames:
                walk_right_spec = next(item for item in ANIMATION_SPECS if item.name == "walk_right")
                right_frames, _right_source_label, _right_pose_path = source_frames_for_spec(walk_right_spec)
                generated_frames["walk_right"] = right_frames
                generated_poses["walk_right"] = right_frames[0] if right_frames else avatar.copy()
            frames = [ImageOps.mirror(frame) for frame in generated_frames["walk_right"]]
            source_label = "mirrored_from_walk_right"
        else:
            frames, source_label, pose_path = source_frames_for_spec(spec)

        saved_pose = output_dir / f"{spec.name}_pose.png"
        pose = frames[0] if frames else avatar.copy()
        pose.save(saved_pose)
        frame_names = _save_frame_sequence(output_dir, spec.name, frames)
        generated_poses[spec.name] = pose
        generated_frames[spec.name] = frames
        current_gif_stat = generated_gif_path.stat() if generated_gif_path.exists() else None
        generator_wrote_gif = (
            frame_sequence_generator is not None
            and current_gif_stat is not None
            and (
                generated_gif_stat is None
                or current_gif_stat.st_mtime_ns != generated_gif_stat.st_mtime_ns
                or current_gif_stat.st_size != generated_gif_stat.st_size
            )
        )
        if not generator_wrote_gif:
            _save_gif(generated_gif_path, frames, spec.duration)
        animations[spec.name] = {
            "type": "gif",
            "src": f"{spec.name}.gif",
            "pose": saved_pose.name,
            "frames": frame_names,
        }
        pose_sources[spec.name] = {
            "src": saved_pose.name,
            "source": source_label,
            "prompt": spec.prompt,
        }

    action_animation_map = {
        spec.name: spec.name
        for spec in selected_specs
        if spec.name in animations
    }
    manifest = {
        "character_id": character_id,
        "format": "behavior-pose-gif",
        "generation_scope": "basic" if animation_names is None else "custom",
        "canvas": {"width": CANVAS_SIZE, "height": CANVAS_SIZE, "background": "transparent"},
        "anchor": {"x": CANVAS_SIZE // 2, "y": 228},
        "source_image_url": character["image_url"],
        "avatar": "avatar.png",
        "pose_sources": pose_sources,
        "animations": animations,
        "action_animation_map": action_animation_map,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "desktop_pet_manifest_url": f"/static/desktop_pet_assets/{character_id}/manifest.json",
        "desktop_pet_asset_dir": f"/static/desktop_pet_assets/{character_id}",
        "desktop_pet_avatar_url": f"/static/desktop_pet_assets/{character_id}/avatar.png",
    }


def publish_existing_behavior_poses(character: dict[str, Any]) -> dict[str, Any]:
    """Publish a partial asset pack from behavior poses already present on disk."""
    character_id = character["id"]
    source_path = _static_url_to_path(character["image_url"])
    output_dir = ASSET_ROOT / character_id
    output_dir.mkdir(parents=True, exist_ok=True)

    avatar = _prepare_pose_image(source_path)
    avatar_path = output_dir / "avatar.png"
    avatar.save(avatar_path)

    animations: dict[str, dict[str, str]] = {}
    pose_sources: dict[str, dict[str, str]] = {
        "avatar": {"src": "avatar.png", "source": "confirmed_character"}
    }
    action_animation_map: dict[str, str] = {"idle": "idle"}

    for spec in ANIMATION_SPECS:
        model_pose = output_dir / f"{spec.pose_name}_model_pose.png"
        existing_pose = output_dir / f"{spec.pose_name}_pose.png"
        if model_pose.exists():
            pose_path = model_pose
            source_label = "generated_behavior_pose"
        elif spec.name == "idle":
            pose_path = existing_pose if existing_pose.exists() else avatar_path
            source_label = "confirmed_character_fallback"
        else:
            continue

        pose = _prepare_pose_image(pose_path)
        saved_pose = output_dir / f"{spec.name}_pose.png"
        pose.save(saved_pose)
        _save_gif(output_dir / f"{spec.name}.gif", _frames_for_animation(spec.name, pose), spec.duration)
        animations[spec.name] = {
            "type": "gif",
            "src": f"{spec.name}.gif",
            "pose": saved_pose.name,
        }
        pose_sources[spec.name] = {
            "src": saved_pose.name,
            "source": source_label,
            "prompt": spec.prompt,
        }
        action_animation_map[spec.name] = spec.name

    manifest = {
        "character_id": character_id,
        "format": "behavior-pose-gif-partial",
        "generation_status": "partial_ready",
        "canvas": {"width": CANVAS_SIZE, "height": CANVAS_SIZE, "background": "transparent"},
        "anchor": {"x": CANVAS_SIZE // 2, "y": 228},
        "source_image_url": character["image_url"],
        "avatar": "avatar.png",
        "pose_sources": pose_sources,
        "animations": animations,
        "action_animation_map": action_animation_map,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "desktop_pet_manifest_url": f"/static/desktop_pet_assets/{character_id}/manifest.json",
        "desktop_pet_asset_dir": f"/static/desktop_pet_assets/{character_id}",
        "desktop_pet_avatar_url": f"/static/desktop_pet_assets/{character_id}/avatar.png",
        "published_animation_count": len(animations),
        "published_animations": sorted(animations),
    }


def publish_existing_behavior_assets(character: dict[str, Any]) -> dict[str, Any]:
    """Publish a partial asset pack from any behavior sheets or poses already present."""
    character_id = character["id"]
    source_path = _static_url_to_path(character["image_url"])
    output_dir = ASSET_ROOT / character_id
    output_dir.mkdir(parents=True, exist_ok=True)

    avatar = _prepare_pose_image(source_path)
    avatar_path = output_dir / "avatar.png"
    avatar.save(avatar_path)

    animations: dict[str, dict[str, Any]] = {}
    pose_sources: dict[str, dict[str, str]] = {
        "avatar": {"src": "avatar.png", "source": "confirmed_character"}
    }
    action_animation_map: dict[str, str] = {"idle": "idle"}

    for spec in ANIMATION_SPECS:
        model_frames = [
            output_dir / f"{spec.pose_name}_model_frame_{index}.png"
            for index in range(1, spec.frame_count + 1)
        ]
        model_sheet = output_dir / f"{spec.pose_name}_model_sheet.png"
        model_pose = output_dir / f"{spec.pose_name}_model_pose.png"
        existing_pose = output_dir / f"{spec.pose_name}_pose.png"
        frame_names: list[str] = []

        if all(path.exists() for path in model_frames):
            frames = [_prepare_pose_image(path) for path in model_frames]
            source_label = "generated_behavior_frame_sequence"
        elif model_sheet.exists():
            frames = _frames_from_sheet(model_sheet, spec.frame_count)
            source_label = "generated_behavior_frames"
        elif model_pose.exists():
            pose = _prepare_pose_image(model_pose)
            frames = _frames_for_animation(spec.name, pose)
            source_label = "generated_behavior_pose"
        elif spec.name == "idle":
            pose_path = existing_pose if existing_pose.exists() else avatar_path
            pose = _prepare_pose_image(pose_path)
            frames = _frames_for_animation(spec.name, pose)
            source_label = "confirmed_character_fallback"
        else:
            continue

        saved_pose = output_dir / f"{spec.name}_pose.png"
        pose = frames[0] if frames else avatar.copy()
        pose.save(saved_pose)
        frame_names = _save_frame_sequence(output_dir, spec.name, frames)
        gif_path = output_dir / f"{spec.name}.gif"
        existing_gif_is_current = (
            gif_path.exists()
            and source_label == "generated_behavior_frame_sequence"
            and gif_path.stat().st_mtime_ns >= max(path.stat().st_mtime_ns for path in model_frames)
        )
        if not existing_gif_is_current:
            _save_gif(gif_path, frames, spec.duration)
        animations[spec.name] = {
            "type": "gif",
            "src": f"{spec.name}.gif",
            "pose": saved_pose.name,
            "frames": frame_names,
        }
        pose_sources[spec.name] = {
            "src": saved_pose.name,
            "source": source_label,
            "prompt": spec.prompt,
        }
        action_animation_map[spec.name] = spec.name

    manifest = {
        "character_id": character_id,
        "format": "behavior-frame-gif-partial",
        "generation_status": "partial_ready",
        "canvas": {"width": CANVAS_SIZE, "height": CANVAS_SIZE, "background": "transparent"},
        "anchor": {"x": CANVAS_SIZE // 2, "y": 228},
        "source_image_url": character["image_url"],
        "avatar": "avatar.png",
        "pose_sources": pose_sources,
        "animations": animations,
        "action_animation_map": action_animation_map,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "desktop_pet_manifest_url": f"/static/desktop_pet_assets/{character_id}/manifest.json",
        "desktop_pet_asset_dir": f"/static/desktop_pet_assets/{character_id}",
        "desktop_pet_avatar_url": f"/static/desktop_pet_assets/{character_id}/avatar.png",
        "published_animation_count": len(animations),
        "published_animations": sorted(animations),
    }
