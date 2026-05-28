"""
Summary agent for day/week/month pet behavior stats.

The summary agent consumes aggregated stats, not raw events. Program code owns
the calculations; the LLM only explains trends and writes gentle suggestions.
"""

import json
from typing import Any, Callable, Optional

from pet_db import get_pet, get_pet_stats, save_summary
from pet_message_agent import _safe_json_from_text


PET_SUMMARY_PROMPT_VERSION = "pet_summary_v1"
FALLBACK_MODEL_NAME = "fallback-template"
DEFAULT_LLM_MODEL_NAME = "openai-default"

LLMCall = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]


def _fallback_summary(pet: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    totals = stats["totals"]
    pet_name = pet["name"]
    range_label = {"day": "这一天", "week": "这段时间", "month": "这段时间"}[
        stats["range"]
    ]

    alerts = []
    suggestions = []

    if totals["drink_count"] == 0:
        alerts.append(
            {
                "level": "info",
                "message": f"{pet_name}{range_label}没有记录到喝水，可以晚点留意一下水碗。",
            }
        )
        suggestions.append("保持水碗清洁，观察它后续是否主动喝水。")

    if totals["poop_count"] == 0:
        alerts.append(
            {
                "level": "info",
                "message": f"{pet_name}{range_label}没有记录到上厕所，可以继续观察。",
            }
        )

    if totals["sleep_minutes"] == 0:
        suggestions.append("暂时没有完整睡眠记录，等 sleep_start 和 sleep_end 都记录后总结会更准确。")

    if not alerts and not suggestions:
        suggestions.append("继续保持观察，当前记录看起来比较平稳。")

    return {
        "summary": (
            f"{pet_name}{range_label}共有吃饭 {totals['eat_count']} 次、喝水 "
            f"{totals['drink_count']} 次、上厕所 {totals['poop_count']} 次，"
            f"完整睡眠记录约 {round(totals['sleep_minutes'] / 60, 1)} 小时。整体先按平稳观察。"
        ),
        "alerts": alerts,
        "suggestions": suggestions,
    }


def _build_prompt(pet: dict[str, Any], stats: dict[str, Any]) -> list[dict[str, Any]]:
    context = {
        "pet": {
            "name": pet["name"],
            "species": pet["species"],
            "personality": pet["personality"],
            "owner_call_name": pet["owner_call_name"],
        },
        "stats": stats,
    }

    system = (
        "你是宠物行为助手的周期总结模块。你必须只输出一个 JSON object。"
        "你只能基于 stats 中已有事实总结，不要编造。"
        "可以描述趋势、给温和观察提醒、建议异常持续时咨询兽医。"
        "禁止医疗诊断、用药建议或治疗方案。"
        "总结要清楚、有信息密度，轻微保留宠物个性，但不要像实时撒娇消息。"
    )
    user = (
        "请基于下面聚合统计生成结构化总结。输出字段必须是："
        "summary, alerts, suggestions。"
        "alerts 是对象数组，每个对象包含 level 和 message；"
        "suggestions 是字符串数组。"
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


def _normalize_summary(parsed: dict[str, Any]) -> dict[str, Any]:
    summary = str(parsed.get("summary", "")).strip()
    if not summary:
        raise ValueError("summary is required")

    alerts = parsed.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []
    normalized_alerts = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        level = alert.get("level", "info")
        if level not in {"info", "warning"}:
            level = "info"
        message = str(alert.get("message", "")).strip()
        if message:
            normalized_alerts.append({"level": level, "message": message})

    suggestions = parsed.get("suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []
    suggestions = [str(item).strip() for item in suggestions if str(item).strip()]

    return {
        "summary": summary,
        "alerts": normalized_alerts,
        "suggestions": suggestions,
    }


def generate_summary(
    pet: dict[str, Any],
    stats: dict[str, Any],
    llm_call: Optional[LLMCall] = None,
    use_llm: bool = True,
) -> tuple[dict[str, Any], str]:
    """Generate one structured summary and return (summary_json, model_name)."""
    if not use_llm:
        return _fallback_summary(pet, stats), FALLBACK_MODEL_NAME

    messages = _build_prompt(pet, stats)
    try:
        response = (llm_call or _call_default_llm)(messages, [])
        text = response["content"][0]["text"]
        parsed = _safe_json_from_text(text)
        if not parsed:
            raise ValueError("LLM did not return parseable JSON")
        return _normalize_summary(parsed), response.get("model", DEFAULT_LLM_MODEL_NAME)
    except Exception:
        return _fallback_summary(pet, stats), FALLBACK_MODEL_NAME


def generate_and_store_summary(
    pet_id: int,
    range_type: str,
    end_date: Optional[str] = None,
    llm_call: Optional[LLMCall] = None,
    use_llm: bool = True,
    db_path: Any = None,
) -> dict[str, Any]:
    """Compute stats, generate a summary, store it, and return the result."""
    stats_kwargs = {"db_path": db_path} if db_path is not None else {}
    pet_kwargs = {"db_path": db_path} if db_path is not None else {}

    pet = get_pet(pet_id, **pet_kwargs)
    if pet is None:
        raise ValueError(f"pet_id {pet_id} does not exist")

    stats = get_pet_stats(pet_id, range_type, end_date=end_date, **stats_kwargs)
    summary, model_name = generate_summary(
        pet=pet,
        stats=stats,
        llm_call=llm_call,
        use_llm=use_llm,
    )

    save_kwargs = {"db_path": db_path} if db_path is not None else {}
    stored = save_summary(
        pet_id=pet_id,
        range_type=range_type,
        start_date=stats["start_date"],
        end_date=stats["end_date"],
        stats=stats,
        summary=summary,
        model_name=model_name,
        prompt_version=PET_SUMMARY_PROMPT_VERSION,
        **save_kwargs,
    )

    return {
        "pet_id": pet_id,
        "range": range_type,
        "start_date": stats["start_date"],
        "end_date": stats["end_date"],
        "summary": summary,
        "stored_summary": stored,
        "model_name": model_name,
        "prompt_version": PET_SUMMARY_PROMPT_VERSION,
    }
