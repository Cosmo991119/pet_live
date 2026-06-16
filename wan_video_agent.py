"""Wan video desktop pet animation helpers."""

from __future__ import annotations

import hashlib
import hmac
import mimetypes
import os
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Sequence
from urllib.parse import quote, urljoin, urlparse

import requests
from dotenv import load_dotenv
from PIL import Image

from desktop_pet_assets import _prepare_pose_image_from_image, _save_gif


PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"
DEFAULT_WAN_VIDEO_MODEL = "wan2.2-kf2v-flash"
DEFAULT_WAN_VIDEO_RESOLUTION = "720P"
DEFAULT_DASHSCOPE_BASE_HTTP_API_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_WAN_GIF_DURATION_MS = 5000
DEFAULT_CLOUDFLARE_R2_KEY_PREFIX = "agent-demo/wan"

load_dotenv(PROJECT_ROOT / ".env")

GREEN_SCREEN_CONTRACT = (
    "背景必须是纯绿色 #00FF00，角色之外只能出现纯绿色背景。"
    "不要添加文字、场景、地面、阴影、反光、渐变、光晕或额外角色。"
)


def _cloudflare_r2_config() -> dict[str, str] | None:
    keys = (
        "CLOUDFLARE_R2_ACCOUNT_ID",
        "CLOUDFLARE_R2_ACCESS_KEY_ID",
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
        "CLOUDFLARE_R2_BUCKET",
        "CLOUDFLARE_R2_PUBLIC_BASE_URL",
    )
    values = {key: os.getenv(key, "").strip() for key in keys}
    if not any(values.values()):
        return None
    missing = [key for key in keys if not values[key]]
    if missing:
        raise ValueError(f"Cloudflare R2 配置不完整，缺少：{', '.join(missing)}。")
    values["CLOUDFLARE_R2_KEY_PREFIX"] = os.getenv(
        "CLOUDFLARE_R2_KEY_PREFIX",
        DEFAULT_CLOUDFLARE_R2_KEY_PREFIX,
    ).strip().strip("/")
    values["CLOUDFLARE_R2_ACCOUNT_ID"] = _cloudflare_r2_account_id(
        values["CLOUDFLARE_R2_ACCOUNT_ID"]
    )
    return values


def _cloudflare_r2_account_id(account_or_endpoint: str) -> str:
    value = account_or_endpoint.strip().rstrip("/")
    if "://" in value:
        host = urlparse(value).netloc
        return host.split(".", 1)[0]
    if ".r2.cloudflarestorage.com" in value:
        return value.split(".", 1)[0]
    return value


