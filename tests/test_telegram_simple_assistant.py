import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import telegram_bot


class TelegramSimpleAssistantTest(unittest.TestCase):
    def test_parse_assistant_commands(self) -> None:
        now = datetime.fromisoformat("2026-05-29T15:00:00+08:00")

        self.assertEqual(
            {
                "item_type": "note",
                "title": "明天改登录页文案",
                "body": "",
                "source": "telegram",
            },
            telegram_bot.parse_assistant_command("记一下 明天改登录页文案", now=now),
        )
        self.assertEqual(
            "todo",
            telegram_bot.parse_assistant_command("待办 写周报", now=now)["item_type"],
        )
        reminder = telegram_bot.parse_assistant_command("提醒 10分钟后 喝水", now=now)
        self.assertEqual("alarm", reminder["item_type"])
        self.assertEqual("喝水", reminder["title"])
        self.assertEqual("2026-05-29T15:10:00+08:00", reminder["due_at"])

        focus = telegram_bot.parse_assistant_command("番茄钟 25 写 PR 描述", now=now)
        self.assertEqual("focus", focus["item_type"])
        self.assertEqual("写 PR 描述", focus["title"])
        self.assertEqual(25, focus["duration_minutes"])
        self.assertEqual("2026-05-29T15:25:00+08:00", focus["due_at"])

    @patch("telegram_bot.owner_params", return_value={"owner_id": 9})
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    def test_handle_assistant_text_creates_item(self, post: Mock, send_message: Mock, _owner) -> None:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "id": 7,
            "item_type": "todo",
            "title": "写周报",
        }
        telegram_bot.ASSISTANT_ACTIVE_CHATS.clear()

        handled = telegram_bot.handle_assistant_text("chat-1", "待办 写周报")

        self.assertTrue(handled)
        self.assertIn("chat-1", telegram_bot.ASSISTANT_ACTIVE_CHATS)
        self.assertEqual(
            f"{telegram_bot.API_BASE_URL}/assistant/items",
            post.call_args.args[0],
        )
        self.assertEqual(
            {
                "owner_id": 9,
                "item_type": "todo",
                "title": "写周报",
                "body": "",
                "source": "telegram",
            },
            post.call_args.kwargs["json"],
        )
        self.assertIn("写周报", send_message.call_args.args[1])

    @patch("telegram_bot.owner_params", return_value={"owner_id": 9})
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_handle_assistant_text_lists_todos(self, get: Mock, send_message: Mock, _owner) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "item_type": "todo", "title": "写周报"},
        ]

        handled = telegram_bot.handle_assistant_text("chat-1", "我的待办")

        self.assertTrue(handled)
        self.assertEqual(
            f"{telegram_bot.API_BASE_URL}/assistant/items",
            get.call_args.args[0],
        )
        self.assertEqual(
            {"owner_id": 9, "item_type": "todo", "status": "open", "limit": 10},
            get.call_args.kwargs["params"],
        )
        self.assertIn("#7 写周报", send_message.call_args.args[1])

    @patch("telegram_bot.owner_params", return_value={"owner_id": 9})
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    def test_handle_assistant_text_completes_item(self, patch_request: Mock, send_message: Mock, _owner) -> None:
        patch_request.return_value.status_code = 200
        patch_request.return_value.json.return_value = {
            "id": 7,
            "status": "done",
            "title": "写周报",
        }

        handled = telegram_bot.handle_assistant_text("chat-1", "完成 7")

        self.assertTrue(handled)
        self.assertEqual(
            f"{telegram_bot.API_BASE_URL}/assistant/items/7/complete",
            patch_request.call_args.args[0],
        )
        self.assertEqual(
            {"owner_id": 9, "status": "done"},
            patch_request.call_args.kwargs["json"],
        )
        self.assertIn("写周报", send_message.call_args.args[1])

    @patch("telegram_bot.owner_params", return_value={"owner_id": 9})
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    @patch("telegram_bot.requests.get")
    def test_send_due_assistant_items_for_chat_notifies_and_dismisses(
        self,
        get: Mock,
        patch_request: Mock,
        send_message: Mock,
        _owner,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "item_type": "alarm", "title": "喝水"},
            {"id": 8, "item_type": "focus", "title": "写 PR 描述"},
        ]
        patch_request.return_value.status_code = 200
        patch_request.return_value.json.return_value = {"id": 7, "status": "dismissed"}

        count = telegram_bot.send_due_assistant_items_for_chat(
            "chat-1",
            now=datetime.fromisoformat("2026-05-29T15:30:00+08:00"),
        )

        self.assertEqual(2, count)
        self.assertEqual(2, send_message.call_count)
        self.assertEqual(2, patch_request.call_count)
        self.assertEqual(
            {"owner_id": 9, "status": "dismissed"},
            patch_request.call_args.kwargs["json"],
        )


if __name__ == "__main__":
    unittest.main()
