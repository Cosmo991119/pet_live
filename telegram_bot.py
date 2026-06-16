"""
Minimal Telegram Bot entrypoint for the pet agent.

This process receives Telegram button/text events and calls the local FastAPI backend.
Slash commands are kept only as debug/bootstrap fallbacks.
"""

import os
import json
import random
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from diagnostics import log_event, log_exception, new_trace_id
from desktop_pet_assets import BASIC_DESKTOP_ANIMATION_NAMES
from pet_message_agent import format_speaker_labeled_message
from pet_runtime_controller import controller_from_env
from pet_status_service import format_action_reply, format_pet_status


load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALLOWED_OWNER_CHAT_IDS = {
    chat_id.strip()
    for chat_id in os.getenv("TELEGRAM_ALLOWED_OWNER_CHAT_IDS", "").split(",")
    if chat_id.strip()
}
API_BASE_URL = os.getenv("PET_AGENT_API_URL", "http://127.0.0.1:8000")
DEFAULT_PET_ID = os.getenv("PET_AGENT_DEFAULT_PET_ID", "")
PROJECT_ROOT = Path(__file__).resolve().parent
PET_FRIEND_DAILY_MESSAGE_INTERVAL_SECONDS = int(
    os.getenv("PET_FRIEND_DAILY_MESSAGE_INTERVAL_SECONDS", "3600")
)
PET_FRIEND_DAILY_MESSAGE_COOLDOWN_SECONDS = int(
    os.getenv("PET_FRIEND_DAILY_MESSAGE_COOLDOWN_SECONDS", "86400")
)
PET_FRIEND_DAILY_MESSAGE_CHANCE = float(os.getenv("PET_FRIEND_DAILY_MESSAGE_CHANCE", "0.15"))
PET_FRIEND_DAILY_MESSAGE_MAX_PER_SCAN = int(
    os.getenv("PET_FRIEND_DAILY_MESSAGE_MAX_PER_SCAN", "1")
)
PET_FRIEND_MEMORY_SHARE_SUGGESTION_COOLDOWN_SECONDS = int(
    os.getenv("PET_FRIEND_MEMORY_SHARE_SUGGESTION_COOLDOWN_SECONDS", "21600")
)
PET_FRIEND_MEMORY_SHARE_SUGGESTION_CHANCE = float(
    os.getenv("PET_FRIEND_MEMORY_SHARE_SUGGESTION_CHANCE", "0.25")
)
ASSISTANT_DUE_SCAN_INTERVAL_SECONDS = int(
    os.getenv("PET_AGENT_ASSISTANT_DUE_SCAN_INTERVAL_SECONDS", "30")
)
PROACTIVE_TICKS_ENABLED = _env_bool("PET_AGENT_PROACTIVE_TICKS_ENABLED", True)
PROACTIVE_TICK_INTERVAL_SECONDS = _env_float(
    "PET_AGENT_PROACTIVE_TICK_INTERVAL_SECONDS",
    600,
)
PROACTIVE_TICK_MINUTES = _env_int("PET_AGENT_PROACTIVE_TICK_MINUTES", 10)
PROACTIVE_TICK_HTTP_TIMEOUT_SECONDS = 20

AVATAR_PREVIEW_PROGRESS_STAGES = [
    "收到设定，正在整理宠物形象线索",
    "正在生成轮廓和整体气质",
    "正在补充颜色、表情和特征",
    "正在检查是否适合做成桌宠",
    "预览快好了，正在保存结果",
]
AVATAR_STYLE_LOCK_RULE = (
    "固定使用精致 Q 版二次元像素艺术画风；透明背景；无地面、无倒影、无投影、无场景。"
    "只转换上传图片的画风，保留主体、姿势、服装、颜色和手持物，不套用旧宠物或动物化设定。"
)
AVATAR_PREVIEW_MAX_CONCURRENT = 1
AVATAR_PROGRESS_INTERVAL_SECONDS = 5
AVATAR_PROGRESS_HEARTBEAT_SECONDS = 30
AVATAR_PROGRESS_SLOW_SECONDS = 90
AVATAR_PROGRESS_TIMEOUT_SECONDS = 180
AVATAR_ASSET_GENERATION_TIMEOUT_SECONDS = 900
AVATAR_ASSET_ANIMATION_LABELS = {
    "idle": "待机",
    "relax": "放松",
    "walk_right": "向右走",
    "walk_left": "向左走",
    "sleep": "睡觉",
    "happy": "开心",
}
STICKER_PACK_SIZE = 12
MEMORY_PHOTO_PENDING_TTL_SECONDS = 30 * 60
PET_SPECIES_LABELS = {
    "cat": "猫",
    "dog": "狗",
    "other": "其他",
}
PET_PERSONALITY_LABELS = {
    "sweet": "甜甜",
    "cool": "酷酷",
    "energetic": "活泼",
    "gentle": "温柔",
}


SET_FIELD_MAP = {
    "name": "name",
    "species": "species",
    "personality": "personality",
    "owner_call": "owner_call_name",
    "mode": "pet_mode",
}

PENDING_SET_FIELDS: dict[str, dict[str, Any]] = {}
PENDING_AVATAR_FLOWS: dict[str, dict[str, Any]] = {}
PENDING_PET_FLOWS: dict[str, dict[str, Any]] = {}
PENDING_RELATIONSHIP_FLOWS: dict[str, dict[str, Any]] = {}
PENDING_FRIENDSHIP_INVITE_FLOWS: dict[str, dict[str, Any]] = {}
PENDING_FRIEND_MEMORY_SHARE_FLOWS: dict[str, dict[str, Any]] = {}
PENDING_MEMORY_PHOTO_FLOWS: dict[str, dict[str, Any]] = {}
CURRENT_PET_IDS: dict[str, int] = {}
OWNER_IDS_BY_CHAT: dict[str, int] = {}
OWNER_DISPLAY_NAMES_BY_CHAT: dict[str, str] = {}
FRIENDSHIP_DAILY_MESSAGE_LAST_SENT: dict[int, float] = {}
FRIENDSHIP_DAILY_MESSAGE_SCAN_LAST = 0.0
MEMORY_SHARE_SUGGESTION_LAST_BY_CHAT: dict[str, float] = {}
ASSISTANT_DUE_SCAN_LAST = 0.0
ASSISTANT_ACTIVE_CHATS: set[str] = set()
ACTIVE_PET_GROUP_CHATS: set[str] = set()
PET_GROUP_LAST_SPEAKER_IDS: dict[str, list[int]] = {}
ACTIVE_AVATAR_GENERATIONS: dict[str, object] = {}
AVATAR_GENERATION_LOCK = threading.Lock()
AVATAR_GENERATION_SEMAPHORE = threading.BoundedSemaphore(AVATAR_PREVIEW_MAX_CONCURRENT)
RUNTIME_CONTROLLER = controller_from_env(PROJECT_ROOT)

RELATIONSHIP_LABEL_OPTIONS: list[tuple[str, str]] = [
    ("爱接 TA 的话", "often_replies_to_target"),
    ("喜欢靠近 TA", "likes_staying_near_target"),
    ("在 TA 旁边很安静", "quiet_around_target"),
    ("常拉 TA 一起玩", "pulls_target_to_play"),
    ("会和 TA 保持距离", "keeps_distance_from_target"),
]

RELATIONSHIP_LABEL_TEXT = {
    key: text for text, key in RELATIONSHIP_LABEL_OPTIONS
}
RELATIONSHIP_EXPRESSION_COOLDOWN_SECONDS = {
    "often_replies_to_target": 180.0,
    "likes_staying_near_target": 300.0,
    "pulls_target_to_play": 360.0,
    "quiet_around_target": 600.0,
    "keeps_distance_from_target": 600.0,
}
RELATIONSHIP_EXPRESSION_COOLDOWNS: dict[tuple[int, int, str], float] = {}


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": data} for text, data in row]
            for row in rows
        ]
    }


SETTINGS_MENU = inline_keyboard(
    [
        [("打开宠物列表", "pets")],
        [("返回主菜单", "menu")],
    ]
)

