"""Unified runtime control for the local pet product loop."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from diagnostics import log_event, log_exception, new_trace_id
from pet_db import DB_PATH, DbPath, get_pet, list_pets


@dataclass
class DesktopCompanionResult:
    ok: bool
    code: str
    message: str
    trace_id: str
    pet: Optional[dict] = None
    pid: Optional[int] = None
    process: Optional[subprocess.Popen] = None


class PetRuntimeController:
    """Coordinate local runtime actions behind a small product-facing interface."""

    def __init__(
        self,
        *,
        project_root: Path,
        default_pet_id: str = "",
        db_path: DbPath = DB_PATH,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    ) -> None:
        self.project_root = Path(project_root)
        self.default_pet_id = default_pet_id
        self.db_path = db_path
        self._popen = popen
        self._desktop_process: Optional[subprocess.Popen] = None

    def launch_desktop_companion(self, chat_id: str = "") -> DesktopCompanionResult:
        trace_id = new_trace_id("desktop")
        try:
            pet = self._default_pet()
            manifest_url = self._profile(pet).get("desktop_pet_manifest_url", "")
            manifest_path = self._local_static_path(manifest_url)
            if manifest_path is None:
                return DesktopCompanionResult(
                    ok=False,
                    code="DESKTOP_ASSETS_MISSING",
                    message="这只宠物还没有可用的桌宠素材包。先点「定制形象」，确认预览后我就能把它带到桌面上。",
                    trace_id=trace_id,
                    pet=pet,
                )

            if self._desktop_process and self._desktop_process.poll() is None:
                return DesktopCompanionResult(
                    ok=True,
                    code="DESKTOP_ALREADY_RUNNING",
                    message=f"{pet['name']} 已经在桌面陪你了。",
                    trace_id=trace_id,
                    pet=pet,
                    pid=self._desktop_process.pid,
                    process=self._desktop_process,
                )

            log_event(
                "desktop_pet_launch_started",
                trace_id,
                chat_id=chat_id,
                pet_id=pet["id"],
                manifest=manifest_url,
            )
            log_dir = self.project_root / "logs"
            log_dir.mkdir(exist_ok=True)
            with (log_dir / "desktop_pet_launch.log").open("ab") as log_file:
                self._desktop_process = self._popen(
                    [
                        sys.executable,
                        str(self.project_root / "launch_desktop_pet.py"),
                        "--pet-id",
                        str(pet["id"]),
                    ],
                    cwd=self.project_root,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            log_event(
                "desktop_pet_launch_spawned",
                trace_id,
                chat_id=chat_id,
                pet_id=pet["id"],
                pid=self._desktop_process.pid,
            )
            return DesktopCompanionResult(
                ok=True,
                code="DESKTOP_LAUNCHED",
                message=f"好，{pet['name']} 出发去桌面陪你了。",
                trace_id=trace_id,
                pet=pet,
                pid=self._desktop_process.pid,
                process=self._desktop_process,
            )
        except Exception as exc:
            code = self._error_code(exc)
            log_exception("desktop_pet_launch_failed", trace_id, exc, chat_id=chat_id)
            return DesktopCompanionResult(
                ok=False,
                code=code,
                message=f"桌面陪伴启动失败。\n错误码：{code}\n调试编号：{trace_id}\n错误原因：{exc}",
                trace_id=trace_id,
            )

    def _default_pet(self) -> dict:
        if self.default_pet_id:
            pet = get_pet(int(self.default_pet_id), db_path=self.db_path)
            if pet is None:
                raise RuntimeError(f"DESKTOP_PET_NOT_FOUND: 找不到默认宠物：{self.default_pet_id}")
            return pet

        pets = list_pets(db_path=self.db_path)
        if not pets:
            raise RuntimeError("DESKTOP_PET_NOT_FOUND: 还没有宠物。")
        return next((pet for pet in pets if pet.get("pet_mode") == "virtual"), pets[0])

    def _profile(self, pet: dict) -> dict:
        try:
            return json.loads(pet.get("profile_json") or "{}")
        except json.JSONDecodeError:
            return {}

    def _local_static_path(self, static_url: str) -> Optional[Path]:
        clean = static_url.split("?", 1)[0]
        if not clean.startswith("/static/"):
            return None
        path = (self.project_root / clean.removeprefix("/")).resolve()
        static_root = (self.project_root / "static").resolve()
        if static_root not in path.parents:
            return None
        return path if path.exists() else None

    def _error_code(self, exc: BaseException) -> str:
        if isinstance(exc, OSError):
            return f"OS_ERROR_{getattr(exc, 'errno', 'UNKNOWN')}"
        text = str(exc)
        if text.startswith("DESKTOP_PET_"):
            return text.split(":", 1)[0]
        return "DESKTOP_PET_LAUNCH_FAILED"


def controller_from_env(project_root: Path) -> PetRuntimeController:
    return PetRuntimeController(
        project_root=project_root,
        default_pet_id=os.getenv("PET_AGENT_DEFAULT_PET_ID", ""),
    )
