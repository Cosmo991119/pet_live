"""
Simulate a pet device sending real-time events to the FastAPI service.

Start the API first:
    uvicorn api:app --port 8000

Then run:
    python3 simulate_events.py
"""

from datetime import datetime, timedelta, timezone
import json
import time
from typing import Any

import requests


API_BASE_URL = "http://127.0.0.1:8000"
PET_ID = 1
DELAY_SECONDS = 1
TZ = timezone(timedelta(hours=8))


def iso_at(hour: int, minute: int = 0, day_offset: int = 0) -> str:
    """Build a demo timestamp for today in Asia/Shanghai-style +08:00 time."""
    now = datetime.now(TZ)
    demo_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    demo_time = demo_time + timedelta(days=day_offset)
    return demo_time.isoformat()


def post_event(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"{API_BASE_URL}/events", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def main() -> None:
    events = [
        {
            "pet_id": PET_ID,
            "behavior": "eat",
            "location_name": "饭盆",
            "occurred_at": iso_at(8, 0),
            "confidence": 0.95,
        },
        {
            "pet_id": PET_ID,
            "behavior": "drink",
            "location_name": "水碗",
            "occurred_at": iso_at(10, 0),
            "confidence": 0.94,
        },
        {
            "pet_id": PET_ID,
            "behavior": "drink",
            "location_name": "水碗",
            "occurred_at": iso_at(10, 3),
            "confidence": 0.92,
        },
        {
            "pet_id": PET_ID,
            "behavior": "poop",
            "location_name": "厕所",
            "occurred_at": iso_at(13, 20),
            "confidence": 0.9,
        },
        {
            "pet_id": PET_ID,
            "behavior": "sleep_start",
            "location_name": "猫窝",
            "occurred_at": iso_at(22, 0),
            "confidence": 0.93,
        },
        {
            "pet_id": PET_ID,
            "behavior": "sleep_end",
            "location_name": "猫窝",
            "occurred_at": iso_at(6, 30, day_offset=1),
            "confidence": 0.91,
        },
    ]

    print(f"Sending {len(events)} events to {API_BASE_URL}/events")
    for payload in events:
        print("\n-> event")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        try:
            result = post_event(payload)
            print("<- response")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except requests.RequestException as exc:
            print(f"Request failed: {exc}")
            print("Make sure the API is running: uvicorn api:app --port 8000")
            return
        time.sleep(DELAY_SECONDS)


if __name__ == "__main__":
    main()