MAIN_REPLY_KEYBOARD = {
    "keyboard": [
        [{"text": "查看状态"}, {"text": "桌面陪伴"}],
        [{"text": "宠物列表"}, {"text": "宠物关系"}],
        [{"text": "宠物好友"}, {"text": "宠物记忆"}],
        [{"text": "创建宠物"}, {"text": "小助手"}],
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

AVATAR_STYLE_PRESETS = {
    "octopus": "章鱼宠物，2D 像素风，单个正立角色，保留参考图的主色和气质，适合桌面宠物。",
    "cat": "猫猫宠物，2D 像素风，单个正立角色，保留参考图的主色和气质，适合桌面宠物。",
    "fox": "狐狸宠物，2D 像素风，单个正立角色，保留参考图的主色和气质，适合桌面宠物。",
    "custom": "",
}


def telegram_api(method: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    response: Optional[requests.Response] = None
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=payload or {},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = str(exc)
        if response is not None:
            detail = f"{response.status_code} {response.text[:300]}"
        raise RuntimeError(f"Telegram {method} failed: {detail}") from None
    return response.json()


def owner_scoping_enabled() -> bool:
    return bool(ALLOWED_OWNER_CHAT_IDS)


def is_chat_allowed(chat_id: str) -> bool:
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        return False
    if ALLOWED_OWNER_CHAT_IDS and chat_id not in ALLOWED_OWNER_CHAT_IDS:
        return False
    return True


def ensure_owner_id(chat_id: str, display_name: str = "") -> Optional[int]:
    if not owner_scoping_enabled():
        return None
    clean_name = str(display_name or "").strip()
    if chat_id in OWNER_IDS_BY_CHAT and not clean_name:
        return OWNER_IDS_BY_CHAT[chat_id]
    if (
        chat_id in OWNER_IDS_BY_CHAT
        and clean_name
        and OWNER_DISPLAY_NAMES_BY_CHAT.get(chat_id) == clean_name
    ):
        return OWNER_IDS_BY_CHAT[chat_id]
    response = requests.post(
        f"{API_BASE_URL}/owners/telegram",
        json={"telegram_chat_id": chat_id, "display_name": clean_name},
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    owner_id = int(response.json()["id"])
    OWNER_IDS_BY_CHAT[chat_id] = owner_id
    if clean_name:
        OWNER_DISPLAY_NAMES_BY_CHAT[chat_id] = clean_name
    return owner_id


def owner_params(chat_id: str) -> dict[str, int]:
    owner_id = ensure_owner_id(chat_id)
    return {"owner_id": owner_id} if owner_id is not None else {}


def owner_params_kwarg(chat_id: Optional[str]) -> dict[str, dict[str, int]]:
    if chat_id is None:
        return {}
    params = dict(owner_params(chat_id))
    return {"params": params} if params else {}


def owner_display_name_from_user(user: Optional[dict[str, Any]]) -> str:
    if not user:
        return ""
    parts = [
        str(user.get("first_name") or "").strip(),
        str(user.get("last_name") or "").strip(),
    ]
    full_name = " ".join(part for part in parts if part).strip()
    return full_name or str(user.get("username") or "").strip()


def remember_owner_display_name(chat_id: str, user: Optional[dict[str, Any]]) -> None:
    display_name = owner_display_name_from_user(user)
    if not display_name or not owner_scoping_enabled():
        return
    try:
        ensure_owner_id(chat_id, display_name=display_name)
    except (RuntimeError, requests.RequestException) as exc:
        log_exception("telegram_owner_display_name_update_failed", None, exc, chat_id=chat_id)


def api_get_pets(chat_id: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{API_BASE_URL}/pets",
        **owner_params_kwarg(chat_id),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def send_message(
    chat_id: str,
    text: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api(
        "sendMessage",
        payload,
    )


def _friendship_contacts_for_chat(
    chat_id: str,
    *,
    pet_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    owner_id = ensure_owner_id(chat_id)
    if owner_id is None:
        return []
    params: dict[str, int] = {"owner_id": owner_id}
    if pet_id is not None:
        params["pet_id"] = int(pet_id)
    response = requests.get(
        f"{API_BASE_URL}/pet-friendships",
        params=params,
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)

    contacts: list[dict[str, Any]] = []
    for friendship in response.json():
        try:
            if bool(friendship.get("muted")):
                continue
            owner_a_id = int(friendship.get("owner_a_id"))
            owner_b_id = int(friendship.get("owner_b_id"))
            if owner_a_id == int(owner_id):
                local_side = "a"
                friend_side = "b"
            elif owner_b_id == int(owner_id):
                local_side = "b"
                friend_side = "a"
            else:
                continue
            friend_chat_id = str(friendship.get(f"owner_{friend_side}_chat_id") or "").strip()
            if not friend_chat_id:
                continue
            contacts.append(
                {
                    "friendship_id": int(friendship["id"]),
                    "affinity": int(friendship.get("affinity") or 0),
                    "local_pet_id": int(friendship[f"pet_{local_side}_id"]),
                    "local_pet_name": str(friendship.get(f"pet_{local_side}_name") or "我家宠物"),
                    "local_owner_id": int(friendship[f"owner_{local_side}_id"]),
                    "local_owner_name": str(friendship.get(f"owner_{local_side}_name") or ""),
                    "local_owner_chat_id": str(friendship.get(f"owner_{local_side}_chat_id") or chat_id),
                    "friend_pet_id": int(friendship[f"pet_{friend_side}_id"]),
                    "friend_pet_name": str(friendship.get(f"pet_{friend_side}_name") or "好友宠物"),
                    "friend_owner_id": int(friendship[f"owner_{friend_side}_id"]),
                    "friend_owner_name": str(friendship.get(f"owner_{friend_side}_name") or ""),
                    "friend_owner_chat_id": friend_chat_id,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    contacts.sort(key=lambda item: (-int(item.get("affinity") or 0), item["friendship_id"]))
    return contacts


def _contact_label(contact: dict[str, Any]) -> str:
    return (
        str(contact.get("friend_owner_name") or "").strip()
        or str(contact.get("friend_pet_name") or "").strip()
        or str(contact.get("friend_owner_chat_id") or "").strip()
        or "好友"
    )


def _find_friendship_contact(
    chat_id: str,
    target: str,
    *,
    pet_id: Optional[int] = None,
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    contacts = _friendship_contacts_for_chat(chat_id, pet_id=pet_id)
    needle = target.strip().casefold()
    if not needle:
        return None, contacts

    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for contact in contacts:
        aliases = [
            str(contact.get("friend_owner_name") or ""),
            str(contact.get("friend_pet_name") or ""),
            str(contact.get("friend_owner_chat_id") or ""),
        ]
        normalized = [alias.strip().casefold() for alias in aliases if alias.strip()]
        if needle in normalized:
            exact.append(contact)
        elif any(needle in alias for alias in normalized):
            partial.append(contact)
    if len(exact) == 1:
        return exact[0], contacts
    if len(exact) > 1:
        return None, contacts
    if len(partial) == 1:
        return partial[0], contacts
    return None, contacts


def _friend_contact_help(contacts: list[dict[str, Any]]) -> str:
    if not contacts:
        return "当前宠物还没有可发送消息的好友。先通过「宠物好友」建立好友关系。"
    names = "、".join(_contact_label(contact) for contact in contacts[:6])
    return f"我没找到这个好友。现在可以指定：{names}"


def remove_reply_keyboard(chat_id: str, text: str = "正在刷新底部键盘。") -> dict[str, Any]:
    return send_message(
        chat_id,
        text,
        reply_markup={"remove_keyboard": True},
    )


def edit_message_text(
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api("editMessageText", payload)


def _telegram_message_id(response: dict[str, Any]) -> Optional[int]:
    try:
        return int(response["result"]["message_id"])
    except (KeyError, TypeError, ValueError):
        return None


def _progress_bar(step: int, total: int) -> str:
    done = max(0, min(step, total))
    return "▰" * done + "▱" * (total - done)


def format_avatar_progress_text(stage: str, trace_id: object, step: int, total: int = 5) -> str:
    return (
        f"{_progress_bar(step, total)} {step}/{total}\n"
        f"{stage}\n\n"
        "生成形象预览通常需要 30-90 秒，我会在这里更新进度。\n"
        f"当前阶段：生成预览\n调试编号：{trace_id}"
    )


def format_avatar_progress_heartbeat_text(trace_id: object, elapsed_seconds: float) -> str:
    elapsed = int(elapsed_seconds)
    if elapsed >= AVATAR_PROGRESS_TIMEOUT_SECONDS:
        status = "已经超过常规等待时间，我还在等生成接口返回；如果失败会在这里说明原因。"
    elif elapsed >= AVATAR_PROGRESS_SLOW_SECONDS:
        status = "这次比平时慢，我还在持续等待生成结果。"
    else:
        status = "预览仍在生成中，我还在等结果返回。"
    return (
        f"{_progress_bar(5, 5)} 5/5\n"
        f"{status}\n\n"
        f"已等待：{elapsed} 秒\n"
        "其他底部按钮仍然可以继续使用。\n"
        f"当前阶段：生成预览\n调试编号：{trace_id}"
    )


def format_avatar_busy_text(flow: dict[str, Any]) -> str:
    trace_id = flow.get("trace_id", "unknown")
    started_at = flow.get("started_at")
    elapsed = ""
    if isinstance(started_at, (int, float)):
        elapsed = f"\n已等待：{int(time.monotonic() - started_at)} 秒"
    return (
        "还在生成中。这只宠物的形象预览已经在生成中，我不会重复提交，避免把生成服务拖卡。\n"
        "我会继续更新上面的进度消息；你也可以先使用其他功能。"
        f"{elapsed}\n调试编号：{trace_id}"
    )


def format_avatar_failure_text(trace_id: object, error: object) -> str:
    error_text = str(error)
    if "insufficient_quota" in error_text or "used up your points" in error_text:
        reason = "图片生成额度不足，模型服务拒绝了这次请求。"
    elif "timed out" in error_text.lower() or "timeout" in error_text.lower():
        reason = "图片生成接口等待超时。"
    else:
        reason = error_text
    return (
        "生成预览失败。\n"
        "阶段：生成形象预览\n"
        f"原因：{reason}\n"
        f"调试编号：{trace_id}"
    )


def _avatar_flow_is_generating(flow: Optional[dict[str, Any]]) -> bool:
    return bool(flow and flow.get("step") in {"generating_preview", "revising_preview"})


def _acquire_avatar_generation_slot(chat_id: str, trace_id: object) -> bool:
    with AVATAR_GENERATION_LOCK:
        if chat_id in ACTIVE_AVATAR_GENERATIONS:
            return False
        if not AVATAR_GENERATION_SEMAPHORE.acquire(blocking=False):
            return False
        ACTIVE_AVATAR_GENERATIONS[chat_id] = trace_id
        return True


def _release_avatar_generation_slot(chat_id: str, trace_id: object) -> None:
    with AVATAR_GENERATION_LOCK:
        if ACTIVE_AVATAR_GENERATIONS.get(chat_id) != trace_id:
            return
        ACTIVE_AVATAR_GENERATIONS.pop(chat_id, None)
        AVATAR_GENERATION_SEMAPHORE.release()


def start_avatar_progress_updater(
    chat_id: str,
    message_id: Optional[int],
    trace_id: object,
    interval_seconds: float = AVATAR_PROGRESS_INTERVAL_SECONDS,
) -> threading.Event:
    stop_event = threading.Event()
    if message_id is None:
        return stop_event

    def _run() -> None:
        started_at = time.monotonic()
        last_heartbeat_at = started_at
        total = len(AVATAR_PREVIEW_PROGRESS_STAGES)
        for index, stage in enumerate(AVATAR_PREVIEW_PROGRESS_STAGES[1:], start=2):
            if stop_event.wait(interval_seconds):
                return
            send_chat_action(chat_id, "upload_photo")
            try:
                edit_message_text(
                    chat_id,
                    message_id,
                    format_avatar_progress_text(stage, trace_id, index, total),
                )
            except RuntimeError as exc:
                log_exception(
                    "avatar_progress_update_failed",
                    trace_id,
                    exc,
                    chat_id=chat_id,
                    step=index,
                )
        while not stop_event.wait(interval_seconds):
            send_chat_action(chat_id, "upload_photo")
            now = time.monotonic()
            if now - last_heartbeat_at < AVATAR_PROGRESS_HEARTBEAT_SECONDS:
                continue
            last_heartbeat_at = now
            try:
                edit_message_text(
                    chat_id,
                    message_id,
                    format_avatar_progress_heartbeat_text(trace_id, now - started_at),
                )
            except RuntimeError as exc:
                log_exception(
                    "avatar_progress_heartbeat_failed",
                    trace_id,
                    exc,
                    chat_id=chat_id,
                )

    threading.Thread(target=_run, daemon=True).start()
    return stop_event


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
    try:
        telegram_api("deleteMyCommands")
    except RuntimeError as exc:
        log_exception("telegram_command_cleanup_failed", None, exc)
    target_chat_ids = []
    if ALLOWED_CHAT_ID:
        target_chat_ids.append(ALLOWED_CHAT_ID)
    target_chat_ids.extend(sorted(ALLOWED_OWNER_CHAT_IDS))
    for chat_id in dict.fromkeys(target_chat_ids):
        try:
            send_main_menu(chat_id)
        except RuntimeError as exc:
            log_exception("telegram_menu_refresh_failed", None, exc, chat_id=chat_id)


def proactive_target_chat_ids() -> list[str]:
    """Return Telegram chats that may receive pet-initiated updates."""
    target_chat_ids: list[str] = []
    if ALLOWED_CHAT_ID:
        target_chat_ids.append(ALLOWED_CHAT_ID)
    target_chat_ids.extend(sorted(ALLOWED_OWNER_CHAT_IDS))
    target_chat_ids.extend(list(CURRENT_PET_IDS.keys()))
    return list(dict.fromkeys(chat_id for chat_id in target_chat_ids if chat_id))


def _generated_tick_message(result: dict[str, Any], pet: Optional[dict[str, Any]] = None) -> str:
    event_result = result.get("event_result") or {}
    message = event_result.get("message") or {}
    text = str(message.get("message") or "").strip()
    pet_name = str(
        event_result.get("pet_name")
        or message.get("pet_name")
        or (pet or {}).get("name")
        or ""
    ).strip()
    return format_speaker_labeled_message(text, pet_name).strip()


def _tick_virtual_pet_for_chat(
    chat_id: str,
    pet: dict[str, Any],
    tick_minutes: int,
) -> Optional[str]:
    params = dict(owner_params(chat_id))
    params["notify"] = "false"
    response = requests.post(
        f"{API_BASE_URL}/virtual-pets/{int(pet['id'])}/tick",
        params=params,
        json={"minutes": tick_minutes},
        timeout=PROACTIVE_TICK_HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return _generated_tick_message(response.json(), pet) or None


def proactive_tick_chat(chat_id: str, tick_minutes: int = PROACTIVE_TICK_MINUTES) -> dict[str, int]:
    """Advance all virtual pets for one chat and send generated event messages."""
    counts = {"pets": 0, "messages": 0}
    pets = [pet for pet in api_get_pets(chat_id) if pet.get("pet_mode") == "virtual"]
    for pet in pets:
        counts["pets"] += 1
        message = _tick_virtual_pet_for_chat(chat_id, pet, tick_minutes)
        if not message:
            continue
        send_message(chat_id, message, reply_markup=MAIN_REPLY_KEYBOARD)
        counts["messages"] += 1
        log_event(
            "proactive_virtual_pet_message_sent",
            None,
            chat_id=chat_id,
            pet_id=pet.get("id"),
        )
    return counts


def proactive_tick_virtual_pets_once(
    tick_minutes: int = PROACTIVE_TICK_MINUTES,
) -> dict[str, int]:
    """Run one proactive virtual-pet tick pass for configured Telegram chats."""
    totals = {"chats": 0, "pets": 0, "messages": 0}
    for chat_id in proactive_target_chat_ids():
        totals["chats"] += 1
        try:
            counts = proactive_tick_chat(chat_id, tick_minutes=tick_minutes)
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            log_exception("proactive_virtual_pet_tick_failed", None, exc, chat_id=chat_id)
            continue
        totals["pets"] += counts["pets"]
        totals["messages"] += counts["messages"]
    return totals


def start_proactive_tick_loop(
    interval_seconds: float = PROACTIVE_TICK_INTERVAL_SECONDS,
    tick_minutes: int = PROACTIVE_TICK_MINUTES,
) -> threading.Event:
    """Start the background loop that lets virtual pets initiate Telegram updates."""
    stop_event = threading.Event()
    interval_seconds = max(1.0, interval_seconds)
    tick_minutes = max(1, min(24 * 60, int(tick_minutes)))

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            proactive_tick_virtual_pets_once(tick_minutes=tick_minutes)

    threading.Thread(target=_run, daemon=True).start()
    return stop_event


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


def get_current_pet_id(chat_id: str) -> int:
    if chat_id in CURRENT_PET_IDS:
        return CURRENT_PET_IDS[chat_id]
    pets = api_get_pets(chat_id)
    if not pets:
        raise RuntimeError("No pet exists yet. Create one before using settings.")
    virtual_pet = next((pet for pet in pets if pet.get("pet_mode") == "virtual"), pets[0])
    pet_id = int(virtual_pet["id"])
    CURRENT_PET_IDS[chat_id] = pet_id
    return pet_id


def get_current_pet(chat_id: str) -> dict[str, Any]:
    pet_id = get_current_pet_id(chat_id)
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is not None:
        return pet
    CURRENT_PET_IDS.pop(chat_id, None)
    pet_id = get_current_pet_id(chat_id)
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        raise RuntimeError(f"找不到正在互动的宠物：{pet_id}")
    return pet


def set_current_pet(chat_id: str, pet_id: int) -> dict[str, Any]:
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        raise RuntimeError(f"找不到宠物：{pet_id}")
    CURRENT_PET_IDS[chat_id] = int(pet_id)
    return pet


def update_pet_by_id(
    pet_id: int,
    field: str,
    value: str,
    chat_id: Optional[str] = None,
) -> dict[str, Any]:
    response = requests.patch(
        f"{API_BASE_URL}/pets/{pet_id}",
        **owner_params_kwarg(chat_id),
        json={SET_FIELD_MAP[field]: value.strip()},
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return response.json()


def update_current_pet(chat_id: str, field: str, value: str) -> dict[str, Any]:
    return update_pet_by_id(get_current_pet_id(chat_id), field, value, chat_id=chat_id)


def pet_settings_keyboard(pet_id: int) -> dict[str, Any]:
    return inline_keyboard(
        [
            [("设置名字", f"prompt_set:{pet_id}:name"), ("主人称呼", f"prompt_set:{pet_id}:owner_call")],
            [("补充性格/行为", f"prompt_profile:{pet_id}:personality_behavior")],
            [("设置说话语气", f"prompt_profile:{pet_id}:speaking_style")],
            [("电子宠物", f"set_pet:{pet_id}:mode:virtual"), ("真实宠物", f"set_pet:{pet_id}:mode:real")],
            [("设置种类", f"prompt_profile:{pet_id}:species")],
            [("返回宠物列表", "pets")],
        ]
    )


def send_main_menu(chat_id: str) -> None:
    remove_reply_keyboard(chat_id)
    send_message(chat_id, "Pet Live Agent 已打开。底部键盘已刷新。", reply_markup=MAIN_REPLY_KEYBOARD)


def show_pet_settings(chat_id: str, pet_id: int) -> None:
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    send_message(
        chat_id,
        f"正在设置：{pet['name']}。也可以直接补充它的性格、习惯和行为细节。",
        reply_markup=pet_settings_keyboard(int(pet["id"])),
    )


def send_settings_menu(chat_id: str) -> None:
    try:
        pet = get_current_pet(chat_id)
        show_pet_settings(chat_id, int(pet["id"]))
        return
    except (RuntimeError, requests.RequestException):
        send_message(chat_id, "请先到「宠物列表」选择一只宠物再设置资料。", reply_markup=MAIN_REPLY_KEYBOARD)


ASSISTANT_HELP_TEXT = (
    "小助手现在会这几件简单事：\n"
    "记一下 明天改登录页文案\n"
    "待办 写周报\n"
    "我的待办 / 我的记事\n"
    "完成 7\n"
    "提醒 10分钟后 喝水\n"
    "闹钟 16:30 开会\n"
    "番茄钟 25 写 PR 描述"
)


def _assistant_now(now: Optional[datetime] = None) -> datetime:
    value = now or datetime.now().astimezone()
    return value.replace(microsecond=0)


def _strip_assistant_prefix(text: str) -> str:
    value = str(text or "").strip()
    for prefix in ("小助手", "龙虾"):
        if value.startswith(prefix):
            return value[len(prefix) :].strip(" ，,:：")
    return value


def _assistant_item_payload(
    item_type: str,
    title: str,
    body: str = "",
    due_at: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "item_type": item_type,
        "title": title.strip(),
        "body": body.strip(),
        "source": "telegram",
    }
    if due_at is not None:
        payload["due_at"] = due_at.replace(microsecond=0).isoformat()
    if duration_minutes is not None:
        payload["duration_minutes"] = int(duration_minutes)
    return payload


def _parse_relative_due(text: str, now: datetime) -> Optional[tuple[datetime, str, int]]:
    match = re.match(r"^(?P<amount>\d{1,4})\s*(?P<unit>分钟|分|小时|时)后\s*(?P<title>.+)$", text)
    if not match:
        return None
    amount = int(match.group("amount"))
    unit = match.group("unit")
    minutes = amount * 60 if unit in {"小时", "时"} else amount
    if minutes <= 0:
        return None
    return now + timedelta(minutes=minutes), match.group("title").strip(), minutes


def _parse_clock_due(text: str, now: datetime) -> Optional[tuple[datetime, str]]:
    match = re.match(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<title>.*)$", text)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23 or minute > 59:
        return None
    due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due_at <= now:
        due_at += timedelta(days=1)
    title = match.group("title").strip() or "提醒一下"
    return due_at, title


def parse_assistant_command(text: str, now: Optional[datetime] = None) -> Optional[dict[str, Any]]:
    """Parse a small Telegram helper command into an assistant item payload."""
    value = _strip_assistant_prefix(text)
    if not value or value in {"小助手", "助手"}:
        return None
    current_time = _assistant_now(now)

    for prefix in ("记一下", "记事", "备忘"):
        if value.startswith(prefix):
            title = value[len(prefix) :].strip(" ，,:：")
            return _assistant_item_payload("note", title) if title else None

    for prefix in ("待办", "todo", "TODO"):
        if value.startswith(prefix):
            title = value[len(prefix) :].strip(" ，,:：")
            return _assistant_item_payload("todo", title) if title else None

    for prefix in ("提醒", "闹钟"):
        if value.startswith(prefix):
            body = value[len(prefix) :].strip(" ，,:：")
            relative = _parse_relative_due(body, current_time)
            if relative:
                due_at, title, _minutes = relative
                return _assistant_item_payload("alarm", title, due_at=due_at)
            clock = _parse_clock_due(body, current_time)
            if clock:
                due_at, title = clock
                return _assistant_item_payload("alarm", title, due_at=due_at)
            return None

    for prefix in ("番茄钟", "专注"):
        if value.startswith(prefix):
            body = value[len(prefix) :].strip(" ，,:：")
            match = re.match(r"^(?:(?P<minutes>\d{1,4})\s*(?:分钟|分|min)?\s*)?(?P<title>.*)$", body)
            minutes = int(match.group("minutes") or 25) if match else 25
            if minutes <= 0:
                return None
            title = (match.group("title") if match else "").strip() or "专注一下"
            return _assistant_item_payload(
                "focus",
                title,
                due_at=current_time + timedelta(minutes=minutes),
                duration_minutes=minutes,
            )

    return None


def _assistant_created_reply(item: dict[str, Any]) -> str:
    item_type = item.get("item_type")
    title = str(item.get("title") or "这件事")
    item_id = item.get("id")
    if item_type == "note":
        return f"记下啦：{title}\n编号：{item_id}"
    if item_type == "todo":
        return f"待办加好啦：{title}\n编号：{item_id}"
    if item_type == "focus":
        return f"好，我陪你专注：{title}\n到点我会叫你。编号：{item_id}"
    return f"闹钟设好啦：{title}\n到点我会叫你。编号：{item_id}"


def _assistant_item_list_title(item_type: str) -> str:
    return {
        "note": "记事本",
        "todo": "待办",
        "alarm": "提醒",
        "focus": "番茄钟",
    }.get(item_type, "小助手事项")


def _assistant_item_line(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "未命名")
    due_at = str(item.get("due_at") or "").strip()
    suffix = f"（{due_at}）" if due_at else ""
    return f"#{item.get('id')} {title}{suffix}"


def send_assistant_item_list(chat_id: str, item_type: str) -> None:
    params = dict(owner_params(chat_id))
    params.update({"item_type": item_type, "status": "open", "limit": 10})
    response = requests.get(
        f"{API_BASE_URL}/assistant/items",
        params=params,
        timeout=10,
    )
    if response.status_code >= 400:
        send_message(chat_id, f"读取小助手列表失败：{response.text}", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    items = response.json()
    title = _assistant_item_list_title(item_type)
    if not items:
        send_message(chat_id, f"{title}现在是空的。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    lines = [f"{title}：", *[_assistant_item_line(item) for item in items]]
    send_message(chat_id, "\n".join(lines), reply_markup=MAIN_REPLY_KEYBOARD)


def complete_assistant_item_from_text(chat_id: str, text: str) -> bool:
    match = re.match(r"^(?:完成|完成待办)\s*#?(?P<item_id>\d+)$", text.strip())
    if not match:
        return False
    payload = dict(owner_params(chat_id))
    payload["status"] = "done"
    item_id = int(match.group("item_id"))
    response = requests.patch(
        f"{API_BASE_URL}/assistant/items/{item_id}/complete",
        json=payload,
        timeout=10,
    )
    if response.status_code >= 400:
        send_message(chat_id, f"完成失败：{response.text}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    item = response.json()
    send_message(
        chat_id,
        f"完成啦：{item.get('title') or f'#{item_id}'}",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )
    return True


def handle_assistant_text(chat_id: str, text: str) -> bool:
    if text.strip() in {"小助手", "助手"}:
        ASSISTANT_ACTIVE_CHATS.add(chat_id)
        send_message(chat_id, ASSISTANT_HELP_TEXT, reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    if text.strip() in {"我的待办", "待办列表"}:
        ASSISTANT_ACTIVE_CHATS.add(chat_id)
        send_assistant_item_list(chat_id, "todo")
        return True
    if text.strip() in {"我的记事", "记事本"}:
        ASSISTANT_ACTIVE_CHATS.add(chat_id)
        send_assistant_item_list(chat_id, "note")
        return True
    if text.strip() in {"提醒列表", "闹钟列表"}:
        ASSISTANT_ACTIVE_CHATS.add(chat_id)
        send_assistant_item_list(chat_id, "alarm")
        return True
    if text.strip() in {"番茄钟列表", "专注列表"}:
        ASSISTANT_ACTIVE_CHATS.add(chat_id)
        send_assistant_item_list(chat_id, "focus")
        return True
    if complete_assistant_item_from_text(chat_id, text):
        ASSISTANT_ACTIVE_CHATS.add(chat_id)
        return True

    payload = parse_assistant_command(text)
    if payload is None:
        return False
    ASSISTANT_ACTIVE_CHATS.add(chat_id)
    payload.update(owner_params(chat_id))
    response = requests.post(
        f"{API_BASE_URL}/assistant/items",
        json=payload,
        timeout=10,
    )
    if response.status_code >= 400:
        send_message(chat_id, f"小助手保存失败：{response.text}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    send_message(
        chat_id,
        _assistant_created_reply(response.json()),
        reply_markup=MAIN_REPLY_KEYBOARD,
    )
    return True


def _assistant_due_reply(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "这件事")
    if item.get("item_type") == "focus":
        return f"番茄钟到点啦：{title}\n先停一下，喝口水，眼睛也休息一下。"
    return f"提醒时间到啦：{title}"


def send_due_assistant_items_for_chat(
    chat_id: str,
    now: Optional[datetime] = None,
) -> int:
    params = dict(owner_params(chat_id))
    params.update(
        {
            "status": "open",
            "due_before": _assistant_now(now).isoformat(),
            "limit": 20,
        }
    )
    response = requests.get(
        f"{API_BASE_URL}/assistant/items",
        params=params,
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    sent_count = 0
    for item in response.json():
        if item.get("item_type") not in {"alarm", "focus"}:
            continue
        send_message(chat_id, _assistant_due_reply(item), reply_markup=MAIN_REPLY_KEYBOARD)
        sent_count += 1
        complete_payload = dict(owner_params(chat_id))
        complete_payload["status"] = "dismissed"
        complete_response = requests.patch(
            f"{API_BASE_URL}/assistant/items/{int(item['id'])}/complete",
            json=complete_payload,
            timeout=10,
        )
        if complete_response.status_code >= 400:
            log_exception(
                "assistant_due_item_dismiss_failed",
                None,
                RuntimeError(complete_response.text),
                chat_id=chat_id,
                item_id=item.get("id"),
            )
    return sent_count


def maybe_send_due_assistant_items(now: Optional[datetime] = None, force: bool = False) -> int:
    global ASSISTANT_DUE_SCAN_LAST
    current_time = time.monotonic()
    if (
        not force
        and current_time - ASSISTANT_DUE_SCAN_LAST < ASSISTANT_DUE_SCAN_INTERVAL_SECONDS
    ):
        return 0
    ASSISTANT_DUE_SCAN_LAST = current_time
    sent_count = 0
    target_chat_ids = list(dict.fromkeys([*proactive_target_chat_ids(), *ASSISTANT_ACTIVE_CHATS]))
    for chat_id in target_chat_ids:
        try:
            sent_count += send_due_assistant_items_for_chat(chat_id, now=now)
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            log_exception("assistant_due_scan_failed", None, exc, chat_id=chat_id)
    return sent_count


def handle_status_command(chat_id: str) -> None:
    pet_id = get_current_pet_id(chat_id)

    pets = api_get_pets(chat_id)
    pet = next((item for item in pets if int(item["id"]) == pet_id), None)
    if not pet:
        send_message(chat_id, f"找不到正在互动的宠物：{pet_id}")
        return
    if pet.get("pet_mode") != "virtual":
        send_message(chat_id, "这只宠物不是电子宠物，暂时没有实时状态面板。")
        return

    snapshot_response = requests.get(
        f"{API_BASE_URL}/virtual-pets/{pet_id}",
        **owner_params_kwarg(chat_id),
        timeout=10,
    )
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


def pet_profile(pet: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(pet.get("profile_json") or "{}")
    except (TypeError, ValueError):
        return {}


def pet_species_label(pet: dict[str, Any], profile: Optional[dict[str, Any]] = None) -> str:
    data = profile if profile is not None else pet_profile(pet)
    if data.get("custom_species"):
        return str(data["custom_species"])
    species = str(pet.get("species") or "")
    return PET_SPECIES_LABELS.get(species, species or "未设置")


def pet_personality_label(pet: dict[str, Any], profile: Optional[dict[str, Any]] = None) -> str:
    data = profile if profile is not None else pet_profile(pet)
    personality = str(pet.get("personality") or "")
    label = PET_PERSONALITY_LABELS.get(personality, personality or "未设置")
    description = str(data.get("personality_description") or "").strip()
    return f"{label}，{description}" if description else label


def pet_avatar_status(profile: dict[str, Any]) -> str:
    if profile.get("desktop_pet_manifest_url"):
        return "桌宠动作素材已就绪"
    desktop_assets_status = profile.get("desktop_pet_assets_status")
    if desktop_assets_status == "failed":
        return "基础形象可用，动作素材生成失败"
    if desktop_assets_status == "generating":
        return "基础形象已生成，动作素材后台生成中"
    if profile.get("character_id"):
        return "基础形象已生成，动作素材后台生成中"
    if profile.get("avatar_image_url"):
        return "基础形象已生成"
    return "还没有生成形象"


def pet_avatar_button_label(pet: dict[str, Any], profile: dict[str, Any]) -> str:
    action = "更新形象" if profile.get("avatar_image_url") or profile.get("character_id") else "生成形象"
    return action


def pet_avatar_image_url(profile: dict[str, Any]) -> Optional[str]:
    return profile.get("desktop_pet_avatar_url") or profile.get("avatar_image_url")


def pet_action_keyboard(pet: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    rows = [
        [
            ("设为互动对象", f"pet_current:{pet['id']}"),
            ("单独上桌面", f"desktop:{pet['id']}"),
        ],
        [
            ("设置资料", f"pet_settings:{pet['id']}"),
        ],
    ]
    if profile.get("character_id") and profile.get("sticker_pack_status") not in {"generating", "ready"}:
        rows.append([("生成表情包", f"stickers:generate:{pet['id']}")])
    rows.append(
        [
            (pet_avatar_button_label(pet, profile), f"set:avatar:{pet['id']}"),
            ("删除", f"pet_delete:ask:{pet['id']}"),
        ]
    )
    return inline_keyboard(rows)


def format_pet_card_text(pet: dict[str, Any], index: int) -> tuple[str, dict[str, Any]]:
    profile = pet_profile(pet)
    lines = [
        f"{index}. {pet['name']}",
        f"种类：{pet_species_label(pet, profile)}",
        f"性格：{pet_personality_label(pet, profile)}",
        f"形象：{pet_avatar_status(profile)}",
    ]
    traits = str(profile.get("traits_description") or "").strip()
    if traits:
        lines.append(f"特征：{traits}")
    notes = profile.get("personality_behavior_notes") or []
    if isinstance(notes, str):
        notes = [notes]
    notes = [str(note).strip() for note in notes if str(note).strip()]
    if notes:
        lines.append(f"性格行为补充：{'；'.join(notes[-3:])}")
    speaking_style = str(profile.get("speaking_style_prompt") or "").strip()
    if speaking_style:
        lines.append(f"说话语气：{speaking_style}")
    return "\n".join(lines), profile


def send_pet_card(chat_id: str, pet: dict[str, Any], index: int) -> None:
    text, profile = format_pet_card_text(pet, index)
    reply_markup = pet_action_keyboard(pet, profile)
    avatar_url = pet_avatar_image_url(profile)
    if avatar_url:
        send_local_photo(chat_id, avatar_url, text, reply_markup=reply_markup)
        return
    send_message(chat_id, text, reply_markup=reply_markup)


def handle_pets_command(chat_id: str) -> None:
    pets = api_get_pets(chat_id)
    if not pets:
        send_message(chat_id, "还没有宠物。", reply_markup=inline_keyboard([[("创建宠物", "pet_create:start")]]))
        return

    send_message(chat_id, "宠物清单", reply_markup=inline_keyboard([[("创建宠物", "pet_create:start")]]))
    for index, pet in enumerate(pets, start=1):
        send_pet_card(chat_id, pet, index)


def handle_pet_group_command(chat_id: str) -> None:
    pets = api_get_pets(chat_id)
    if not pets:
        send_message(chat_id, "还没有宠物。", reply_markup=inline_keyboard([[("创建宠物", "pet_create:start")]]))
        return
    ACTIVE_PET_GROUP_CHATS.add(chat_id)
    current_id = get_current_pet_id(chat_id)
    intro_markup = None
    if len(pets) >= 2:
        intro_markup = inline_keyboard([[("编辑宠物关系", "rel:start")]])
    send_message(
        chat_id,
        "这里就是你和宠物们的群聊。它们的状态消息都会发到这里；底部互动按钮会先照顾你指定的互动对象。",
        reply_markup=intro_markup,
    )
    for index, pet in enumerate(pets, start=1):
        marker = "（正在互动）" if int(pet["id"]) == current_id else ""
        text = f"{index}. {pet['name']}{marker}\n种类：{pet_species_label(pet)}"
        send_message(
            chat_id,
            text,
            reply_markup=inline_keyboard(
                [[
                    ("设为互动对象", f"pet_current:{pet['id']}"),
                    ("单独上桌面", f"desktop:{pet['id']}"),
                ]]
            ),
        )


def handle_choose_pet_command(chat_id: str) -> None:
    handle_pet_group_command(chat_id)


def _fetch_pets(chat_id: Optional[str] = None) -> list[dict[str, Any]]:
    if chat_id is not None:
        return api_get_pets(chat_id)
    response = requests.get(f"{API_BASE_URL}/pets", timeout=10)
    response.raise_for_status()
    return response.json()


def _pet_name_by_id(pets: list[dict[str, Any]], pet_id: int) -> str:
    pet = next((pet for pet in pets if int(pet["id"]) == int(pet_id)), None)
    return str(pet.get("name")) if pet else f"宠物 {pet_id}"


def start_relationship_flow(chat_id: str) -> None:
    pets = _fetch_pets(chat_id)
    if len(pets) < 2:
        send_message(chat_id, "至少要有两只宠物，才能设置宠物之间的关系。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    PENDING_RELATIONSHIP_FLOWS[chat_id] = {"step": "choose_source"}
    rows = [[(str(pet["name"]), f"rel:source:{pet['id']}")] for pet in pets]
    send_message(
        chat_id,
        "先选一只宠物：我们要设置它对谁的感觉或习惯？",
        reply_markup=inline_keyboard(rows),
    )


def choose_relationship_source(chat_id: str, source_id: int) -> None:
    pets = _fetch_pets(chat_id)
    source = next((pet for pet in pets if int(pet["id"]) == source_id), None)
    if source is None:
        send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    PENDING_RELATIONSHIP_FLOWS[chat_id] = {
        "step": "choose_target",
        "from_pet_id": source_id,
    }
    rows = [
        [(str(pet["name"]), f"rel:target:{pet['id']}")]
        for pet in pets
        if int(pet["id"]) != source_id
    ]
    send_message(
        chat_id,
        f"要设置 {source['name']} 对哪只宠物的感觉？",
        reply_markup=inline_keyboard(rows),
    )


def _relationship_label_rows(selected: list[str]) -> list[list[tuple[str, str]]]:
    rows: list[list[tuple[str, str]]] = []
    for text, key in RELATIONSHIP_LABEL_OPTIONS:
        prefix = "✓ " if key in selected else ""
        rows.append([(f"{prefix}{text}", f"rel:label:{key}")])
    rows.append([("选好了", "rel:labels_done"), ("取消", "rel:cancel")])
    return rows


def choose_relationship_target(chat_id: str, target_id: int) -> None:
    flow = PENDING_RELATIONSHIP_FLOWS.get(chat_id)
    if not flow or "from_pet_id" not in flow:
        start_relationship_flow(chat_id)
        return
    pets = _fetch_pets(chat_id)
    source_id = int(flow["from_pet_id"])
    if source_id == target_id:
        send_message(chat_id, "不能设置宠物对自己的关系。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    source_name = _pet_name_by_id(pets, source_id)
    target_name = _pet_name_by_id(pets, target_id)
    flow.update(
        {
            "step": "choose_labels",
            "to_pet_id": target_id,
            "selected_labels": [],
            "from_pet_name": source_name,
            "to_pet_name": target_name,
        }
    )
    send_message(
        chat_id,
        f"{source_name} 对 {target_name} 通常是什么感觉或习惯？可以多选。",
        reply_markup=inline_keyboard(_relationship_label_rows([])),
    )


def toggle_relationship_label(chat_id: str, label: str) -> None:
    flow = PENDING_RELATIONSHIP_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "choose_labels":
        start_relationship_flow(chat_id)
        return
    valid_labels = {key for _text, key in RELATIONSHIP_LABEL_OPTIONS}
    if label not in valid_labels:
        send_message(chat_id, "这个关系标签暂时不可用。")
        return
    selected = list(flow.get("selected_labels") or [])
    if label in selected:
        selected.remove(label)
    else:
        selected.append(label)
    flow["selected_labels"] = selected
    send_message(
        chat_id,
        f"已选择 {len(selected)} 个标签。还可以继续调整。",
        reply_markup=inline_keyboard(_relationship_label_rows(selected)),
    )


def relationship_labels_done(chat_id: str) -> None:
    flow = PENDING_RELATIONSHIP_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "choose_labels":
        start_relationship_flow(chat_id)
        return
    if not flow.get("selected_labels"):
        send_message(chat_id, "至少先选一个关系标签。")
        return
    flow["step"] = "await_note"
    send_message(
        chat_id,
        (
            f"要不要补一句 {flow['from_pet_name']} 对 {flow['to_pet_name']} 的细节？"
            "\n可以直接发一句话，也可以跳过。"
        ),
        reply_markup=inline_keyboard([[("跳过备注", "rel:note_skip"), ("取消", "rel:cancel")]]),
    )


def _relationship_label_summary(labels: list[str]) -> str:
    return "、".join(RELATIONSHIP_LABEL_TEXT.get(label, label) for label in labels)


def finish_relationship_flow(chat_id: str, note: str = "") -> None:
    flow = PENDING_RELATIONSHIP_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "await_note":
        start_relationship_flow(chat_id)
        return
    from_pet_id = int(flow["from_pet_id"])
    to_pet_id = int(flow["to_pet_id"])
    labels = list(flow.get("selected_labels") or [])
    payload = {"labels": labels, "note": note.strip(), "muted": False}
    try:
        response = requests.put(
            f"{API_BASE_URL}/pet-relationships/{from_pet_id}/{to_pet_id}",
            json=payload,
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
    except (RuntimeError, requests.RequestException) as exc:
        send_message(chat_id, f"关系保存失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return

    from_name = str(flow["from_pet_name"])
    to_name = str(flow["to_pet_name"])
    PENDING_RELATIONSHIP_FLOWS.pop(chat_id, None)
    label_summary = _relationship_label_summary(labels)
    detail = f"\n你写的细节：{note.strip()}" if note.strip() else ""
    send_message(
        chat_id,
        (
            f"{from_name} 轻轻看了看 {to_name}：我记住啦。\n"
            f"关系标签：{label_summary}{detail}\n"
            "以后群聊里，这个关系可能会轻轻影响它们的接话和短反应。"
        ),
        reply_markup=inline_keyboard(
            [
                [("也设置反方向", f"rel:reverse:{to_pet_id}:{from_pet_id}")],
                [("查看宠物列表", "pets_group")],
            ]
        ),
    )


def handle_relationship_text(chat_id: str, text: str) -> bool:
    flow = PENDING_RELATIONSHIP_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "await_note":
        return False
    finish_relationship_flow(chat_id, text)
    return True


def start_friendship_invite_flow(chat_id: str) -> None:
    if not owner_scoping_enabled():
        send_message(
            chat_id,
            "宠物好友需要先启用多主人 allowlist：TELEGRAM_ALLOWED_OWNER_CHAT_IDS。",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return
    pets = api_get_pets(chat_id)
    if not pets:
        send_message(chat_id, "还没有宠物。先创建一只宠物，再生成好友邀请。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    rows = [[(str(pet["name"]), f"friend:invite_pet:{pet['id']}")] for pet in pets]
    send_message(
        chat_id,
        "选择一只宠物生成好友邀请。对方打开邀请后，会选择 TA 自己的一只宠物确认。",
        reply_markup=inline_keyboard(rows),
    )


def create_friendship_invite_for_pet(chat_id: str, pet_id: int) -> None:
    owner_id = ensure_owner_id(chat_id)
    if owner_id is None:
        send_message(chat_id, "宠物好友需要先启用多主人 allowlist。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    try:
        response = requests.post(
            f"{API_BASE_URL}/pet-friendship-invites",
            json={"inviter_owner_id": owner_id, "inviter_pet_id": pet_id},
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
    except (RuntimeError, requests.RequestException) as exc:
        send_message(chat_id, f"好友邀请生成失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    invite = response.json()
    token = invite["token"]
    send_message(
        chat_id,
        (
            f"{pet['name']} 的好友邀请生成好了。\n"
            f"把这段发给对方主人：/pet_friend_invite {token}\n"
            "对方确认后，两只宠物才会成为好友。"
        ),
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def handle_friendship_invite_command(chat_id: str, text: str) -> bool:
    parts = text.strip().split(maxsplit=1)
    if not parts or parts[0] not in {"/pet_friend_invite", "/friend"}:
        return False
    if len(parts) != 2 or not parts[1].strip():
        send_message(chat_id, "请带上好友邀请码，比如：/pet_friend_invite abc123")
        return True
    token = parts[1].strip()
    owner_id = ensure_owner_id(chat_id)
    if owner_id is None:
        send_message(chat_id, "宠物好友需要先启用多主人 allowlist。", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    try:
        invite_response = requests.get(
            f"{API_BASE_URL}/pet-friendship-invites/{token}",
            timeout=10,
        )
        if invite_response.status_code >= 400:
            raise RuntimeError(invite_response.text)
        invite = invite_response.json()
        pets = api_get_pets(chat_id)
    except (RuntimeError, requests.RequestException) as exc:
        send_message(chat_id, f"读取好友邀请失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    if not pets:
        send_message(chat_id, "你还没有宠物。先创建一只宠物，再接受好友邀请。", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    if len(pets) == 1:
        accept_friendship_invite_for_pet(chat_id, token, int(pets[0]["id"]))
        return True
    PENDING_FRIENDSHIP_INVITE_FLOWS[chat_id] = {"token": token, "step": "choose_receiver_pet"}
    rows = [[(str(pet["name"]), f"friend:accept_pet:{pet['id']}")] for pet in pets]
    send_message(
        chat_id,
        f"{invite.get('inviter_pet_name', '对方宠物')} 发来了好友邀请。选择你家哪只宠物接受？",
        reply_markup=inline_keyboard(rows),
    )
    return True


def accept_friendship_invite_for_pet(chat_id: str, token: str, pet_id: int) -> None:
    owner_id = ensure_owner_id(chat_id)
    if owner_id is None:
        send_message(chat_id, "宠物好友需要先启用多主人 allowlist。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    try:
        response = requests.post(
            f"{API_BASE_URL}/pet-friendship-invites/{token}/accept",
            json={"receiver_owner_id": owner_id, "receiver_pet_id": pet_id},
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
    except (RuntimeError, requests.RequestException) as exc:
        send_message(chat_id, f"接受好友邀请失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    friendship = response.json()
    PENDING_FRIENDSHIP_INVITE_FLOWS.pop(chat_id, None)
    other_name = (
        friendship.get("pet_a_name")
        if int(friendship.get("pet_b_id")) == int(pet_id)
        else friendship.get("pet_b_name")
    )
    send_message(
        chat_id,
        f"{pet['name']} 和 {other_name or '对方宠物'} 已经成为好友啦。",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def _parse_friend_owner_share(text: str) -> Optional[dict[str, str]]:
    match = re.match(
        r"^分享给\s*(?P<target>[^：:，,\s]+)\s*(?P<sep>[：:，,\s])\s*(?P<content>.+)$",
        text.strip(),
    )
    if not match:
        return None
    return {
        "target": match.group("target").strip(),
        "content": match.group("content").strip(),
    }


def handle_friend_owner_share_text(chat_id: str, text: str) -> bool:
    parsed = _parse_friend_owner_share(text)
    if parsed is None:
        if text.strip().startswith("分享给"):
            send_message(
                chat_id,
                "要分享给哪位好友主人？可以发：分享给小红：今天黑米学会了握手",
                reply_markup=MAIN_REPLY_KEYBOARD,
            )
            return True
        return False
    if ensure_owner_id(chat_id) is None:
        send_message(chat_id, "跨主人分享需要先启用多主人 allowlist。", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    try:
        pet = get_current_pet(chat_id)
        contact, contacts = _find_friendship_contact(
            chat_id,
            parsed["target"],
            pet_id=int(pet["id"]),
        )
        if contact is None:
            send_message(chat_id, _friend_contact_help(contacts), reply_markup=MAIN_REPLY_KEYBOARD)
            return True
        target_label = _contact_label(contact)
        send_message(
            str(contact["friend_owner_chat_id"]),
            (
                f"{pet['name']} 托我带来一条分享：\n"
                f"{parsed['content']}\n\n"
                f"来自好友宠物 {pet['name']}。"
            ),
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        send_message(chat_id, f"已分享给{target_label}。", reply_markup=MAIN_REPLY_KEYBOARD)
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        send_message(chat_id, f"分享失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
    return True


def _parse_friend_memory_share(text: str) -> Optional[dict[str, Any]]:
    match = re.match(
        r"^分享记忆\s*#?(?P<memory_id>\d+)\s*给\s*(?P<target>.+)$",
        text.strip(),
    )
    if not match:
        return None
    return {
        "memory_id": int(match.group("memory_id")),
        "target": match.group("target").strip(" ：:，,"),
    }


def _memory_for_friend_share(chat_id: str, memory_id: int) -> Optional[dict[str, Any]]:
    owned_pet_ids = set(_all_pet_ids_for_memory(chat_id))
    response = requests.get(
        f"{API_BASE_URL}/pet-memories",
        params={
            **owner_params(chat_id),
            "limit": 100,
            "visibility": "home",
        },
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    for memory in response.json():
        participant_ids = {
            int(pet_id) for pet_id in memory.get("participant_pet_ids") or []
        }
        if int(memory.get("id")) == int(memory_id) and owned_pet_ids.intersection(participant_ids):
            return memory
    return None


def start_friend_memory_share_confirmation(chat_id: str, text: str) -> bool:
    parsed = _parse_friend_memory_share(text)
    if parsed is None:
        return False
    if ensure_owner_id(chat_id) is None:
        send_message(chat_id, "记忆分享给好友需要先启用多主人 allowlist。", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    try:
        pet = get_current_pet(chat_id)
        memory = _memory_for_friend_share(chat_id, int(parsed["memory_id"]))
        if memory is None:
            send_message(chat_id, "找不到这条记忆，或它不属于当前聊天。", reply_markup=MAIN_REPLY_KEYBOARD)
            return True
        contact, contacts = _find_friendship_contact(
            chat_id,
            str(parsed["target"]),
            pet_id=int(pet["id"]),
        )
        if contact is None:
            send_message(chat_id, _friend_contact_help(contacts), reply_markup=MAIN_REPLY_KEYBOARD)
            return True
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        send_message(chat_id, f"准备分享记忆失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True

    PENDING_FRIEND_MEMORY_SHARE_FLOWS[chat_id] = {
        "memory": memory,
        "contact": contact,
        "pet": pet,
    }
    content = str(memory.get("content") or "").replace("\n", " ")
    if len(content) > 80:
        content = f"{content[:80]}..."
    send_message(
        chat_id,
        (
            f"要把这条记忆分享给{_contact_label(contact)}吗？\n"
            f"#{memory.get('id')} {memory.get('title') or '记忆'}：{content}\n\n"
            "回复“确认分享”发送，回复“取消分享”取消。"
        ),
        reply_markup=MAIN_REPLY_KEYBOARD,
    )
    return True


def handle_friend_memory_share_confirmation_text(chat_id: str, text: str) -> bool:
    flow = PENDING_FRIEND_MEMORY_SHARE_FLOWS.get(chat_id)
    if not flow:
        return False
    value = text.strip()
    if value in {"取消分享", "取消"}:
        PENDING_FRIEND_MEMORY_SHARE_FLOWS.pop(chat_id, None)
        send_message(chat_id, "已取消这次记忆分享。", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    if value not in {"确认分享", "确认", "发送"}:
        return False

    memory = flow["memory"]
    contact = flow["contact"]
    pet = flow["pet"]
    send_message(
        str(contact["friend_owner_chat_id"]),
        (
            f"{pet['name']} 想把一条主人同意分享的记忆告诉"
            f"{contact['friend_pet_name']}：\n"
            f"{memory.get('content') or ''}\n\n"
            f"记忆：#{memory.get('id')} {memory.get('title') or '未命名'}"
        ),
        reply_markup=MAIN_REPLY_KEYBOARD,
    )
    PENDING_FRIEND_MEMORY_SHARE_FLOWS.pop(chat_id, None)
    send_message(chat_id, "已分享这条记忆。", reply_markup=MAIN_REPLY_KEYBOARD)
    return True


def _memory_share_suggestion_text(chat_id: str, memory: dict[str, Any]) -> str:
    memory_id = int(memory.get("id") or 0)
    if not memory_id or random.random() > PET_FRIEND_MEMORY_SHARE_SUGGESTION_CHANCE:
        return ""
    now = time.monotonic()
    last_at = MEMORY_SHARE_SUGGESTION_LAST_BY_CHAT.get(chat_id, 0.0)
    if now - last_at < PET_FRIEND_MEMORY_SHARE_SUGGESTION_COOLDOWN_SECONDS:
        return ""
    try:
        contacts = _friendship_contacts_for_chat(chat_id)
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        log_exception("friend_memory_share_suggestion_failed", None, exc, chat_id=chat_id)
        return ""
    if not contacts:
        return ""
    MEMORY_SHARE_SUGGESTION_LAST_BY_CHAT[chat_id] = now
    target = _contact_label(contacts[0])
    return f"\n\n这条也许可以分享给好友。愿意的话发：分享记忆 {memory_id} 给 {target}"


def maybe_send_friendship_daily_messages(now: Optional[float] = None) -> int:
    global FRIENDSHIP_DAILY_MESSAGE_SCAN_LAST
    if not owner_scoping_enabled():
        return 0
    current_time = time.monotonic() if now is None else float(now)
    if (
        FRIENDSHIP_DAILY_MESSAGE_SCAN_LAST
        and current_time - FRIENDSHIP_DAILY_MESSAGE_SCAN_LAST
        < PET_FRIEND_DAILY_MESSAGE_INTERVAL_SECONDS
    ):
        return 0
    FRIENDSHIP_DAILY_MESSAGE_SCAN_LAST = current_time

    sent_count = 0
    templates = [
        "{local_pet_name} 给 {friend_pet_name} 发来一条日常小消息：今天也来打个招呼。",
        "{local_pet_name} 想问问 {friend_pet_name}：今天有没有好好吃饭呀？",
        "{local_pet_name} 路过好友列表，轻轻戳了戳 {friend_pet_name}。",
        "{local_pet_name} 给 {friend_pet_name} 留了一句：下次一起玩。",
    ]
    for chat_id in sorted(ALLOWED_OWNER_CHAT_IDS):
        if sent_count >= PET_FRIEND_DAILY_MESSAGE_MAX_PER_SCAN:
            break
        try:
            contacts = _friendship_contacts_for_chat(chat_id)
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            log_exception("friend_daily_message_scan_failed", None, exc, chat_id=chat_id)
            continue
        for contact in contacts:
            if sent_count >= PET_FRIEND_DAILY_MESSAGE_MAX_PER_SCAN:
                break
            friendship_id = int(contact["friendship_id"])
            last_sent = FRIENDSHIP_DAILY_MESSAGE_LAST_SENT.get(friendship_id, 0.0)
            if last_sent and current_time - last_sent < PET_FRIEND_DAILY_MESSAGE_COOLDOWN_SECONDS:
                continue
            affinity = max(0, min(100, int(contact.get("affinity") or 0)))
            chance = PET_FRIEND_DAILY_MESSAGE_CHANCE * (0.5 + affinity / 100)
            if random.random() > chance:
                continue
            template = random.choice(templates)
            send_message(
                str(contact["friend_owner_chat_id"]),
                template.format(
                    local_pet_name=contact["local_pet_name"],
                    friend_pet_name=contact["friend_pet_name"],
                ),
                reply_markup=MAIN_REPLY_KEYBOARD,
            )
            FRIENDSHIP_DAILY_MESSAGE_LAST_SENT[friendship_id] = current_time
            sent_count += 1
    return sent_count


def build_relationship_context_for_candidates(
    candidate_pet_ids: list[int],
    relationships: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return structured relationship summaries relevant to one group-chat turn."""
    candidate_ids = {int(pet_id) for pet_id in candidate_pet_ids}
    context: list[dict[str, Any]] = []
    for relationship in relationships:
        from_pet_id = int(relationship["from_pet_id"])
        to_pet_id = int(relationship["to_pet_id"])
        if from_pet_id not in candidate_ids or to_pet_id not in candidate_ids:
            continue
        labels = list(relationship.get("labels") or [])
        context.append(
            {
                "from_pet_id": from_pet_id,
                "to_pet_id": to_pet_id,
                "from_pet_name": relationship.get("from_pet_name"),
                "to_pet_name": relationship.get("to_pet_name"),
                "labels": labels,
                "note": relationship.get("note") or "",
                "allow_natural_expression": not bool(relationship.get("muted")),
                "constraints": [
                    "use only as a light adjustment to pet personality",
                    "do not escalate into an unconfirmed major relationship narrative",
                ],
            }
        )
    return context


def _relationship_expression_blocked_reason(
    relationship: dict[str, Any],
    now: float,
) -> Optional[str]:
    if relationship.get("muted"):
        return "muted"
    from_pet_id = int(relationship["from_pet_id"])
    to_pet_id = int(relationship["to_pet_id"])
    labels = list(relationship.get("labels") or [])
    for label in labels:
        cooldown_key = (from_pet_id, to_pet_id, str(label))
        blocked_until = RELATIONSHIP_EXPRESSION_COOLDOWNS.get(cooldown_key, 0.0)
        if blocked_until > now:
            return "runtime cooldown"
    return None


def _record_relationship_expression(
    relationship: dict[str, Any],
    now: float,
) -> None:
    from_pet_id = int(relationship["from_pet_id"])
    to_pet_id = int(relationship["to_pet_id"])
    for label in list(relationship.get("labels") or []):
        cooldown_seconds = RELATIONSHIP_EXPRESSION_COOLDOWN_SECONDS.get(str(label), 300.0)
        RELATIONSHIP_EXPRESSION_COOLDOWNS[(from_pet_id, to_pet_id, str(label))] = (
            now + cooldown_seconds
        )


def _relationship_context_item(
    relationship: dict[str, Any],
    role: str,
    allow_natural_expression: bool,
    blocked_reason: Optional[str] = None,
) -> dict[str, Any]:
    item = {
        "role": role,
        "from_pet_id": int(relationship["from_pet_id"]),
        "to_pet_id": int(relationship["to_pet_id"]),
        "from_pet_name": relationship.get("from_pet_name"),
        "to_pet_name": relationship.get("to_pet_name"),
        "labels": list(relationship.get("labels") or []),
        "note": relationship.get("note") or "",
        "allow_natural_expression": allow_natural_expression,
        "constraints": [
            "use only as a light adjustment to pet personality",
            "do not escalate into an unconfirmed major relationship narrative",
        ],
    }
    if blocked_reason:
        item["expression_blocked_reason"] = blocked_reason
    return item


def build_relationship_context_for_turn(
    speaker_pet_id: int,
    candidate_pet_ids: list[int],
    relationships: list[dict[str, Any]],
    now: Optional[float] = None,
    record_expression: bool = True,
) -> list[dict[str, Any]]:
    """Return relationship context for one speaker using runtime-only cooldown state."""
    current_time = time.monotonic() if now is None else now
    speaker_id = int(speaker_pet_id)
    candidate_ids = {int(pet_id) for pet_id in candidate_pet_ids}
    if speaker_id not in candidate_ids:
        return []

    relationship_by_pair = {
        (int(relationship["from_pet_id"]), int(relationship["to_pet_id"])): relationship
        for relationship in relationships
        if int(relationship["from_pet_id"]) in candidate_ids
        and int(relationship["to_pet_id"]) in candidate_ids
    }
    context: list[dict[str, Any]] = []
    for target_id in sorted(candidate_ids - {speaker_id}):
        outgoing = relationship_by_pair.get((speaker_id, target_id))
        incoming = relationship_by_pair.get((target_id, speaker_id))
        if outgoing:
            blocked_reason = _relationship_expression_blocked_reason(outgoing, current_time)
            allow_expression = blocked_reason is None
            context.append(
                _relationship_context_item(
                    outgoing,
                    role="primary_outgoing",
                    allow_natural_expression=allow_expression,
                    blocked_reason=blocked_reason,
                )
            )
            if allow_expression and record_expression:
                _record_relationship_expression(outgoing, current_time)
            if incoming:
                context.append(
                    _relationship_context_item(
                        incoming,
                        role="secondary_reverse",
                        allow_natural_expression=False,
                    )
                )
        elif incoming:
            context.append(
                _relationship_context_item(
                    incoming,
                    role="weak_incoming",
                    allow_natural_expression=False,
                )
            )
    return context


def _call_group_chat_llm(
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    from llm_openai import openai_llm_call

    return openai_llm_call(messages, tools or [])


def _pet_profile_for_prompt(pet: dict[str, Any]) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    if pet.get("profile_json"):
        try:
            profile = json.loads(pet.get("profile_json") or "{}")
        except json.JSONDecodeError:
            profile = {}
    return {
        "id": int(pet["id"]),
        "name": pet.get("name"),
        "species": pet_species_label(pet),
        "personality": pet.get("personality"),
        "owner_call_name": pet.get("owner_call_name"),
        "personality_description": profile.get("personality_description", ""),
        "traits_description": profile.get("traits_description", ""),
        "personality_behavior_notes": profile.get("personality_behavior_notes") or [],
        "speaking_style_prompt": profile.get("speaking_style_prompt", ""),
    }


def build_pet_group_chat_messages(
    owner_text: str,
    speaker: dict[str, Any],
    pets: list[dict[str, Any]],
    relationship_context: list[dict[str, Any]],
    pet_memory_context: Optional[list[dict[str, Any]]] = None,
    short_reaction: bool = False,
) -> list[dict[str, Any]]:
    context = {
        "speaker": _pet_profile_for_prompt(speaker),
        "all_pets": [_pet_profile_for_prompt(pet) for pet in pets],
        "relationship_context": relationship_context,
        "pet_memory_context": pet_memory_context or [],
        "owner_message": owner_text,
        "short_reaction": short_reaction,
    }
    system = (
        "你是多宠物群聊里的单轮发言生成器。"
        "只替 speaker 这一只宠物说一句中文，不要替所有宠物开会。"
        "宠物身份和性格永远优先；relationship_context 只作为轻微调味。"
        "只有 allow_natural_expression 为 true 的关系可以被自然说出来；"
        "其他关系只能影响语气或接话方向，不能直接宣布关系状态。"
        "pet_memory_context 是可召回的长期记忆；必须遵守每条 recall_guidance，"
        "尤其不要把主人分享的现实片段说成宠物亲自在场。"
        "不要复述秘密或敏感细节。"
        "不要升级成未确认的大关系叙事，不要说自己在读取标签或规则。"
        "如果 short_reaction 为 true，只能接一句很短的反应，不能展开完整回答。"
    )
    user = (
        "请根据下面 JSON 生成 speaker 的一句自然回复。"
        "只输出正文，不要 JSON，不要加解释。"
        "\n\n上下文 JSON：\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_pet_memory_context_for_prompt(
    memories: list[dict[str, Any]],
    speaker_pet_id: int,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return compact durable memory context for one speaking pet."""
    context: list[dict[str, Any]] = []
    for memory in memories:
        if memory.get("recall_policy") == "owner_asked_only":
            continue
        participants = list(memory.get("participants") or [])
        participant_pet_ids = [
            int(participant.get("pet_id"))
            for participant in participants
            if participant.get("pet_id") is not None
        ]
        if not participant_pet_ids:
            participant_pet_ids = [
                int(pet_id) for pet_id in memory.get("participant_pet_ids") or []
            ]
            participants = [
                {"pet_id": pet_id, "role": "participant"}
                if memory.get("memory_type") == "co_experienced"
                else {"pet_id": pet_id, "role": "shared_with"}
                for pet_id in participant_pet_ids
            ]
        speaker_role = ""
        for participant in participants:
            if int(participant.get("pet_id")) == int(speaker_pet_id):
                speaker_role = str(participant.get("role") or "")
                break
        speaker_participates = speaker_role == "participant"
        if memory.get("memory_type") == "co_experienced" and speaker_role not in {
            "participant",
            "shared_with",
        }:
            continue
        if speaker_role == "mentioned_only":
            continue
        context.append(
            {
                "id": memory.get("id"),
                "memory_type": memory.get("memory_type"),
                "title": memory.get("title") or "",
                "content": memory.get("content") or "",
                "source": memory.get("source") or "",
                "use_class": memory.get("use_class") or "recallable",
                "emotional_tone": memory.get("emotional_tone") or "",
                "participant_pet_ids": participant_pet_ids,
                "speaker_memory_role": speaker_role,
                "speaker_participates": speaker_participates,
                "recall_guidance": memory.get("recall_guidance") or "",
            }
        )
        if len(context) >= limit:
            break
    return context


def _memory_text_for_relevance(memory: dict[str, Any]) -> str:
    return " ".join(
        str(memory.get(key) or "")
        for key in ("title", "content", "emotional_tone")
    )


def _memory_relevance_score(memory: dict[str, Any], owner_text: str) -> int:
    text = owner_text.strip().lower()
    memory_text = _memory_text_for_relevance(memory).lower()
    if not text or not memory_text:
        return 0
    score = 0
    if text in memory_text or memory_text in text:
        score += 20
    owner_chars = {char for char in text if char.isalnum() or "\u4e00" <= char <= "\u9fff"}
    memory_chars = {char for char in memory_text if char.isalnum() or "\u4e00" <= char <= "\u9fff"}
    score += len(owner_chars.intersection(memory_chars))
    return score


def _memory_importance(memory: dict[str, Any]) -> int:
    try:
        return int(memory.get("importance") or 3)
    except (TypeError, ValueError):
        return 3


def _memory_id(memory: dict[str, Any]) -> int:
    try:
        return int(memory.get("id") or 0)
    except (TypeError, ValueError):
        return 0


def _scope_and_rank_memories(
    memories: list[dict[str, Any]],
    candidate_pet_ids: Optional[list[int]] = None,
    owner_text: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    candidate_set = {int(pet_id) for pet_id in candidate_pet_ids or []}
    scoped: list[dict[str, Any]] = []
    for memory in memories:
        if memory.get("use_class") == "private":
            continue
        participant_ids = {
            int(pet_id) for pet_id in memory.get("participant_pet_ids") or []
        }
        if candidate_set and participant_ids and not candidate_set.intersection(participant_ids):
            continue
        scoped.append(memory)
    return sorted(
        scoped,
        key=lambda memory: (
            _memory_relevance_score(memory, owner_text),
            _memory_importance(memory),
            _memory_id(memory),
        ),
        reverse=True,
    )[:limit]


def fetch_recent_pet_memories(
    chat_id: Optional[str] = None,
    candidate_pet_ids: Optional[list[int]] = None,
    owner_text: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Fetch scoped durable memories for Telegram group chat prompting."""
    try:
        params = {
            "limit": min(max(limit * 3, limit), 100),
            "visibility": "home",
        }
        if chat_id is not None:
            params.update(owner_params(chat_id))
        response = requests.get(
            f"{API_BASE_URL}/pet-memories",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return _scope_and_rank_memories(
            response.json(),
            candidate_pet_ids=candidate_pet_ids,
            owner_text=owner_text,
            limit=limit,
        )
    except StopIteration:
        return []
    except Exception as exc:
        log_exception("pet_memory_fetch_failed", None, exc)
        return []


def _all_pet_ids_for_memory(chat_id: str) -> list[int]:
    pets = api_get_pets(chat_id)
    return [int(pet["id"]) for pet in pets]


def _memory_command_content(text: str) -> str:
    value = text.strip()
    prefixes = [
        "记住这个：",
        "记住这个:",
        "记住这件事：",
        "记住这件事:",
        "记住：",
        "记住:",
        "记一下：",
        "记一下:",
        "记住这个",
        "记一下",
    ]
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix) :].strip(" ：:，,。")
    return ""


def _owner_call_name_preference(text: str) -> str:
    value = text.strip()
    prefixes = ["以后都叫我", "以后叫我", "以后请叫我"]
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix) :].strip(" ：:，,。")
    return ""


def _post_group_memory(
    chat_id: str,
    *,
    title: str,
    content: str,
    use_class: str,
    importance: int = 3,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    participant_pet_ids = _all_pet_ids_for_memory(chat_id)
    if not participant_pet_ids:
        raise RuntimeError("还没有宠物，不能写入长期记忆。")
    response = requests.post(
        f"{API_BASE_URL}/pet-memories",
        **owner_params_kwarg(chat_id),
        json={
            "memory_type": "owner_shared",
            "title": title,
            "content": content,
            "source": "telegram",
            "emotional_tone": "",
            "importance": importance,
            "visibility": "home",
            "use_class": use_class,
            "participant_pet_ids": participant_pet_ids,
            "metadata": {
                "telegram_chat_id": chat_id,
                **(metadata or {}),
            },
        },
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return response.json()


def handle_memory_menu(chat_id: str) -> None:
    try:
        owned_pet_ids = set(_all_pet_ids_for_memory(chat_id))
        params = {
            **owner_params(chat_id),
            "limit": 8,
            "visibility": "home",
        }
        response = requests.get(
            f"{API_BASE_URL}/pet-memories",
            params=params,
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
        memories = [
            memory
            for memory in response.json()
            if owned_pet_ids.intersection(
                int(pet_id) for pet_id in memory.get("participant_pet_ids") or []
            )
        ]
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        send_message(chat_id, f"读取记忆失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return

    if not memories:
        send_message(chat_id, "还没有长期记忆。你可以说“记住这个：……”来保存一条。", reply_markup=MAIN_REPLY_KEYBOARD)
        return

    lines = ["最近记忆："]
    for memory in memories:
        title = str(memory.get("title") or "未命名记忆")
        use_class = str(memory.get("use_class") or "recallable")
        content = str(memory.get("content") or "").replace("\n", " ")
        if len(content) > 36:
            content = f"{content[:36]}..."
        lines.append(f"#{memory.get('id')} [{use_class}] {title}：{content}")
    lines.append("要删除可以发：忘记记忆 记忆编号")
    send_message(chat_id, "\n".join(lines), reply_markup=MAIN_REPLY_KEYBOARD)


def _delete_memory_from_chat(chat_id: str, memory_id: int) -> None:
    try:
        owned_pet_ids = set(_all_pet_ids_for_memory(chat_id))
        list_response = requests.get(
            f"{API_BASE_URL}/pet-memories",
            params={
                **owner_params(chat_id),
                "limit": 100,
                "visibility": "home",
            },
            timeout=10,
        )
        if list_response.status_code >= 400:
            raise RuntimeError(list_response.text)
        allowed_memory_ids = {
            int(memory["id"])
            for memory in list_response.json()
            if owned_pet_ids.intersection(
                int(pet_id) for pet_id in memory.get("participant_pet_ids") or []
            )
        }
        if int(memory_id) not in allowed_memory_ids:
            send_message(chat_id, "找不到这条记忆，或它不属于当前聊天。", reply_markup=MAIN_REPLY_KEYBOARD)
            return
        response = requests.delete(
            f"{API_BASE_URL}/pet-memories/{memory_id}",
            **owner_params_kwarg(chat_id),
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
        memory = response.json()
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        send_message(chat_id, f"删除记忆失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return

    title = str(memory.get("title") or f"#{memory_id}")
    send_message(chat_id, f"已忘记：{title}", reply_markup=MAIN_REPLY_KEYBOARD)


def handle_pet_memory_text(chat_id: str, text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    if value == "宠物记忆":
        handle_memory_menu(chat_id)
        return True
    if start_friend_memory_share_confirmation(chat_id, value):
        return True

    for prefix in ("忘记记忆", "删除记忆"):
        if value.startswith(prefix):
            raw_id = value[len(prefix) :].strip(" #：:")
            if not raw_id.isdigit():
                send_message(chat_id, "要删除哪条记忆？可以发：忘记记忆 9", reply_markup=MAIN_REPLY_KEYBOARD)
                return True
            _delete_memory_from_chat(chat_id, int(raw_id))
            return True

    memory_content = _memory_command_content(value)
    if memory_content:
        try:
            memory = _post_group_memory(
                chat_id,
                title="群聊记忆",
                content=memory_content,
                use_class="recallable",
                importance=4,
                metadata={
                    "capture_rule": "explicit_remember",
                    "raw_text": value,
                },
            )
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            send_message(chat_id, f"保存记忆失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
            return True
        send_message(
            chat_id,
            f"记下了。记忆编号：{memory.get('id')}"
            f"{_memory_share_suggestion_text(chat_id, memory)}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True

    call_name = _owner_call_name_preference(value)
    if call_name:
        try:
            memory = _post_group_memory(
                chat_id,
                title="称呼偏好",
                content=f"主人希望宠物以后叫 TA {call_name}。",
                use_class="behavioral",
                importance=4,
                metadata={
                    "capture_rule": "owner_call_name_preference",
                    "raw_text": value,
                    "preferred_call_name": call_name,
                },
            )
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            send_message(chat_id, f"保存称呼偏好失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
            return True
        send_message(
            chat_id,
            f"好，我记下了，以后叫你{call_name}。记忆编号：{memory.get('id')}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True

    return False


def _group_chat_text_from_llm(response: dict[str, Any]) -> str:
    content = response.get("content") or []
    if not content:
        return ""
    text = content[0].get("text", "") if isinstance(content[0], dict) else ""
    return str(text).strip()


def _json_object_from_llm_text(text: str) -> Optional[dict[str, Any]]:
    value = text.strip()
    if not value:
        return None
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start == -1 or end <= start:
            return None
    try:
        parsed = json.loads(value[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def build_pet_group_responder_plan_messages(
    owner_text: str,
    pets: list[dict[str, Any]],
    recent_speaker_pet_ids: Optional[list[int]] = None,
) -> list[dict[str, Any]]:
    context = {
        "owner_message": owner_text,
        "recent_speaker_pet_ids": recent_speaker_pet_ids or [],
        "pets": [_pet_profile_for_prompt(pet) for pet in pets],
    }
    system = (
        "你是多宠物群聊的回应调度器。"
        "根据主人这句话，判断哪只宠物需要回应。"
        "如果主人明确点名某只宠物，优先让被点名的宠物回应。"
        "如果主人说“其他/别的/另外/剩下”的宠物，优先避开 recent_speaker_pet_ids。"
        "如果是问所有宠物，可以选择 1 到 2 只最适合回应的宠物。"
        "只输出 JSON，不要解释。"
    )
    user = (
        "请输出 JSON object，字段为 responder_pet_ids。"
        "responder_pet_ids 是宠物 id 数组，最多 2 个。"
        "\n\n上下文 JSON：\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _normalize_pet_reference(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s_\-·•.。・]+", "", normalized)


def _pet_reference_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized)


def _directly_mentioned_pets(owner_text: str, pets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mentioned: list[dict[str, Any]] = []
    normalized_text = _normalize_pet_reference(owner_text)
    fuzzy_matches: list[tuple[float, dict[str, Any]]] = []
    for pet in pets:
        name = str(pet.get("name") or "").strip()
        if name and name in owner_text:
            mentioned.append(pet)
            continue
        normalized_name = _normalize_pet_reference(name)
        if normalized_name and normalized_name in normalized_text:
            mentioned.append(pet)
            continue
        if len(normalized_name) < 5:
            continue
        best_score = 0.0
        for token in _pet_reference_tokens(owner_text):
            normalized_token = _normalize_pet_reference(token)
            if not normalized_token:
                continue
            best_score = max(
                best_score,
                SequenceMatcher(None, normalized_token, normalized_name).ratio(),
            )
        if best_score >= 0.88:
            fuzzy_matches.append((best_score, pet))
    if fuzzy_matches:
        fuzzy_matches.sort(key=lambda item: item[0], reverse=True)
        top_score = fuzzy_matches[0][0]
        ambiguous = len(fuzzy_matches) > 1 and fuzzy_matches[1][0] >= top_score - 0.03
        if not ambiguous:
            fuzzy_pet = fuzzy_matches[0][1]
            if all(int(pet.get("id")) != int(fuzzy_pet.get("id")) for pet in mentioned):
                mentioned.append(fuzzy_pet)
    return mentioned


def _asks_for_other_pets(owner_text: str) -> bool:
    return any(keyword in owner_text for keyword in ("其他", "别的", "另外", "剩下"))


def choose_pet_group_responders(
    owner_text: str,
    pets: list[dict[str, Any]],
    current_pet_id: Optional[int],
    recent_speaker_pet_ids: Optional[list[int]] = None,
    planner_llm_call: Optional[Any] = None,
) -> list[dict[str, Any]]:
    mentioned = _directly_mentioned_pets(owner_text, pets)
    if mentioned:
        return mentioned[:2]

    excluded_ids = set(recent_speaker_pet_ids or []) if _asks_for_other_pets(owner_text) else set()
    candidate_pets = [pet for pet in pets if int(pet["id"]) not in excluded_ids]
    if not candidate_pets:
        candidate_pets = pets
    pet_by_id = {int(pet["id"]): pet for pet in candidate_pets}
    try:
        messages = build_pet_group_responder_plan_messages(
            owner_text,
            candidate_pets,
            recent_speaker_pet_ids=recent_speaker_pet_ids,
        )
        response = (planner_llm_call or _call_group_chat_llm)(messages, [])
        plan = _json_object_from_llm_text(_group_chat_text_from_llm(response)) or {}
        responder_ids = plan.get("responder_pet_ids") or []
        responders = [
            pet_by_id[int(pet_id)]
            for pet_id in responder_ids
            if int(pet_id) in pet_by_id
        ]
        if responders:
            return responders[:2]
    except Exception as exc:
        log_exception("pet_group_chat_planner_failed", None, exc)

    if current_pet_id in pet_by_id:
        return [pet_by_id[int(current_pet_id)]]
    return candidate_pets[:1]


def build_pet_group_reaction_gate_messages(
    owner_text: str,
    primary_speaker: dict[str, Any],
    primary_reply: str,
    candidate_reactors: list[dict[str, Any]],
    reaction_context_by_pet_id: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    context = {
        "owner_message": owner_text,
        "primary_speaker": _pet_profile_for_prompt(primary_speaker),
        "primary_reply": primary_reply,
        "candidate_reactors": [_pet_profile_for_prompt(pet) for pet in candidate_reactors],
        "reaction_context_by_pet_id": reaction_context_by_pet_id,
    }
    system = (
        "你是多宠物群聊的接话判断器。"
        "判断主宠物回复后，其他每只候选宠物是否应该短短接一句。"
        "只有 relationship_context 显示 allow_natural_expression 为 true 时才允许自然接话。"
        "如果用户明确只问了某一只宠物，通常不要让其他宠物插话。"
        "接话必须少、短、轻，不要抢主回复。只输出 JSON。"
    )
    user = (
        "请输出 JSON object，字段为 reactions。"
        "reactions 是数组，每项包含 pet_id 和 should_react。"
        "可以允许多只宠物短接话，但每只只能很短。"
        "\n\n上下文 JSON：\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def choose_followup_reactors(
    owner_text: str,
    primary_speaker: dict[str, Any],
    primary_reply: str,
    pets: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    reaction_gate_llm_call: Optional[Any] = None,
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    mentioned = _directly_mentioned_pets(owner_text, pets)
    if len(mentioned) == 1 and int(mentioned[0]["id"]) == int(primary_speaker["id"]):
        return []

    candidate_ids = [int(pet["id"]) for pet in pets]
    candidate_reactors: list[dict[str, Any]] = []
    reaction_context_by_pet_id: dict[int, list[dict[str, Any]]] = {}
    for pet in pets:
        pet_id = int(pet["id"])
        if pet_id == int(primary_speaker["id"]):
            continue
        context = build_relationship_context_for_turn(
            speaker_pet_id=pet_id,
            candidate_pet_ids=candidate_ids,
            relationships=relationships,
            record_expression=False,
        )
        allowed_context = [
            item
            for item in context
            if item.get("role") == "primary_outgoing"
            and int(item.get("to_pet_id")) == int(primary_speaker["id"])
            and item.get("allow_natural_expression")
        ]
        if allowed_context:
            candidate_reactors.append(pet)
            reaction_context_by_pet_id[pet_id] = allowed_context

    if not candidate_reactors:
        return []

    try:
        messages = build_pet_group_reaction_gate_messages(
            owner_text=owner_text,
            primary_speaker=primary_speaker,
            primary_reply=primary_reply,
            candidate_reactors=candidate_reactors,
            reaction_context_by_pet_id=reaction_context_by_pet_id,
        )
        response = (reaction_gate_llm_call or _call_group_chat_llm)(messages, [])
        decision = _json_object_from_llm_text(_group_chat_text_from_llm(response)) or {}
        reaction_items = decision.get("reactions")
        if not isinstance(reaction_items, list):
            if decision.get("should_react"):
                reaction_items = [{"pet_id": decision.get("reactor_pet_id"), "should_react": True}]
            else:
                reaction_items = []
        reactions: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        for item in reaction_items:
            if not isinstance(item, dict) or not item.get("should_react"):
                continue
            try:
                reactor_id = int(item.get("pet_id"))
            except (TypeError, ValueError):
                continue
            reactor = next((pet for pet in candidate_reactors if int(pet["id"]) == reactor_id), None)
            if reactor is None:
                continue
            reactions.append((reactor, reaction_context_by_pet_id[reactor_id]))
        return reactions
    except Exception as exc:
        log_exception("pet_group_chat_reaction_gate_failed", None, exc)
        return []


def handle_pet_group_chat_text(
    chat_id: str,
    text: str,
    llm_call: Optional[Any] = None,
    planner_llm_call: Optional[Any] = None,
    reaction_gate_llm_call: Optional[Any] = None,
) -> bool:
    if not text.strip():
        return False
    try:
        pets = api_get_pets(chat_id)
        if not pets:
            send_message(chat_id, "还没有宠物。", reply_markup=inline_keyboard([[("创建宠物", "pet_create:start")]]))
            return True

        ACTIVE_PET_GROUP_CHATS.add(chat_id)
        recent_speaker_pet_ids = PET_GROUP_LAST_SPEAKER_IDS.get(chat_id, [])
        responders = choose_pet_group_responders(
            owner_text=text.strip(),
            pets=pets,
            current_pet_id=None,
            recent_speaker_pet_ids=recent_speaker_pet_ids,
            planner_llm_call=planner_llm_call,
        )
        candidate_ids = [int(pet["id"]) for pet in pets]
        relationships_response = requests.get(f"{API_BASE_URL}/pet-relationships", timeout=10)
        relationships_response.raise_for_status()
        relationships = relationships_response.json()
        memories = fetch_recent_pet_memories(
            chat_id=chat_id,
            candidate_pet_ids=candidate_ids,
            owner_text=text.strip(),
            limit=8,
        )
        sent_speaker_ids: list[int] = []
        primary_reply = ""
        for speaker in responders:
            relationship_context = build_relationship_context_for_turn(
                speaker_pet_id=int(speaker["id"]),
                candidate_pet_ids=candidate_ids,
                relationships=relationships,
            )
            messages = build_pet_group_chat_messages(
                owner_text=text.strip(),
                speaker=speaker,
                pets=pets,
                relationship_context=relationship_context,
                pet_memory_context=build_pet_memory_context_for_prompt(
                    memories,
                    speaker_pet_id=int(speaker["id"]),
                ),
            )
            response = (llm_call or _call_group_chat_llm)(messages, [])
            reply = _group_chat_text_from_llm(response)
            if not reply:
                raise ValueError("LLM returned empty group chat reply")
            if not primary_reply:
                primary_reply = reply
            sent_speaker_ids.append(int(speaker["id"]))
            send_message(
                chat_id,
                f"{speaker['name']}：{reply}",
                reply_markup=MAIN_REPLY_KEYBOARD,
            )

        primary_speaker = responders[0]
        followups = choose_followup_reactors(
            owner_text=text.strip(),
            primary_speaker=primary_speaker,
            primary_reply=primary_reply,
            pets=[pet for pet in pets if int(pet["id"]) not in set(sent_speaker_ids[1:])],
            relationships=relationships,
            reaction_gate_llm_call=reaction_gate_llm_call,
        )
        for reactor, reaction_context in followups:
            reaction_messages = build_pet_group_chat_messages(
                owner_text=text.strip(),
                speaker=reactor,
                pets=pets,
                relationship_context=reaction_context,
                pet_memory_context=build_pet_memory_context_for_prompt(
                    memories,
                    speaker_pet_id=int(reactor["id"]),
                ),
                short_reaction=True,
            )
            reaction_response = (llm_call or _call_group_chat_llm)(reaction_messages, [])
            reaction = _group_chat_text_from_llm(reaction_response)
            if reaction:
                for item in reaction_context:
                    _record_relationship_expression(item, time.monotonic())
                send_message(
                    chat_id,
                    f"{reactor['name']}：{reaction}",
                    reply_markup=MAIN_REPLY_KEYBOARD,
                )
                sent_speaker_ids.append(int(reactor["id"]))
        if sent_speaker_ids:
            PET_GROUP_LAST_SPEAKER_IDS[chat_id] = sent_speaker_ids[-3:]
        return True
    except Exception as exc:
        log_exception("pet_group_chat_reply_failed", None, exc, chat_id=chat_id)
        send_message(chat_id, f"群聊回复生成失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True


def find_pet(pet_id: int, chat_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    pets = api_get_pets(chat_id) if chat_id is not None else _fetch_pets()
    return next((pet for pet in pets if int(pet["id"]) == pet_id), None)


def ask_delete_pet(chat_id: str, pet_id: int) -> None:
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    send_message(
        chat_id,
        f"确定要删除「{pet['name']}」吗？\n删除后它的状态记录也会从本地演示库里移除。",
        reply_markup=inline_keyboard(
            [
                [("确认删除", f"pet_delete:confirm:{pet_id}")],
                [("取消", "pets")],
            ]
        ),
    )


def delete_pet_from_chat(chat_id: str, pet_id: int) -> None:
    try:
        response = requests.delete(
            f"{API_BASE_URL}/pets/{pet_id}",
            **owner_params_kwarg(chat_id),
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
        pet = response.json()
    except (RuntimeError, requests.RequestException) as exc:
        send_message(chat_id, f"删除失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return

    send_message(chat_id, f"已删除「{pet['name']}」。")
    if CURRENT_PET_IDS.get(chat_id) == int(pet_id):
        CURRENT_PET_IDS.pop(chat_id, None)
    handle_pets_command(chat_id)


def handle_desktop_companion_menu(chat_id: str) -> None:
    pets = api_get_pets(chat_id)
    if not pets:
        send_message(chat_id, "还没有宠物。", reply_markup=inline_keyboard([[("创建宠物", "pet_create:start")]]))
        return

    rows = [[("全部有素材的一起上桌面", "desktop:all")]]
    rows.extend([[(f"{pet['name']} 单独上桌面", f"desktop:{pet['id']}")] for pet in pets])
    send_message(
        chat_id,
        "想让谁来桌面陪你？可以选一只，也可以让已经有桌宠素材的宠物一起出现。",
        reply_markup=inline_keyboard(rows),
    )


def handle_desktop_companion(chat_id: str, pet_id: Optional[int] = None) -> None:
    if pet_id is None:
        handle_desktop_companion_menu(chat_id)
        return
    else:
        try:
            set_current_pet(chat_id, pet_id)
        except (RuntimeError, requests.RequestException) as exc:
            send_message(chat_id, f"指定互动对象失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
            return
    result = RUNTIME_CONTROLLER.launch_desktop_companion(chat_id=chat_id, pet_id=pet_id)
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


def handle_all_desktop_companions(chat_id: str) -> None:
    result = RUNTIME_CONTROLLER.launch_all_desktop_companions(chat_id=chat_id)
    send_message(
        chat_id,
        f"{result.message}\n\n调试编号：{result.trace_id}",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def start_pet_create_flow(chat_id: str) -> None:
    trace_id = new_trace_id("pet_create")
    PENDING_PET_FLOWS[chat_id] = {"step": "await_name", "trace_id": trace_id}
    log_event("pet_create_flow_started", trace_id, chat_id=chat_id)
    send_message(
        chat_id,
        "先给新宠物起个名字。接下来我会继续问物种、性格描述和特征描述。",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def handle_pet_create_text(chat_id: str, text: str) -> bool:
    flow = PENDING_PET_FLOWS.get(chat_id)
    if not flow:
        return False
    step = flow.get("step")
    value = text.strip()
    if not value:
        send_message(chat_id, "这一步需要输入一点文字。")
        return True

    if step == "await_name":
        flow.update({"step": "await_species", "name": value})
        send_message(
            chat_id,
            f"名字收到：{value}。它是什么类型的宠物？可以点猫/狗，或者直接输入自定义种类。",
            reply_markup=inline_keyboard(
                [[("猫", "pet_create:species:cat"), ("狗", "pet_create:species:dog"), ("其他", "pet_create:species:other")]]
            ),
        )
        return True

    if step == "await_species":
        set_pet_create_species(chat_id, value)
        return True

    if step == "await_custom_species":
        flow.update({"step": "await_personality_description", "species": "other", "custom_species": value})
        send_message(chat_id, f"种类记下了：{value}。请描述一下它的性格，比如黏人、傲娇、安静、爱冒险。")
        return True

    if step == "await_personality_description":
        flow.update({"step": "await_traits_description", "personality_description": value})
        send_message(chat_id, "性格记下了。再描述一下它的外观特征、辨识点或你想保留的气质。")
        return True

    if step != "await_traits_description":
        return False

    flow["traits_description"] = value
    trace_id = flow.get("trace_id")
    try:
        profile = {
            "personality_description": flow["personality_description"],
            "traits_description": flow["traits_description"],
        }
        if flow.get("custom_species"):
            profile["custom_species"] = flow["custom_species"]
        pet_response = requests.post(
            f"{API_BASE_URL}/pets",
            json={
                "name": flow["name"],
                **owner_params(chat_id),
                "species": flow["species"],
                "personality": "gentle",
                "owner_call_name": "妈",
                "pet_mode": "virtual",
                "profile": profile,
            },
            timeout=30,
        )
        if pet_response.status_code >= 400:
            raise RuntimeError(pet_response.text)
        pet = pet_response.json()
        CURRENT_PET_IDS[chat_id] = int(pet["id"])
    except (RuntimeError, requests.RequestException, ValueError, KeyError) as exc:
        log_exception("pet_create_flow_failed", trace_id, exc, chat_id=chat_id)
        send_message(chat_id, f"创建宠物失败。\n调试编号：{trace_id}\n错误：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True

    PENDING_PET_FLOWS.pop(chat_id, None)
    log_event("pet_create_flow_succeeded", trace_id, chat_id=chat_id, pet_id=pet.get("id"))
    send_message(
        chat_id,
        f"{pet['name']} 的基础资料建好了。下一步继续把它做成独一无二的桌宠形象。",
        reply_markup=inline_keyboard(
            [
                [("定制形象", f"set:avatar:{pet['id']}")],
                [("设置宠物关系", "rel:start")],
                [("返回主菜单", "menu")],
            ]
        ),
    )
    return True


def set_pet_create_species(chat_id: str, species: str) -> None:
    flow = PENDING_PET_FLOWS.get(chat_id)
    if not flow or flow.get("step") != "await_species":
        send_message(chat_id, "当前没有等待选择物种的新宠物流程。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    normalized = species.strip().lower()
    if normalized == "other":
        flow.update({"step": "await_custom_species"})
        send_message(chat_id, "它具体是什么种类？可以直接输入，比如章鱼、龙猫、狐狸、史莱姆。")
        return
    if normalized in PET_SPECIES_LABELS:
        flow.update({"step": "await_personality_description", "species": normalized})
        send_message(
            chat_id,
            f"种类收到：{PET_SPECIES_LABELS[normalized]}。请描述一下它的性格，比如黏人、傲娇、安静、爱冒险。",
        )
        return
    flow.update({"step": "await_personality_description", "species": "other", "custom_species": species.strip()})
    send_message(chat_id, f"种类记下了：{species.strip()}。请描述一下它的性格，比如黏人、傲娇、安静、爱冒险。")


def start_avatar_flow(chat_id: str, pet_id: Optional[int] = None) -> None:
    current_flow = PENDING_AVATAR_FLOWS.get(chat_id)
    if _avatar_flow_is_generating(current_flow):
        send_message(chat_id, format_avatar_busy_text(current_flow or {}), reply_markup=MAIN_REPLY_KEYBOARD)
        return
    trace_id = new_trace_id("avatar")
    PENDING_AVATAR_FLOWS[chat_id] = {"step": "await_photo", "trace_id": trace_id, "pet_id": pet_id}
    log_event("avatar_flow_started", trace_id, chat_id=chat_id, pet_id=pet_id)
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


def _message_has_image(message: dict[str, Any]) -> bool:
    if message.get("photo"):
        return True
    document = message.get("document") or {}
    return str(document.get("mime_type", "")).startswith("image/")


def _avatar_default_style_from_pet(flow: dict[str, Any], chat_id: Optional[str] = None) -> str:
    pet_id = flow.get("pet_id")
    parts = ["根据参考图生成一个适合桌面陪伴的完整宠物形象。"]
    if pet_id is None:
        parts.append("保持参考图的主要气质、颜色和可爱特征。")
        return "\n".join(parts)
    try:
        pets = api_get_pets(chat_id) if chat_id is not None else _fetch_pets()
        pet = next((item for item in pets if int(item["id"]) == int(pet_id)), None)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pet = None
    if not pet:
        parts.append("保持参考图的主要气质、颜色和可爱特征。")
        return "\n".join(parts)

    profile = {}
    try:
        profile = json.loads(pet.get("profile_json") or "{}")
    except (TypeError, ValueError):
        profile = {}
    species = profile.get("custom_species") or pet.get("species") or "宠物"
    parts.append(f"宠物种类：{species}")
    if profile.get("personality_description"):
        parts.append(f"性格：{profile['personality_description']}")
    if profile.get("traits_description"):
        parts.append(f"外观特征：{profile['traits_description']}")
    return "\n".join(parts)


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
    caption = (message.get("caption") or "").strip()
    style_text = caption or _avatar_default_style_from_pet(flow, chat_id=chat_id)
    send_message(chat_id, "收到参考图了，我先开始生成预览。生成后你还可以继续发文字微调。")
    start_avatar_preview_generation(chat_id, style_text)
    return True


def _photo_file_id_from_message(message: dict[str, Any]) -> str:
    photos = message.get("photo") or []
    if photos:
        return str(photos[-1].get("file_id", ""))
    document = message.get("document") or {}
    if str(document.get("mime_type", "")).startswith("image/"):
        return str(document.get("file_id", ""))
    return ""


def _looks_like_co_experienced_memory(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    shared_signals = [
        "一起",
        "我们",
        "陪我",
        "陪着我",
        "陪你们",
        "带着",
        "和你们",
        "跟你们",
        "和你",
        "跟你",
        "共同",
        "一块",
    ]
    return any(signal in normalized for signal in shared_signals) and _has_photo_moment_signal(normalized)


def _looks_like_sensitive_memory(text: str) -> bool:
    normalized = text.strip()
    sensitive_signals = [
        "失眠",
        "崩溃",
        "哭",
        "医院",
        "生病",
        "病",
        "抑郁",
        "焦虑",
        "难过",
        "压力",
        "加班",
        "吵架",
        "分手",
        "离婚",
        "钱",
        "工资",
        "身份证",
    ]
    return any(signal in normalized for signal in sensitive_signals)


def _is_memory_cancel_text(text: str) -> bool:
    normalized = text.strip()
    cancel_signals = ["不要记", "别记", "不用记", "不记", "只是看看", "别保存", "不要保存"]
    return any(signal in normalized for signal in cancel_signals)


def _is_memory_confirm_text(text: str) -> bool:
    normalized = text.strip()
    confirm_signals = ["记住", "保存", "可以", "好", "嗯"]
    return any(signal in normalized for signal in confirm_signals)


def _has_photo_moment_signal(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    moment_signals = [
        "拍",
        "照片",
        "图片",
        "去了",
        "出去",
        "去",
        "看",
        "玩",
        "守夜",
        "散步",
        "旅行",
        "海边",
        "晚霞",
        "今天",
        "昨晚",
        "刚才",
    ]
    return any(signal in normalized for signal in moment_signals)


def _memory_title_from_text(text: str) -> str:
    title = text.strip().replace("\n", " ")
    return title[:18] if title else "共同经历"


def _list_pets_for_memory(chat_id: str) -> list[dict[str, Any]]:
    return api_get_pets(chat_id)


def _photo_memory_metadata(chat_id: str, flow: dict[str, Any], capture_rule: str) -> dict[str, Any]:
    return {
        "capture_rule": capture_rule,
        "telegram_chat_id": chat_id,
        "telegram_photo_file_id": flow.get("photo_file_id"),
        "telegram_photo_message_id": flow.get("message_id"),
        "telegram_photo_caption": flow.get("caption", ""),
    }


def _create_photo_memory_from_text(
    chat_id: str,
    text: str,
    flow: dict[str, Any],
    participant_pets: list[dict[str, Any]],
    visibility: str = "home",
    recall_policy: str = "normal",
) -> dict[str, Any]:
    if not participant_pets:
        raise RuntimeError("还没有宠物，不能写入共同记忆。")
    participant_pet_ids = [int(pet["id"]) for pet in participant_pets]
    response = requests.post(
        f"{API_BASE_URL}/pet-memories",
        **owner_params_kwarg(chat_id),
        json={
            "memory_type": "co_experienced",
            "title": _memory_title_from_text(text),
            "content": text.strip(),
            "source": "telegram",
            "emotional_tone": "warm",
            "importance": 4,
            "visibility": visibility,
            "recall_policy": recall_policy,
            "participant_pet_ids": participant_pet_ids,
            "participants": [
                {"pet_id": pet_id, "role": "participant"}
                for pet_id in participant_pet_ids
            ],
            "metadata": _photo_memory_metadata(chat_id, flow, "co_experienced_photo"),
        },
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return response.json()


def _create_pet_photo_memory_from_text(
    chat_id: str,
    text: str,
    flow: dict[str, Any],
) -> Optional[dict[str, Any]]:
    if not _has_photo_moment_signal(text):
        return None
    pets = _list_pets_for_memory(chat_id)
    mentioned_pets = _directly_mentioned_pets(text, pets)
    if not mentioned_pets:
        return None
    participant_pet_ids = [int(pet["id"]) for pet in mentioned_pets]
    response = requests.post(
        f"{API_BASE_URL}/pet-memories",
        **owner_params_kwarg(chat_id),
        json={
            "memory_type": "pet_milestone",
            "title": _memory_title_from_text(text),
            "content": text.strip(),
            "source": "telegram",
            "emotional_tone": "warm",
            "importance": 3,
            "visibility": "home",
            "use_class": "recallable",
            "participant_pet_ids": participant_pet_ids,
            "metadata": _photo_memory_metadata(chat_id, flow, "pet_photo_moment"),
        },
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    memory = response.json()
    memory["mentioned_pet_names"] = [
        str(pet.get("name") or "").strip()
        for pet in mentioned_pets
        if str(pet.get("name") or "").strip()
    ]
    return memory


def handle_memory_photo(chat_id: str, message: dict[str, Any]) -> bool:
    if not _message_has_image(message):
        return False
    file_id = _photo_file_id_from_message(message)
    if not file_id:
        send_message(chat_id, "我看到像是图片，但没有拿到可用的文件编号。")
        return True
    PENDING_MEMORY_PHOTO_FLOWS[chat_id] = {
        "photo_file_id": file_id,
        "message_id": message.get("message_id"),
        "caption": (message.get("caption") or "").strip(),
        "step": "await_story",
        "created_monotonic": time.monotonic(),
    }
    send_message(
        chat_id,
        "我看到这张照片啦。这里面有哪只宠物的回忆吗？你给我讲讲当时发生了什么、哪些宠物在这段回忆里。",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )
    return True


def _ask_for_memory_participants(chat_id: str, flow: dict[str, Any], content: str) -> None:
    flow["step"] = "await_participants"
    flow["pending_content"] = content
    try:
        pets = _list_pets_for_memory(chat_id)
        pet_names = "、".join(
            str(pet.get("name") or "").strip()
            for pet in pets
            if str(pet.get("name") or "").strip()
        )
    except (RuntimeError, requests.RequestException, ValueError):
        pet_names = ""
    suffix = f"现在的宠物有：{pet_names}。" if pet_names else ""
    send_message(
        chat_id,
        f"这听起来像共同经历。是哪几只宠物在这段回忆里？请直接告诉我名字。{suffix}",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def _memory_photo_flow_expired(flow: dict[str, Any]) -> bool:
    created = flow.get("created_monotonic")
    if created is None:
        return False
    try:
        return time.monotonic() - float(created) > MEMORY_PHOTO_PENDING_TTL_SECONDS
    except (TypeError, ValueError):
        return False


def _pet_refs_from_ids(pet_ids: list[int]) -> list[dict[str, Any]]:
    return [{"id": int(pet_id)} for pet_id in pet_ids]


def _ask_sensitive_memory_confirmation(
    chat_id: str,
    flow: dict[str, Any],
    content: str,
    participant_pets: list[dict[str, Any]],
) -> None:
    flow["step"] = "await_sensitive_confirm"
    flow["pending_content"] = content
    flow["pending_participant_pet_ids"] = [int(pet["id"]) for pet in participant_pets]
    send_message(
        chat_id,
        "这听起来很重要，也有点私密。要我长期记住吗？如果记住，我只会在你问起时提。",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def handle_memory_photo_text(chat_id: str, text: str) -> bool:
    flow = PENDING_MEMORY_PHOTO_FLOWS.get(chat_id)
    if not flow:
        return False
    content = text.strip()
    if not content:
        return False
    if _memory_photo_flow_expired(flow):
        PENDING_MEMORY_PHOTO_FLOWS.pop(chat_id, None)
        send_message(
            chat_id,
            "这张照片的记忆记录已经过期啦。你可以重新发一次照片，我再认真听你讲。",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True
    if _is_memory_cancel_text(content):
        PENDING_MEMORY_PHOTO_FLOWS.pop(chat_id, None)
        send_message(
            chat_id,
            "好，我只当作看过这张照片，不写进长期记忆。",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True
    if flow.get("step") == "await_sensitive_confirm":
        if not _is_memory_confirm_text(content):
            send_message(
                chat_id,
                "如果要长期记住，请回复“记住”；如果不想保存，可以说“不要记住”。",
                reply_markup=MAIN_REPLY_KEYBOARD,
            )
            return True
        try:
            memory = _create_photo_memory_from_text(
                chat_id,
                str(flow.get("pending_content") or content),
                flow,
                _pet_refs_from_ids([int(pet_id) for pet_id in flow.get("pending_participant_pet_ids") or []]),
                visibility="private",
                recall_policy="owner_asked_only",
            )
        except (RuntimeError, requests.RequestException) as exc:
            log_exception("pet_memory_photo_create_failed", None, exc, chat_id=chat_id)
            send_message(chat_id, f"共同记忆保存失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
            return True
        PENDING_MEMORY_PHOTO_FLOWS.pop(chat_id, None)
        send_message(
            chat_id,
            f"记住了。我会把它小心收好，只会在你问起时提。记忆编号：{memory.get('id')}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True
    if flow.get("step") == "await_participants":
        try:
            pets = _list_pets_for_memory(chat_id)
            mentioned_pets = _directly_mentioned_pets(content, pets)
            if not mentioned_pets:
                send_message(
                    chat_id,
                    "我还没确认是哪几只宠物。请直接发宠物名字，或说“不要记住”。",
                    reply_markup=MAIN_REPLY_KEYBOARD,
                )
                return True
            if _looks_like_sensitive_memory(str(flow.get("pending_content") or content)):
                _ask_sensitive_memory_confirmation(
                    chat_id,
                    flow,
                    str(flow.get("pending_content") or content),
                    mentioned_pets,
                )
                return True
            memory = _create_photo_memory_from_text(
                chat_id,
                str(flow.get("pending_content") or content),
                flow,
                mentioned_pets,
            )
        except (RuntimeError, requests.RequestException) as exc:
            log_exception("pet_memory_photo_create_failed", None, exc, chat_id=chat_id)
            send_message(chat_id, f"共同记忆保存失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
            return True
        PENDING_MEMORY_PHOTO_FLOWS.pop(chat_id, None)
        pet_names = "、".join(
            str(pet.get("name") or "").strip()
            for pet in mentioned_pets
            if str(pet.get("name") or "").strip()
        )
        send_message(
            chat_id,
            f"记住了。这是你和 {pet_names} 的共同记忆。记忆编号：{memory.get('id')}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True
    if not _looks_like_co_experienced_memory(content):
        try:
            pet_memory = _create_pet_photo_memory_from_text(chat_id, content, flow)
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            log_exception("pet_photo_memory_create_failed", None, exc, chat_id=chat_id)
            send_message(chat_id, f"照片记忆保存失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
            return True
        if pet_memory:
            PENDING_MEMORY_PHOTO_FLOWS.pop(chat_id, None)
            pet_names = "、".join(pet_memory.get("mentioned_pet_names") or [])
            subject_text = f"{pet_names}的" if pet_names else "这只宠物的"
            send_message(
                chat_id,
                f"记下了。这张照片会作为{subject_text}回忆参考。记忆编号：{pet_memory.get('id')}",
                reply_markup=MAIN_REPLY_KEYBOARD,
            )
            handle_pet_group_chat_text(chat_id, content)
            return True
        PENDING_MEMORY_PHOTO_FLOWS.pop(chat_id, None)
        send_message(
            chat_id,
            "这段更像普通说明，我先不写成共同记忆。以后你可以说“我们一起……”再讲发生了什么。",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return True
    try:
        pets = _list_pets_for_memory(chat_id)
        mentioned_pets = _directly_mentioned_pets(content, pets)
        if not mentioned_pets:
            _ask_for_memory_participants(chat_id, flow, content)
            return True
        if _looks_like_sensitive_memory(content):
            _ask_sensitive_memory_confirmation(chat_id, flow, content, mentioned_pets)
            return True
        memory = _create_photo_memory_from_text(chat_id, content, flow, mentioned_pets)
    except (RuntimeError, requests.RequestException) as exc:
        log_exception("pet_memory_photo_create_failed", None, exc, chat_id=chat_id)
        send_message(chat_id, f"共同记忆保存失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    PENDING_MEMORY_PHOTO_FLOWS.pop(chat_id, None)
    pet_names = "、".join(
        str(pet.get("name") or "").strip()
        for pet in mentioned_pets
        if str(pet.get("name") or "").strip()
    )
    send_message(
        chat_id,
        f"记住了。这是你和 {pet_names} 的共同记忆。记忆编号：{memory.get('id')}",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )
    return True


def _content_type_for_extension(extension: str) -> str:
    normalized = extension.lower()
    if normalized in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if normalized == ".webp":
        return "image/webp"
    return "image/png"


def _avatar_generation_source(flow: dict[str, Any], prefer_preview: bool) -> tuple[bytes, str, str]:
    if prefer_preview:
        preview_url = (flow.get("preview") or {}).get("image_url", "")
        preview_path = _local_static_path(preview_url)
        if preview_path is not None:
            extension = preview_path.suffix or ".png"
            return preview_path.read_bytes(), _content_type_for_extension(extension), extension
    return (
        flow["image_bytes"],
        flow.get("content_type", "image/jpeg"),
        flow.get("extension", ".jpg"),
    )


def _avatar_style_instruction(flow: dict[str, Any], text: str, revision: bool) -> str:
    base = text.strip()
    if revision:
        previous_style = str(flow.get("style") or "").strip()
        if previous_style:
            base = f"{previous_style}\n\n用户对当前预览的修改要求：{base}"
        else:
            base = f"用户对当前预览的修改要求：{base}"
    return f"{base}\n\n{AVATAR_STYLE_LOCK_RULE}"


def _finish_avatar_preview_generation(
    chat_id: str,
    trace_id: object,
    style_text: str,
    preview: dict[str, Any],
    started_at: float,
    progress_message_id: Optional[int],
    revision: bool,
) -> None:
    flow = PENDING_AVATAR_FLOWS.get(chat_id)
    if not flow or flow.get("trace_id") != trace_id:
        return

    flow.update({"step": "await_confirm", "preview": preview, "style": style_text.strip()})
    elapsed = round(time.monotonic() - started_at, 1)
    log_event(
        "avatar_preview_generation_succeeded",
        trace_id,
        chat_id=chat_id,
        image_url=preview.get("image_url"),
        style_mode=preview.get("style_mode"),
        elapsed_seconds=elapsed,
        revision=revision,
    )
    complete_text = f"{_progress_bar(5, 5)} 5/5\n预览生成好了，用时 {elapsed} 秒。现在发给你确认。\n\n调试编号：{trace_id}"
    if progress_message_id is not None:
        try:
            edit_message_text(chat_id, progress_message_id, complete_text)
        except RuntimeError:
            send_message(chat_id, complete_text)
    else:
        send_message(chat_id, complete_text)
    caption = "这是更新后的形象预览。还可以继续发文字让我微调，满意后再确认生成桌宠素材。"
    if not revision:
        caption = "这是形象预览。确认后会绑定到这只宠物身上，再正式开始陪伴的旅程哦！"
    send_local_photo(
        chat_id,
        preview["image_url"],
        caption,
        reply_markup=inline_keyboard(
            [
                [("确认并生成桌宠素材", "avatar:confirm")],
                [("重新开始", "avatar:restart"), ("取消", "avatar:cancel")],
            ]
        ),
    )


def _run_avatar_preview_generation(
    chat_id: str,
    trace_id: object,
    style_text: str,
    source_bytes: bytes,
    content_type: str,
    extension: str,
    progress_message_id: Optional[int],
    progress_stop: threading.Event,
    started_at: float,
    revision: bool,
) -> None:
    slot_released = False

    def release_slot_once() -> None:
        nonlocal slot_released
        if slot_released:
            return
        _release_avatar_generation_slot(chat_id, trace_id)
        slot_released = True

    try:
        response = requests.post(
            f"{API_BASE_URL}/image-style",
            files={
                "image": (
                    f"telegram-reference{extension}",
                    source_bytes,
                    content_type,
                )
            },
            data={
                "style": style_text,
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
            revision=revision,
        )
        if response.status_code >= 400:
            log_event(
                "avatar_preview_api_failed",
                trace_id,
                chat_id=chat_id,
                status_code=response.status_code,
                response_text=response.text[:1000],
                revision=revision,
            )
            raise RuntimeError(response.text)
        preview = response.json()
    except (RuntimeError, requests.RequestException) as exc:
        flow = PENDING_AVATAR_FLOWS.get(chat_id)
        if flow and flow.get("trace_id") == trace_id:
            if revision and flow.get("preview"):
                flow["step"] = "await_confirm"
            else:
                PENDING_AVATAR_FLOWS.pop(chat_id, None)
        log_exception("avatar_preview_generation_failed", trace_id, exc, chat_id=chat_id, revision=revision)
        failure_text = format_avatar_failure_text(trace_id, exc)
        if progress_message_id is not None:
            try:
                edit_message_text(chat_id, progress_message_id, failure_text)
            except RuntimeError:
                send_message(chat_id, failure_text, reply_markup=MAIN_REPLY_KEYBOARD)
            else:
                send_message(
                    chat_id,
                    f"这次形象预览生成失败了。\n调试编号：{trace_id}",
                    reply_markup=MAIN_REPLY_KEYBOARD,
                )
        else:
            send_message(chat_id, failure_text, reply_markup=MAIN_REPLY_KEYBOARD)
        progress_stop.set()
        release_slot_once()
        return

    progress_stop.set()
    try:
        _finish_avatar_preview_generation(
            chat_id=chat_id,
            trace_id=trace_id,
            style_text=style_text,
            preview=preview,
            started_at=started_at,
            progress_message_id=progress_message_id,
            revision=revision,
        )
    finally:
        release_slot_once()


def start_avatar_preview_generation(chat_id: str, text: str, revision: bool = False) -> None:
    flow = PENDING_AVATAR_FLOWS.get(chat_id)
    if not flow:
        return
    if _avatar_flow_is_generating(flow):
        send_message(chat_id, format_avatar_busy_text(flow), reply_markup=MAIN_REPLY_KEYBOARD)
        return

    source_bytes, content_type, extension = _avatar_generation_source(flow, prefer_preview=revision)
    trace_id = flow.get("trace_id")
    if not _acquire_avatar_generation_slot(chat_id, trace_id):
        send_message(
            chat_id,
            "现在已经有形象生成任务在运行，我先不重复提交，避免机器人卡住。\n"
            "请等当前进度消息结束后再试；其他底部按钮可以继续使用。\n\n"
            f"调试编号：{trace_id}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return

    started_at = time.monotonic()
    flow.update(
        {
            "step": "revising_preview" if revision else "generating_preview",
            "started_at": started_at,
        }
    )
    style_text = _avatar_style_instruction(flow, text, revision)
    log_event(
        "avatar_preview_generation_started",
        trace_id,
        chat_id=chat_id,
        content_type=content_type,
        extension=extension,
        style_length=len(style_text.strip()),
        revision=revision,
    )
    progress_response = send_message(
        chat_id,
        format_avatar_progress_text(
            AVATAR_PREVIEW_PROGRESS_STAGES[0],
            trace_id,
            1,
            len(AVATAR_PREVIEW_PROGRESS_STAGES),
        ),
    )
    progress_message_id = _telegram_message_id(progress_response)
    flow["progress_message_id"] = progress_message_id
    progress_stop = start_avatar_progress_updater(chat_id, progress_message_id, trace_id)
    send_chat_action(chat_id, "upload_photo")
    threading.Thread(
        target=_run_avatar_preview_generation,
        args=(
            chat_id,
            trace_id,
            style_text,
            source_bytes,
            content_type,
            extension,
            progress_message_id,
            progress_stop,
            started_at,
            revision,
        ),
        daemon=True,
    ).start()


def handle_avatar_style_text(chat_id: str, text: str) -> bool:
    flow = PENDING_AVATAR_FLOWS.get(chat_id)
    if not flow:
        return False
    step = flow.get("step")
    if step in {"generating_preview", "revising_preview"}:
        send_message(chat_id, format_avatar_busy_text(flow), reply_markup=MAIN_REPLY_KEYBOARD)
        return True
    if step == "await_confirm":
        if not text.strip():
            send_message(chat_id, "可以直接发一句修改要求，比如：去掉绳子、毛更卷一点、眼睛更亮。")
            return True
        start_avatar_preview_generation(chat_id, text.strip(), revision=True)
        return True
    if step != "await_style":
        return False
    if not text.strip():
        send_message(chat_id, "请描述一下想要的形象风格。")
        return True
    start_avatar_preview_generation(chat_id, text.strip())
    return True


def _pet_id_for_avatar_flow(flow: dict[str, Any]) -> int:
    return int(flow["pet_id"]) if flow.get("pet_id") is not None else get_default_pet_id()


def _profile_for_pet_id(pet_id: int, chat_id: Optional[str] = None) -> dict[str, Any]:
    pets = api_get_pets(chat_id) if chat_id is not None else _fetch_pets()
    pet = next(
        (item for item in pets if int(item["id"]) == pet_id),
        None,
    )
    if pet and pet.get("profile_json"):
        return json.loads(pet["profile_json"] or "{}")
    return {}


def _profile_with_character(
    pet_id: int,
    character: dict[str, Any],
    desktop_assets_status: str,
    chat_id: Optional[str] = None,
) -> dict[str, Any]:
    profile = _profile_for_pet_id(pet_id, chat_id=chat_id)
    profile.update(
        {
            "avatar_image_url": character["image_url"],
            "walking_reference_image_url": character.get("walking_reference_image_url"),
            "character_id": character["id"],
            "desktop_pet_manifest_url": character.get("desktop_pet_manifest_url"),
            "desktop_pet_asset_dir": character.get("desktop_pet_asset_dir"),
            "desktop_pet_avatar_url": character.get("desktop_pet_avatar_url"),
            "desktop_pet_assets_status": desktop_assets_status,
        }
    )
    return profile


def update_pet_profile(chat_id: str, trace_id: object, pet_id: int, profile: dict[str, Any]) -> None:
    update_response = requests.patch(
        f"{API_BASE_URL}/pets/{pet_id}",
        **owner_params_kwarg(chat_id),
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


def bind_character_to_pet(
    chat_id: str,
    trace_id: object,
    pet_id: int,
    character: dict[str, Any],
    desktop_assets_status: str,
) -> None:
    profile = _profile_with_character(pet_id, character, desktop_assets_status, chat_id=chat_id)
    update_pet_profile(chat_id, trace_id, pet_id, profile)


def mark_pet_desktop_assets_status(
    chat_id: str,
    trace_id: object,
    pet_id: int,
    desktop_assets_status: str,
) -> None:
    profile = _profile_for_pet_id(pet_id, chat_id=chat_id)
    profile["desktop_pet_assets_status"] = desktop_assets_status
    update_pet_profile(chat_id, trace_id, pet_id, profile)


def _sticker_pack_urls(stickers: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("image_url") or "").strip()
        for item in stickers
        if str(item.get("image_url") or "").strip()
    ]


def generate_sticker_pack_in_background(
    chat_id: str,
    trace_id: object,
    pet_id: int,
    character_id: str,
    started_at: float,
) -> None:
    try:
        log_event(
            "sticker_pack_background_started",
            trace_id,
            chat_id=chat_id,
            pet_id=pet_id,
            character_id=character_id,
        )
        response = requests.post(
            f"{API_BASE_URL}/characters/{character_id}/sticker-pack",
            json={"theme": "日常聊天表情包"},
            timeout=900,
        )
        if response.status_code >= 400:
            log_event(
                "sticker_pack_create_failed",
                trace_id,
                chat_id=chat_id,
                status_code=response.status_code,
                response_text=response.text[:1000],
            )
            raise RuntimeError(response.text)
        pack = response.json()
        stickers = pack.get("stickers") or []
        sticker_urls = _sticker_pack_urls(stickers)
        if len(sticker_urls) != STICKER_PACK_SIZE:
            raise RuntimeError(f"表情包数量不对：期望 {STICKER_PACK_SIZE} 张，实际 {len(sticker_urls)} 张")

        profile = _profile_for_pet_id(pet_id, chat_id=chat_id)
        profile["sticker_pack_status"] = "ready"
        profile["sticker_pack_character_id"] = character_id
        profile["sticker_pack_urls"] = sticker_urls
        profile["sticker_pack_theme"] = pack.get("theme") or "日常聊天表情包"
        update_pet_profile(chat_id, trace_id, pet_id, profile)
        log_event(
            "sticker_pack_created",
            trace_id,
            chat_id=chat_id,
            pet_id=pet_id,
            character_id=character_id,
            elapsed_seconds=round(time.monotonic() - started_at, 1),
        )
        send_message(
            chat_id,
            f"表情包生成好了，共 {len(sticker_urls)} 张。我先发给你预览。",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        for index, sticker in enumerate(stickers, start=1):
            image_url = str(sticker.get("image_url") or "")
            if image_url:
                send_local_photo(chat_id, image_url, f"表情包 {index}/{len(sticker_urls)}")
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        log_exception("sticker_pack_background_failed", trace_id, exc, chat_id=chat_id, character_id=character_id)
        try:
            profile = _profile_for_pet_id(pet_id, chat_id=chat_id)
            profile["sticker_pack_status"] = "failed"
            update_pet_profile(chat_id, trace_id, pet_id, profile)
        except (RuntimeError, requests.RequestException, ValueError) as status_exc:
            log_exception(
                "sticker_pack_status_update_failed",
                trace_id,
                status_exc,
                chat_id=chat_id,
                pet_id=pet_id,
            )
        send_message(
            chat_id,
            f"表情包生成失败。\n调试编号：{trace_id}\n错误：{exc}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )


def start_sticker_pack_generation(chat_id: str, pet_id: int) -> None:
    trace_id = new_trace_id("stickers")
    try:
        pet = find_pet(pet_id, chat_id=chat_id)
        if pet is None:
            send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
            return
        profile = pet_profile(pet)
        character_id = str(profile.get("character_id") or "").strip()
        if not character_id:
            send_message(chat_id, "这只宠物还没有确认过形象，先生成并确认形象后才能做表情包。", reply_markup=MAIN_REPLY_KEYBOARD)
            return
        status = str(profile.get("sticker_pack_status") or "")
        if status == "generating":
            send_message(chat_id, "这只宠物的表情包正在生成中，我不会重复提交。", reply_markup=MAIN_REPLY_KEYBOARD)
            return
        if status == "ready":
            send_message(chat_id, "这只宠物已经生成过表情包了。", reply_markup=MAIN_REPLY_KEYBOARD)
            return

        profile["sticker_pack_status"] = "generating"
        profile["sticker_pack_character_id"] = character_id
        update_pet_profile(chat_id, trace_id, pet_id, profile)
        started_at = time.monotonic()
        send_message(
            chat_id,
            f"收到，我开始给 {pet['name']} 生成 {STICKER_PACK_SIZE} 张表情包。这个会比较慢，完成后我会直接发回来。\n\n调试编号：{trace_id}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        threading.Thread(
            target=generate_sticker_pack_in_background,
            args=(chat_id, trace_id, pet_id, character_id, started_at),
            daemon=True,
        ).start()
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        log_exception("sticker_pack_start_failed", trace_id, exc, chat_id=chat_id, pet_id=pet_id)
        send_message(chat_id, f"表情包生成启动失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)


def update_pet_profile_note(
    pet_id: int,
    note_type: str,
    text: str,
    chat_id: Optional[str] = None,
) -> dict[str, Any]:
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        raise RuntimeError(f"找不到宠物：{pet_id}")
    profile = pet_profile(pet)
    value = text.strip()
    if not value:
        raise RuntimeError("补充内容不能为空")
    payload: dict[str, Any] = {"profile": profile}
    if note_type == "personality_behavior":
        notes = profile.get("personality_behavior_notes") or []
        if isinstance(notes, str):
            notes = [notes]
        notes = [str(note).strip() for note in notes if str(note).strip()]
        notes.append(value)
        profile["personality_behavior_notes"] = notes
    elif note_type == "speaking_style":
        profile["speaking_style_prompt"] = value
    elif note_type == "species":
        profile["custom_species"] = value
        payload["species"] = "other"
    else:
        raise RuntimeError(f"不支持的资料类型：{note_type}")
    response = requests.patch(
        f"{API_BASE_URL}/pets/{pet_id}",
        **owner_params_kwarg(chat_id),
        json=payload,
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return response.json()


def start_profile_note_flow(chat_id: str, pet_id: int, note_type: str) -> None:
    pet = find_pet(pet_id, chat_id=chat_id)
    if pet is None:
        send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    PENDING_SET_FIELDS[chat_id] = {
        "kind": "profile_note",
        "note_type": note_type,
        "pet_id": int(pet_id),
    }
    if note_type == "species":
        prompt = f"直接输入 {pet['name']} 的种类，比如：猫、狗、狐狸、龙猫、史莱姆。"
    elif note_type == "speaking_style":
        prompt = f"直接描述 {pet['name']} 的说话语气，比如：短句、傲娇、嘴硬但会认真回答。"
    else:
        prompt = f"直接发一句话补充 {pet['name']} 的性格、习惯或行为，比如：陌生人靠近会先躲起来。"
    send_message(
        chat_id,
        prompt,
        reply_markup=MAIN_REPLY_KEYBOARD,
    )


def generate_avatar_assets_in_background(
    chat_id: str,
    trace_id: object,
    pet_id: int,
    character_id: str,
    started_at: float,
) -> None:
    completed_animation_labels: list[str] = []
    try:
        log_event(
            "avatar_assets_background_started",
            trace_id,
            chat_id=chat_id,
            pet_id=pet_id,
            character_id=character_id,
        )
        character = None
        total = len(BASIC_DESKTOP_ANIMATION_NAMES)
        for index, animation_name in enumerate(BASIC_DESKTOP_ANIMATION_NAMES, start=1):
            assets_response = requests.post(
                f"{API_BASE_URL}/characters/{character_id}/desktop-assets",
                params={"animations": animation_name},
                timeout=AVATAR_ASSET_GENERATION_TIMEOUT_SECONDS,
            )
            if assets_response.status_code >= 400:
                log_event(
                    "avatar_assets_create_failed",
                    trace_id,
                    chat_id=chat_id,
                    status_code=assets_response.status_code,
                    response_text=assets_response.text[:1000],
                    animation_name=animation_name,
                )
                raise RuntimeError(assets_response.text)
            character = assets_response.json()
            bind_character_to_pet(chat_id, trace_id, pet_id, character, "generating")
            label = AVATAR_ASSET_ANIMATION_LABELS.get(animation_name, animation_name)
            completed_animation_labels.append(label)
            log_event(
                "avatar_asset_animation_created",
                trace_id,
                chat_id=chat_id,
                character_id=character.get("id"),
                animation_name=animation_name,
                animation_index=index,
                animation_total=total,
                manifest=character.get("desktop_pet_manifest_url"),
                elapsed_seconds=round(time.monotonic() - started_at, 1),
            )
            send_message(
                chat_id,
                f"桌宠动作已生成：{label}（{index}/{total}）。已生成的动作已经可以先用。",
                reply_markup=MAIN_REPLY_KEYBOARD,
            )
        if character is None:
            raise RuntimeError("没有生成任何桌宠动作素材。")
        bind_character_to_pet(chat_id, trace_id, pet_id, character, "ready")
        log_event(
            "avatar_assets_created",
            trace_id,
            chat_id=chat_id,
            character_id=character.get("id"),
            manifest=character.get("desktop_pet_manifest_url"),
            elapsed_seconds=round(time.monotonic() - started_at, 1),
        )
        send_message(
            chat_id,
            "桌宠动画素材包已经生成完成，后续桌面陪伴会使用新的动作素材。",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        log_exception("avatar_assets_background_failed", trace_id, exc, chat_id=chat_id, character_id=character_id)
        try:
            mark_pet_desktop_assets_status(chat_id, trace_id, pet_id, "failed")
        except (RuntimeError, requests.RequestException, ValueError) as status_exc:
            log_exception(
                "avatar_assets_status_update_failed",
                trace_id,
                status_exc,
                chat_id=chat_id,
                pet_id=pet_id,
            )
        send_message(
            chat_id,
            "基础形象已经可用，但桌宠动画素材后台生成没有全部完成。\n"
            f"已完成动作：{('、'.join(completed_animation_labels) if completed_animation_labels else '暂无')}\n"
            f"调试编号：{trace_id}\n错误：{exc}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )


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
        "收到确认。现在先绑定基础形象；桌宠动画素材会在后台继续生成。\n\n"
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
            timeout=120,
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
        pet_id = _pet_id_for_avatar_flow(flow)
        bind_character_to_pet(chat_id, trace_id, pet_id, character, "generating")
        walking_reference_image_url = str(character.get("walking_reference_image_url") or "").strip()
        if walking_reference_image_url:
            send_local_photo(
                chat_id,
                walking_reference_image_url,
                "这是站立行走参考图。后续行走 GIF 会用这张图作为 Wan 的首帧参考。",
                reply_markup=MAIN_REPLY_KEYBOARD,
            )
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        log_exception("avatar_confirm_failed", trace_id, exc, chat_id=chat_id)
        send_message(
            chat_id,
            f"确认失败。\n阶段：确认并绑定基础形象\n调试编号：{trace_id}\n错误：{exc}",
            reply_markup=MAIN_REPLY_KEYBOARD,
        )
        return

    PENDING_AVATAR_FLOWS.pop(chat_id, None)
    log_event(
        "avatar_confirm_succeeded",
        trace_id,
        chat_id=chat_id,
        character_id=character.get("id"),
        elapsed_seconds=round(time.monotonic() - started_at, 1),
    )
    send_message(
        chat_id,
        f"确认好了。基础形象已经绑定到这只宠物，动画素材正在后台生成；你可以继续使用其他功能。\n\n调试编号：{trace_id}",
        reply_markup=MAIN_REPLY_KEYBOARD,
    )
    threading.Thread(
        target=generate_avatar_assets_in_background,
        args=(chat_id, trace_id, pet_id, character["id"], started_at),
        daemon=True,
    ).start()


def handle_action_button(chat_id: str, action: str) -> None:
    pet_id = get_current_pet_id(chat_id)
    response = requests.post(
        f"{API_BASE_URL}/virtual-pets/{pet_id}/actions",
        **owner_params_kwarg(chat_id),
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
    pets = api_get_pets(chat_id)
    pet = next((item for item in pets if int(item["id"]) == pet_id), {"name": "宠物"})
    event_result = result.get("event_result") or {}
    generated_message = (event_result.get("message") or {}).get("message")
    generated_message = format_speaker_labeled_message(
        generated_message or "",
        str(event_result.get("pet_name") or pet.get("name") or ""),
    )
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
    pending = PENDING_SET_FIELDS.pop(chat_id, None)
    if not pending:
        return False
    if pending.get("kind") == "profile_note":
        pet_id = int(pending["pet_id"])
        note_type = str(pending["note_type"])
        try:
            pet = update_pet_profile_note(pet_id, note_type, text, chat_id=chat_id)
            target_labels = {
                "species": "种类",
                "speaking_style": "说话语气",
            }
            target = target_labels.get(note_type, "性格/行为资料")
            send_message(
                chat_id,
                f"已补充 {pet['name']} 的{target}。之后群聊会参考这些细节。",
                reply_markup=pet_settings_keyboard(pet_id),
            )
        except RuntimeError as exc:
            send_message(chat_id, f"设置失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return True

    field = pending["field"]
    pet_id = int(pending["pet_id"])

    try:
        pet = update_pet_by_id(pet_id, field, text, chat_id=chat_id)
        send_message(
            chat_id,
            f"设置好啦：{pet['name']} 的 {field} 已更新。",
            reply_markup=pet_settings_keyboard(pet_id),
        )
    except RuntimeError as exc:
        send_message(chat_id, f"设置失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
    return True


def handle_callback(callback_query: dict[str, Any]) -> None:
    callback_id = str(callback_query.get("id", ""))
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not is_chat_allowed(chat_id):
        return
    remember_owner_display_name(chat_id, callback_query.get("from"))

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
    if data == "pets_group":
        handle_pet_group_command(chat_id)
        return
    if data == "rel:start":
        start_relationship_flow(chat_id)
        return
    if data == "friend:start":
        start_friendship_invite_flow(chat_id)
        return
    if data.startswith("friend:invite_pet:"):
        create_friendship_invite_for_pet(chat_id, int(data.rsplit(":", 1)[1]))
        return
    if data.startswith("friend:accept_pet:"):
        flow = PENDING_FRIENDSHIP_INVITE_FLOWS.get(chat_id)
        if not flow or not flow.get("token"):
            send_message(chat_id, "当前没有等待接受的好友邀请。", reply_markup=MAIN_REPLY_KEYBOARD)
            return
        accept_friendship_invite_for_pet(
            chat_id,
            str(flow["token"]),
            int(data.rsplit(":", 1)[1]),
        )
        return
    if data.startswith("rel:source:"):
        choose_relationship_source(chat_id, int(data.rsplit(":", 1)[1]))
        return
    if data.startswith("rel:target:"):
        choose_relationship_target(chat_id, int(data.rsplit(":", 1)[1]))
        return
    if data.startswith("rel:label:"):
        toggle_relationship_label(chat_id, data.rsplit(":", 1)[1])
        return
    if data == "rel:labels_done":
        relationship_labels_done(chat_id)
        return
    if data == "rel:note_skip":
        finish_relationship_flow(chat_id)
        return
    if data == "rel:cancel":
        PENDING_RELATIONSHIP_FLOWS.pop(chat_id, None)
        send_message(chat_id, "已取消宠物关系设置。", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    if data.startswith("rel:reverse:"):
        _prefix, _action, from_pet_id, to_pet_id = data.split(":", 3)
        choose_relationship_source(chat_id, int(from_pet_id))
        choose_relationship_target(chat_id, int(to_pet_id))
        return
    if data == "desktop":
        handle_desktop_companion(chat_id)
        return
    if data == "desktop:all":
        handle_all_desktop_companions(chat_id)
        return
    if data.startswith("desktop:"):
        handle_desktop_companion(chat_id, pet_id=int(data.rsplit(":", 1)[1]))
        return
    if data.startswith("pet_current:"):
        try:
            pet = set_current_pet(chat_id, int(data.rsplit(":", 1)[1]))
            send_message(
                chat_id,
                f"接下来底部互动按钮会先照顾：{pet['name']}。\n这个聊天仍然是你和所有宠物的群聊。",
                reply_markup=MAIN_REPLY_KEYBOARD,
            )
        except (RuntimeError, requests.RequestException) as exc:
            send_message(chat_id, f"指定互动对象失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    if data.startswith("pet_settings:"):
        show_pet_settings(chat_id, int(data.rsplit(":", 1)[1]))
        return
    if data.startswith("stickers:generate:"):
        start_sticker_pack_generation(chat_id, int(data.rsplit(":", 1)[1]))
        return
    if data == "pet_create:start":
        start_pet_create_flow(chat_id)
        return
    if data.startswith("pet_create:species:"):
        set_pet_create_species(chat_id, data.rsplit(":", 1)[1])
        return
    if data.startswith("pet_delete:ask:"):
        ask_delete_pet(chat_id, int(data.rsplit(":", 1)[1]))
        return
    if data.startswith("pet_delete:confirm:"):
        delete_pet_from_chat(chat_id, int(data.rsplit(":", 1)[1]))
        return
    if data.startswith("prompt_set:"):
        parts = data.split(":")
        if len(parts) == 3:
            _prefix, pet_id, field = parts
            pet = find_pet(int(pet_id), chat_id=chat_id)
            if pet is None:
                send_message(chat_id, "这只宠物已经不存在了。", reply_markup=MAIN_REPLY_KEYBOARD)
                return
        else:
            field = data.split(":", 1)[1]
            pet = get_current_pet(chat_id)
        PENDING_SET_FIELDS[chat_id] = {"field": field, "pet_id": int(pet["id"])}
        send_message(chat_id, f"正在设置：{pet['name']}。\n请输入新的 {field}。")
        return
    if data.startswith("prompt_profile:"):
        _prefix, pet_id, note_type = data.split(":", 2)
        start_profile_note_flow(chat_id, int(pet_id), note_type)
        return
    if data == "set:avatar":
        start_avatar_flow(chat_id)
        return
    if data.startswith("set:avatar:"):
        start_avatar_flow(chat_id, pet_id=int(data.rsplit(":", 1)[1]))
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
            pet = update_current_pet(chat_id, field, value)
            send_message(
                chat_id,
                f"设置好啦：{pet['name']} 的 {field} 已更新为 {value}。",
                reply_markup=SETTINGS_MENU,
            )
        except RuntimeError as exc:
            send_message(chat_id, f"设置失败：{exc}", reply_markup=SETTINGS_MENU)
        return
    if data.startswith("set_pet:"):
        _prefix, pet_id, field, value = data.split(":", 3)
        try:
            pet = update_pet_by_id(int(pet_id), field, value, chat_id=chat_id)
            send_message(
                chat_id,
                f"设置好啦：{pet['name']} 的 {field} 已更新为 {value}。",
                reply_markup=pet_settings_keyboard(int(pet_id)),
            )
        except RuntimeError as exc:
            send_message(chat_id, f"设置失败：{exc}", reply_markup=MAIN_REPLY_KEYBOARD)
        return
    if data.startswith("act:"):
        handle_action_button(chat_id, data.split(":", 1)[1])
        return

    send_message(chat_id, "这个按钮我还不会处理。", reply_markup=MAIN_REPLY_KEYBOARD)


def handle_message(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not is_chat_allowed(chat_id):
        send_message(chat_id, "当前需要邀请或订阅后才能使用这个宠物助手。")
        return
    remember_owner_display_name(chat_id, message.get("from"))

    text = (message.get("text") or "").strip()
    if handle_avatar_photo(chat_id, message):
        return
    if handle_memory_photo(chat_id, message):
        return
    if handle_pet_create_text(chat_id, text):
        return
    if handle_relationship_text(chat_id, text):
        return
    if handle_friendship_invite_command(chat_id, text):
        return
    if handle_pending_text(chat_id, text):
        return
    if handle_avatar_style_text(chat_id, text):
        return
    if handle_memory_photo_text(chat_id, text):
        return
    if handle_friend_memory_share_confirmation_text(chat_id, text):
        return
    if handle_pet_memory_text(chat_id, text):
        return
    if handle_friend_owner_share_text(chat_id, text):
        return

    if text.startswith("/start"):
        send_main_menu(chat_id)
    elif text == "查看状态":
        handle_status_command(chat_id)
    elif text == "桌面陪伴":
        handle_desktop_companion(chat_id)
    elif text == "宠物列表":
        handle_pets_command(chat_id)
    elif text in {"宠物群聊", "选择宠物"}:
        handle_pet_group_command(chat_id)
    elif text == "宠物关系":
        start_relationship_flow(chat_id)
    elif text == "宠物好友":
        start_friendship_invite_flow(chat_id)
    elif text == "宠物记忆":
        handle_memory_menu(chat_id)
    elif text == "创建宠物":
        start_pet_create_flow(chat_id)
    elif text == "小助手":
        handle_assistant_text(chat_id, text)
    elif text == "设置资料":
        send_message(chat_id, "资料设置已经移到「宠物列表」里，每只宠物卡片下都有设置入口。", reply_markup=MAIN_REPLY_KEYBOARD)
    elif text == "定制形象":
        remove_reply_keyboard(chat_id)
        send_message(chat_id, "形象定制入口已经移到创建宠物后的下一步。", reply_markup=MAIN_REPLY_KEYBOARD)
    elif text in ACTION_BUTTON_MAP:
        handle_action_button(chat_id, ACTION_BUTTON_MAP[text])
    elif handle_assistant_text(chat_id, text):
        return
    elif handle_pet_group_chat_text(chat_id, text):
        return


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

        try:
            maybe_send_friendship_daily_messages()
        except Exception as exc:
            log_exception("friend_daily_message_tick_failed", None, exc)

        try:
            maybe_send_due_assistant_items()
        except Exception as exc:
            log_exception("assistant_due_scan_tick_failed", None, exc)

        time.sleep(1)


if __name__ == "__main__":
    configure_bot_ui()
    if PROACTIVE_TICKS_ENABLED:
        start_proactive_tick_loop()
    poll_forever()
