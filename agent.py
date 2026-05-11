"""
Agent 核心层：ReAct 循环
真实版本：LLM 决定调什么工具
Mock 版本：用预设规则模拟 LLM 决策，展示相同的数据流
"""

import json
from tools import TOOLS, execute_tool


def _rewrite_search_query(query: str, messages: list) -> str:
    """从对话历史提取最近用户消息，补全追问为完整查询词"""
    recent_user_msgs = [
        m["content"] for m in messages
        if m["role"] == "user" and isinstance(m["content"], str)
    ][-3:-1]  # 取最近2条用户消息（不含当前）

    if not recent_user_msgs:
        return query

    context = " | ".join(recent_user_msgs)
    return f"{context} >> {query}"

# ── LLM 选择：改这一行切换 mock / 真实 ──
# from llm_poe import poe_llm_call as llm_call   # 真实 POE
# 未来换成 Anthropic：from llm_anthropic import anthropic_llm_call as llm_call
USE_REAL_LLM = True    # 改成 True 启用真实 LLM

# ──────────────────────────────────────────
# Mock LLM（模拟 Claude API 的响应格式）
# ──────────────────────────────────────────

def mock_llm_call(messages: list, tools: list) -> dict:
    """
    模拟 LLM 响应。
    真实 Claude API 返回格式相同：stop_reason + content blocks
    """
    last_user_msg = ""
    for msg in reversed(messages):
        if msg["role"] == "user":
            if isinstance(msg["content"], str):
                last_user_msg = msg["content"]
            break

    # 第一轮：分析问题，决定是否用工具
    tool_results_in_history = any(
        isinstance(msg.get("content"), list) and
        any(isinstance(b, dict) and b.get("type") == "tool_result" for b in msg["content"])
        for msg in messages
    )

    if not tool_results_in_history:
        # 还没搜索过 → 决定调工具
        if any(word in last_user_msg.lower() for word in ["什么", "是", "比较", "how", "what", "compare", "difference"]):
            # 提取搜索关键词
            query = last_user_msg.replace("？", "").replace("?", "").strip()
            return {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_001",
                        "name": "search_web",
                        "input": {"query": query}
                    }
                ]
            }
        elif any(word in last_user_msg for word in ["+", "-", "*", "/", "计算", "等于"]):
            expr = last_user_msg.replace("计算", "").replace("等于多少", "").strip()
            return {
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_002",
                        "name": "calculate",
                        "input": {"expression": expr}
                    }
                ]
            }

    # 有工具结果了 → 整合回答
    tool_result_content = ""
    for msg in messages:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_result_content = block.get("content", "")

    return {
        "stop_reason": "end_turn",
        "content": [
            {
                "type": "text",
                "text": f"基于搜索结果，我的回答是：\n\n{tool_result_content}\n\n如需更多信息请继续提问。"
            }
        ]
    }


# ──────────────────────────────────────────
# ReAct 核心循环
# ──────────────────────────────────────────

def run_agent(user_question: str, verbose: bool = True, history: list = None, system_prompt: str = None) -> tuple[str, list]:
    """
    ReAct loop with memory support.
    history: 传入上一轮的对话历史，实现多轮记忆
    system_prompt: agent 的角色和规则，每次注入但不存入历史
    返回 (answer, updated_history)
    """
    # 在历史基础上追加新问题，保留最近10轮防止超出 context window
    if history is None:
        messages = []
    else:
        messages = history[-20:]  # 每轮2条消息，保留最近10轮
    messages.append({"role": "user", "content": user_question})

    # system prompt 每次注入，不存入 history
    def build_llm_messages():
        if system_prompt:
            return [{"role": "system", "content": system_prompt}] + messages
        return messages
    step = 0
    max_steps = 10  # 防止无限循环

    if verbose:
        print(f"\n{'='*50}")
        print(f"用户问题: {user_question}")
        print(f"{'='*50}")

    while step < max_steps:
        step += 1
        if verbose:
            print(f"\n[Step {step}] LLM 思考中...")

        # 调用 LLM（带重试）
        response = None
        for attempt in range(3):
            try:
                if USE_REAL_LLM:
                    from llm_poe import poe_llm_call
                    response = poe_llm_call(build_llm_messages(), TOOLS)
                else:
                    response = mock_llm_call(build_llm_messages(), TOOLS)
                break  # 成功就退出重试循环
            except Exception as e:
                if verbose:
                    print(f"[Step {step}] LLM 调用失败 (第{attempt+1}次): {e}")
                if attempt == 2:
                    return f"Error: LLM 调用失败 3 次，放弃。最后错误: {e}", messages

        stop_reason = response["stop_reason"]

        if verbose:
            print(f"[Step {step}] LLM 决定: {stop_reason}")

        # ── 情况1：LLM 决定调工具 ──
        if stop_reason == "tool_use":
            tool_results = []
            for block in response["content"]:
                if block["type"] == "tool_use":
                    tool_name = block["name"]
                    tool_input = block["input"]

                    if verbose:
                        print(f"[Step {step}] 调用工具: {tool_name}({tool_input})")

                    try:
                        if tool_name == "search_knowledge":
                            tool_input["query"] = _rewrite_search_query(
                                tool_input["query"], messages
                            )
                            if verbose:
                                print(f"[Step {step}] 查询改写为: {tool_input['query']}")
                        result = execute_tool(tool_name, tool_input)
                    except Exception as e:
                        result = f"Error: 工具 '{tool_name}' 执行失败: {e}"

                    if verbose:
                        print(f"[Step {step}] 工具返回: {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                        "is_error": result.startswith("Error:")
                    })

            # 把 LLM 的决定 + 工具结果都加入对话历史
            messages.append({"role": "assistant", "content": response["content"]})
            messages.append({"role": "user", "content": tool_results})

        # ── 情况2：LLM 决定直接回答 ──
        elif stop_reason == "end_turn":
            final_answer = response["content"][0]["text"]
            if verbose:
                print(f"\n{'='*50}")
                print(f"最终回答:\n{final_answer}")
                print(f"{'='*50}")
            # 把这轮 assistant 回答也存进历史
            messages.append({"role": "assistant", "content": final_answer})
            return final_answer, messages

    return "Error: 超过最大步骤数", messages
