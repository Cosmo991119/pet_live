"""
Event-message agent for pet behavior sessions.

The database layer owns facts. This module turns those facts into a structured,
pet-like message that can be shown in the console today and sent to Telegram
later.
"""

import json
from typing import Any, Callable, Optional

from pet_db import save_event_message


PET_EVENT_MESSAGE_PROMPT_VERSION = "pet_event_message_v1"
FALLBACK_MODEL_NAME = "fallback-template"
DEFAULT_LLM_MODEL_NAME = "poe-default"

LLMCall = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]


PERSONALITY_LABELS = {
    "sweet": "甜甜撒娇型",
    "cool": "傲娇高冷型",
    "energetic": "活泼话痨型",
    "gentle": "温柔乖巧型",
}

BEHAVIOR_LABELS = {
    "eat": "吃饭",
    "drink": "喝水",
    "poop": "上厕所",
    "play": "玩耍",
}


def _safe_json_from_text(text: str) -> Optional[dict[str, Any]]:
    """Parse a JSON object from model text."""
    text = text.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _fallback_message(
    pet: dict[str, Any],
    event: dict[str, Any],
    session: Optional[dict[str, Any]],
) -> dict[str, Any]:
    pet_name = pet["name"]
    call_name = pet["owner_call_name"]
    personality = pet["personality"]
    behavior = event["behavior"]
    raw_count = session["raw_event_count"] if session else 1

    if behavior == "eat":
        templates = {
            "sweet": f"{call_name}，{pet_name}刚刚去吃饭啦，吃饱一点才有力气贴贴你。",
            "cool": f"{call_name}，我去吃饭了。只是正常补充能量，不用太激动。",
            "energetic": f"{call_name}！{pet_name}开饭啦，今天也要元气满满地干饭。",
            "gentle": f"{call_name}，{pet_name}刚刚吃饭了，会好好照顾自己的。",
        }
    elif behavior == "drink":
        templates = {
            "sweet": f"{call_name}，{pet_name}刚刚去喝水啦，水碗边今天有点像我的快乐小基地。",
            "cool": f"{call_name}，我顺路喝了点水，一切都在掌控中。",
            "energetic": f"{call_name}！我喝水啦，咕嘟咕嘟，补水任务完成。",
            "gentle": f"{call_name}，{pet_name}刚刚喝了点水，你不用担心。",
        }
    elif behavior == "poop":
        templates = {
            "sweet": f"{call_name}，{pet_name}刚刚去厕所啦，完成一件小正事。",
            "cool": f"{call_name}，厕所任务完成。你可以晚点再来检查。",
            "energetic": f"{call_name}！厕所打卡完成，今天也是认真生活的小朋友。",
            "gentle": f"{call_name}，{pet_name}刚刚去厕所了，状态看起来还平稳。",
        }
    else:
        templates = {
            "sweet": f"{call_name}，{pet_name}刚刚玩了一会儿，现在心情亮晶晶的。",
            "cool": f"{call_name}，我刚刚活动了一下。只是稍微玩玩，别说我幼稚。",
            "energetic": f"{call_name}！我刚刚玩得超开心，现在整只宠都在冒元气。",
            "gentle": f"{call_name}，{pet_name}刚刚玩了一会儿，看起来心情轻松了不少。",
        }

    internal_signal = "repeated_session" if raw_count > 1 else "normal"
    return {
        "message": templates.get(personality, templates["gentle"]),
        "severity": "normal",
        "facts_used": ["current_event", "current_session", "today_stats"],
        "internal_signal": internal_signal,
    }


