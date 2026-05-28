"""Wan image-to-video desktop pet animation helpers."""

from __future__ import annotations

import os
from http import HTTPStatus
from pathlib import Path
from typing import Sequence
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from PIL import Image

from desktop_pet_assets import _prepare_pose_image_from_image, _save_gif


PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"
DEFAULT_WAN_I2V_MODEL = "wan2.2-i2v-plus"
DEFAULT_DASHSCOPE_BASE_HTTP_API_URL = "https://dashscope.aliyuncs.com/api/v1"

load_dotenv(PROJECT_ROOT / ".env")

GREEN_SCREEN_CONTRACT = (
    "背景必须是纯绿色 #00FF00，角色之外只能出现纯绿色背景。"
    "不要添加文字、场景、地面、阴影、反光、渐变、光晕或额外角色。"
)


def static_url_to_public_url(image_url: str) -> str:
    public_base_url = os.getenv("PET_AGENT_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_base_url:
        raise ValueError("使用 Wan 图生视频需要设置 PET_AGENT_PUBLIC_BASE_URL，让 Wan 能访问基础形象图。")
    clean_url = image_url.split("?", 1)[0]
    if not clean_url.startswith("/static/"):
        raise ValueError("Wan 图生视频目前只支持本地 /static/ 形象图。")
    return urljoin(public_base_url + "/", clean_url.lstrip("/"))


def create_green_screen_reference(image_url: str, output_dir: Path) -> str:
    source_path = PROJECT_ROOT / image_url.split("?", 1)[0].lstrip("/")
    if not source_path.exists():
        raise ValueError("Wan 绿背参考图源文件不存在。")
    with Image.open(source_path) as source:
        rgba = source.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (0, 255, 0, 255))
    background.alpha_composite(rgba)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "wan_green_reference.png"
    background.convert("RGB").save(output_path)
    relative = "/" + output_path.relative_to(PROJECT_ROOT).as_posix()
    return relative


def wan_prompt_for_animation(animation_name: str) -> str:
    if animation_name == "idle":
        return (
            "保持参考图角色身份、像素画风、服装颜色和完整坐姿主体。"
            "生成一个桌宠待机短视频：角色坐着不移动位置，下半身和底部锚点固定，"
            "只有上半身轻轻左右摇晃，动作非常轻柔、循环自然。"
            f"首帧和尾帧一致，适合无缝循环。{GREEN_SCREEN_CONTRACT}"
        )
    if animation_name == "walk_right":
        action_prompt = (
            "生成向右移动的动作，角色面向右侧，第一帧就必须是符合物种设定的移动姿势。"
            "只保留角色身份、颜色和画风，不要保留参考图里的坐姿、抱东西姿势、手部拿东西姿势或蜷缩姿势。"
            "角色必须用符合自身身体结构的方式移动，不要坐着滑动、不要原地保持坐姿。"
            "如果角色是人形或有人形手臂，手臂自然下垂并随步伐轻微摆动，不要端起或僵硬抬手；"
            "如果角色是四足动物，就按正常四足动物步态运动，不要添加人类手臂或人腿；"
            "如果角色是章鱼、鱿鱼、蜗牛、蛞蝓或其他软体动物，就不要做人类或哺乳动物步态，"
            "必须保留柔软身体和腕足/触手，用腕足交替支撑爬行、贴地蠕动或轻轻滑行前进；"
            "如果角色是章鱼或触手生物，就保留触手，不要添加人类腿、脚、鞋或手；"
            "如果角色是鱼类，就用尾巴和尾鳍左右摆动的游动方式前进，身体轻微摆动，不要添加腿、脚或走路步态。"
            "步行动作清晰，身体整体位置稳定，适合桌宠在 Swift 窗口中整体移动。"
        )
    elif animation_name == "walk_left":
        action_prompt = (
            "生成向左移动的动作，角色面向左侧，第一帧就必须是符合物种设定的移动姿势。"
            "只保留角色身份、颜色和画风，不要保留参考图里的坐姿、抱东西姿势、手部拿东西姿势或蜷缩姿势。"
            "角色必须用符合自身身体结构的方式移动，不要坐着滑动、不要原地保持坐姿。"
            "如果角色是人形或有人形手臂，手臂自然下垂并随步伐轻微摆动，不要端起或僵硬抬手；"
            "如果角色是四足动物，就按正常四足动物步态运动，不要添加人类手臂或人腿；"
            "如果角色是章鱼、鱿鱼、蜗牛、蛞蝓或其他软体动物，就不要做人类或哺乳动物步态，"
            "必须保留柔软身体和腕足/触手，用腕足交替支撑爬行、贴地蠕动或轻轻滑行前进；"
            "如果角色是章鱼或触手生物，就保留触手，不要添加人类腿、脚、鞋或手；"
            "如果角色是鱼类，就用尾巴和尾鳍左右摆动的游动方式前进，身体轻微摆动，不要添加腿、脚或走路步态。"
            "步行动作清晰，身体整体位置稳定，适合桌宠在 Swift 窗口中整体移动。"
        )
    elif animation_name == "sleep":
        action_prompt = "生成角色睡眠呼吸动作，角色安静睡着，身体轻微起伏。"
    elif animation_name == "happy":
        action_prompt = "生成角色轻轻开心的动作，眼神变亮，表情自然开心，头上冒开心泡泡。"
    else:
        action_prompt = f"生成桌宠动作短视频：{animation_name}，动作清晰但位置稳定。首帧和尾帧一致，适合无缝循环。{GREEN_SCREEN_CONTRACT}"
    return (
        "保持参考图角色身份、像素画风、服装颜色和完整主体。"
        f"{action_prompt}"
        "首帧和尾帧一致，适合无缝循环和转成透明 GIF。"
        f"{GREEN_SCREEN_CONTRACT}"
    )


