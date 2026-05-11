"""
Simulate owner interactions with a virtual pet through the FastAPI service.

Start the API first:
    uvicorn api:app --port 8000

Then run:
    python3 simulate_virtual_pet.py
"""

import json
import time
from typing import Any

import requests


API_BASE_URL = "http://127.0.0.1:8000"
PET_ID = 2
DELAY_SECONDS = 1


def print_json(label: str, value: dict[str, Any]) -> None:
    print(f"\n{label}")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def get_status() -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}/virtual-pets/{PET_ID}", timeout=10)
    response.raise_for_status()
    return response.json()


def tick(minutes: int) -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/virtual-pets/{PET_ID}/tick",
        json={"minutes": minutes},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def action(name: str) -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/virtual-pets/{PET_ID}/actions",
        json={"action": name},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def run_step(label: str, fn) -> bool:
    print(f"\n== {label} ==")
    try:
        result = fn()
        print_json("<- response", result)
        return True
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        print("Make sure the API is running: uvicorn api:app --port 8000")
        return False


def main() -> None:
    steps = [
        ("status", get_status),
        ("pet", lambda: action("pet")),
        ("tick 30 minutes", lambda: tick(30)),
        ("play", lambda: action("play")),
        ("tick 30 minutes", lambda: tick(30)),
        ("feed", lambda: action("feed")),
        ("tick 60 minutes", lambda: tick(60)),
        ("lullaby", lambda: action("lullaby")),
        ("tick 30 minutes", lambda: tick(30)),
        ("final status", get_status),
    ]

    print(f"Simulating virtual pet interactions for pet_id={PET_ID}")
    for label, fn in steps:
        if not run_step(label, fn):
            return
        time.sleep(DELAY_SECONDS)


if __name__ == "__main__":
    main()
