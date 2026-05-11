"""Run the local pet agent product loop.

This starts the FastAPI backend and Telegram bot together so the Telegram
button flow does not depend on remembering separate dev commands.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"


def _open_log(name: str):
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / name
    return path.open("ab")


def _start_process(label: str, command: list[str], log_name: str) -> tuple[str, subprocess.Popen, object]:
    log_file = _open_log(log_name)
    log_file.write(f"\n--- starting {label}: {' '.join(command)} ---\n".encode("utf-8"))
    log_file.flush()
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"{label} started pid={process.pid}, log=logs/{log_name}")
    return label, process, log_file


def _terminate(label: str, process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    print(f"stopping {label} pid={process.pid}")
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FastAPI and Telegram bot together.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn reload.")
    args = parser.parse_args()

    api_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "api:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if not args.no_reload:
        api_command.append("--reload")

    processes: list[tuple[str, subprocess.Popen, object]] = [
        _start_process("fastapi", api_command, "fastapi.log"),
        _start_process("telegram", [sys.executable, "telegram_bot.py"], "telegram_bot.log"),
    ]

    shutting_down = False

    def _handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutting_down
        shutting_down = True
        print(f"received signal {signum}; shutting down")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    exit_code = 0
    try:
        while not shutting_down:
            for label, process, _log_file in processes:
                code = process.poll()
                if code is not None:
                    print(f"{label} exited with code {code}; shutting down companion process")
                    exit_code = code or 1
                    shutting_down = True
                    break
            time.sleep(1)
    finally:
        for label, process, log_file in processes:
            _terminate(label, process)
            log_file.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