def generate_wan_video_url(
    *,
    image_url: str,
    prompt: str,
    model: str | None = None,
) -> str:
    try:
        import dashscope
        from dashscope import VideoSynthesis
    except ImportError as exc:
        raise ValueError("缺少 dashscope 依赖，请先安装 requirements.txt。") from exc

    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("WAN_KEY")
    if not api_key:
        raise ValueError("缺少 DASHSCOPE_API_KEY 或 WAN_KEY，无法调用 Wan 图生视频。")
    dashscope.api_key = api_key

    dashscope.base_http_api_url = os.getenv(
        "DASHSCOPE_BASE_HTTP_API_URL",
        DEFAULT_DASHSCOPE_BASE_HTTP_API_URL,
    )
    rsp = VideoSynthesis.async_call(
        model=model or os.getenv("WAN_I2V_MODEL", DEFAULT_WAN_I2V_MODEL),
        prompt=prompt,
        img_url=image_url,
    )
    if rsp.status_code != HTTPStatus.OK:
        raise ValueError(f"Wan 图生视频任务创建失败：{rsp.status_code} {rsp.code} {rsp.message}")

    rsp = VideoSynthesis.wait(rsp)
    if rsp.status_code != HTTPStatus.OK:
        raise ValueError(f"Wan 图生视频任务失败：{rsp.status_code} {rsp.code} {rsp.message}")

    video_url = getattr(rsp.output, "video_url", None)
    if not video_url:
        raise ValueError("Wan 图生视频完成但没有返回 video_url。")
    return video_url


def download_video(video_url: str, output_path: Path) -> Path:
    response = requests.get(video_url, timeout=120)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path


def _iter_video_frames(video_path: Path):
    try:
        import imageio.v3 as iio
    except ImportError as exc:
        raise ValueError("缺少 imageio/imageio-ffmpeg 依赖，无法从 Wan 视频抽帧。") from exc
    return iio.imiter(video_path, plugin="FFMPEG")


def _remove_green_screen(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            green_distance = abs(r - 0) + abs(g - 255) + abs(b - 0)
            green_dominance = g - max(r, b)
            if green_distance <= 170 or (g >= 120 and green_dominance >= 45):
                pixels[x, y] = (r, g, b, 0)
            elif green_dominance > 12:
                cleaned_g = max(r, b, min(g, int((r + b) / 2) + 18))
                pixels[x, y] = (r, cleaned_g, b, a)
    return rgba


def video_to_gif(
    *,
    video_path: Path,
    gif_path: Path,
    frame_paths: Sequence[Path],
    fps: float = 8.0,
    duration_ms: int = 160,
    max_frames: int | None = None,
) -> list[Path]:
    frames = []
    saved_source_frames = []
    frame_interval = max(1, int(24 / fps))
    for index, frame in enumerate(_iter_video_frames(video_path), start=1):
        if index == 1 or (index - 1) % frame_interval == 0:
            image = Image.fromarray(frame).convert("RGBA")
            prepared = _prepare_pose_image_from_image(_remove_green_screen(image))
            frames.append(prepared)
            if len(saved_source_frames) < len(frame_paths):
                saved_source_frames.append(prepared)
        if max_frames is not None and len(frames) >= max_frames:
            break

    if not frames:
        raise ValueError("Wan 视频没有抽取到可用帧。")
    while len(saved_source_frames) < len(frame_paths):
        saved_source_frames.append(frames[-1].copy())

    saved_paths = []
    for path, frame in zip(frame_paths, saved_source_frames):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.save(path)
        saved_paths.append(path)
    _save_gif(gif_path, frames, duration=duration_ms)
    return saved_paths


def generate_wan_animation_gif(
    *,
    image_url: str,
    animation_name: str,
    output_dir: Path,
    frame_count: int,
    duration_ms: int,
) -> list[Path]:
    green_reference_url = create_green_screen_reference(image_url, output_dir)
    public_image_url = static_url_to_public_url(green_reference_url)
    prompt = wan_prompt_for_animation(animation_name)
    video_url = generate_wan_video_url(image_url=public_image_url, prompt=prompt)
    video_path = output_dir / f"{animation_name}_wan_video.mp4"
    download_video(video_url, video_path)
    frame_paths = [output_dir / f"{animation_name}_model_frame_{index}.png" for index in range(1, frame_count + 1)]
    return video_to_gif(
        video_path=video_path,
        gif_path=output_dir / f"{animation_name}.gif",
        frame_paths=frame_paths,
        fps=float(os.getenv("WAN_GIF_FPS", "12")),
        duration_ms=duration_ms,
        max_frames=None,
    )
