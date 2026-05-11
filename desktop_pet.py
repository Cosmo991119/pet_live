"""Desktop floating pet companion.

This is the QQ-pet-style surface: a small always-on-top desktop window that
uses the selected pet's confirmed avatar instead of rendering inside the web UI.
"""

from __future__ import annotations

import argparse
import json
import random
import tkinter as tk
from pathlib import Path
from typing import Any, Optional

from pet_db import get_pet, list_pets
from virtual_pet_service import apply_virtual_pet_action, get_virtual_pet_snapshot


PROJECT_ROOT = Path(__file__).resolve().parent
TRANSPARENT_COLOR = "#ff00ff"
PET_SIZE = 168


def _profile(pet: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(pet.get("profile_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _default_virtual_pet_id() -> int:
    pets = list_pets()
    virtual = next((pet for pet in pets if pet.get("pet_mode") == "virtual"), None)
    if virtual:
        return int(virtual["id"])
    if pets:
        return int(pets[0]["id"])
    raise RuntimeError("No pet exists yet. Create a virtual pet in the web UI first.")


def _local_static_path(image_url: str) -> Optional[Path]:
    clean = image_url.split("?", 1)[0]
    if not clean.startswith("/static/"):
        return None
    path = (PROJECT_ROOT / clean.removeprefix("/")).resolve()
    static_root = (PROJECT_ROOT / "static").resolve()
    if static_root not in path.parents:
        return None
    return path if path.exists() else None


class DesktopPet:
    def __init__(self, pet_id: int) -> None:
        self.pet_id = pet_id
        self.pet = get_pet(pet_id)
        if self.pet is None:
            raise RuntimeError(f"pet_id {pet_id} does not exist")

        self.root = tk.Tk()
        self.root.title(f"{self.pet['name']} Desktop Pet")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self._enable_transparency()

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.x = max(40, self.screen_w - 260)
        self.y = max(80, self.screen_h - 300)
        self.dx = -1
        self.drag_start: Optional[tuple[int, int]] = None
        self.message_after_id: Optional[str] = None

        self.frame = tk.Frame(self.root, bg=TRANSPARENT_COLOR)
        self.frame.pack()

        self.speech = tk.Label(
            self.frame,
            text="",
            bg="white",
            fg="#20231f",
            padx=10,
            pady=7,
            wraplength=220,
            justify="left",
            relief="solid",
            bd=1,
        )
        self.speech.pack(pady=(0, 4))
        self.speech.pack_forget()

        self.canvas = tk.Canvas(
            self.frame,
            width=PET_SIZE,
            height=PET_SIZE,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.photo: Optional[tk.PhotoImage] = None
        self.avatar_item: Optional[int] = None
        self._draw_pet()
        self._bind_events()
        self._move_to(self.x, self.y)
        self._say(f"{self.pet['name']} 到桌面上来啦。")
        self._animate()
        self._poll_state()

    def _enable_transparency(self) -> None:
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            # macOS Tk builds may not support transparentcolor. The pet still
            # works as a small borderless always-on-top companion window.
            pass

    def _bind_events(self) -> None:
        for widget in (self.frame, self.canvas, self.speech):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)
            widget.bind("<Double-Button-1>", self._pet_action)
            widget.bind("<Button-2>", self._show_menu)
            widget.bind("<Button-3>", self._show_menu)

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="摸摸", command=lambda: self._run_action("pet"))
        self.menu.add_command(label="陪玩", command=lambda: self._run_action("play"))
        self.menu.add_command(label="加水", command=lambda: self._run_action("refill"))
        self.menu.add_separator()
        self.menu.add_command(label="退出桌面宠物", command=self.root.destroy)

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root - self.x, event.y_root - self.y)

    def _drag(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        ox, oy = self.drag_start
        self._move_to(event.x_root - ox, event.y_root - oy)

    def _end_drag(self, _event: tk.Event) -> None:
        self.drag_start = None

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _move_to(self, x: int, y: int) -> None:
        self.x = max(0, min(self.screen_w - PET_SIZE, int(x)))
        self.y = max(0, min(self.screen_h - PET_SIZE, int(y)))
        self.root.geometry(f"+{self.x}+{self.y}")

    def _load_avatar(self) -> Optional[tk.PhotoImage]:
        avatar_url = _profile(self.pet).get("avatar_image_url")
        if not avatar_url:
            return None
        avatar_path = _local_static_path(avatar_url)
        if avatar_path is None:
            return None
        image = tk.PhotoImage(file=str(avatar_path))
        max_side = max(image.width(), image.height())
        if max_side > PET_SIZE:
            factor = max(1, int(max_side / PET_SIZE))
            image = image.subsample(factor, factor)
        return image

    def _draw_pet(self) -> None:
        self.canvas.delete("all")
        self.photo = self._load_avatar()
        if self.photo:
            self.avatar_item = self.canvas.create_image(
                PET_SIZE // 2,
                PET_SIZE // 2,
                image=self.photo,
                anchor="center",
            )
            return

        self.canvas.create_oval(42, 42, 126, 132, fill="#eef6ea", outline="#263027", width=3)
        self.canvas.create_polygon(48, 48, 64, 12, 82, 48, fill="#eef6ea", outline="#263027", width=3)
        self.canvas.create_polygon(86, 48, 104, 12, 120, 48, fill="#eef6ea", outline="#263027", width=3)
        self.canvas.create_oval(68, 76, 76, 84, fill="#263027", outline="")
        self.canvas.create_oval(94, 76, 102, 84, fill="#263027", outline="")
        self.canvas.create_oval(82, 94, 88, 100, fill="#263027", outline="")

    def _say(self, text: str, seconds: int = 4) -> None:
        self.speech.configure(text=text)
        self.speech.pack(pady=(0, 4), before=self.canvas)
        if self.message_after_id:
            self.root.after_cancel(self.message_after_id)
        self.message_after_id = self.root.after(seconds * 1000, self.speech.pack_forget)

    def _animate(self) -> None:
        if self.drag_start is None:
            if random.random() < 0.08:
                self.dx *= -1
            self._move_to(self.x + self.dx, self.y)
        self.root.after(120, self._animate)

    def _poll_state(self) -> None:
        try:
            snapshot = get_virtual_pet_snapshot(self.pet_id)
            state = snapshot["state"]
            if state.get("energy", 100) < 25:
                self._say("我有点困，先趴在桌面上陪你。", seconds=3)
            elif state.get("thirst", 0) > 75:
                self._say("水碗好像在召唤我。", seconds=3)
            elif state.get("hunger", 0) > 75:
                self._say("我可以假装没有看饭碗，但只能假装一小会儿。", seconds=3)
        except Exception:
            pass
        self.root.after(45_000, self._poll_state)

    def _pet_action(self, _event: tk.Event) -> None:
        self._run_action("pet")

    def _run_action(self, action: str) -> None:
        labels = {
            "pet": "摸摸",
            "play": "陪玩",
            "refill": "加水",
        }
        try:
            apply_virtual_pet_action(self.pet_id, action, use_llm=False)
            self._say(f"{labels.get(action, action)}收到。")
        except Exception as exc:
            self._say(str(exc), seconds=5)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the floating desktop pet.")
    parser.add_argument("--pet-id", type=int, default=None, help="Pet id to show.")
    args = parser.parse_args()
    pet_id = args.pet_id if args.pet_id is not None else _default_virtual_pet_id()
    DesktopPet(pet_id).run()


if __name__ == "__main__":
    main()
