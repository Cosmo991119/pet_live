"""
Event-message agent for pet behavior sessions.

The database layer owns facts. This module turns those facts into a structured,
pet-like message that can be shown in the console today and sent to Telegram
later.
"""

import hashlib
import json
from typing import Any, Callable, Optional

from pet_db import save_event_message


PET_EVENT_MESSAGE_PROMPT_VERSION = "pet_event_message_v1"
FALLBACK_MODEL_NAME = "fallback-template"
DEFAULT_LLM_MODEL_NAME = "openai-default"

LLMCall = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]


PERSONALITY_LABELS = {
    "sweet": "甜甜撒娇型",
    "cool": "傲娇高冷型",
    "energetic": "活泼话痨型",
    "gentle": "温柔乖巧型",
}

PERSONALITY_VOICE_GUIDES = {
    "sweet": "性格语气：甜甜撒娇型。更爱贴贴、撒娇、邀功，句子软一点，可以带一点黏人的小心思。",
    "cool": "性格语气：傲娇高冷型。嘴上克制、有点别扭，少撒娇，不要像系统报告，可以用轻微的反差可爱。",
    "energetic": "性格语气：活泼话痨型。动作感强，像刚跑回来汇报小发现，句子更有弹性，但别刷屏。",
    "gentle": "性格语气：温柔乖巧型。安静、体贴、会自己照顾自己，像轻轻告诉主人一件小事。",
}

BEHAVIOR_LABELS = {
    "eat": "吃饭",
    "drink": "喝水",
    "poop": "上厕所",
    "play": "玩耍",
}


def format_speaker_labeled_message(message: str, pet_name: str) -> str:
    """Return pet speech with one stable speaker prefix."""
    name = str(pet_name or "").strip()
    text = str(message)
    if not name or not text.strip():
        return text

    stripped = text.lstrip()
    existing_labels = (
        f"{name}:",
        f"{name}：",
        f"【{name}】",
        f"[{name}]",
    )
    if stripped.startswith(existing_labels):
        return text
    return f"{name}：{text}"


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


