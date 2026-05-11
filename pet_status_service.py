"""
Pet status presentation service.

This module turns backend state and stats into short user-facing text. It is
kept separate from Telegram so desktop and other clients can reuse it later.
"""

from typing import Any


def _bar(value: float) -> str:
    filled = max(0, min(5, round(value / 20)))
    return "#" * filled + "-" * (5 - filled)


def _mood_line(pet_name: str, state: dict[str, Any]) -> str:
    hunger = float(state.get("hunger", 0))
    thirst = float(state.get("thirst", 0))
    energy = float(state.get("energy", 0))
    mood = float(state.get("mood", 0))
    is_sleeping = bool(state.get("is_sleeping", False))

    if is_sleeping:
        return f"{pet_name}现在在睡觉，电量正在慢慢回满。"
    if thirst >= 70:
        return f"{pet_name}有点口渴，正在惦记水池。"
    if hunger >= 70:
        return f"{pet_name}有点饿，可能快要去吃饭了。"
    if energy <= 30:
        return f"{pet_name}有点困，想窝一会儿。"
    if mood >= 70:
        return f"{pet_name}心情不错，尾巴都快藏不住了。"
    return f"{pet_name}状态平稳，正在自己的小世界里晃悠。"


def format_pet_status(
    pet: dict[str, Any],
    snapshot: dict[str, Any],
    today_stats: dict[str, Any],
) -> str:
    """Create a compact status message for chat clients."""
    pet_name = pet["name"]
    state = snapshot["state"]
    totals = today_stats["totals"]

    lines = [
        _mood_line(pet_name, state),
        "",
        f"饥饿 {_bar(state['hunger'])} {state['hunger']:.0f}/100",
        f"口渴 {_bar(state['thirst'])} {state['thirst']:.0f}/100",
        f"精力 {_bar(state['energy'])} {state['energy']:.0f}/100",
        f"心情 {_bar(state['mood'])} {state['mood']:.0f}/100",
        f"亲密 {_bar(state['affection'])} {state['affection']:.0f}/100",
        "",
        (
            "今天："
            f"吃饭 {totals['eat_count']} 次，"
            f"喝水 {totals['drink_count']} 次，"
            f"玩耍 {totals['play_count']} 次，"
            f"厕所 {totals['poop_count']} 次。"
        ),
    ]
    return "\n".join(lines)


def format_action_reply(
    pet: dict[str, Any],
    action: str,
    snapshot: dict[str, Any],
    generated_message: str = "",
) -> str:
    """Create a pet-like reply after an owner action."""
    pet_name = pet["name"]
    call_name = pet["owner_call_name"]
    personality = pet["personality"]
    state = snapshot["state"]

    if generated_message:
        return generated_message

    templates = {
        "feed": {
            "sweet": f"{call_name}，饭饭到了！{pet_name}认真吃完，等一下要贴贴。",
            "cool": f"{call_name}，我吃了。只是刚好需要补充能量，不是特地等你喂。",
            "energetic": f"{call_name}！开饭啦开饭啦，{pet_name}补充元气成功。",
            "gentle": f"{call_name}，{pet_name}吃到饭了，会乖乖照顾自己的。",
        },
        "refill": {
            "sweet": f"{call_name}，水变满啦，我的小水池又亮晶晶了。",
            "cool": f"{call_name}，水补好了。我会自己喝，不用一直盯着。",
            "energetic": f"{call_name}！水池补给完成，咕嘟预备队集合。",
            "gentle": f"{call_name}，谢谢你加水，我待会儿会去喝一点。",
        },
        "play": {
            "sweet": f"{call_name}，刚刚一起玩好开心，{pet_name}现在想围着你转圈。",
            "cool": f"{call_name}，刚才那不叫撒娇，只是适量活动。",
            "energetic": f"{call_name}！再玩一会儿嘛，我现在整只宠都亮起来了。",
            "gentle": f"{call_name}，刚才玩得很开心，{pet_name}心情轻轻变好了。",
        },
        "pet": {
            "sweet": f"{call_name}，摸摸收到了，{pet_name}要把脑袋再递过来一点。",
            "cool": f"{call_name}，可以了。再摸一下也不是不行。",
            "energetic": f"{call_name}！摸摸充电成功，亲密度咻地一下上来了。",
            "gentle": f"{call_name}，被摸摸之后安心多了，我会乖一点。",
        },
        "clean": {
            "sweet": f"{call_name}，洗干净啦，{pet_name}现在香香软软的。",
            "cool": f"{call_name}，清洁完成。形象管理也是必要的。",
            "energetic": f"{call_name}！清洁完毕，闪亮登场。",
            "gentle": f"{call_name}，现在干净舒服多了，谢谢你照顾我。",
        },
        "lullaby": {
            "sweet": f"{call_name}，声音轻轻的，{pet_name}要把眼睛眯起来了。",
            "cool": f"{call_name}，这首还不错。我只是稍微休息一下。",
            "energetic": f"{call_name}，我会努力安静下来，虽然脑袋里还在蹦蹦跳。",
            "gentle": f"{call_name}，听到哄睡声音了，我慢慢放松下来。",
        },
    }

    message = templates.get(action, {}).get(
        personality,
        f"{call_name}，{pet_name}收到你的照顾啦。",
    )
    if bool(state.get("is_sleeping", False)):
        return f"{message}\n现在我有点困，想窝着休息一会儿。"
    return message