def _aws_v4_signing_key(secret_key: str, date_stamp: str) -> bytes:
    date_key = hmac.new(f"AWS4{secret_key}".encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
    region_key = hmac.new(date_key, b"auto", hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def _cloudflare_r2_authorization_headers(
    *,
    access_key_id: str,
    secret_access_key: str,
    host: str,
    canonical_uri: str,
    content_type: str,
    payload: bytes,
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(payload).hexdigest()
    headers_to_sign = {
        "content-type": content_type,
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    signed_headers = ";".join(sorted(headers_to_sign))
    canonical_headers = "".join(f"{key}:{headers_to_sign[key]}\n" for key in sorted(headers_to_sign))
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{date_stamp}/auto/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _aws_v4_signing_key(secret_access_key, date_stamp),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    return {**headers_to_sign, "Authorization": authorization}


def _cloudflare_r2_public_url(public_base_url: str, object_key: str) -> str:
    return urljoin(public_base_url.strip().rstrip("/") + "/", quote(object_key, safe="/-_.~"))


def _cloudflare_r2_object_key(clean_url: str, payload: bytes, prefix: str) -> str:
    static_path = Path(clean_url.lstrip("/"))
    digest = hashlib.sha256(payload).hexdigest()[:16]
    hashed_name = f"{static_path.stem}-{digest}{static_path.suffix}"
    object_path = (static_path.parent / hashed_name).as_posix()
    return f"{prefix}/{object_path}" if prefix else object_path


def _upload_static_file_to_cloudflare_r2(source_path: Path, clean_url: str, config: dict[str, str]) -> str:
    if not source_path.exists():
        raise ValueError("Cloudflare R2 上传源文件不存在。")
    payload = source_path.read_bytes()
    object_key = _cloudflare_r2_object_key(clean_url, payload, config["CLOUDFLARE_R2_KEY_PREFIX"])
    content_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    host = f"{config['CLOUDFLARE_R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    canonical_uri = "/" + quote(f"{config['CLOUDFLARE_R2_BUCKET']}/{object_key}", safe="/-_.~")
    endpoint = f"https://{host}{canonical_uri}"
    headers = _cloudflare_r2_authorization_headers(
        access_key_id=config["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        secret_access_key=config["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        host=host,
        canonical_uri=canonical_uri,
        content_type=content_type,
        payload=payload,
    )
    response = requests.put(endpoint, data=payload, headers=headers, timeout=60)
    response.raise_for_status()
    return _cloudflare_r2_public_url(config["CLOUDFLARE_R2_PUBLIC_BASE_URL"], object_key)


def static_url_to_public_url(image_url: str) -> str:
    clean_url = image_url.split("?", 1)[0]
    if clean_url.startswith(("https://", "http://")):
        return clean_url
    if not clean_url.startswith("/static/"):
        raise ValueError("Wan 图生视频目前只支持本地 /static/ 形象图。")

    r2_config = _cloudflare_r2_config()
    if r2_config is not None:
        return _upload_static_file_to_cloudflare_r2(PROJECT_ROOT / clean_url.lstrip("/"), clean_url, r2_config)

    public_base_url = os.getenv("PET_AGENT_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_base_url:
        raise ValueError("使用 Wan 图生视频需要设置 PET_AGENT_PUBLIC_BASE_URL，或配置 Cloudflare R2 公开桶。")
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
            "如果角色是章鱼、鱿鱼、鱼类、水母、海马、海豚、虾、蟹、海龟或其他海洋或水生动物，"
            "一律使用游动姿势，不要做贴地爬行、走路或哺乳动物步态；"
            "如果角色是章鱼、鱿鱼或其他腕足触手类海洋动物，必须使用游动漂移："
            "身体悬浮滑行，腕足像柔软飘带一样自然展开、收拢和波动，部分腕足向后轻轻扫动制造推进感；"
            "不要让腕足吸附地面或像脚一样交替走路。"
            "必须保留原本的腕足、触手、鱼鳍、尾巴或水生身体结构，用腕足、触手、鱼鳍、尾巴或身体波动表现前进。"
            "如果角色是鱼类，就用尾巴和尾鳍左右摆动的游动方式前进，身体轻微摆动，不要添加腿、脚或走路步态。"
            "不要添加人类腿、脚、鞋或手。移动动作清晰，身体整体位置稳定，适合桌宠在 Swift 窗口中整体移动。"
        )
    elif animation_name == "walk_left":
        action_prompt = (
            "生成向左移动的动作，角色面向左侧，第一帧就必须是符合物种设定的移动姿势。"
            "只保留角色身份、颜色和画风，不要保留参考图里的坐姿、抱东西姿势、手部拿东西姿势或蜷缩姿势。"
            "角色必须用符合自身身体结构的方式移动，不要坐着滑动、不要原地保持坐姿。"
            "如果角色是人形或有人形手臂，手臂自然下垂并随步伐轻微摆动，不要端起或僵硬抬手；"
            "如果角色是四足动物，就按正常四足动物步态运动，不要添加人类手臂或人腿；"
            "如果角色是章鱼、鱿鱼、鱼类、水母、海马、海豚、虾、蟹、海龟或其他海洋或水生动物，"
            "一律使用游动姿势，不要做贴地爬行、走路或哺乳动物步态；"
            "如果角色是章鱼、鱿鱼或其他腕足触手类海洋动物，必须使用游动漂移："
            "身体悬浮滑行，腕足像柔软飘带一样自然展开、收拢和波动，部分腕足向后轻轻扫动制造推进感；"
            "不要让腕足吸附地面或像脚一样交替走路。"
            "必须保留原本的腕足、触手、鱼鳍、尾巴或水生身体结构，用腕足、触手、鱼鳍、尾巴或身体波动表现前进。"
            "如果角色是鱼类，就用尾巴和尾鳍左右摆动的游动方式前进，身体轻微摆动，不要添加腿、脚或走路步态。"
            "不要添加人类腿、脚、鞋或手。移动动作清晰，身体整体位置稳定，适合桌宠在 Swift 窗口中整体移动。"
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


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _wan_video_model(model: str | None) -> str:
    return model or os.getenv("WAN_VIDEO_MODEL", DEFAULT_WAN_VIDEO_MODEL)


def _is_kf2v_model(model: str) -> bool:
    return "kf2v" in model.lower()


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
    model_name = _wan_video_model(model)

    if _is_kf2v_model(model_name):
        try:
            rsp = VideoSynthesis.call(
                api_key=api_key,
                model=model_name,
                prompt=prompt,
                first_frame_url=image_url,
                last_frame_url=image_url,
                resolution=os.getenv("WAN_VIDEO_RESOLUTION", DEFAULT_WAN_VIDEO_RESOLUTION),
                prompt_extend=_env_bool("WAN_PROMPT_EXTEND", True),
            )
        except Exception as exc:
            raise ValueError(f"Wan 图生视频任务失败：{exc}") from exc
        if rsp.status_code != HTTPStatus.OK:
            raise ValueError(f"Wan 图生视频任务失败：{rsp.status_code} {rsp.code} {rsp.message}")
        video_url = getattr(rsp.output, "video_url", None)
        if not video_url:
            raise ValueError("Wan 图生视频完成但没有返回 video_url。")
        return video_url

    try:
        rsp = VideoSynthesis.async_call(
            model=model_name,
            prompt=prompt,
            img_url=image_url,
        )
    except Exception as exc:
        raise ValueError(f"Wan 图生视频任务创建失败：{exc}") from exc
    if rsp.status_code != HTTPStatus.OK:
        raise ValueError(f"Wan 图生视频任务创建失败：{rsp.status_code} {rsp.code} {rsp.message}")

    try:
        rsp = VideoSynthesis.wait(rsp)
    except Exception as exc:
        raise ValueError(f"Wan 图生视频任务失败：{exc}") from exc
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
    target_duration_ms: int | None = None,
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
    gif_frame_duration_ms: int | list[int] = duration_ms
    if target_duration_ms is not None:
        total_centiseconds = max(len(frames) * 2, round(target_duration_ms / 10))
        base_centiseconds = total_centiseconds // len(frames)
        extra_centiseconds = total_centiseconds % len(frames)
        gif_frame_duration_ms = [
            (base_centiseconds + (1 if index < extra_centiseconds else 0)) * 10
            for index in range(len(frames))
        ]
    _save_gif(gif_path, frames, duration=gif_frame_duration_ms)
    return saved_paths


def generate_wan_animation_gif(
    *,
    image_url: str,
    animation_name: str,
    output_dir: Path,
    frame_count: int,
    duration_ms: int,
    target_duration_ms: int | None = None,
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
        target_duration_ms=(
            target_duration_ms
            if target_duration_ms is not None
            else int(os.getenv("WAN_GIF_DURATION_MS", str(DEFAULT_WAN_GIF_DURATION_MS)))
        ),
        max_frames=None,
    )
