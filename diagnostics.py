"""Small structured diagnostics helpers for local debugging."""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


LOG_DIR = Path("logs")
LOG_PATH = LOG_DIR / "pet_agent_diagnostics.jsonl"


def new_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def log_event(
    event: str,
    trace_id: Optional[str] = None,
    **fields: Any,
) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "event": event,
        "trace_id": trace_id,
        **fields,
    }
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def log_exception(
    event: str,
    trace_id: Optional[str],
    exc: BaseException,
    **fields: Any,
) -> None:
    log_event(
        event,
        trace_id,
        error_type=type(exc).__name__,
        error=str(exc),
        traceback=traceback.format_exc(),
        **fields,
    )
