"""
Minimal Telegram Bot entrypoint for the pet agent.

This process receives Telegram button/text events and calls the local FastAPI backend.
Slash commands are kept only as debug/bootstrap fallbacks.
"""

import os
import json
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from diagnostics import log_event, log_exception, new_trace_id
from pet_runtime_controller import controller_from_env
from pet_status_service import format_action_reply, format_pet_status


load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_BASE_URL = os.getenv("PET_AGENT_API_URL", "http://127.0.0.1:8000")
DEFAULT_PET_ID = os.getenv("PET_AGENT_DEFAULT_PET_ID", "")
PROJECT_ROOT = Path(__file__).resolve().parent


SET_FIELD_MAP = {
    "name": "name",
    "species": "species",
    "personality": "personality",
    "owner_call": "owner_call_name",
    "mode": "pet_mode",
}

PENDING_SET_FIELDS: dict[str, str] = {}
PENDING_AVATAR_FLOWS: dict[str, dict[str, Any]] = {}
RUNTIME_CONTROLLER = controller_from_env(PROJECT_ROOT)


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": data} for text, data in row]
            for row in rows
        ]
    }


SETTINGS_MENU = inline_keyboard(
    [
        [("设置名字", "prompt_set:name"), ("主人称呼", "prompt_set:owner_call")],
        [("甜甜", "set:personality:sweet"), ("酷酷", "set:personality:cool")],
        [("活泼", "set:personality:energetic"), ("温柔", "set:personality:gentle")],
        [("电子宠物", "set:mode:virtual"), ("真实宠物", "set:mode:real")],
        [("猫", "set:species:cat"), ("狗", "set:species:dog"), ("其他", "set:species:other")],
        [("定制形象", "set:avatar"), ("返回主菜单", "menu")],
    ]
)

