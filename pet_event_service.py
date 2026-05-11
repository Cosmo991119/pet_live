"""
Application service for pet event ingestion.

This layer connects the database, session logic, message agent, and notifier.
FastAPI should call this service instead of duplicating orchestration logic.
"""

from typing import Any, Optional

from notifier import Notifier, notify_event_message
from pet_db import (
    DB_PATH,
    SESSION_BEHAVIORS,
    DbPath,
    get_pet,
    get_pet_stats,
    handle_sleep_event,
    record_event,
    upsert_behavior_session,
)
from pet_message_agent import generate_and_store_event_message


def _behavior_notification_decision(session_result: dict[str, Any]) -> dict[str, Any]:
    """Decide whether a behavior-session event should notify the owner."""
    if session_result["is_new_session"]:
        return {"should_notify": True, "reason": "new_behavior_session"}
    return {"should_notify": False, "reason": "existing_session_updated"}


def process_pet_event(
    payload: dict[str, Any],
    notifier: Optional[Notifier] = None,
    use_llm: bool = True,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """
    Process one structured pet behavior event.

    The function records the raw event first. If the event is high confidence,
    it updates the relevant behavior or sleep session. New behavior sessions
    trigger one generated message and optional notification.
    """
    pet_id = int(payload["pet_id"])
    behavior = payload["behavior"]
    location_name = payload.get("location_name")
    occurred_at = payload["occurred_at"]
    confidence = float(payload["confidence"])

    event = record_event(
        pet_id=pet_id,
        behavior=behavior,
        location_name=location_name,
        occurred_at=occurred_at,
        confidence=confidence,
        raw_payload=payload,
        db_path=db_path,
    )

    if event["status"] == "low_confidence":
        return {
            "event_id": event["id"],
            "session_id": None,
            "message": None,
            "reason": "low_confidence",
        }

    pet = get_pet(pet_id, db_path=db_path)
    if pet is None:
        raise ValueError(f"pet_id {pet_id} does not exist")

    if behavior in SESSION_BEHAVIORS:
        session_result = upsert_behavior_session(event, db_path=db_path)
        session = session_result["session"]
        notification_decision = _behavior_notification_decision(session_result)

        if not notification_decision["should_notify"]:
            return {
                "event_id": event["id"],
                "session_id": session["id"] if session else None,
                "message": None,
                "reason": notification_decision["reason"],
                "notification": {
                    "sent": False,
                    "reason": notification_decision["reason"],
                },
            }

        today = occurred_at[:10]
        today_stats = get_pet_stats(pet_id, "day", end_date=today, db_path=db_path)
        message_result = generate_and_store_event_message(
            pet=pet,
            event=event,
            session=session,
            today_stats=today_stats,
            use_llm=use_llm,
            db_path=db_path,
        )
        notification = {"sent": False, "reason": "no_notifier"}
        if notifier:
            try:
                notify_event_message(notifier, pet_id, message_result)
                notification = {"sent": True, "reason": notification_decision["reason"]}
            except Exception:
                notification = {
                    "sent": False,
                    "reason": "notification_delivery_failed",
                }

        return {
            "event_id": event["id"],
            "session_id": session["id"],
            "message": message_result["message"],
            "reason": None,
            "notification": notification,
        }

    sleep_result = handle_sleep_event(event, db_path=db_path)
    sleep_session = sleep_result["sleep_session"]
    return {
        "event_id": event["id"],
        "session_id": sleep_session["id"] if sleep_session else None,
        "message": None,
        "reason": f"sleep_{sleep_result['action']}",
        "anomaly": sleep_result["anomaly"],
    }
