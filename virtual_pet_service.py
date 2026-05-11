"""
Service layer for virtual pet state and owner actions.

Each request restores simulator state from SQLite, advances or modifies it, and
saves the updated state back to SQLite.
"""

import json
from datetime import datetime
from typing import Any, Optional

from notifier import Notifier
from pet_db import (
    DB_PATH,
    DbPath,
    get_pet,
    get_virtual_pet_state,
    save_virtual_pet_state,
)
from pet_event_service import process_pet_event
from pet_simulator import OWNER_ACTIONS, PetSimulator, PetState


def _load_simulator(pet_id: int, db_path: DbPath = DB_PATH) -> PetSimulator:
    pet = get_pet(pet_id, db_path=db_path)
    if pet is None:
        raise ValueError(f"pet_id {pet_id} does not exist")
    if pet.get("pet_mode") != "virtual":
        raise ValueError(f"pet_id {pet_id} is not a virtual pet")

    saved = get_virtual_pet_state(pet_id, db_path=db_path)
    if saved:
        state = PetState.from_dict(json.loads(saved["state_json"]))
        return PetSimulator(
            pet_id=pet_id,
            personality=pet["personality"],
            start_time=datetime.fromisoformat(saved["current_time"]),
            state=state,
        )

    return PetSimulator(pet_id=pet_id, personality=pet["personality"])


def _save_simulator(sim: PetSimulator, db_path: DbPath = DB_PATH) -> dict[str, Any]:
    return save_virtual_pet_state(
        pet_id=sim.pet_id,
        state=sim.state.to_dict(),
        current_time=sim.now.isoformat(),
        db_path=db_path,
    )


def get_virtual_pet_snapshot(
    pet_id: int,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    sim = _load_simulator(pet_id, db_path=db_path)
    return sim.snapshot()


def tick_virtual_pet(
    pet_id: int,
    minutes: int = 10,
    notifier: Optional[Notifier] = None,
    use_llm: bool = True,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    if minutes <= 0 or minutes > 24 * 60:
        raise ValueError("minutes must be between 1 and 1440")

    sim = _load_simulator(pet_id, db_path=db_path)
    event = sim.tick(minutes=minutes)
    saved_state = _save_simulator(sim, db_path=db_path)

    event_result = None
    if event:
        event_result = process_pet_event(
            event.to_payload(),
            notifier=notifier,
            use_llm=use_llm,
            db_path=db_path,
        )

    return {
        "pet_id": pet_id,
        "snapshot": sim.snapshot(),
        "event": event.to_payload() if event else None,
        "event_result": event_result,
        "stored_state": saved_state,
    }


def apply_virtual_pet_action(
    pet_id: int,
    action: str,
    notifier: Optional[Notifier] = None,
    use_llm: bool = True,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    if action not in OWNER_ACTIONS:
        raise ValueError(f"action must be one of {sorted(OWNER_ACTIONS)}")

    sim = _load_simulator(pet_id, db_path=db_path)
    event = sim.apply_owner_action(action)
    saved_state = _save_simulator(sim, db_path=db_path)

    event_result = None
    if event:
        event_result = process_pet_event(
            event.to_payload(),
            notifier=notifier,
            use_llm=use_llm,
            db_path=db_path,
        )

    return {
        "pet_id": pet_id,
        "action": action,
        "snapshot": sim.snapshot(),
        "event": event.to_payload() if event else None,
        "event_result": event_result,
        "stored_state": saved_state,
    }
