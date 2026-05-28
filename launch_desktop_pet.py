"""Launch the native macOS floating desktop pet."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from pet_db import get_pet, list_pets


PROJECT_ROOT = Path(__file__).resolve().parent


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


def _static_path(static_url: str) -> Optional[Path]:
    clean = static_url.split("?", 1)[0]
    if not clean.startswith("/static/"):
        return None
    path = (PROJECT_ROOT / clean.removeprefix("/")).resolve()
    static_root = (PROJECT_ROOT / "static").resolve()
    if static_root not in path.parents:
        return None
    return path if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the native desktop pet.")
    parser.add_argument("--pet-id", type=int, default=None)
    parser.add_argument("--offset-index", type=int, default=0)
    args = parser.parse_args()

    pet_id = args.pet_id if args.pet_id is not None else _default_virtual_pet_id()
    pet = get_pet(pet_id)
    if pet is None:
        raise RuntimeError(f"pet_id {pet_id} does not exist")

    profile = _profile(pet)
    manifest_path = _static_path(profile.get("desktop_pet_manifest_url", ""))
    image_path = _static_path(profile.get("desktop_pet_avatar_url", ""))
    if image_path is None:
        image_path = _static_path(profile.get("avatar_image_url", ""))
    command = [
        "swift",
        str(PROJECT_ROOT / "desktop_pet_mac.swift"),
        "--name",
        pet["name"],
    ]
    if image_path is not None:
        command.extend(["--image", str(image_path)])
    if manifest_path is not None:
        command.extend(["--manifest", str(manifest_path)])
    command.extend(["--offset-index", str(args.offset_index)])

    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
