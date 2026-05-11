import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"


def anthropic_llm_call(messages: list, tools: list) -> dict:
    kwargs = {"model": MODEL, "max_tokens": 4096, "messages": messages, "tools": tools}

    # 提取 system prompt（不属于 messages）
    filtered = [m for m in messages if m["role"] != "system"]
    system_msgs = [m["content"] for m in messages if m["role"] == "system"]
    kwargs["messages"] = filtered
    if system_msgs:
        kwargs["system"] = system_msgs[0]

    response = _client.messages.create(**kwargs)

    if response.stop_reason == "tool_use":
        return {
            "stop_reason": "tool_use",
            "content": [
                {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                for b in response.content
                if b.type == "tool_use"
            ],
        }

    text = next((b.text for b in response.content if hasattr(b, "text")), "")
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}
