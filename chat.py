"""
命令行对话界面
运行：python3 chat.py
"""
from agent import run_agent
from prompts import ASSISTANT_PROMPT
from rag import build_knowledge_base
import os


def check_knowledge_base():
    if not os.path.exists("chroma_db"):
        print("知识库不存在，正在构建...")
        build_knowledge_base()


def main():
    check_knowledge_base()

    print("=" * 50)
    print("Agent 已启动，输入 'quit' 或 'exit' 退出")
    print("=" * 50)

    history = None

    while True:
        try:
            user_input = input("\n你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "退出"):
            print("再见！")
            break

        answer, history = run_agent(
            user_input,
            verbose=False,
            history=history,
            system_prompt=ASSISTANT_PROMPT,
        )
        print(f"\nAgent：{answer}")


if __name__ == "__main__":
    main()
