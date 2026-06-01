import tempfile
import unittest
from pathlib import Path
from typing import Any, Optional

from notifier import Notifier, notify_event_message
from pet_db import create_pet, init_db
from pet_event_service import process_pet_event
from pet_message_agent import generate_event_message


class CapturingNotifier(Notifier):
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send(
        self,
        pet_id: int,
        message: str,
        severity: str = "normal",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.messages.append(
            {
                "pet_id": pet_id,
                "message": message,
                "severity": severity,
                "metadata": metadata or {},
            }
        )


class PetEventNotificationsTest(unittest.TestCase):
    def test_event_notification_text_includes_pet_speaker_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            pet = create_pet(
                name="黑米",
                species="cat",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            notifier = CapturingNotifier()

            result = process_pet_event(
                {
                    "pet_id": pet["id"],
                    "behavior": "drink",
                    "location_name": "水碗",
                    "occurred_at": "2026-05-29T17:43:00",
                    "confidence": 0.95,
                },
                notifier=notifier,
                use_llm=False,
                db_path=db_path,
            )

            self.assertEqual(
                {"sent": True, "reason": "new_behavior_session"},
                result["notification"],
            )
            self.assertEqual(1, len(notifier.messages))
            self.assertEqual("黑米", notifier.messages[0]["metadata"]["pet_name"])
            self.assertTrue(result["message"]["message"].startswith("黑米："))
            self.assertEqual(result["message"]["message"], notifier.messages[0]["message"])

    def test_event_notification_keeps_existing_pet_speaker_label(self) -> None:
        notifier = CapturingNotifier()

        notify_event_message(
            notifier,
            pet_id=8,
            message_result={
                "pet_name": "黑米",
                "message": {
                    "message": "黑米：妈，我顺路喝了点水。",
                    "severity": "normal",
                    "facts_used": ["current_event"],
                    "internal_signal": "normal",
                },
                "model_name": "gpt-test",
                "prompt_version": "pet_event_message_v1",
            },
        )

        self.assertEqual("黑米：妈，我顺路喝了点水。", notifier.messages[0]["message"])

    def test_fallback_event_messages_vary_for_repeated_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            heimi = create_pet(
                name="黑米",
                species="cat",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            jiefang = create_pet(
                name="解放",
                species="dog",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )

            first = process_pet_event(
                {
                    "pet_id": heimi["id"],
                    "behavior": "eat",
                    "location_name": "饭盆",
                    "occurred_at": "2026-05-30T02:09:00",
                    "confidence": 0.95,
                },
                use_llm=False,
                db_path=db_path,
            )
            second = process_pet_event(
                {
                    "pet_id": jiefang["id"],
                    "behavior": "eat",
                    "location_name": "饭盆",
                    "occurred_at": "2026-05-30T02:09:00",
                    "confidence": 0.95,
                },
                use_llm=False,
                db_path=db_path,
            )

            self.assertNotEqual(
                first["message"]["message"].split("：", maxsplit=1)[1],
                second["message"]["message"].split("：", maxsplit=1)[1],
            )

    def test_fallback_event_messages_avoid_report_like_filler(self) -> None:
        report_like_phrases = ("状态", "平稳", "掌控", "不用担心", "任务完成")
        for personality in ("sweet", "cool", "energetic", "gentle"):
            for behavior in ("eat", "drink", "poop", "play"):
                for event_id in range(3):
                    with self.subTest(
                        personality=personality,
                        behavior=behavior,
                        event_id=event_id,
                    ):
                        result, _ = generate_event_message(
                            pet={
                                "id": 1,
                                "name": "黑米",
                                "species": "cat",
                                "personality": personality,
                                "owner_call_name": "妈",
                            },
                            event={
                                "id": event_id,
                                "behavior": behavior,
                                "location_name": "猫砂盆",
                                "occurred_at": "2026-06-02T01:53:00",
                                "confidence": 0.95,
                            },
                            session={"id": 9, "raw_event_count": 1},
                            today_stats={},
                            use_llm=False,
                        )

                        for phrase in report_like_phrases:
                            self.assertNotIn(phrase, result["message"])

    def test_llm_prompt_includes_pet_personality_voice_guidance(self) -> None:
        captured_messages: list[dict[str, Any]] = []

        def fake_llm(
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]],
        ) -> dict[str, Any]:
            captured_messages.extend(messages)
            return {
                "model": "fake-model",
                "content": [
                    {
                        "text": (
                            '{"message": "妈，我刚喝了两口水。", '
                            '"severity": "normal", '
                            '"facts_used": ["current_event"], '
                            '"internal_signal": "normal"}'
                        )
                    }
                ],
            }

        generate_event_message(
            pet={
                "id": 8,
                "name": "解放",
                "species": "dog",
                "personality": "energetic",
                "owner_call_name": "妈",
            },
            event={
                "id": 3,
                "behavior": "drink",
                "location_name": "水碗",
                "occurred_at": "2026-06-02T01:21:00",
                "confidence": 0.95,
            },
            session={"id": 10, "raw_event_count": 1},
            today_stats={},
            llm_call=fake_llm,
        )

        prompt_text = "\n".join(message["content"] for message in captured_messages)
        self.assertIn("活泼话痨型", prompt_text)
        self.assertIn("性格语气", prompt_text)
        self.assertIn("不要每条都用主人称呼开头", prompt_text)
        self.assertIn("不要写成监控播报", prompt_text)


if __name__ == "__main__":
    unittest.main()
