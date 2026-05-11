"""Small deterministic work-helper actions for the desktop pet shell."""

import re
from typing import Any


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？.!?])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _summary(text: str) -> dict[str, Any]:
    sentences = _sentences(text)
    if not sentences:
        raise ValueError("text is required")

    selected = sentences[:3]
    return {
        "mode": "summarize",
        "title": "小助手总结好了",
        "result": "\n".join(selected),
        "items": selected,
    }


def _todos(text: str) -> dict[str, Any]:
    chunks = re.split(r"[\n。；;.!?！？]+", text.strip())
    items = []
    for chunk in chunks:
        cleaned = chunk.strip(" -\t")
        if cleaned:
            items.append(cleaned)
    if not items:
        raise ValueError("text is required")

    todos = [f"- {item}" for item in items[:8]]
    return {
        "mode": "todos",
        "title": "我把事情叼成待办了",
        "result": "\n".join(todos),
        "items": items[:8],
    }


def assist_with_text(mode: str, text: str) -> dict[str, Any]:
    """Return a JSON-ready helper result for safe local text tasks."""
    if mode == "summarize":
        return _summary(text)
    if mode == "todos":
        return _todos(text)
    raise ValueError("mode must be one of ['summarize', 'todos']")