def _fallback_variant_index(
    pet: dict[str, Any],
    event: dict[str, Any],
    option_count: int,
) -> int:
    if option_count <= 1:
        return 0

    try:
        return (int(pet.get("id", 0)) + int(event.get("id", 0))) % option_count
    except (TypeError, ValueError):
        seed = "|".join(
            str(part or "")
            for part in (
                pet.get("id"),
                pet.get("name"),
                event.get("id"),
                event.get("behavior"),
                event.get("location_name"),
                event.get("occurred_at"),
            )
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % option_count


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

    templates = {
        "eat": {
            "sweet": [
                f"{call_name}，我去吃饭啦，吃饱一点才有力气贴贴你。",
                f"饭碗那边香香的，{pet_name}吃完以后有一点点想邀功。",
                f"{call_name}，饭饭已经认真吃好啦，待会儿想轻轻蹭你一下。",
            ],
            "cool": [
                f"{call_name}，我去吃饭了。只是顺便，不是特地让你夸我。",
                f"饭碗那边我看过了，也吃过了，你可以假装没发现我很认真。",
                f"{call_name}，我补了一点能量，接下来继续优雅路过。",
            ],
            "energetic": [
                f"{call_name}！我开饭啦，吃完感觉脚步都轻快了一点。",
                f"饭碗那边刚刚很热闹，{pet_name}已经精神抖擞地回来了。",
                f"{call_name}！我吃好啦，下一站准备继续陪你巡逻。",
            ],
            "gentle": [
                f"{call_name}，我刚才去吃饭了，会慢慢把自己照顾好。",
                f"{pet_name}去饭盆旁边吃了一会儿，现在安安静静地回来了。",
                f"{call_name}，饭已经吃好啦，我会乖乖留一点精神陪你。",
            ],
        },
        "drink": {
            "sweet": [
                f"{call_name}，{pet_name}刚刚去喝水啦，水碗边今天有点像我的快乐小基地。",
                f"{call_name}，我去水碗边咕嘟了一下，顺便想了你一下。",
                f"水碗边咕嘟咕嘟了一小会儿，{pet_name}清清爽爽地回来啦。",
            ],
            "cool": [
                f"{call_name}，我顺路喝了点水。别看我，我只是刚好路过。",
                f"水碗那边我碰巧去了一趟，也就喝了几口而已。",
                f"{call_name}，我刚喝完水，准备继续若无其事地巡视。",
            ],
            "energetic": [
                f"{call_name}！我喝水啦，咕嘟咕嘟，像给自己重新开机了一下。",
                f"水碗那边刚刚响起咕嘟声，{pet_name}又精神一点啦。",
                f"{call_name}！我喝完水啦，可以继续蹦跶一小会儿。",
            ],
            "gentle": [
                f"{call_name}，我刚才去喝了几口水，会慢慢照顾好自己。",
                f"{pet_name}去水碗边待了一小会儿，胡须旁边像沾了点清凉。",
                f"{call_name}，我记得喝水啦，现在轻轻回来陪你。",
            ],
        },
        "poop": {
            "sweet": [
                f"{call_name}，我刚才去厕所啦，办好了一件有点害羞的小正事。",
                f"厕所那边的小事处理好啦，{pet_name}现在轻松一点点。",
                f"{call_name}，我处理完小事务回来了，继续乖乖待在你附近。",
            ],
            "cool": [
                f"{call_name}，厕所那边我去过了。你晚点再看也行。",
                f"我处理完厕所那边的事了，出来时顺便整理了一下表情。",
                f"{call_name}，那件小事结束了，我们可以都装作很从容。",
            ],
            "energetic": [
                f"{call_name}！我去厕所啦，出来以后脚步都轻快了一点。",
                f"厕所那边刚刚被我认真拜访过，{pet_name}轻装回来了。",
                f"{call_name}！小事务解决完毕，我又可以到处晃一圈了。",
            ],
            "gentle": [
                f"{call_name}，我刚才去厕所了，出来以后安静地整理了一下自己。",
                f"厕所那边已经处理好啦，{pet_name}现在舒服一些。",
                f"{call_name}，我把厕所的小事做好了，晚点你再看也来得及。",
            ],
        },
        "play": {
            "sweet": [
                f"{call_name}，{pet_name}刚刚玩了一会儿，现在心情亮晶晶的。",
                f"{call_name}，我刚活动了一下，快乐都快藏不住啦。",
                f"{call_name}，{pet_name}玩够一小轮了，想把开心分你一点。",
            ],
            "cool": [
                f"{call_name}，我刚刚活动了一下。只是稍微玩玩，别说我幼稚。",
                f"{call_name}，我稍微动了动，不代表我很兴奋。",
                f"{call_name}，刚才只是短暂放松，你可以理解为优雅热身。",
            ],
            "energetic": [
                f"{call_name}！我刚刚玩得超开心，现在整只宠都在冒元气。",
                f"{call_name}！我刚玩完一小轮，快乐都快从脚底弹出来了。",
                f"{call_name}！我玩了一小会儿，现在想原地转两圈。",
            ],
            "gentle": [
                f"{call_name}，{pet_name}刚刚玩了一会儿，看起来心情轻松了不少。",
                f"{call_name}，{pet_name}活动了一小会儿，现在安静又开心。",
                f"{call_name}，我刚玩了一下，心情变得软软亮亮的。",
            ],
        },
    }
    behavior_templates = templates.get(behavior, templates["play"])
    options = behavior_templates.get(personality, behavior_templates["gentle"])
    message = options[_fallback_variant_index(pet, event, len(options))]

    internal_signal = "repeated_session" if raw_count > 1 else "normal"
    return {
        "message": message,
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
            "personality_voice_guide": PERSONALITY_VOICE_GUIDES.get(
                pet["personality"],
                PERSONALITY_VOICE_GUIDES["gentle"],
            ),
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
        "必须贴合 pet.personality_voice_guide 的性格语气，让不同宠物像不同角色。"
        "数据只用于后台判断，默认不要直接报数字。"
        "不要每条都用主人称呼开头，可以从动作、感受、地点小细节开头。"
        "不要写成监控播报，避免把“状态、平稳、掌控、不用担心、任务完成”当作填充句。"
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
    from llm_openai import openai_llm_call

    return openai_llm_call(messages, [])


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
        return result, response.get("model", DEFAULT_LLM_MODEL_NAME)
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
    pet_name = str(pet.get("name", "")).strip()
    result = {
        **result,
        "message": format_speaker_labeled_message(result["message"], pet_name),
    }
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
        "pet_name": pet_name,
        "message": result,
        "stored_message": saved,
        "model_name": model_name,
        "prompt_version": PET_EVENT_MESSAGE_PROMPT_VERSION,
    }
