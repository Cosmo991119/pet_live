"""
POE LLM 适配层：把 OpenAI 格式转成 agent.py 期望的 Anthropic 格式
换真实 Anthropic key 后，直接删掉这个文件，agent.py 改一行即可
"""
import json
import os
from dotenv import load_dotenv
import openai

load_dotenv()

_client = openai.OpenAI(
    api_key=os.getenv("POE_API_KEY"),
    base_url="https://api.poe.com/v1",
)

# 改这里换模型：支持的模型参考 POE 文档
MODEL = "gemini-3-flash"


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
                # assistant 消息带工具调用
                result.append({
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
                })
            elif tool_results:
                # 工具结果：OpenAI 用独立的 "tool" role
                for b in tool_results:
                    result.append({
                        "role": "tool",
                        "tool_call_id": b["tool_use_id"],
                        "content": b["content"],
                    })
            elif texts:
                result.append({"role": role, "content": texts[0]["text"]})

    return result


def _response_to_anthropic(response) -> dict:
    choice = response.choices[0]
    msg = choice.message

    if choice.finish_reason == "tool_calls" and msg.tool_calls:
        return {
            "stop_reason": "tool_use",
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
        "content": [{"type": "text", "text": msg.content or ""}],
    }


def poe_llm_call(messages: list, tools: list) -> dict:
    """
    真实 LLM 调用，返回 Anthropic 格式。
    agent.py 里把 mock_llm_call 换成这个即可。
    """
    response = _client.chat.completions.create(
        model=MODEL,
        messages=_messages_to_openai(messages),
        tools=_tools_to_openai(tools),
        tool_choice="auto",
    )
    return _response_to_anthropic(response)
