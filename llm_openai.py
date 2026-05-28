"""
OpenAI GPT LLM adapter.

Converts OpenAI Chat Completions tool-call responses into the Anthropic-like
shape expected by agent.py.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-5.5")


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("缺少 OPENAI_API_KEY，请先在 .env 中配置。")
    return OpenAI(api_key=api_key)


def _tools_to_openai(tools: list) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def _messages_to_openai(messages: list) -> list:
    result = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            result.append({"role": role, "content": content})

        elif isinstance(content, list):
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            tool_results = [b for b in content if b.get("type") == "tool_result"]
            texts = [b for b in content if b.get("type") == "text"]

            if tool_uses:
                result.append(
                    {
                        "role": "assistant",
                        "content": texts[0]["text"] if texts else None,
                        "tool_calls": [
                            {
                                "id": b["id"],
                                "type": "function",
                                "function": {
                                    "name": b["name"],
                                    "arguments": json.dumps(b["input"]),
                                },
                            }
                            for b in tool_uses
                        ],
                    }
                )
            elif tool_results:
                for b in tool_results:
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": b["tool_use_id"],
                            "content": b["content"],
                        }
                    )
            elif texts:
                result.append({"role": role, "content": texts[0]["text"]})

    return result


def _response_to_anthropic(response) -> dict:
    choice = response.choices[0]
    msg = choice.message

    if choice.finish_reason == "tool_calls" and msg.tool_calls:
        return {
            "stop_reason": "tool_use",
            "model": response.model,
            "content": [
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ],
        }

    return {
        "stop_reason": "end_turn",
        "model": response.model,
        "content": [{"type": "text", "text": msg.content or ""}],
    }


def openai_llm_call(messages: list, tools: list) -> dict:
    """Call OpenAI GPT and return the internal Anthropic-like response shape."""
    kwargs = {
        "model": MODEL,
        "messages": _messages_to_openai(messages),
    }
    if tools:
        kwargs["tools"] = _tools_to_openai(tools)
        kwargs["tool_choice"] = "auto"

    response = _client().chat.completions.create(**kwargs)
    return _response_to_anthropic(response)