MAIN_REPLY_KEYBOARD = {
    "keyboard": [
        [{"text": "查看状态"}, {"text": "桌面陪伴"}],
        [{"text": "宠物列表"}],
        [{"text": "设置资料"}, {"text": "定制形象"}],
        [{"text": "喂饭"}, {"text": "加水"}, {"text": "陪玩"}],
        [{"text": "摸摸"}, {"text": "清洁"}, {"text": "哄睡"}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}

ACTION_BUTTON_MAP = {
    "喂饭": "feed",
    "加水": "refill",
    "陪玩": "play",
    "摸摸": "pet",
    "清洁": "clean",
    "哄睡": "lullaby",
}

ACTION_LABELS = {
    "feed": "喂饭",
    "refill": "加水",
    "play": "陪玩",
    "pet": "摸摸",
    "clean": "清洁",
    "lullaby": "哄睡",
}

MAIN_INLINE_MENU = inline_keyboard(
    [
        [("桌面陪伴", "desktop"), ("查看状态", "status")],
        [("定制形象", "set:avatar"), ("设置资料", "settings")],
        [("喂饭", "act:feed"), ("加水", "act:refill"), ("陪玩", "act:play")],
        [("摸摸", "act:pet"), ("清洁", "act:clean"), ("哄睡", "act:lullaby")],
    ]
)

AVATAR_STYLE_PRESETS = {
    "octopus": "章鱼宠物，2D 像素风，单个正立角色，保留参考图的主色和气质，适合桌面宠物。",
    "cat": "猫猫宠物，2D 像素风，单个正立角色，保留参考图的主色和气质，适合桌面宠物。",
    "fox": "狐狸宠物，2D 像素风，单个正立角色，保留参考图的主色和气质，适合桌面宠物。",
    "custom": "",
}


def telegram_api(method: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=payload or {},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException:
        raise RuntimeError(f"Telegram {method} failed") from None
    return response.json()


def send_message(
    chat_id: str,
    text: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    telegram_api(
        "sendMessage",
        payload,
    )


def send_photo(
    chat_id: str,
    photo_url: str,
    caption: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> None:
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    telegram_api("sendPhoto", payload)


def _local_static_path(static_url: str) -> Optional[Path]:
    clean = static_url.split("?", 1)[0]
    if clean.startswith(API_BASE_URL.rstrip("/")):
        clean = clean.removeprefix(API_BASE_URL.rstrip("/"))
    if not clean.startswith("/static/"):
        return None
    path = (PROJECT_ROOT / clean.removeprefix("/")).resolve()
    static_root = (PROJECT_ROOT / "static").resolve()
    if static_root not in path.parents:
        return None
    return path if path.exists() else None


def send_local_photo(
    chat_id: str,
    static_url: str,
    caption: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> None:
    image_path = _local_static_path(static_url)
    if image_path is None:
        send_photo(chat_id, _absolute_api_url(static_url), caption, reply_markup)
        return

    data: dict[str, str] = {
        "chat_id": chat_id,
        "caption": caption,
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    try:
        with image_path.open("rb") as file:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data=data,
                files={"photo": (image_path.name, file)},
                timeout=60,
            )
            response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Telegram sendPhoto failed: {exc}") from None


def send_chat_action(chat_id: str, action: str = "typing") -> None:
    try:
        telegram_api("sendChatAction", {"chat_id": chat_id, "action": action})
    except RuntimeError:
        pass


def answer_callback(callback_query_id: str) -> None:
    telegram_api("answerCallbackQuery", {"callback_query_id": callback_query_id})


def configure_bot_ui() -> None:
    """Hide slash commands and refresh the persistent button keyboard."""
    telegram_api("deleteMyCommands")
    if ALLOWED_CHAT_ID:
        send_main_menu(ALLOWED_CHAT_ID)


def get_default_pet_id() -> int:
    if DEFAULT_PET_ID:
        return int(DEFAULT_PET_ID)

    response = requests.get(f"{API_BASE_URL}/pets", timeout=10)
    response.raise_for_status()
    pets = response.json()
    if not pets:
        raise RuntimeError("No pet exists yet. Create one before using settings.")
    virtual_pet = next((pet for pet in pets if pet.get("pet_mode") == "virtual"), pets[0])
    return int(virtual_pet["id"])


def update_default_pet(field: str, value: str) -> dict[str, Any]:
    pet_id = get_default_pet_id()
    response = requests.patch(
        f"{API_BASE_URL}/pets/{pet_id}",
        json={SET_FIELD_MAP[field]: value.strip()},
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return response.json()


def send_main_menu(chat_id: str) -> None:
    send_message(chat_id, "Pet Live Agent 已打开。底部键盘已刷新。", reply_markup=MAIN_REPLY_KEYBOARD)
    send_message(chat_id, "常用操作", reply_markup=MAIN_INLINE_MENU)


def send_settings_menu(chat_id: str) -> None:
    send_message(chat_id, "要设置哪一项？", reply_markup=SETTINGS_MENU)


def handle_status_command(chat_id: str) -> None:
    pet_id = get_default_pet_id()

    pet_response = requests.get(f"{API_BASE_URL}/pets", timeout=10)
    pet_response.raise_for_status()
    pets = pet_response.json()
    pet = next((item for item in pets if int(item["id"]) == pet_id), None)
    if not pet:
        send_message(chat_id, f"找不到默认宠物：{pet_id}")
        return
    if pet.get("pet_mode") != "virtual":
        send_message(chat_id, "这只宠物不是电子宠物，暂时没有实时状态面板。")
        return

    snapshot_response = requests.get(f"{API_BASE_URL}/virtual-pets/{pet_id}", timeout=10)
    snapshot_response.raise_for_status()
    stats_response = requests.get(
        f"{API_BASE_URL}/pets/{pet_id}/stats",
        params={"range": "day"},
        timeout=10,
    )
    stats_response.raise_for_status()

    send_message(
        chat_id,
        format_pet_status(
            pet=pet,
            snapshot=snapshot_response.json(),
            today_stats=stats_response.json(),
        ),
    )


def handle_pets_command(chat_id: str) -> None:
    response = requests.get(f"{API_BASE_URL}/pets", timeout=10)
    response.raise_for_status()
    pets = response.json()
    lines = [
        f"{pet['id']}: {pet['name']} ({pet['pet_mode']}, {pet['personality']})"
        for pet in pets
    ]
    send_message(chat_id, "\n".join(lines) if lines else "还没有宠物。")


def handle_desktop_companion(chat_id: str) -> None:
    result = RUNTIME_CONTROLLER.launch_desktop_companion(chat_id=chat_id)
    if result.ok:
        send_message(
            chat_id,
            f"{result.message}\n\n调试编号：{result.trace_id}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return

    send_message(
        chat_id,
        f"{result.message}\n调试编号：{result.trace_id}" if "调试编号" not in result.message else result.message,
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def start_avatar_flow(chat_id: str) -> None:
    trace_id = new_trace_id("avatar")
    PENDING_AVATAR_FLOWS[chat_id] = {"step": "await_photo", "trace_id": trace_id}
    log_event("avatar_flow_started", trace_id, chat_id=chat_id)
    send_message(
        chat_id,
        f"把参考图发给我。收到后我会再问你想要的宠物形象风格；先只生成预览，等你确认后才会生成桌宠素材包。\n\n调试编号：{trace_id}",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def _content_type_from_telegram_path(file_path: str, fallback: str) -> tuple[str, str]:
    suffix = os.path.splitext(file_path.split("?", 1)[0])[1].lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg", ".jpg"
    if suffix == ".png":
        return "image/png", ".png"
    if suffix == ".webp":
        return "image/webp", ".webp"
    if fallback in {"image/jpeg", "image/png", "image/webp"}:
        extension = ".jpg" if fallback == "image/jpeg" else f".{fallback.rsplit('/', 1)[1]}"
        return fallback, extension
    return "image/jpeg", ".jpg"


def _download_telegram_file(file_id: str) -> tuple[bytes, str, str]:
    file_info = telegram_api("getFile", {"file_id": file_id})
    file_path = (file_info.get("result") or {}).get("file_path")
    if not file_path:
        raise RuntimeError("Telegram 没有返回文件路径")
    response = requests.get(
        f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}",
        timeout=60,
    )
    response.raise_for_status()
    header_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    content_type, extension = _content_type_from_telegram_path(file_path, header_type)
    return response.content, content_type, extension


def _absolute_api_url(path: str) -> str:
    return f"{API_BASE_URL.rstrip('/')}{path}"


def handle_avatar_photo(chat_id: str, message: dict[str, Any]) -> bool:
    flow = PENDING_AVATAR_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "await_photo":
        return False

    photos = message.get("photo") or []
    document = message.get("document") or {}
    file_id = ""
    if photos:
        file_id = photos[-1]["file_id"]
    elif str(document.get("mime_type", "")).startswith("image/"):
        file_id = document.get("file_id", "")
    if not file_id:
        send_message(chat_id, "请发送一张图片作为参考。")
        return True

    try:
        image_bytes, content_type, extension = _download_telegram_file(file_id)
    except (RuntimeError, requests.RequestException) as exc:
        trace_id = flow.get("trace_id")
        log_exception("avatar_photo_download_failed", trace_id, exc, chat_id=chat_id)
        send_message(chat_id, f"图片读取失败。\n阶段：读取 Telegram 图片\n调试编号：{trace_id}\n错误：{exc}")
        return True
    trace_id = flow.get("trace_id")
    log_event(
        "avatar_photo_received",
        trace_id,
        chat_id=chat_id,
        bytes=len(image_bytes),
        content_type=content_type,
        extension=extension,
    )

    flow.update(
        {
            "step": "await_style",
            "image_bytes": image_bytes,
            "content_type": content_type,
            "extension": extension,
        }
    )
    send_message(
        chat_id,
        "收到参考图了。选一个方向，或直接发文字描述你想要的桌宠形象。",
        reply_markup=inline_keyboard(
            [
                [("章鱼宠物", "avatar_style:octopus"), ("猫猫宠物", "avatar_style:cat")],
                [("狐狸宠物", "avatar_style:fox"), ("自己描述", "avatar_style:custom")],
            ]
        ),
    )
    return True


def handle_avatar_style_text(chat_id: str, text: str) -> bool:
    flow = PENDING_AVATAR_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "await_style":
        return False
    if not text.strip():
        send_message(chat_id, "请描述一下想要的形象风格。")
        return True

    flow["step"] = "generating_preview"
    trace_id = flow.get("trace_id")
    log_event(
        "avatar_preview_generation_started",
        trace_id,
        chat_id=chat_id,
        content_type=flow.get("content_type"),
        extension=flow.get("extension"),
        style_length=len(text.strip()),
    )
    started_at = time.monotonic()
    send_message(
        chat_id,
        "开始生成形象预览。通常需要 30-90 秒；这一步只生成预览，不会生成桌宠素材包。\n\n"
        f"当前阶段：生成预览\n调试编号：{trace_id}",
    )
    send_chat_action(chat_id, "upload_photo")
    try:
        response = requests.post(
            f"{API_BASE_URL}/image-style",
            files={
                "image": (
                    f"telegram-reference{flow.get('extension', '.jpg')}",
                    flow["image_bytes"],
                    flow["content_type"],
                )
            },
            data={
                "style": text.strip(),
                "style_mode": "animal_pixel_2d",
            },
            timeout=180,
        )
        elapsed = round(time.monotonic() - started_at, 1)
        log_event(
            "avatar_preview_api_returned",
            trace_id,
            chat_id=chat_id,
            status_code=response.status_code,
            elapsed_seconds=elapsed,
        )
        if response.status_code >= 400:
            log_event(
                "avatar_preview_api_failed",
                trace_id,
                chat_id=chat_id,
                status_code=response.status_code,
                response_text=response.text[:1000],
            )
            raise RuntimeError(response.text)
        preview = response.json()
    except (RuntimeError, requests.RequestException) as exc:
        PENDING_AVATAR_FLOWS.pop(chat_id, None)
        log_exception("avatar_preview_generation_failed", trace_id, exc, chat_id=chat_id)
        send_message(
            chat_id,
            f"生成预览失败。\n阶段：生成形象预览\n调试编号：{trace_id}\n错误：{exc}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True

    flow.update({"step": "await_confirm", "preview": preview, "style": text.strip()})
    elapsed = round(time.monotonic() - started_at, 1)
    log_event(
        "avatar_preview_generation_succeeded",
        trace_id,
        chat_id=chat_id,
        image_url=preview.get("image_url"),
        style_mode=preview.get("style_mode"),
        elapsed_seconds=elapsed,
    )
    send_message(
        chat_id,
        f"预览生成好了，用时 {elapsed} 秒。现在发给你确认。",
    )
    send_local_photo(
        chat_id,
        preview["image_url"],
        "这是形象预览。确认后我才会生成桌宠素材包并设为当前宠物。",
        reply_markup=inline_keyboard(
            [
                [("确认并生成桌宠素材", "avatar:confirm")],
                [("重新开始", "avatar:restart"), ("取消", "avatar:cancel")],
            ]
        ),
    )
    return True


def confirm_avatar_flow(chat_id: str) -> None:
    flow = PENDING_AVATAR_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "await_confirm":
        send_message(chat_id, "当前没有等待确认的形象。", reply_markup=MAIN_REPLY_KEYBOARD)
        return

    preview = flow["preview"]
    trace_id = flow.get("trace_id")
    log_event("avatar_confirm_started", trace_id, chat_id=chat_id, preview=preview)
    started_at = time.monotonic()
    send_message(
        chat_id,
        "收到确认。现在开始生成桌宠素材包并绑定到当前宠物。\n\n"
        f"当前阶段：确认角色\n调试编号：{trace_id}",
    )
    send_chat_action(chat_id, "typing")
    try:
        character_response = requests.post(
            f"{API_BASE_URL}/characters",
            json={
                "image_url": preview["image_url"],
                "style_mode": preview["style_mode"],
                "description": flow.get("style", "Telegram custom avatar"),
            },
            timeout=30,
        )
        if character_response.status_code >= 400:
            log_event(
                "avatar_character_create_failed",
                trace_id,
                chat_id=chat_id,
                status_code=character_response.status_code,
                response_text=character_response.text[:1000],
            )
            raise RuntimeError(character_response.text)
        character = character_response.json()
        log_event(
            "avatar_character_created",
            trace_id,
            chat_id=chat_id,
            character_id=character.get("id"),
            elapsed_seconds=round(time.monotonic() - started_at, 1),
        )
        send_message(
            chat_id,
            "角色已确认。继续生成 idle / walk / sleep / happy / work 等桌宠动画素材。",
        )
        send_chat_action(chat_id, "typing")

        assets_response = requests.post(
            f"{API_BASE_URL}/characters/{character['id']}/desktop-assets",
            timeout=120,
        )
        if assets_response.status_code >= 400:
            log_event(
                "avatar_assets_create_failed",
                trace_id,
                chat_id=chat_id,
                status_code=assets_response.status_code,
                response_text=assets_response.text[:1000],
            )
            raise RuntimeError(assets_response.text)
        character = assets_response.json()
        log_event(
            "avatar_assets_created",
            trace_id,
            chat_id=chat_id,
            character_id=character.get("id"),
            manifest=character.get("desktop_pet_manifest_url"),
            elapsed_seconds=round(time.monotonic() - started_at, 1),
        )
        send_message(chat_id, "桌宠素材包已生成。最后一步：绑定到当前宠物。")
        send_chat_action(chat_id, "typing")

        pet_id = get_default_pet_id()
        pets_response = requests.get(f"{API_BASE_URL}/pets", timeout=10)
        pets_response.raise_for_status()
        pet = next(
            (item for item in pets_response.json() if int(item["id"]) == pet_id),
            None,
        )
        profile = {}
        if pet and pet.get("profile_json"):
            import json

            profile = json.loads(pet["profile_json"] or "{}")
        profile.update(
            {
                "avatar_image_url": character["image_url"],
                "character_id": character["id"],
                "desktop_pet_manifest_url": character.get("desktop_pet_manifest_url"),
                "desktop_pet_asset_dir": character.get("desktop_pet_asset_dir"),
                "desktop_pet_avatar_url": character.get("desktop_pet_avatar_url"),
            }
        )
        update_response = requests.patch(
            f"{API_BASE_URL}/pets/{pet_id}",
            json={"profile": profile},
            timeout=30,
        )
        if update_response.status_code >= 400:
            log_event(
                "avatar_pet_bind_failed",
                trace_id,
                chat_id=chat_id,
                status_code=update_response.status_code,
                response_text=update_response.text[:1000],
            )
            raise RuntimeError(update_response.text)
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        log_exception("avatar_confirm_failed", trace_id, exc, chat_id=chat_id)
        send_message(
            chat_id,
            f"确认失败。\n阶段：生成素材并绑定宠物\n调试编号：{trace_id}\n错误：{exc}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return

    PENDING_AVATAR_FLOWS.pop(chat_id, None)
    log_event(
        "avatar_confirm_succeeded",
        trace_id,
        chat_id=chat_id,
        character_id=character.get("id"),
        manifest=character.get("desktop_pet_manifest_url"),
        elapsed_seconds=round(time.monotonic() - started_at, 1),
    )
    send_message(
        chat_id,
        f"确认好了。我已经生成桌宠素材包，并设为当前宠物形象。\n\n调试编号：{trace_id}",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def handle_action_button(chat_id: str, action: str) -> None:
    pet_id = get_default_pet_id()
    response = requests.post(
        f"{API_BASE_URL}/virtual-pets/{pet_id}/actions",
        json={"action": action},
        timeout=20,
    )
    if response.status_code >= 400:
        send_message(
            chat_id,
            f"{ACTION_LABELS.get(action, action)}失败：{response.text}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return

    result = response.json()
    pet_response = requests.get(f"{API_BASE_URL}/pets", timeout=10)
    pet_response.raise_for_status()
    pets = pet_response.json()
    pet = next((item for item in pets if int(item["id"]) == pet_id), {"name": "宠物"})
    event_result = result.get("event_result") or {}
    generated_message = (event_result.get("message") or {}).get("message")
    send_message(
        chat_id,
        format_action_reply(
            pet=pet,
            action=action,
            snapshot=result["snapshot"],
            generated_message=generated_message or "",
        ),
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def handle_pending_text(chat_id: str, text: str) -> bool:
    field = PENDING_SET_FIELDS.pop(chat_id, None)
    if not field:
        return False

    try:
        pet = update_default_pet(field, text)
        send_message(
            chat_id,
            f"设置好啦：{pet['name']} 的 {field} 已更新。",
            reply_markup=SETTINGS_MENU,
        )
    except RuntimeError as exc:
        send_message(chat_id, f"设置失败：{exc}", reply_markup=SETTINGS_MENU)
    return True


def handle_callback(callback_query: dict[str, Any]) -> None:
    callback_id = str(callback_query.get("id", ""))
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        return

    if callback_id:
        answer_callback(callback_id)

    data = callback_query.get("data", "")
    if data == "menu":
        send_main_menu(chat_id)
        return
    if data == "settings":
        send_settings_menu(chat_id)
        return
    if data == "status":
        handle_status_command(chat_id)
        return
    if data == "pets":
        handle_pets_command(chat_id)
        return
    if data == "desktop":
        handle_desktop_companion(chat_id)
        return
    if data.startswith("prompt_set:"):
        field = data.split(":", 1)[1]
        PENDING_SET_FIELDS[chat_id] = field
        send_message(chat_id, f"请输入新的 {field}。")
        return
    if data == "set:avatar":
        start_avatar_flow(chat_id)
        return
    if data == "avatar:confirm":
        confirm_avatar_flow(chat_id)
        return
    if data == "avatar:restart":
        start_avatar_flow(chat_id)
        return
    if data == "avatar:cancel":
        PENDING_AVATAR_FLOWS.pop(chat_id, None)
        send_message(chat_id, "已取消形象定制。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    if data.startswith("avatar_style:"):
        preset = data.split(":", 1)[1]
        prompt = AVATAR_STYLE_PRESETS.get(preset, "")
        if not prompt:
            send_message(chat_id, "直接发一句你想要的桌宠形象描述就行。")
            return
        handle_avatar_style_text(chat_id, prompt)
        return
    if data.startswith("set:"):
        _, field, value = data.split(":", 2)
        try:
            pet = update_default_pet(field, value)
            send_message(
                chat_id,
                f"设置好啦：{pet['name']} 的 {field} 已更新为 {value}。",
                reply_markup=SETTINGS_MENU,
            )
        except RuntimeError as exc:
            send_message(chat_id, f"设置失败：{exc}", reply_markup=SETTINGS_MENU)
        return
    if data.startswith("act:"):
        handle_action_button(chat_id, data.split(":", 1)[1])
        return

    send_message(chat_id, "这个按钮我还不会处理。", reply_markup=MAIN_REPLY_KEYBOARD)


def handle_message(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        return

    text = (message.get("text") or "").strip()
    if handle_avatar_photo(chat_id, message):
        return
    if handle_pending_text(chat_id, text):
        return
    if handle_avatar_style_text(chat_id, text):
        return

    if text.startswith("/start"):
        send_main_menu(chat_id)
    elif text == "查看状态":
        handle_status_command(chat_id)
    elif text == "桌面陪伴":
        handle_desktop_companion(chat_id)
    elif text == "宠物列表":
        handle_pets_command(chat_id)
    elif text == "设置资料":
        send_settings_menu(chat_id)
    elif text == "定制形象":
        start_avatar_flow(chat_id)
    elif text in ACTION_BUTTON_MAP:
        handle_action_button(chat_id, ACTION_BUTTON_MAP[text])
    else:
        send_message(chat_id, "可以直接点下方按钮操作。", reply_markup=MAIN_REPLY_KEYBOARD)


def poll_forever() -> None:
    offset: Optional[int] = None
    consecutive_poll_failures = 0
    while True:
        payload: dict[str, Any] = {"timeout": 25}
        if offset is not None:
            payload["offset"] = offset

        try:
            data = telegram_api("getUpdates", payload)
            consecutive_poll_failures = 0
        except RuntimeError as exc:
            consecutive_poll_failures += 1
            log_exception(
                "telegram_poll_failed",
                None,
                exc,
                consecutive_failures=consecutive_poll_failures,
            )
            time.sleep(min(30, 2 * consecutive_poll_failures))
            continue

        for update in data.get("result", []):
            offset = update["update_id"] + 1
            try:
                message = update.get("message")
                if message:
                    handle_message(message)
                callback_query = update.get("callback_query")
                if callback_query:
                    handle_callback(callback_query)
            except Exception as exc:
                chat_id = ""
                message = update.get("message") or {}
                callback_query = update.get("callback_query") or {}
                if message:
                    chat_id = str((message.get("chat") or {}).get("id", ""))
                elif callback_query:
                    chat_id = str(((callback_query.get("message") or {}).get("chat") or {}).get("id", ""))
                log_exception(
                    "telegram_update_handling_failed",
                    None,
                    exc,
                    update_id=update.get("update_id"),
                    chat_id=chat_id,
                )
                if chat_id:
                    try:
                        send_message(
                            chat_id,
                            "刚刚处理消息时出错了，但机器人还在运行。请重试一次；如果继续失败，把这条消息的时间发给我排查。",
                            reply_markup=MAIN_REPLY_KEYBOARD,
                        )
                    except Exception:
                        pass

        time.sleep(1)


if __name__ == "__main__":
    configure_bot_ui()
    poll_forever()
