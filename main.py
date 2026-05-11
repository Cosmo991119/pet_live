"""
入口：测试 agent
"""
from agent import run_agent
from prompts import ASSISTANT_PROMPT as SYSTEM_PROMPT

if __name__ == "__main__":
    print("=" * 50)
    print("测试1：计算（必须用工具）")
    print("=" * 50)
    run_agent("128乘以256等于多少", verbose=True, system_prompt=SYSTEM_PROMPT)
    run_agent("深圳现在是什么天气?", verbose=True, system_prompt=SYSTEM_PROMPT)

    print("\n")
    print("=" * 50)
    print("测试2：多轮对话 + 记忆")
    print("=" * 50)
    history = None
    questions = [
        "帮我记住我最喜欢的编程语言是C++",
        "我最喜欢什么编程语言？",
        "那我应该学Python还是继续用C++做AI开发？",
    ]
    for q in questions:
        _, history = run_agent(q, verbose=True, history=history, system_prompt=SYSTEM_PROMPT)
        print()
