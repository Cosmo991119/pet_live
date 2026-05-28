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


@dataclass
class DesktopCompanionGroupResult:
    ok: bool
    code: str
    message: str
    trace_id: str
    results: list[DesktopCompanionResult]


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
        self._desktop_processes: dict[int, subprocess.Popen] = {}

    def launch_desktop_companion(
        self,
        chat_id: str = "",
        pet_id: Optional[int] = None,
        offset_index: int = 0,
    ) -> DesktopCompanionResult:
        trace_id = new_trace_id("desktop")
        try:
            pet = self._pet_for_launch(pet_id)
            pet_id = int(pet["id"])
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

            running_process = self._desktop_processes.get(pet_id)
            if running_process and running_process.poll() is None:
                return DesktopCompanionResult(
                    ok=True,
                    code="DESKTOP_ALREADY_RUNNING",
                    message=f"{pet['name']} 已经在桌面陪你了。",
                    trace_id=trace_id,
                    pet=pet,
                    pid=running_process.pid,
                    process=running_process,
                )

            log_event(
                "desktop_pet_launch_started",
                trace_id,
                chat_id=chat_id,
                pet_id=pet_id,
                manifest=manifest_url,
            )
            log_dir = self.project_root / "logs"
            log_dir.mkdir(exist_ok=True)
            with (log_dir / "desktop_pet_launch.log").open("ab") as log_file:
                process = self._popen(
                    [
                        sys.executable,
                        str(self.project_root / "launch_desktop_pet.py"),
                        "--pet-id",
                        str(pet_id),
                        "--offset-index",
                        str(offset_index),
                    ],
                    cwd=self.project_root,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            self._desktop_processes[pet_id] = process
            log_event(
                "desktop_pet_launch_spawned",
                trace_id,
                chat_id=chat_id,
                pet_id=pet_id,
                pid=process.pid,
            )
            return DesktopCompanionResult(
                ok=True,
                code="DESKTOP_LAUNCHED",
                message=f"好，{pet['name']} 出发去桌面陪你了。",
                trace_id=trace_id,
                pet=pet,
                pid=process.pid,
                process=process,
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

    def launch_all_desktop_companions(self, chat_id: str = "") -> DesktopCompanionGroupResult:
        trace_id = new_trace_id("desktop_group")
        try:
            pets = list_pets(db_path=self.db_path)
        except Exception as exc:
            code = self._error_code(exc)
            log_exception("desktop_pet_group_launch_failed", trace_id, exc, chat_id=chat_id)
            return DesktopCompanionGroupResult(
                ok=False,
                code=code,
                message=f"桌面陪伴启动失败。\n错误码：{code}\n调试编号：{trace_id}\n错误原因：{exc}",
                trace_id=trace_id,
                results=[],
            )
        if not pets:
            return DesktopCompanionGroupResult(
                ok=False,
                code="DESKTOP_PET_NOT_FOUND",
                message="还没有宠物。先创建一只宠物，再让它们来桌面陪你。",
                trace_id=trace_id,
                results=[],
            )

        results = [
            self.launch_desktop_companion(chat_id=chat_id, pet_id=int(pet["id"]), offset_index=index)
            for index, pet in enumerate(pets)
        ]
        active_names = [
            str(result.pet.get("name", "宠物"))
            for result in results
            if result.ok and result.code in {"DESKTOP_LAUNCHED", "DESKTOP_ALREADY_RUNNING"} and result.pet
        ]
        waiting_names = [
            str(result.pet.get("name", "宠物"))
            for result in results
            if result.code == "DESKTOP_ASSETS_MISSING" and result.pet
        ]
        failed_results = [
            result for result in results
            if not result.ok and result.code != "DESKTOP_ASSETS_MISSING"
        ]

        if active_names:
            parts = [f"{'、'.join(active_names)} 已经在桌面陪你了。"]
            if waiting_names:
                parts.append(f"{'、'.join(waiting_names)} 还没有桌宠动作素材，先留在群聊里。")
            if failed_results:
                parts.append(f"{len(failed_results)} 只宠物启动失败，调试编号见日志。")
            return DesktopCompanionGroupResult(
                ok=True,
                code="DESKTOP_GROUP_LAUNCHED",
                message="\n".join(parts),
                trace_id=trace_id,
                results=results,
            )

        if waiting_names and not failed_results:
            return DesktopCompanionGroupResult(
                ok=False,
                code="DESKTOP_ASSETS_MISSING",
                message="现在还没有可上桌面的宠物素材。先给宠物生成形象并确认，桌宠素材会在后台完成。",
                trace_id=trace_id,
                results=results,
            )

        return DesktopCompanionGroupResult(
            ok=False,
            code="DESKTOP_GROUP_LAUNCH_FAILED",
            message="这次没有成功启动桌面陪伴，请看调试编号排查。",
            trace_id=trace_id,
            results=results,
        )

    def _pet_for_launch(self, pet_id: Optional[int] = None) -> dict:
        if pet_id is not None:
            pet = get_pet(int(pet_id), db_path=self.db_path)
            if pet is None:
                raise RuntimeError(f"DESKTOP_PET_NOT_FOUND: 找不到宠物：{pet_id}")
            return pet

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