def _build_prompt(
    pet: dict[str, Any],
    event: dict[str, Any],
    session: Optional[dict[str, Any]],
    today_stats: dict[str, Any],
    historical_baseline: Optional[dict[str, Any]],
) -> list[dict[str, Any]]:
    context = {
        "pet": {
            "name": pet["name"],
            "species": pet["species"],
            "personality": pet["personality"],
            "personality_label": PERSONALITY_LABELS.get(pet["personality"], "温柔乖巧型"),
            "owner_call_name": pet["owner_call_name"],
        },
        "current_event": {
            "behavior": event["behavior"],
            "behavior_label": BEHAVIOR_LABELS.get(event["behavior"], event["behavior"]),
            "location_name": event["location_name"],
            "occurred_at": event["occurred_at"],
            "confidence": event["confidence"],
        },
        "current_session": session or {},
        "today_stats": today_stats,
        "historical_baseline": historical_baseline or {},
    }

    system = (
        "你是宠物行为助手的文案生成模块。你必须只输出一个 JSON object。"
        "实时消息要像宠物对主人说话，讨喜、有性格，但不要像数据报表。"
        "数据只用于后台判断，默认不要直接报数字。"
        "可以做轻微观察提醒，但禁止医疗诊断、用药建议或治疗方案。"
    )
    user = (
        "请基于下面事实生成结构化实时消息。输出字段必须是："
        "message, severity, facts_used, internal_signal。"
        "severity 只能是 normal/info/warning。facts_used 是字符串数组。"
        "\n\n事实 JSON：\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _call_default_llm(messages: list[dict[str, Any]]) -> dict[str, Any]:
    from llm_poe import poe_llm_call

    return poe_llm_call(messages, [])


def generate_event_message(
    pet: dict[str, Any],
    event: dict[str, Any],
    session: Optional[dict[str, Any]],
    today_stats: dict[str, Any],
    historical_baseline: Optional[dict[str, Any]] = None,
    llm_call: Optional[LLMCall] = None,
    use_llm: bool = True,
) -> tuple[dict[str, Any], str]:
    """Generate a structured event message and return (message_json, model_name)."""
    if not use_llm:
        return _fallback_message(pet, event, session), FALLBACK_MODEL_NAME

    messages = _build_prompt(pet, event, session, today_stats, historical_baseline)

    try:
        response = (llm_call or _call_default_llm)(messages, [])
        text = response["content"][0]["text"]
        parsed = _safe_json_from_text(text)
        if not parsed:
            raise ValueError("LLM did not return parseable JSON")

        result = {
            "message": str(parsed["message"]),
            "severity": parsed.get("severity", "normal"),
            "facts_used": parsed.get("facts_used", ["current_event"]),
            "internal_signal": parsed.get("internal_signal", "normal"),
        }
        if result["severity"] not in {"normal", "info", "warning"}:
            result["severity"] = "normal"
        if not isinstance(result["facts_used"], list):
            result["facts_used"] = ["current_event"]
        return result, DEFAULT_LLM_MODEL_NAME
    except Exception:
        return _fallback_message(pet, event, session), FALLBACK_MODEL_NAME


def generate_and_store_event_message(
    pet: dict[str, Any],
    event: dict[str, Any],
    session: Optional[dict[str, Any]],
    today_stats: dict[str, Any],
    historical_baseline: Optional[dict[str, Any]] = None,
    llm_call: Optional[LLMCall] = None,
    use_llm: bool = True,
    db_path: Any = None,
) -> dict[str, Any]:
    """Generate an event message, store it, and return the structured result."""
    result, model_name = generate_event_message(
        pet=pet,
        event=event,
        session=session,
        today_stats=today_stats,
        historical_baseline=historical_baseline,
        llm_call=llm_call,
        use_llm=use_llm,
    )
    db_kwargs = {"db_path": db_path} if db_path is not None else {}
    saved = save_event_message(
        pet_id=pet["id"],
        event_id=event["id"],
        session_id=session["id"] if session else None,
        message=result["message"],
        severity=result["severity"],
        facts_used=result["facts_used"],
        internal_signal=result["internal_signal"],
        model_name=model_name,
        prompt_version=PET_EVENT_MESSAGE_PROMPT_VERSION,
        **db_kwargs,
    )
    return {
        "message": result,
        "stored_message": saved,
        "model_name": model_name,
        "prompt_version": PET_EVENT_MESSAGE_PROMPT_VERSION,
    }
