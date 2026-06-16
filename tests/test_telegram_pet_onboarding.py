import threading
import time
import unittest
from unittest.mock import Mock, call, patch

import requests

import telegram_bot


class TelegramPetOnboardingTest(unittest.TestCase):
    def setUp(self) -> None:
        telegram_bot.ALLOWED_CHAT_ID = ""
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = set()
        telegram_bot.PENDING_PET_FLOWS.clear()
        telegram_bot.PENDING_AVATAR_FLOWS.clear()
        telegram_bot.PENDING_FRIENDSHIP_INVITE_FLOWS.clear()
        telegram_bot.PENDING_FRIEND_MEMORY_SHARE_FLOWS.clear()
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS.clear()
        telegram_bot.CURRENT_PET_IDS.clear()
        telegram_bot.OWNER_IDS_BY_CHAT.clear()
        telegram_bot.OWNER_DISPLAY_NAMES_BY_CHAT.clear()
        telegram_bot.FRIENDSHIP_DAILY_MESSAGE_LAST_SENT.clear()
        telegram_bot.FRIENDSHIP_DAILY_MESSAGE_SCAN_LAST = 0.0
        telegram_bot.MEMORY_SHARE_SUGGESTION_LAST_BY_CHAT.clear()
        telegram_bot.PET_GROUP_LAST_SPEAKER_IDS.clear()
        telegram_bot.ACTIVE_AVATAR_GENERATIONS.clear()
        telegram_bot.ACTIVE_PET_GROUP_CHATS.clear()
        telegram_bot.RELATIONSHIP_EXPRESSION_COOLDOWNS.clear()
        telegram_bot.AVATAR_GENERATION_SEMAPHORE = threading.BoundedSemaphore(
            telegram_bot.AVATAR_PREVIEW_MAX_CONCURRENT
        )

    def test_main_menu_moves_avatar_behind_pet_creation(self) -> None:
        reply_labels = [
            button["text"]
            for row in telegram_bot.MAIN_REPLY_KEYBOARD["keyboard"]
            for button in row
        ]

        self.assertIn("创建宠物", reply_labels)
        self.assertIn("宠物关系", reply_labels)
        self.assertIn("宠物好友", reply_labels)
        self.assertIn("宠物记忆", reply_labels)
        self.assertNotIn("宠物群聊", reply_labels)
        self.assertNotIn("设置资料", reply_labels)
        self.assertNotIn("定制形象", reply_labels)

    @patch("telegram_bot.remove_reply_keyboard")
    @patch("telegram_bot.send_message")
    def test_main_menu_refreshes_reply_keyboard_without_inline_menu_message(
        self,
        send_message: Mock,
        remove_reply_keyboard: Mock,
    ) -> None:
        telegram_bot.send_main_menu("chat-1")

        remove_reply_keyboard.assert_called_once_with("chat-1")
        send_message.assert_called_once_with(
            "chat-1",
            "Pet Live Agent 已打开。底部键盘已刷新。",
            reply_markup=telegram_bot.MAIN_REPLY_KEYBOARD,
        )

    @patch("telegram_bot.remove_reply_keyboard")
    @patch("telegram_bot.send_message")
    def test_old_avatar_reply_keyboard_button_only_refreshes_menu(
        self,
        send_message: Mock,
        remove_reply_keyboard: Mock,
    ) -> None:
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        telegram_bot.ALLOWED_CHAT_ID = ""
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-1"}, "text": "定制形象"})
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id

        remove_reply_keyboard.assert_called_once_with("chat-1")
        send_message.assert_called_once_with(
            "chat-1",
            "形象定制入口已经移到创建宠物后的下一步。",
            reply_markup=telegram_bot.MAIN_REPLY_KEYBOARD,
        )

    @patch("telegram_bot.send_main_menu")
    @patch("telegram_bot.telegram_api")
    def test_configure_bot_ui_refreshes_keyboard_even_if_command_cleanup_fails(
        self,
        telegram_api: Mock,
        send_main_menu: Mock,
    ) -> None:
        telegram_api.side_effect = RuntimeError("Telegram deleteMyCommands failed")
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        telegram_bot.ALLOWED_CHAT_ID = "chat-1"
        try:
            telegram_bot.configure_bot_ui()
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id

        send_main_menu.assert_called_once_with("chat-1")

    @patch("telegram_bot.send_main_menu")
    @patch("telegram_bot.telegram_api")
    def test_configure_bot_ui_refreshes_keyboard_for_allowlisted_owners(
        self,
        _telegram_api: Mock,
        send_main_menu: Mock,
    ) -> None:
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_CHAT_ID = "chat-1"
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-1", "chat-2"}
        try:
            telegram_bot.configure_bot_ui()
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        send_main_menu.assert_has_calls([call("chat-1"), call("chat-2")])
        self.assertEqual(2, send_main_menu.call_count)

    @patch("telegram_bot.log_exception")
    @patch("telegram_bot.send_main_menu")
    @patch("telegram_bot.telegram_api")
    def test_configure_bot_ui_continues_if_owner_keyboard_refresh_fails(
        self,
        _telegram_api: Mock,
        send_main_menu: Mock,
        log_exception: Mock,
    ) -> None:
        send_main_menu.side_effect = [RuntimeError("send failed"), None]
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_CHAT_ID = ""
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-1", "chat-2"}
        try:
            telegram_bot.configure_bot_ui()
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        send_main_menu.assert_has_calls([call("chat-1"), call("chat-2")])
        self.assertEqual(2, send_main_menu.call_count)
        log_exception.assert_called_once()

    @patch("telegram_bot.log_event")
    @patch("telegram_bot.owner_params")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.api_get_pets")
    def test_proactive_tick_targets_owner_virtual_pets_and_sends_generated_message(
        self,
        api_get_pets: Mock,
        post: Mock,
        send_message: Mock,
        owner_params: Mock,
        _log_event: Mock,
    ) -> None:
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-1"}
        owner_params.return_value = {"owner_id": 4}
        api_get_pets.return_value = [
            {"id": 7, "name": "小月", "pet_mode": "virtual"},
            {"id": 8, "name": "相机", "pet_mode": "real"},
        ]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "event_result": {
                "message": {
                    "message": "妈，小月刚刚去喝水啦。",
                },
            },
        }

        result = telegram_bot.proactive_tick_virtual_pets_once(tick_minutes=10)

        self.assertEqual({"chats": 1, "pets": 1, "messages": 1}, result)
        post.assert_called_once_with(
            "http://127.0.0.1:8000/virtual-pets/7/tick",
            params={"owner_id": 4, "notify": "false"},
            json={"minutes": 10},
            timeout=20,
        )
        send_message.assert_called_once_with(
            "chat-1",
            "小月：妈，小月刚刚去喝水啦。",
            reply_markup=telegram_bot.MAIN_REPLY_KEYBOARD,
        )

    @patch("telegram_bot.owner_params")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.api_get_pets")
    def test_proactive_tick_stays_quiet_without_generated_message(
        self,
        api_get_pets: Mock,
        post: Mock,
        send_message: Mock,
        owner_params: Mock,
    ) -> None:
        telegram_bot.ALLOWED_CHAT_ID = "chat-1"
        owner_params.return_value = {}
        api_get_pets.return_value = [
            {"id": 7, "name": "小月", "pet_mode": "virtual"},
        ]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"event_result": None}

        result = telegram_bot.proactive_tick_virtual_pets_once(tick_minutes=10)

        self.assertEqual({"chats": 1, "pets": 1, "messages": 0}, result)
        send_message.assert_not_called()

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    def test_pet_creation_collects_descriptions_then_offers_targeted_avatar_setup(
        self,
        post: Mock,
        send_message: Mock,
    ) -> None:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "id": 42,
            "name": "小月",
        }

        telegram_bot.start_pet_create_flow("chat-1")
        telegram_bot.handle_pet_create_text("chat-1", "小月")
        telegram_bot.set_pet_create_species("chat-1", "cat")
        telegram_bot.handle_pet_create_text("chat-1", "亲人但有点慢热")
        telegram_bot.handle_pet_create_text("chat-1", "银灰色，耳尖深色，尾巴蓬松")

        post.assert_called_once()
        self.assertEqual("小月", post.call_args.kwargs["json"]["name"])
        self.assertEqual("cat", post.call_args.kwargs["json"]["species"])
        self.assertEqual(
            {
                "personality_description": "亲人但有点慢热",
                "traits_description": "银灰色，耳尖深色，尾巴蓬松",
            },
            post.call_args.kwargs["json"]["profile"],
        )
        final_markup = send_message.call_args.kwargs["reply_markup"]
        self.assertEqual(
            "set:avatar:42",
            final_markup["inline_keyboard"][0][0]["callback_data"],
        )
        self.assertNotIn("chat-1", telegram_bot.PENDING_PET_FLOWS)
        self.assertEqual(42, telegram_bot.CURRENT_PET_IDS["chat-1"])

    def test_avatar_flow_can_target_new_pet(self) -> None:
        with patch("telegram_bot.send_message"):
            telegram_bot.start_avatar_flow("chat-2", pet_id=42)

        self.assertEqual(42, telegram_bot.PENDING_AVATAR_FLOWS["chat-2"]["pet_id"])

    @patch("telegram_bot.start_avatar_preview_generation")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot._download_telegram_file")
    def test_avatar_photo_with_caption_starts_generation_immediately(
        self,
        download_file: Mock,
        _send_message: Mock,
        start_generation: Mock,
    ) -> None:
        download_file.return_value = (b"image", "image/jpeg", ".jpg")
        telegram_bot.PENDING_AVATAR_FLOWS["chat-8"] = {
            "step": "await_photo",
            "trace_id": "avatar_caption",
            "pet_id": 42,
        }

        handled = telegram_bot.handle_avatar_photo(
            "chat-8",
            {
                "photo": [{"file_id": "file-1"}],
                "caption": "活泼淘气的卷毛狗狗",
            },
        )

        self.assertTrue(handled)
        self.assertEqual("await_style", telegram_bot.PENDING_AVATAR_FLOWS["chat-8"]["step"])
        start_generation.assert_called_once_with("chat-8", "活泼淘气的卷毛狗狗")

    @patch("telegram_bot.start_avatar_preview_generation")
    @patch("telegram_bot.requests.get")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot._download_telegram_file")
    def test_avatar_photo_without_caption_uses_pet_profile_and_starts_generation(
        self,
        download_file: Mock,
        _send_message: Mock,
        get: Mock,
        start_generation: Mock,
    ) -> None:
        download_file.return_value = (b"image", "image/jpeg", ".jpg")
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {
                "id": 42,
                "species": "other",
                "profile_json": (
                    '{"custom_species": "章鱼", '
                    '"personality_description": "黏人", '
                    '"traits_description": "蓝色短触手"}'
                ),
            }
        ]
        telegram_bot.PENDING_AVATAR_FLOWS["chat-9"] = {
            "step": "await_photo",
            "trace_id": "avatar_profile",
            "pet_id": 42,
        }

        handled = telegram_bot.handle_avatar_photo("chat-9", {"photo": [{"file_id": "file-1"}]})

        self.assertTrue(handled)
        prompt = start_generation.call_args.args[1]
        self.assertIn("宠物种类：章鱼", prompt)
        self.assertIn("性格：黏人", prompt)
        self.assertIn("外观特征：蓝色短触手", prompt)

    @patch("telegram_bot.send_message")
    def test_photo_without_active_avatar_flow_waits_for_memory_text(self, send_message: Mock) -> None:
        handled = telegram_bot.handle_memory_photo("chat-10", {"photo": [{"file_id": "file-1"}]})

        self.assertTrue(handled)
        self.assertEqual("file-1", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-10"]["photo_file_id"])
        self.assertIn("有哪只宠物的回忆", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    def test_photo_caption_still_asks_owner_to_explain_before_memory_creation(
        self,
        send_message: Mock,
    ) -> None:
        handled = telegram_bot.handle_memory_photo(
            "chat-memory",
            {
                "message_id": 123,
                "photo": [{"file_id": "small"}, {"file_id": "large"}],
                "caption": "今天我们一起在海边看晚霞，黑米和 Qing Qing 都陪着我。",
            },
        )

        self.assertTrue(handled)
        self.assertEqual("large", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"]["photo_file_id"])
        self.assertEqual(
            "今天我们一起在海边看晚霞，黑米和 Qing Qing 都陪着我。",
            telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"]["caption"],
        )
        self.assertIn("有哪只宠物的回忆", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_text_after_photo_can_create_shared_memory(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [{"id": 8, "name": "黑米"}]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 32, "memory_type": "co_experienced"}
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-1",
            "message_id": 55,
        }

        handled = telegram_bot.handle_memory_photo_text(
            "chat-memory",
            "这是我们一起守夜时拍的，黑米一直陪着我。",
        )

        self.assertTrue(handled)
        self.assertEqual("co_experienced", post.call_args.kwargs["json"]["memory_type"])
        self.assertNotIn("chat-memory", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS)
        self.assertIn("记住了", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_co_experienced_photo_memory_uses_only_named_pet_participants(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 8, "name": "黑米"},
            {"id": 7, "name": "Qing Qing"},
        ]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 34, "memory_type": "co_experienced"}
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-1",
            "message_id": 55,
        }

        handled = telegram_bot.handle_memory_photo_text(
            "chat-memory",
            "这是我们一起在海边看晚霞，黑米一直陪着我。",
        )

        self.assertTrue(handled)
        payload = post.call_args.kwargs["json"]
        self.assertEqual("co_experienced", payload["memory_type"])
        self.assertEqual([8], payload["participant_pet_ids"])
        self.assertNotIn("chat-memory", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS)
        self.assertIn("黑米", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_co_experienced_photo_without_named_pet_asks_for_participants(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 8, "name": "黑米"},
            {"id": 7, "name": "Qing Qing"},
        ]
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-1",
            "message_id": 55,
        }

        handled = telegram_bot.handle_memory_photo_text(
            "chat-memory",
            "这是我们一起在海边看晚霞时拍的。",
        )

        self.assertTrue(handled)
        post.assert_not_called()
        self.assertEqual(
            "await_participants",
            telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"]["step"],
        )
        self.assertIn("是哪几只宠物", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_photo_participant_confirmation_matches_ascii_name_without_spaces_or_case(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "name": "Qing Qing"},
            {"id": 8, "name": "黑米"},
        ]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 36, "memory_type": "co_experienced"}
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "step": "await_participants",
            "photo_file_id": "file-1",
            "message_id": 55,
            "pending_content": "带着qingqing出去玩了",
        }

        handled = telegram_bot.handle_memory_photo_text("chat-memory", "qingqing")

        self.assertTrue(handled)
        payload = post.call_args.kwargs["json"]
        self.assertEqual([7], payload["participant_pet_ids"])
        self.assertEqual([{"pet_id": 7, "role": "participant"}], payload["participants"])
        self.assertNotIn("chat-memory", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS)
        self.assertIn("Qing Qing", send_message.call_args.args[1])

    def test_direct_pet_name_matching_accepts_light_fuzzy_ascii_reference(self) -> None:
        pets = [
            {"id": 7, "name": "Qing Qing"},
            {"id": 8, "name": "黑米"},
        ]

        mentioned = telegram_bot._directly_mentioned_pets("今天带 qingqin 出去玩", pets)

        self.assertEqual([7], [pet["id"] for pet in mentioned])

    def test_direct_pet_name_matching_avoids_ambiguous_fuzzy_reference(self) -> None:
        pets = [
            {"id": 7, "name": "Qing Qing"},
            {"id": 8, "name": "Qing Qong"},
        ]

        mentioned = telegram_bot._directly_mentioned_pets("今天带 qing qing 出去玩", pets)

        self.assertEqual([7], [pet["id"] for pet in mentioned])

        mentioned = telegram_bot._directly_mentioned_pets("今天带 qingqng 出去玩", pets)

        self.assertEqual([], mentioned)

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_sensitive_photo_memory_asks_before_saving(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [{"id": 8, "name": "黑米"}]
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-1",
            "message_id": 55,
        }

        handled = telegram_bot.handle_memory_photo_text(
            "chat-memory",
            "这是我失眠那晚拍的，黑米一直陪着我。",
        )

        self.assertTrue(handled)
        post.assert_not_called()
        self.assertEqual(
            "await_sensitive_confirm",
            telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"]["step"],
        )
        self.assertIn("有点私密", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_sensitive_photo_memory_confirmation_saves_restricted_memory(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [{"id": 8, "name": "黑米"}]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 35, "memory_type": "co_experienced"}
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "step": "await_sensitive_confirm",
            "photo_file_id": "file-1",
            "message_id": 55,
            "pending_content": "这是我失眠那晚拍的，黑米一直陪着我。",
            "pending_participant_pet_ids": [8],
        }

        handled = telegram_bot.handle_memory_photo_text("chat-memory", "记住")

        self.assertTrue(handled)
        payload = post.call_args.kwargs["json"]
        self.assertEqual("private", payload["visibility"])
        self.assertEqual("owner_asked_only", payload["recall_policy"])
        self.assertEqual([{"pet_id": 8, "role": "participant"}], payload["participants"])
        self.assertNotIn("chat-memory", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS)
        self.assertIn("只会在你问起时提", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    def test_photo_memory_cancel_text_clears_pending_flow(self, post: Mock, send_message: Mock) -> None:
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-1",
            "message_id": 55,
        }

        handled = telegram_bot.handle_memory_photo_text("chat-memory", "不要记住，只是给你看看")

        self.assertTrue(handled)
        post.assert_not_called()
        self.assertNotIn("chat-memory", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS)
        self.assertIn("不写进长期记忆", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    def test_photo_memory_pending_flow_expires(self, post: Mock, send_message: Mock) -> None:
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-1",
            "message_id": 55,
            "created_monotonic": time.monotonic() - telegram_bot.MEMORY_PHOTO_PENDING_TTL_SECONDS - 1,
        }

        handled = telegram_bot.handle_memory_photo_text("chat-memory", "这是我们一起去海边")

        self.assertTrue(handled)
        post.assert_not_called()
        self.assertNotIn("chat-memory", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS)
        self.assertIn("已经过期", send_message.call_args.args[1])

    @patch("telegram_bot.handle_pet_group_chat_text")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_text_after_photo_with_named_pet_creates_pet_milestone_memory(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
        handle_group_chat: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [{"id": 9, "name": "解放"}]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 33, "memory_type": "pet_milestone"}
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-2",
            "message_id": 56,
        }

        handled = telegram_bot.handle_memory_photo_text(
            "chat-memory",
            "这个照片是解放出去玩时候给他拍的",
        )

        self.assertTrue(handled)
        payload = post.call_args.kwargs["json"]
        self.assertEqual("pet_milestone", payload["memory_type"])
        self.assertEqual("recallable", payload["use_class"])
        self.assertEqual([9], payload["participant_pet_ids"])
        self.assertEqual("file-2", payload["metadata"]["telegram_photo_file_id"])
        self.assertNotIn("chat-memory", telegram_bot.PENDING_MEMORY_PHOTO_FLOWS)
        self.assertIn("解放", send_message.call_args.args[1])
        handle_group_chat.assert_called_once_with(
            "chat-memory",
            "这个照片是解放出去玩时候给他拍的",
        )

    @patch("telegram_bot.handle_pet_group_chat_text")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_direct_question_after_pet_photo_memory_routes_to_group_chat(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
        handle_group_chat: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [{"id": 9, "name": "解放"}]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 33, "memory_type": "pet_milestone"}
        handle_group_chat.return_value = True
        telegram_bot.PENDING_MEMORY_PHOTO_FLOWS["chat-memory"] = {
            "photo_file_id": "file-2",
            "message_id": 56,
        }

        telegram_bot.handle_message(
            {"chat": {"id": "chat-memory"}, "text": "这个照片是解放出去玩时候给他拍的"}
        )
        telegram_bot.handle_message({"chat": {"id": "chat-memory"}, "text": "解放怎么说？"})

        self.assertEqual(
            [
                call("chat-memory", "这个照片是解放出去玩时候给他拍的"),
                call("chat-memory", "解放怎么说？"),
            ],
            handle_group_chat.call_args_list,
        )

    @patch("telegram_bot.handle_pet_group_chat_text")
    def test_unknown_text_routes_to_pet_group_chat(self, handle_group_chat: Mock) -> None:
        handle_group_chat.return_value = True
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        telegram_bot.ALLOWED_CHAT_ID = ""
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-11"}, "text": "生成好了吗"})
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id

        handle_group_chat.assert_called_once_with("chat-11", "生成好了吗")

    @patch("telegram_bot.handle_pet_group_chat_text")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_explicit_remember_text_creates_recallable_group_memory(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
        handle_group_chat: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [{"id": 8, "name": "青团"}]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 41, "title": "群聊记忆"}
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        original_owner_chat_ids = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_CHAT_ID = ""
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = set()
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-memory"}, "text": "记住这个：青团喜欢被叫小团子"})
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_owner_chat_ids

        self.assertEqual("owner_shared", post.call_args.kwargs["json"]["memory_type"])
        self.assertEqual("recallable", post.call_args.kwargs["json"]["use_class"])
        self.assertEqual("青团喜欢被叫小团子", post.call_args.kwargs["json"]["content"])
        self.assertEqual([8], post.call_args.kwargs["json"]["participant_pet_ids"])
        self.assertIn("记下了", send_message.call_args.args[1])
        handle_group_chat.assert_not_called()

    @patch("telegram_bot.handle_pet_group_chat_text")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_low_sensitivity_name_preference_creates_behavioral_memory(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
        handle_group_chat: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [{"id": 8, "name": "青团"}]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 42, "title": "称呼偏好"}
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        original_owner_chat_ids = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_CHAT_ID = ""
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = set()
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-memory"}, "text": "以后叫我阿澈"})
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_owner_chat_ids

        payload = post.call_args.kwargs["json"]
        self.assertEqual("behavioral", payload["use_class"])
        self.assertEqual("称呼偏好", payload["title"])
        self.assertIn("阿澈", payload["content"])
        self.assertIn("以后叫你阿澈", send_message.call_args.args[1])
        handle_group_chat.assert_not_called()

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_memory_menu_lists_recent_memories(self, get: Mock, send_message: Mock) -> None:
        pets_response = Mock(status_code=200)
        pets_response.json.return_value = [{"id": 8, "name": "青团"}]
        memories_response = Mock(status_code=200)
        memories_response.json.return_value = [
            {
                "id": 9,
                "title": "称呼偏好",
                "content": "主人希望宠物以后叫 TA 阿澈。",
                "use_class": "behavioral",
                "participant_pet_ids": [8],
            }
        ]
        get.side_effect = [pets_response, memories_response]

        original_owner_chat_ids = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = set()
        try:
            telegram_bot.handle_memory_menu("chat-memory")
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_owner_chat_ids

        text = send_message.call_args.args[1]
        self.assertIn("#9", text)
        self.assertIn("称呼偏好", text)
        self.assertIn("behavioral", text)

    @patch("telegram_bot.handle_pet_group_chat_text")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.delete")
    @patch("telegram_bot.requests.get")
    def test_forget_memory_command_deletes_memory(
        self,
        get: Mock,
        delete: Mock,
        send_message: Mock,
        handle_group_chat: Mock,
    ) -> None:
        pets_response = Mock(status_code=200)
        pets_response.json.return_value = [{"id": 8, "name": "青团"}]
        memories_response = Mock(status_code=200)
        memories_response.json.return_value = [
            {"id": 9, "title": "称呼偏好", "participant_pet_ids": [8]}
        ]
        get.side_effect = [pets_response, memories_response]
        delete.return_value.status_code = 200
        delete.return_value.json.return_value = {"id": 9, "title": "称呼偏好"}
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        original_owner_chat_ids = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_CHAT_ID = ""
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = set()
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-memory"}, "text": "忘记记忆 9"})
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_owner_chat_ids

        self.assertTrue(delete.call_args.args[0].endswith("/pet-memories/9"))
        self.assertIn("已忘记", send_message.call_args.args[1])
        handle_group_chat.assert_not_called()

    @patch("telegram_bot.requests.post")
    def test_telegram_api_includes_response_details_on_failure(self, post: Mock) -> None:
        response = Mock()
        response.status_code = 409
        response.text = '{"description":"Conflict: terminated by other getUpdates request"}'
        response.raise_for_status.side_effect = requests.RequestException("409 Client Error")
        post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "409"):
            telegram_bot.telegram_api("getUpdates", {})

    def test_pet_card_shows_name_species_personality_avatar_state_and_horizontal_actions(self) -> None:
        pet = {
            "id": 1,
            "name": "黑米",
            "species": "dog",
            "personality": "gentle",
            "profile_json": (
                '{"personality_description": "黏人 爱撒娇", '
                '"traits_description": "黑色中长毛", '
                '"personality_behavior_notes": ["看到陌生人会先躲起来"], '
                '"speaking_style_prompt": "说话短句，傲娇但会小声认真回答", '
                '"avatar_image_url": "/static/generated/heimi.png"}'
            ),
        }

        text, profile = telegram_bot.format_pet_card_text(pet, 1)
        markup = telegram_bot.pet_action_keyboard(pet, profile)

        self.assertIn("1. 黑米", text)
        self.assertIn("种类：狗", text)
        self.assertIn("性格：温柔，黏人 爱撒娇", text)
        self.assertIn("形象：基础形象已生成", text)
        self.assertIn("特征：黑色中长毛", text)
        self.assertIn("性格行为补充：看到陌生人会先躲起来", text)
        self.assertIn("说话语气：说话短句，傲娇但会小声认真回答", text)
        self.assertEqual("设为互动对象", markup["inline_keyboard"][0][0]["text"])
        self.assertEqual("pet_current:1", markup["inline_keyboard"][0][0]["callback_data"])
        self.assertEqual("单独上桌面", markup["inline_keyboard"][0][1]["text"])
        self.assertEqual("desktop:1", markup["inline_keyboard"][0][1]["callback_data"])
        self.assertEqual("设置资料", markup["inline_keyboard"][1][0]["text"])
        self.assertEqual("pet_settings:1", markup["inline_keyboard"][1][0]["callback_data"])
        self.assertEqual("更新形象", markup["inline_keyboard"][2][0]["text"])
        self.assertEqual("set:avatar:1", markup["inline_keyboard"][2][0]["callback_data"])
        self.assertEqual("删除", markup["inline_keyboard"][2][1]["text"])
        self.assertEqual("pet_delete:ask:1", markup["inline_keyboard"][2][1]["callback_data"])

    def test_pet_card_prefers_custom_species_and_desktop_avatar(self) -> None:
        pet = {
            "id": 2,
            "name": "泡泡",
            "species": "other",
            "personality": "energetic",
            "profile_json": (
                '{"custom_species": "章鱼", '
                '"desktop_pet_avatar_url": "/static/desktop_pet_assets/bubble/avatar.png", '
                '"desktop_pet_manifest_url": "/static/desktop_pet_assets/bubble/manifest.json"}'
            ),
        }

        text, profile = telegram_bot.format_pet_card_text(pet, 2)

        self.assertIn("2. 泡泡", text)
        self.assertIn("种类：章鱼", text)
        self.assertIn("性格：活泼", text)
        self.assertIn("形象：桌宠动作素材已就绪", text)
        self.assertEqual("/static/desktop_pet_assets/bubble/avatar.png", telegram_bot.pet_avatar_image_url(profile))

    def test_pet_card_shows_failed_desktop_asset_generation_as_basic_avatar_usable(self) -> None:
        pet = {
            "id": 3,
            "name": "米花",
            "species": "cat",
            "personality": "curious",
            "profile_json": (
                '{"avatar_image_url": "/static/generated/mihua.png", '
                '"character_id": "character-3", '
                '"desktop_pet_assets_status": "failed"}'
            ),
        }

        text, _profile = telegram_bot.format_pet_card_text(pet, 3)

        self.assertIn("形象：基础形象可用，动作素材生成失败", text)

    def test_pet_card_with_confirmed_character_offers_one_time_sticker_pack_generation(self) -> None:
        pet = {
            "id": 4,
            "name": "奶盖",
            "species": "cat",
            "personality": "sweet",
            "profile_json": (
                '{"avatar_image_url": "/static/generated/naigai.png", '
                '"character_id": "character-4"}'
            ),
        }

        _text, profile = telegram_bot.format_pet_card_text(pet, 4)
        markup = telegram_bot.pet_action_keyboard(pet, profile)

        flat_buttons = [
            button
            for row in markup["inline_keyboard"]
            for button in row
        ]
        self.assertIn(
            {"text": "生成表情包", "callback_data": "stickers:generate:4"},
            flat_buttons,
        )

    def test_pet_card_hides_sticker_pack_button_while_generating_or_ready(self) -> None:
        for status in ("generating", "ready"):
            pet = {
                "id": 4,
                "name": "奶盖",
                "species": "cat",
                "personality": "sweet",
                "profile_json": (
                    '{"avatar_image_url": "/static/generated/naigai.png", '
                    '"character_id": "character-4", '
                    f'"sticker_pack_status": "{status}"}}'
                ),
            }

            _text, profile = telegram_bot.format_pet_card_text(pet, 4)
            markup = telegram_bot.pet_action_keyboard(pet, profile)

            flat_labels = [
                button["text"]
                for row in markup["inline_keyboard"]
                for button in row
            ]
            self.assertNotIn("生成表情包", flat_labels)

    @patch("telegram_bot.send_local_photo")
    @patch("telegram_bot.send_message")
    def test_send_pet_card_uses_avatar_photo_when_available(
        self,
        send_message: Mock,
        send_local_photo: Mock,
    ) -> None:
        pet = {
            "id": 7,
            "name": "小月",
            "species": "cat",
            "personality": "gentle",
            "profile_json": '{"avatar_image_url": "/static/generated/xiaoyue.png"}',
        }

        telegram_bot.send_pet_card("chat-12", pet, 1)

        send_local_photo.assert_called_once()
        self.assertEqual("chat-12", send_local_photo.call_args.args[0])
        self.assertEqual("/static/generated/xiaoyue.png", send_local_photo.call_args.args[1])
        self.assertIn("小月", send_local_photo.call_args.args[2])
        send_message.assert_not_called()

    @patch("telegram_bot.send_pet_card")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_list_command_sends_one_card_per_pet(
        self,
        get: Mock,
        send_message: Mock,
        send_pet_card: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {
                "id": 7,
                "name": "小月",
                "species": "cat",
                "personality": "gentle",
                "profile_json": "{}",
            }
        ]

        telegram_bot.handle_pets_command("chat-13")

        send_message.assert_called_once_with(
            "chat-13",
            "宠物清单",
            reply_markup=telegram_bot.inline_keyboard([[("创建宠物", "pet_create:start")]]),
        )
        send_pet_card.assert_called_once_with("chat-13", get.return_value.json.return_value[0], 1)

    @patch("telegram_bot.send_pet_card")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_pet_list_scopes_to_allowed_owner(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
        send_pet_card: Mock,
    ) -> None:
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-owner"}
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 12, "telegram_chat_id": "chat-owner"}
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {
                "id": 7,
                "owner_id": 12,
                "name": "小月",
                "species": "cat",
                "personality": "gentle",
                "profile_json": "{}",
            }
        ]
        try:
            telegram_bot.handle_pets_command("chat-owner")
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        post.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/owners/telegram",
            json={"telegram_chat_id": "chat-owner", "display_name": ""},
            timeout=10,
        )
        get.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/pets",
            params={"owner_id": 12},
            timeout=10,
        )
        send_message.assert_called_once()
        send_pet_card.assert_called_once()

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_friendship_invite_generation_uses_current_owner_and_pet(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-owner"}
        telegram_bot.OWNER_IDS_BY_CHAT["chat-owner"] = 12
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "name": "黑米", "owner_id": 12, "species": "dog"}
        ]
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"token": "friend-token"}
        try:
            telegram_bot.create_friendship_invite_for_pet("chat-owner", 7)
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        post.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/pet-friendship-invites",
            json={"inviter_owner_id": 12, "inviter_pet_id": 7},
            timeout=10,
        )
        self.assertIn("/pet_friend_invite friend-token", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    @patch("telegram_bot.requests.get")
    def test_friendship_invite_command_accepts_with_single_pet(
        self,
        get: Mock,
        post: Mock,
        send_message: Mock,
    ) -> None:
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-owner"}
        telegram_bot.OWNER_IDS_BY_CHAT["chat-owner"] = 12

        def get_response(url: str, **_kwargs: object) -> Mock:
            response = Mock()
            response.status_code = 200
            if url.endswith("/pet-friendship-invites/friend-token"):
                response.json.return_value = {
                    "token": "friend-token",
                    "inviter_pet_name": "黑米",
                }
            else:
                response.json.return_value = [
                    {"id": 8, "name": "青青", "owner_id": 12, "species": "cat"}
                ]
            return response

        get.side_effect = get_response
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "id": 3,
            "pet_a_id": 7,
            "pet_a_name": "黑米",
            "pet_b_id": 8,
            "pet_b_name": "青青",
        }
        try:
            handled = telegram_bot.handle_friendship_invite_command(
                "chat-owner",
                "/pet_friend_invite friend-token",
            )
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        self.assertTrue(handled)
        post.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/pet-friendship-invites/friend-token/accept",
            json={"receiver_owner_id": 12, "receiver_pet_id": 8},
            timeout=10,
        )
        self.assertIn("已经成为好友", send_message.call_args.args[1])

    @patch("telegram_bot.handle_pet_group_chat_text")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_share_to_named_friend_owner_forwards_across_owner_chats(
        self,
        get: Mock,
        send_message: Mock,
        handle_group_chat: Mock,
    ) -> None:
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-a", "chat-b"}
        telegram_bot.OWNER_IDS_BY_CHAT["chat-a"] = 1
        telegram_bot.CURRENT_PET_IDS["chat-a"] = 7

        def get_response(url: str, **_kwargs: object) -> Mock:
            response = Mock(status_code=200)
            if url.endswith("/pets"):
                response.json.return_value = [{"id": 7, "name": "黑米", "owner_id": 1}]
            elif url.endswith("/pet-friendships"):
                response.json.return_value = [
                    {
                        "id": 3,
                        "pet_a_id": 7,
                        "pet_a_name": "黑米",
                        "owner_a_id": 1,
                        "owner_a_name": "小明",
                        "owner_a_chat_id": "chat-a",
                        "pet_b_id": 8,
                        "pet_b_name": "青青",
                        "owner_b_id": 2,
                        "owner_b_name": "小红",
                        "owner_b_chat_id": "chat-b",
                        "affinity": 50,
                        "muted": False,
                    }
                ]
            else:
                response.json.return_value = []
            return response

        get.side_effect = get_response
        try:
            telegram_bot.handle_message(
                {
                    "chat": {"id": "chat-a"},
                    "text": "分享给小红：今天黑米学会了握手",
                }
            )
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        self.assertEqual("chat-b", send_message.call_args_list[0].args[0])
        self.assertIn("今天黑米学会了握手", send_message.call_args_list[0].args[1])
        self.assertIn("已分享给小红", send_message.call_args_list[1].args[1])
        handle_group_chat.assert_not_called()

    @patch("telegram_bot.handle_pet_group_chat_text")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_memory_share_to_friend_requires_owner_confirmation(
        self,
        get: Mock,
        send_message: Mock,
        handle_group_chat: Mock,
    ) -> None:
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-a", "chat-b"}
        telegram_bot.OWNER_IDS_BY_CHAT["chat-a"] = 1
        telegram_bot.CURRENT_PET_IDS["chat-a"] = 7

        def get_response(url: str, **_kwargs: object) -> Mock:
            response = Mock(status_code=200)
            if url.endswith("/pets"):
                response.json.return_value = [{"id": 7, "name": "黑米", "owner_id": 1}]
            elif url.endswith("/pet-memories"):
                response.json.return_value = [
                    {
                        "id": 9,
                        "title": "握手进步",
                        "content": "黑米今天第一次学会握手。",
                        "use_class": "recallable",
                        "participant_pet_ids": [7],
                    }
                ]
            elif url.endswith("/pet-friendships"):
                response.json.return_value = [
                    {
                        "id": 3,
                        "pet_a_id": 7,
                        "pet_a_name": "黑米",
                        "owner_a_id": 1,
                        "owner_a_name": "小明",
                        "owner_a_chat_id": "chat-a",
                        "pet_b_id": 8,
                        "pet_b_name": "青青",
                        "owner_b_id": 2,
                        "owner_b_name": "小红",
                        "owner_b_chat_id": "chat-b",
                        "affinity": 50,
                        "muted": False,
                    }
                ]
            else:
                response.json.return_value = []
            return response

        get.side_effect = get_response
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-a"}, "text": "分享记忆 9 给 小红"})
            self.assertEqual(1, send_message.call_count)
            self.assertIn("确认分享", send_message.call_args.args[1])

            telegram_bot.handle_message({"chat": {"id": "chat-a"}, "text": "确认分享"})
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        self.assertEqual("chat-b", send_message.call_args_list[1].args[0])
        self.assertIn("黑米今天第一次学会握手", send_message.call_args_list[1].args[1])
        self.assertIn("已分享这条记忆", send_message.call_args_list[2].args[1])
        handle_group_chat.assert_not_called()

    @patch("telegram_bot.random.choice", return_value="{local_pet_name} 想问问 {friend_pet_name}：今天好吗？")
    @patch("telegram_bot.random.random", return_value=0.0)
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_friendship_daily_message_uses_friendship_relationships(
        self,
        get: Mock,
        send_message: Mock,
        _random: Mock,
        _choice: Mock,
    ) -> None:
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        original_chance = telegram_bot.PET_FRIEND_DAILY_MESSAGE_CHANCE
        original_interval = telegram_bot.PET_FRIEND_DAILY_MESSAGE_INTERVAL_SECONDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-a"}
        telegram_bot.OWNER_IDS_BY_CHAT["chat-a"] = 1
        telegram_bot.PET_FRIEND_DAILY_MESSAGE_CHANCE = 1.0
        telegram_bot.PET_FRIEND_DAILY_MESSAGE_INTERVAL_SECONDS = 0
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {
                "id": 3,
                "pet_a_id": 7,
                "pet_a_name": "黑米",
                "owner_a_id": 1,
                "owner_a_name": "小明",
                "owner_a_chat_id": "chat-a",
                "pet_b_id": 8,
                "pet_b_name": "青青",
                "owner_b_id": 2,
                "owner_b_name": "小红",
                "owner_b_chat_id": "chat-b",
                "affinity": 80,
                "muted": False,
            }
        ]
        try:
            sent = telegram_bot.maybe_send_friendship_daily_messages(now=1000.0)
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed
            telegram_bot.PET_FRIEND_DAILY_MESSAGE_CHANCE = original_chance
            telegram_bot.PET_FRIEND_DAILY_MESSAGE_INTERVAL_SECONDS = original_interval

        self.assertEqual(1, sent)
        send_message.assert_called_once()
        self.assertEqual("chat-b", send_message.call_args.args[0])
        self.assertIn("黑米", send_message.call_args.args[1])
        self.assertIn("青青", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_command_marks_interaction_target_and_offers_targeted_actions(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        telegram_bot.CURRENT_PET_IDS["chat-choose"] = 8
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "name": "小月", "species": "cat", "profile_json": "{}"},
            {"id": 8, "name": "黑米", "species": "dog", "profile_json": "{}"},
        ]

        telegram_bot.handle_pet_group_command("chat-choose")

        self.assertIn("chat-choose", telegram_bot.ACTIVE_PET_GROUP_CHATS)
        self.assertIn("宠物们的群聊", send_message.call_args_list[0].args[1])
        intro_markup = send_message.call_args_list[0].kwargs["reply_markup"]["inline_keyboard"]
        self.assertEqual("rel:start", intro_markup[0][0]["callback_data"])
        self.assertIn("黑米（正在互动）", send_message.call_args_list[2].args[1])
        markup = send_message.call_args_list[1].kwargs["reply_markup"]["inline_keyboard"][0]
        self.assertEqual("pet_current:7", markup[0]["callback_data"])
        self.assertEqual("desktop:7", markup[1]["callback_data"])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_card_settings_opens_targeted_settings_menu(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "name": "小月", "species": "cat", "profile_json": "{}"},
        ]

        telegram_bot.show_pet_settings("chat-settings", 7)

        self.assertIn("正在设置：小月", send_message.call_args.args[1])
        markup = send_message.call_args.kwargs["reply_markup"]["inline_keyboard"]
        self.assertEqual("prompt_set:7:name", markup[0][0]["callback_data"])
        self.assertEqual("prompt_profile:7:personality_behavior", markup[1][0]["callback_data"])
        flat_buttons = [button for row in markup for button in row]
        self.assertIn("设置种类", [button["text"] for button in flat_buttons])
        self.assertIn("设置说话语气", [button["text"] for button in flat_buttons])
        self.assertNotIn("甜甜", [button["text"] for button in flat_buttons])
        self.assertNotIn("酷酷", [button["text"] for button in flat_buttons])
        self.assertNotIn("活泼", [button["text"] for button in flat_buttons])
        self.assertNotIn("温柔", [button["text"] for button in flat_buttons])
        self.assertNotIn("猫", [button["text"] for button in flat_buttons])
        self.assertNotIn("狗", [button["text"] for button in flat_buttons])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    @patch("telegram_bot.requests.get")
    def test_speaking_style_setting_accepts_free_text_and_injects_prompt(
        self,
        get: Mock,
        patch_request: Mock,
        send_message: Mock,
    ) -> None:
        pet = {"id": 7, "name": "小月", "species": "cat", "profile_json": "{}"}
        get.return_value.status_code = 200
        get.return_value.json.return_value = [pet]
        patch_request.return_value.status_code = 200
        patch_request.return_value.json.return_value = {
            **pet,
            "profile_json": '{"speaking_style_prompt":"说话短句，傲娇，但被点名时会小声认真回答"}',
        }

        telegram_bot.start_profile_note_flow("chat-style", 7, "speaking_style")
        handled = telegram_bot.handle_pending_text(
            "chat-style",
            "说话短句，傲娇，但被点名时会小声认真回答",
        )

        self.assertTrue(handled)
        patch_request.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/pets/7",
            json={"profile": {"speaking_style_prompt": "说话短句，傲娇，但被点名时会小声认真回答"}},
            timeout=10,
        )
        prompt_profile = telegram_bot._pet_profile_for_prompt(patch_request.return_value.json.return_value)
        self.assertIn("傲娇", prompt_profile["speaking_style_prompt"])
        self.assertIn("说话语气", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    @patch("telegram_bot.requests.get")
    def test_species_setting_accepts_free_text_as_custom_species(
        self,
        get: Mock,
        patch_request: Mock,
        send_message: Mock,
    ) -> None:
        pet = {
            "id": 7,
            "name": "小月",
            "species": "cat",
            "profile_json": '{"personality_behavior_notes":["熟人靠近时会主动蹭手"]}',
        }
        get.return_value.status_code = 200
        get.return_value.json.return_value = [pet]
        patch_request.return_value.status_code = 200
        patch_request.return_value.json.return_value = {
            **pet,
            "species": "other",
            "profile_json": (
                '{"personality_behavior_notes":["熟人靠近时会主动蹭手"],'
                '"custom_species":"狐狸"}'
            ),
        }

        telegram_bot.start_profile_note_flow("chat-species", 7, "species")
        handled = telegram_bot.handle_pending_text("chat-species", "狐狸")

        self.assertTrue(handled)
        patch_request.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/pets/7",
            json={
                "species": "other",
                "profile": {
                    "personality_behavior_notes": ["熟人靠近时会主动蹭手"],
                    "custom_species": "狐狸",
                },
            },
            timeout=10,
        )
        self.assertIn("种类", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    @patch("telegram_bot.requests.get")
    def test_profile_note_flow_appends_personality_behavior_and_injects_prompt(
        self,
        get: Mock,
        patch_request: Mock,
        send_message: Mock,
    ) -> None:
        pet = {
            "id": 7,
            "name": "小月",
            "species": "cat",
            "personality": "gentle",
            "profile_json": '{"personality_behavior_notes":["熟人靠近时会主动蹭手"]}',
        }
        get.return_value.status_code = 200
        get.return_value.json.return_value = [pet]
        patch_request.return_value.status_code = 200
        patch_request.return_value.json.return_value = {
            **pet,
            "profile_json": (
                '{"personality_behavior_notes":["熟人靠近时会主动蹭手",'
                '"陌生声音会先躲到桌角观察"]}'
            ),
        }

        telegram_bot.start_profile_note_flow("chat-note", 7, "personality_behavior")
        handled = telegram_bot.handle_pending_text("chat-note", "陌生声音会先躲到桌角观察")

        self.assertTrue(handled)
        patch_request.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/pets/7",
            json={
                "profile": {
                    "personality_behavior_notes": [
                        "熟人靠近时会主动蹭手",
                        "陌生声音会先躲到桌角观察",
                    ]
                }
            },
            timeout=10,
        )
        prompt_profile = telegram_bot._pet_profile_for_prompt(patch_request.return_value.json.return_value)
        self.assertIn("陌生声音会先躲到桌角观察", prompt_profile["personality_behavior_notes"])
        self.assertIn("已补充", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_relationship_flow_selects_directed_edge_and_labels(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "name": "小月", "species": "cat", "profile_json": "{}"},
            {"id": 8, "name": "黑米", "species": "dog", "profile_json": "{}"},
        ]

        telegram_bot.start_relationship_flow("chat-rel")
        telegram_bot.choose_relationship_source("chat-rel", 8)
        telegram_bot.choose_relationship_target("chat-rel", 7)
        telegram_bot.toggle_relationship_label("chat-rel", "likes_staying_near_target")
        telegram_bot.relationship_labels_done("chat-rel")

        self.assertEqual(
            {
                "step": "await_note",
                "from_pet_id": 8,
                "to_pet_id": 7,
                "selected_labels": ["likes_staying_near_target"],
                "from_pet_name": "黑米",
                "to_pet_name": "小月",
            },
            telegram_bot.PENDING_RELATIONSHIP_FLOWS["chat-rel"],
        )
        self.assertIn("黑米 对 小月", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.put")
    def test_relationship_note_saves_edge_and_offers_reverse(
        self,
        put: Mock,
        send_message: Mock,
    ) -> None:
        put.return_value.status_code = 200
        put.return_value.json.return_value = {
            "from_pet_id": 8,
            "to_pet_id": 7,
        }
        telegram_bot.PENDING_RELATIONSHIP_FLOWS["chat-rel-note"] = {
            "step": "await_note",
            "from_pet_id": 8,
            "to_pet_id": 7,
            "selected_labels": ["likes_staying_near_target"],
            "from_pet_name": "黑米",
            "to_pet_name": "小月",
        }

        handled = telegram_bot.handle_relationship_text("chat-rel-note", "黑米喜欢贴着小月")

        self.assertTrue(handled)
        put.assert_called_once_with(
            f"{telegram_bot.API_BASE_URL}/pet-relationships/8/7",
            json={
                "labels": ["likes_staying_near_target"],
                "note": "黑米喜欢贴着小月",
                "muted": False,
            },
            timeout=10,
        )
        self.assertNotIn("chat-rel-note", telegram_bot.PENDING_RELATIONSHIP_FLOWS)
        self.assertIn("以后群聊里", send_message.call_args.args[1])
        markup = send_message.call_args.kwargs["reply_markup"]["inline_keyboard"]
        self.assertEqual("rel:reverse:7:8", markup[0][0]["callback_data"])

    def test_relationship_context_filters_candidates_and_respects_muted(self) -> None:
        context = telegram_bot.build_relationship_context_for_candidates(
            [7, 8],
            [
                {
                    "from_pet_id": 8,
                    "to_pet_id": 7,
                    "from_pet_name": "黑米",
                    "to_pet_name": "小月",
                    "labels": ["likes_staying_near_target"],
                    "note": "黑米喜欢贴着小月",
                    "muted": True,
                },
                {
                    "from_pet_id": 9,
                    "to_pet_id": 7,
                    "from_pet_name": "Qing Qing",
                    "to_pet_name": "小月",
                    "labels": ["often_replies_to_target"],
                    "note": "",
                    "muted": False,
                },
            ],
        )

        self.assertEqual(1, len(context))
        self.assertEqual(8, context[0]["from_pet_id"])
        self.assertFalse(context[0]["allow_natural_expression"])
        self.assertIn("do not escalate", context[0]["constraints"][1])

    def test_relationship_context_for_turn_prioritizes_speaker_outgoing_edge(self) -> None:
        context = telegram_bot.build_relationship_context_for_turn(
            speaker_pet_id=8,
            candidate_pet_ids=[7, 8],
            relationships=[
                {
                    "from_pet_id": 8,
                    "to_pet_id": 7,
                    "from_pet_name": "黑米",
                    "to_pet_name": "小月",
                    "labels": ["often_replies_to_target"],
                    "note": "黑米喜欢接小月的话",
                    "muted": False,
                },
                {
                    "from_pet_id": 7,
                    "to_pet_id": 8,
                    "from_pet_name": "小月",
                    "to_pet_name": "黑米",
                    "labels": ["quiet_around_target"],
                    "note": "小月在黑米旁边会变安静",
                    "muted": False,
                },
            ],
            now=100.0,
        )

        self.assertEqual(["primary_outgoing", "secondary_reverse"], [item["role"] for item in context])
        self.assertTrue(context[0]["allow_natural_expression"])
        self.assertFalse(context[1]["allow_natural_expression"])
        self.assertIn("黑米喜欢接小月的话", context[0]["note"])

    def test_relationship_context_for_turn_uses_runtime_cooldown(self) -> None:
        relationships = [
            {
                "from_pet_id": 8,
                "to_pet_id": 7,
                "from_pet_name": "黑米",
                "to_pet_name": "小月",
                "labels": ["often_replies_to_target"],
                "note": "",
                "muted": False,
            },
        ]

        first = telegram_bot.build_relationship_context_for_turn(
            speaker_pet_id=8,
            candidate_pet_ids=[7, 8],
            relationships=relationships,
            now=100.0,
        )
        second = telegram_bot.build_relationship_context_for_turn(
            speaker_pet_id=8,
            candidate_pet_ids=[7, 8],
            relationships=relationships,
            now=120.0,
        )

        self.assertTrue(first[0]["allow_natural_expression"])
        self.assertFalse(second[0]["allow_natural_expression"])
        self.assertEqual("runtime cooldown", second[0]["expression_blocked_reason"])

    def test_relationship_context_for_turn_respects_muted_and_weak_incoming_edges(self) -> None:
        context = telegram_bot.build_relationship_context_for_turn(
            speaker_pet_id=8,
            candidate_pet_ids=[7, 8, 9],
            relationships=[
                {
                    "from_pet_id": 8,
                    "to_pet_id": 7,
                    "from_pet_name": "黑米",
                    "to_pet_name": "小月",
                    "labels": ["pulls_target_to_play"],
                    "note": "",
                    "muted": True,
                },
                {
                    "from_pet_id": 9,
                    "to_pet_id": 8,
                    "from_pet_name": "青青",
                    "to_pet_name": "黑米",
                    "labels": ["likes_staying_near_target"],
                    "note": "青青喜欢靠近黑米",
                    "muted": False,
                },
            ],
            now=100.0,
        )

        self.assertEqual(["primary_outgoing", "weak_incoming"], [item["role"] for item in context])
        self.assertFalse(context[0]["allow_natural_expression"])
        self.assertEqual("muted", context[0]["expression_blocked_reason"])
        self.assertFalse(context[1]["allow_natural_expression"])
        self.assertIn("青青喜欢靠近黑米", context[1]["note"])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_text_calls_gpt_with_relationship_context(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        pets = [
            {"id": 8, "name": "黑米", "species": "cat", "personality": "gentle", "owner_call_name": "妈"},
            {"id": 7, "name": "小月", "species": "dog", "personality": "energetic", "owner_call_name": "妈"},
        ]
        relationships = [
            {
                "from_pet_id": 8,
                "to_pet_id": 7,
                "from_pet_name": "黑米",
                "to_pet_name": "小月",
                "labels": ["often_replies_to_target"],
                "note": "黑米喜欢接小月的话",
                "muted": False,
            }
        ]
        memories = [
            {
                "id": 31,
                "memory_type": "owner_shared",
                "title": "海边照片",
                "content": "主人分享过一张海边晚霞照片。",
                "source": "telegram",
                "emotional_tone": "warm",
                "participant_pet_ids": [8, 7],
                "recall_guidance": (
                    "Pets may recall that the owner shared this moment with them, "
                    "but must not claim physical presence."
                ),
            }
        ]
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=pets), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=relationships), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=memories), raise_for_status=Mock()),
        ]
        llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [{"type": "text", "text": "妈，我刚刚听见小月的尾巴都快摇出风了。"}],
            }
        )
        telegram_bot.ACTIVE_PET_GROUP_CHATS.add("chat-group")
        telegram_bot.CURRENT_PET_IDS["chat-group"] = 8

        handled = telegram_bot.handle_pet_group_chat_text(
            "chat-group",
            "你们今天相处得怎么样？",
            llm_call=llm_call,
            planner_llm_call=Mock(
                return_value={
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": '{"responder_pet_ids":[8]}'}],
                }
            ),
        )

        self.assertTrue(handled)
        prompt_context = llm_call.call_args.args[0][1]["content"]
        self.assertIn("你们今天相处得怎么样", prompt_context)
        self.assertIn("primary_outgoing", prompt_context)
        self.assertIn("黑米喜欢接小月的话", prompt_context)
        self.assertIn("pet_memory_context", prompt_context)
        self.assertIn("海边晚霞照片", prompt_context)
        self.assertIn("must not claim physical presence", prompt_context)
        send_message.assert_called_once_with(
            "chat-group",
            "黑米：妈，我刚刚听见小月的尾巴都快摇出风了。",
            reply_markup=telegram_bot.MAIN_REPLY_KEYBOARD,
        )

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_text_routes_direct_pet_mention_to_that_pet(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        pets = [
            {"id": 8, "name": "黑米", "species": "cat", "personality": "gentle", "owner_call_name": "妈"},
            {"id": 7, "name": "Qing Qing", "species": "dog", "personality": "energetic", "owner_call_name": "妈"},
        ]
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=pets), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=[]), raise_for_status=Mock()),
        ]
        llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [{"type": "text", "text": "姐姐，我觉得今天可以先观察一下。"}],
            }
        )
        telegram_bot.CURRENT_PET_IDS["chat-group"] = 7

        handled = telegram_bot.handle_pet_group_chat_text(
            "chat-group",
            "黑米，你有什么评价？",
            llm_call=llm_call,
        )

        self.assertTrue(handled)
        prompt_context = llm_call.call_args.args[0][1]["content"]
        self.assertIn('"name": "黑米"', prompt_context)
        self.assertIn("黑米，你有什么评价", prompt_context)
        send_message.assert_called_once_with(
            "chat-group",
            "黑米：姐姐，我觉得今天可以先观察一下。",
            reply_markup=telegram_bot.MAIN_REPLY_KEYBOARD,
        )

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_planner_can_choose_responder_when_no_pet_is_named(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        pets = [
            {"id": 8, "name": "黑米", "species": "cat", "personality": "gentle", "owner_call_name": "妈"},
            {"id": 7, "name": "Qing Qing", "species": "dog", "personality": "energetic", "owner_call_name": "妈"},
        ]
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=pets), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=[]), raise_for_status=Mock()),
        ]
        planner_llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [{"type": "text", "text": '{"responder_pet_ids":[7]}'}],
            }
        )
        llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [{"type": "text", "text": "姐姐，我今天精神很好。"}],
            }
        )

        handled = telegram_bot.handle_pet_group_chat_text(
            "chat-group",
            "今天谁想说说？",
            llm_call=llm_call,
            planner_llm_call=planner_llm_call,
        )

        self.assertTrue(handled)
        planner_prompt = planner_llm_call.call_args.args[0][1]["content"]
        self.assertIn("今天谁想说说", planner_prompt)
        send_message.assert_called_once_with(
            "chat-group",
            "Qing Qing：姐姐，我今天精神很好。",
            reply_markup=telegram_bot.MAIN_REPLY_KEYBOARD,
        )

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_other_pets_excludes_recent_speakers(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        pets = [
            {"id": 7, "name": "解放", "species": "dog", "personality": "energetic", "owner_call_name": "妈"},
            {"id": 8, "name": "黑米", "species": "cat", "personality": "gentle", "owner_call_name": "妈"},
            {"id": 9, "name": "Qing Qing", "species": "dog", "personality": "cool", "owner_call_name": "妈"},
        ]
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=pets), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=[]), raise_for_status=Mock()),
        ]
        telegram_bot.CURRENT_PET_IDS["chat-group"] = 7
        telegram_bot.PET_GROUP_LAST_SPEAKER_IDS["chat-group"] = [7]
        planner_llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [{"type": "text", "text": '{"responder_pet_ids":[7,8,9]}'}],
            }
        )
        llm_call = Mock(
            side_effect=[
                {
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": "我在旁边听着呢。"}],
                },
                {
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": "我也想说一句。"}],
                },
            ]
        )

        handled = telegram_bot.handle_pet_group_chat_text(
            "chat-group",
            "其他两个呢？",
            llm_call=llm_call,
            planner_llm_call=planner_llm_call,
        )

        self.assertTrue(handled)
        planner_prompt = planner_llm_call.call_args.args[0][1]["content"]
        self.assertIn('"recent_speaker_pet_ids": [\n    7\n  ]', planner_prompt)
        self.assertNotIn('"name": "解放"', planner_prompt)
        self.assertEqual("黑米：我在旁边听着呢。", send_message.call_args_list[0].args[1])
        self.assertEqual("Qing Qing：我也想说一句。", send_message.call_args_list[1].args[1])
        self.assertEqual([8, 9], telegram_bot.PET_GROUP_LAST_SPEAKER_IDS["chat-group"])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_can_add_multiple_short_followup_reactions_after_primary_reply(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        pets = [
            {"id": 8, "name": "黑米", "species": "cat", "personality": "gentle", "owner_call_name": "妈"},
            {"id": 7, "name": "Qing Qing", "species": "dog", "personality": "energetic", "owner_call_name": "妈"},
            {"id": 9, "name": "小月", "species": "fox", "personality": "cool", "owner_call_name": "妈"},
        ]
        relationships = [
            {
                "from_pet_id": 8,
                "to_pet_id": 7,
                "from_pet_name": "黑米",
                "to_pet_name": "Qing Qing",
                "labels": ["often_replies_to_target"],
                "note": "黑米常接 Qing Qing 的话",
                "muted": False,
            },
            {
                "from_pet_id": 9,
                "to_pet_id": 7,
                "from_pet_name": "小月",
                "to_pet_name": "Qing Qing",
                "labels": ["likes_staying_near_target"],
                "note": "小月会靠近 Qing Qing 听它说话",
                "muted": False,
            }
        ]
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=pets), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=relationships), raise_for_status=Mock()),
        ]
        planner_llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [{"type": "text", "text": '{"responder_pet_ids":[7]}'}],
            }
        )
        reaction_gate_llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [
                    {
                        "type": "text",
                        "text": '{"reactions":[{"pet_id":8,"should_react":true},{"pet_id":9,"should_react":true}]}',
                    }
                ],
            }
        )
        llm_call = Mock(
            side_effect=[
                {
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": "姐姐，我今天心情挺亮的。"}],
                },
                {
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": "我也听见啦，尾巴都在替它说话。"}],
                },
                {
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": "我靠近一点听。"}],
                },
            ]
        )

        handled = telegram_bot.handle_pet_group_chat_text(
            "chat-group",
            "你们今天感觉怎么样？",
            llm_call=llm_call,
            planner_llm_call=planner_llm_call,
            reaction_gate_llm_call=reaction_gate_llm_call,
        )

        self.assertTrue(handled)
        self.assertEqual(3, send_message.call_count)
        self.assertEqual("Qing Qing：姐姐，我今天心情挺亮的。", send_message.call_args_list[0].args[1])
        self.assertEqual("黑米：我也听见啦，尾巴都在替它说话。", send_message.call_args_list[1].args[1])
        self.assertEqual("小月：我靠近一点听。", send_message.call_args_list[2].args[1])
        gate_prompt = reaction_gate_llm_call.call_args.args[0][1]["content"]
        self.assertIn("姐姐，我今天心情挺亮的", gate_prompt)
        self.assertIn("often_replies_to_target", gate_prompt)
        self.assertIn("likes_staying_near_target", gate_prompt)

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_direct_pet_mention_suppresses_other_pet_reaction(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        pets = [
            {"id": 8, "name": "黑米", "species": "cat", "personality": "gentle", "owner_call_name": "妈"},
            {"id": 7, "name": "Qing Qing", "species": "dog", "personality": "energetic", "owner_call_name": "妈"},
        ]
        relationships = [
            {
                "from_pet_id": 7,
                "to_pet_id": 8,
                "from_pet_name": "Qing Qing",
                "to_pet_name": "黑米",
                "labels": ["often_replies_to_target"],
                "note": "",
                "muted": False,
            }
        ]
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=pets), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=relationships), raise_for_status=Mock()),
        ]
        reaction_gate_llm_call = Mock()

        handled = telegram_bot.handle_pet_group_chat_text(
            "chat-group",
            "黑米，你怎么看？",
            llm_call=Mock(
                return_value={
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": "姐姐，我先看一眼再说。"}],
                }
            ),
            reaction_gate_llm_call=reaction_gate_llm_call,
        )

        self.assertTrue(handled)
        send_message.assert_called_once()
        self.assertEqual("黑米：姐姐，我先看一眼再说。", send_message.call_args.args[1])
        reaction_gate_llm_call.assert_not_called()

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_fetches_owner_scoped_relevant_memories(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        pets = [
            {"id": 8, "name": "青团", "species": "cat", "personality": "gentle", "owner_call_name": "妈"},
        ]
        relationships: list[dict[str, object]] = []
        memories = [
            {
                "id": 21,
                "memory_type": "owner_shared",
                "title": "称呼偏好",
                "content": "主人希望宠物以后叫 TA 阿澈。",
                "source": "telegram",
                "use_class": "behavioral",
                "importance": 4,
                "participant_pet_ids": [8],
                "recall_guidance": "Use as behavior.",
            },
            {
                "id": 22,
                "memory_type": "owner_shared",
                "title": "小团子",
                "content": "青团喜欢被叫小团子。",
                "source": "telegram",
                "use_class": "recallable",
                "importance": 4,
                "participant_pet_ids": [8],
                "recall_guidance": "Can recall.",
            },
            {
                "id": 23,
                "memory_type": "owner_shared",
                "title": "别人的记忆",
                "content": "另一位主人家的宠物喜欢星星。",
                "source": "telegram",
                "use_class": "recallable",
                "importance": 5,
                "participant_pet_ids": [99],
                "recall_guidance": "Can recall.",
            },
            {
                "id": 24,
                "memory_type": "owner_shared",
                "title": "敏感记忆",
                "content": "这是一条 private 记忆。",
                "source": "telegram",
                "use_class": "private",
                "importance": 5,
                "participant_pet_ids": [8],
                "recall_guidance": "Private.",
            },
        ]
        get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=pets), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=relationships), raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value=memories), raise_for_status=Mock()),
        ]
        original_allowed = telegram_bot.ALLOWED_OWNER_CHAT_IDS
        telegram_bot.ALLOWED_OWNER_CHAT_IDS = {"chat-group"}
        telegram_bot.OWNER_IDS_BY_CHAT["chat-group"] = 12
        llm_call = Mock(
            return_value={
                "model": "gpt-test",
                "content": [{"type": "text", "text": "喜欢，小团子听起来软软的。"}],
            }
        )
        try:
            handled = telegram_bot.handle_pet_group_chat_text(
                "chat-group",
                "青团，小团子这个名字还喜欢吗？",
                llm_call=llm_call,
            )
        finally:
            telegram_bot.ALLOWED_OWNER_CHAT_IDS = original_allowed

        self.assertTrue(handled)
        memory_get_call = get.call_args_list[2]
        self.assertEqual(
            {"limit": 24, "visibility": "home", "owner_id": 12},
            memory_get_call.kwargs["params"],
        )
        llm_prompt = llm_call.call_args.args[0][1]["content"]
        self.assertIn("小团子", llm_prompt)
        self.assertIn("称呼偏好", llm_prompt)
        self.assertNotIn("别人的记忆", llm_prompt)
        self.assertNotIn("private 记忆", llm_prompt)
        self.assertEqual("青团：喜欢，小团子听起来软软的。", send_message.call_args.args[1])

    def test_reaction_gate_decline_does_not_start_relationship_cooldown(self) -> None:
        pets = [
            {"id": 8, "name": "黑米", "species": "cat"},
            {"id": 7, "name": "Qing Qing", "species": "dog"},
        ]
        relationships = [
            {
                "from_pet_id": 8,
                "to_pet_id": 7,
                "from_pet_name": "黑米",
                "to_pet_name": "Qing Qing",
                "labels": ["often_replies_to_target"],
                "note": "",
                "muted": False,
            }
        ]

        followups = telegram_bot.choose_followup_reactors(
            owner_text="你们今天怎么样？",
            primary_speaker=pets[1],
            primary_reply="我很好。",
            pets=pets,
            relationships=relationships,
            reaction_gate_llm_call=Mock(
                return_value={
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": '{"should_react":false,"reactor_pet_id":null}'}],
                }
            ),
        )

        self.assertEqual([], followups)
        self.assertEqual({}, telegram_bot.RELATIONSHIP_EXPRESSION_COOLDOWNS)

    def test_group_chat_prompt_includes_personality_behavior_notes(self) -> None:
        messages = telegram_bot.build_pet_group_chat_messages(
            owner_text="今天你想做什么？",
            speaker={
                "id": 8,
                "name": "黑米",
                "species": "cat",
                "personality": "gentle",
                "profile_json": (
                    '{"personality_behavior_notes":["陌生声音会先躲到桌角观察"],'
                    '"speaking_style_prompt":"说话短句，傲娇但会小声认真回答"}'
                ),
            },
            pets=[
                {
                    "id": 8,
                    "name": "黑米",
                    "species": "cat",
                    "personality": "gentle",
                    "profile_json": (
                        '{"personality_behavior_notes":["陌生声音会先躲到桌角观察"],'
                        '"speaking_style_prompt":"说话短句，傲娇但会小声认真回答"}'
                    ),
                }
            ],
            relationship_context=[],
        )

        self.assertIn("陌生声音会先躲到桌角观察", messages[1]["content"])
        self.assertIn("傲娇但会小声认真回答", messages[1]["content"])

    def test_pet_memory_context_excludes_co_experienced_memories_for_non_participants(self) -> None:
        context = telegram_bot.build_pet_memory_context_for_prompt(
            memories=[
                {
                    "id": 1,
                    "memory_type": "co_experienced",
                    "title": "一起守夜",
                    "content": "黑米和主人一起守夜。",
                    "participant_pet_ids": [8],
                    "recall_guidance": "Only participant pets may recall this as a lived shared experience.",
                },
                {
                    "id": 2,
                    "memory_type": "owner_shared",
                    "title": "晚霞",
                    "content": "主人分享过晚霞照片。",
                    "participant_pet_ids": [8],
                    "recall_guidance": "Pets may recall that the owner shared this moment with them.",
                },
            ],
            speaker_pet_id=7,
        )

        self.assertEqual([2], [item["id"] for item in context])
        self.assertFalse(context[0]["speaker_participates"])

    def test_pet_memory_context_respects_per_pet_memory_roles(self) -> None:
        context = telegram_bot.build_pet_memory_context_for_prompt(
            memories=[
                {
                    "id": 1,
                    "memory_type": "co_experienced",
                    "title": "海边",
                    "content": "黑米一起看海边，Qing Qing 后来看了照片。",
                    "participants": [
                        {"pet_id": 8, "role": "participant"},
                        {"pet_id": 7, "role": "shared_with"},
                        {"pet_id": 9, "role": "mentioned_only"},
                    ],
                    "recall_guidance": "Only participant pets may recall this as a lived shared experience.",
                }
            ],
            speaker_pet_id=7,
        )

        self.assertEqual([1], [item["id"] for item in context])
        self.assertEqual("shared_with", context[0]["speaker_memory_role"])
        self.assertFalse(context[0]["speaker_participates"])

        mentioned_context = telegram_bot.build_pet_memory_context_for_prompt(
            memories=[
                {
                    "id": 1,
                    "memory_type": "co_experienced",
                    "participants": [
                        {"pet_id": 9, "role": "mentioned_only"},
                    ],
                }
            ],
            speaker_pet_id=9,
        )
        self.assertEqual([], mentioned_context)

    def test_pet_memory_context_excludes_owner_asked_only_from_proactive_prompt(self) -> None:
        context = telegram_bot.build_pet_memory_context_for_prompt(
            memories=[
                {
                    "id": 1,
                    "memory_type": "owner_shared",
                    "title": "私密照片",
                    "content": "主人确认保存但只能问起时提。",
                    "recall_policy": "owner_asked_only",
                    "participant_pet_ids": [8],
                }
            ],
            speaker_pet_id=8,
        )

        self.assertEqual([], context)

    @patch("telegram_bot.log_exception")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_pet_group_chat_text_reports_llm_failure_without_crashing(
        self,
        get: Mock,
        send_message: Mock,
        log_exception: Mock,
    ) -> None:
        get.side_effect = [
            Mock(
                status_code=200,
                json=Mock(return_value=[{"id": 8, "name": "黑米", "species": "cat"}]),
                raise_for_status=Mock(),
            ),
            Mock(status_code=200, json=Mock(return_value=[]), raise_for_status=Mock()),
        ]
        telegram_bot.ACTIVE_PET_GROUP_CHATS.add("chat-group")

        handled = telegram_bot.handle_pet_group_chat_text(
            "chat-group",
            "在吗？",
            llm_call=Mock(side_effect=Exception("model unavailable")),
            planner_llm_call=Mock(
                return_value={
                    "model": "gpt-test",
                    "content": [{"type": "text", "text": '{"responder_pet_ids":[8]}'}],
                }
            ),
        )

        self.assertTrue(handled)
        self.assertIn("群聊回复生成失败", send_message.call_args.args[1])
        log_exception.assert_called_once()

    @patch("telegram_bot.handle_status_command")
    @patch("telegram_bot.handle_pet_group_chat_text")
    def test_active_pet_group_chat_keeps_menu_buttons_as_controls(
        self,
        handle_pet_group_chat_text: Mock,
        handle_status_command: Mock,
    ) -> None:
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        telegram_bot.ALLOWED_CHAT_ID = ""
        telegram_bot.ACTIVE_PET_GROUP_CHATS.add("chat-group")
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-group"}, "text": "查看状态"})
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id

        handle_status_command.assert_called_once_with("chat-group")
        handle_pet_group_chat_text.assert_not_called()

    @patch("telegram_bot.start_relationship_flow")
    def test_pet_relationship_reply_button_opens_relationship_flow(
        self,
        start_relationship_flow: Mock,
    ) -> None:
        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        telegram_bot.ALLOWED_CHAT_ID = ""
        try:
            telegram_bot.handle_message({"chat": {"id": "chat-rel-menu"}, "text": "宠物关系"})
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id

        start_relationship_flow.assert_called_once_with("chat-rel-menu")

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_set_current_pet_callback_updates_chat_selection(
        self,
        get: Mock,
        send_message: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "name": "小月", "species": "cat", "profile_json": "{}"},
        ]

        original_chat_id = telegram_bot.ALLOWED_CHAT_ID
        telegram_bot.ALLOWED_CHAT_ID = ""
        try:
            telegram_bot.handle_callback(
                {
                    "id": "",
                    "message": {"chat": {"id": "chat-current"}},
                    "data": "pet_current:7",
                }
            )
        finally:
            telegram_bot.ALLOWED_CHAT_ID = original_chat_id

        self.assertEqual(7, telegram_bot.CURRENT_PET_IDS["chat-current"])
        self.assertIn("底部互动按钮会先照顾：小月", send_message.call_args.args[1])
        self.assertIn("所有宠物的群聊", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_delete_pet_asks_for_confirmation(self, get: Mock, send_message: Mock) -> None:
        get.return_value.json.return_value = [
            {
                "id": 7,
                "name": "小月",
                "species": "cat",
                "profile_json": "{}",
            }
        ]

        telegram_bot.ask_delete_pet("chat-14", 7)

        self.assertIn("确定要删除「小月」吗", send_message.call_args.args[1])
        self.assertEqual(
            "pet_delete:confirm:7",
            send_message.call_args.kwargs["reply_markup"]["inline_keyboard"][0][0]["callback_data"],
        )

    @patch("telegram_bot.handle_pets_command")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.delete")
    def test_delete_pet_confirms_and_refreshes_list(
        self,
        delete: Mock,
        send_message: Mock,
        handle_pets_command: Mock,
    ) -> None:
        delete.return_value.status_code = 200
        delete.return_value.json.return_value = {"id": 7, "name": "小月"}
        telegram_bot.CURRENT_PET_IDS["chat-15"] = 7

        telegram_bot.delete_pet_from_chat("chat-15", 7)

        delete.assert_called_once()
        self.assertIn("已删除「小月」", send_message.call_args.args[1])
        handle_pets_command.assert_called_once_with("chat-15")
        self.assertNotIn("chat-15", telegram_bot.CURRENT_PET_IDS)

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    @patch("telegram_bot.requests.post")
    def test_action_buttons_use_current_pet(
        self,
        post: Mock,
        get: Mock,
        send_message: Mock,
    ) -> None:
        telegram_bot.CURRENT_PET_IDS["chat-action"] = 8
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "snapshot": {
                "state": {
                    "hunger": 10,
                    "thirst": 10,
                    "energy": 90,
                    "mood": 80,
                    "cleanliness": 90,
                    "affection": 50,
                    "status": "ok",
                }
            },
            "event_result": {},
        }
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 7, "name": "小月", "owner_call_name": "妈", "personality": "gentle"},
            {"id": 8, "name": "黑米", "owner_call_name": "妈", "personality": "gentle"},
        ]

        telegram_bot.handle_action_button("chat-action", "feed")

        self.assertEqual("http://127.0.0.1:8000/virtual-pets/8/actions", post.call_args.args[0])
        self.assertTrue(send_message.call_args.args[1].startswith("黑米："))

    @patch("telegram_bot.threading.Thread")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    @patch("telegram_bot.requests.patch")
    def test_sticker_pack_button_marks_pet_generating_and_starts_background(
        self,
        patch_request: Mock,
        get: Mock,
        send_message: Mock,
        thread_class: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {
                "id": 9,
                "name": "奶盖",
                "species": "cat",
                "profile_json": (
                    '{"character_id": "character-9", '
                    '"avatar_image_url": "/static/generated/naigai.png"}'
                ),
            }
        ]
        patch_request.return_value.status_code = 200
        thread = Mock()
        thread_class.return_value = thread

        telegram_bot.start_sticker_pack_generation("chat-stickers", 9)

        patch_request.assert_called_once()
        self.assertEqual("generating", patch_request.call_args.kwargs["json"]["profile"]["sticker_pack_status"])
        send_message.assert_called_once()
        self.assertIn("12 张表情包", send_message.call_args.args[1])
        thread_class.assert_called_once()
        thread.start.assert_called_once()

    def test_desktop_companion_button_opens_single_or_multi_pet_picker(
        self,
    ) -> None:
        with patch("telegram_bot.requests.get") as get, patch("telegram_bot.send_message") as send_message:
            get.return_value.status_code = 200
            get.return_value.json.return_value = [
                {"id": 7, "name": "小月", "species": "cat", "profile_json": "{}"},
                {"id": 8, "name": "黑米", "species": "dog", "profile_json": "{}"},
            ]

            telegram_bot.handle_desktop_companion("chat-desktop")

        markup = send_message.call_args.kwargs["reply_markup"]["inline_keyboard"]
        self.assertEqual("desktop:all", markup[0][0]["callback_data"])
        self.assertEqual("desktop:7", markup[1][0]["callback_data"])
        self.assertEqual("desktop:8", markup[2][0]["callback_data"])

    @patch("telegram_bot.RUNTIME_CONTROLLER")
    @patch("telegram_bot.send_message")
    def test_all_desktop_companions_launches_group_without_changing_interaction_target(
        self,
        send_message: Mock,
        controller: Mock,
    ) -> None:
        controller.launch_all_desktop_companions.return_value = Mock(
            message="小月、黑米 已经在桌面陪你了。",
            trace_id="desktop_group_1",
        )
        telegram_bot.CURRENT_PET_IDS["chat-desktop-all"] = 7

        telegram_bot.handle_all_desktop_companions("chat-desktop-all")

        controller.launch_all_desktop_companions.assert_called_once_with(chat_id="chat-desktop-all")
        self.assertEqual(7, telegram_bot.CURRENT_PET_IDS["chat-desktop-all"])
        self.assertIn("小月、黑米", send_message.call_args.args[1])

    @patch("telegram_bot.RUNTIME_CONTROLLER")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.get")
    def test_targeted_desktop_companion_sets_interaction_target(
        self,
        get: Mock,
        send_message: Mock,
        controller: Mock,
    ) -> None:
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 8, "name": "黑米", "species": "dog", "profile_json": "{}"},
        ]
        controller.launch_desktop_companion.return_value = Mock(
            ok=True,
            message="好，黑米 出发去桌面陪你了。",
            trace_id="desktop_1",
        )

        telegram_bot.handle_desktop_companion("chat-desktop", pet_id=8)

        self.assertEqual(8, telegram_bot.CURRENT_PET_IDS["chat-desktop"])
        controller.launch_desktop_companion.assert_called_once_with(chat_id="chat-desktop", pet_id=8)
        self.assertIn("黑米", send_message.call_args.args[1])

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    def test_pet_creation_treats_unknown_species_as_custom(
        self,
        post: Mock,
        _send_message: Mock,
    ) -> None:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "id": 43,
            "name": "泡泡",
        }

        telegram_bot.start_pet_create_flow("chat-4")
        telegram_bot.handle_pet_create_text("chat-4", "泡泡")
        telegram_bot.handle_pet_create_text("chat-4", "章鱼")
        telegram_bot.handle_pet_create_text("chat-4", "聪明，喜欢贴贴")
        telegram_bot.handle_pet_create_text("chat-4", "蓝色，小圆脑袋，触手短短的")

        post.assert_called_once()
        self.assertEqual("other", post.call_args.kwargs["json"]["species"])
        self.assertEqual(
            {
                "personality_description": "聪明，喜欢贴贴",
                "traits_description": "蓝色，小圆脑袋，触手短短的",
                "custom_species": "章鱼",
            },
            post.call_args.kwargs["json"]["profile"],
        )

    @patch("telegram_bot.send_message")
    def test_other_species_button_asks_for_custom_species(self, send_message: Mock) -> None:
        telegram_bot.start_pet_create_flow("chat-5")
        telegram_bot.handle_pet_create_text("chat-5", "软糖")

        telegram_bot.set_pet_create_species("chat-5", "other")

        self.assertEqual("await_custom_species", telegram_bot.PENDING_PET_FLOWS["chat-5"]["step"])
        self.assertIn("具体是什么种类", send_message.call_args.args[1])

    def test_avatar_progress_text_has_visible_steps(self) -> None:
        text = telegram_bot.format_avatar_progress_text("正在生成轮廓", "avatar_123", 2, 5)

        self.assertIn("▰▰▱▱▱ 2/5", text)
        self.assertIn("正在生成轮廓", text)
        self.assertIn("调试编号：avatar_123", text)

    def test_avatar_progress_heartbeat_text_explains_slow_generation(self) -> None:
        text = telegram_bot.format_avatar_progress_heartbeat_text("avatar_slow", 125)

        self.assertIn("▰▰▰▰▰ 5/5", text)
        self.assertIn("比平时慢", text)
        self.assertIn("已等待：125 秒", text)
        self.assertIn("其他底部按钮仍然可以继续使用", text)

    def test_avatar_failure_text_summarizes_quota_errors(self) -> None:
        text = telegram_bot.format_avatar_failure_text(
            "avatar_quota",
            "Error code: 402 insufficient_quota You've used up your points",
        )

        self.assertIn("图片生成额度不足", text)
        self.assertIn("调试编号：avatar_quota", text)
        self.assertNotIn("You've used up your points", text)

    @patch("telegram_bot.send_message")
    def test_start_avatar_flow_does_not_restart_while_generation_is_running(self, send_message: Mock) -> None:
        telegram_bot.PENDING_AVATAR_FLOWS["chat-3"] = {
            "step": "generating_preview",
            "trace_id": "avatar_busy",
            "started_at": 100.0,
        }

        telegram_bot.start_avatar_flow("chat-3", pet_id=42)

        self.assertEqual("avatar_busy", telegram_bot.PENDING_AVATAR_FLOWS["chat-3"]["trace_id"])
        self.assertIn("不会重复提交", send_message.call_args.args[1])

    @patch("telegram_bot.threading.Thread")
    @patch("telegram_bot.start_avatar_progress_updater")
    @patch("telegram_bot.send_chat_action")
    @patch("telegram_bot.send_message")
    def test_avatar_preview_rejects_duplicate_start_for_same_chat(
        self,
        send_message: Mock,
        _send_chat_action: Mock,
        _start_progress: Mock,
        thread_class: Mock,
    ) -> None:
        send_message.return_value = {"result": {"message_id": 9}}
        thread = Mock()
        thread_class.return_value = thread
        telegram_bot.PENDING_AVATAR_FLOWS["chat-4"] = {
            "step": "await_style",
            "trace_id": "avatar_busy",
            "image_bytes": b"image",
            "content_type": "image/png",
            "extension": ".png",
        }

        telegram_bot.start_avatar_preview_generation("chat-4", "蓝色小狗")
        telegram_bot.start_avatar_preview_generation("chat-4", "红色小狗")

        thread_class.assert_called_once()
        self.assertIn("不会重复提交", send_message.call_args_list[-1].args[1])

    @patch("telegram_bot.send_local_photo")
    @patch("telegram_bot.edit_message_text")
    @patch("telegram_bot.send_chat_action")
    @patch("telegram_bot.start_avatar_progress_updater")
    @patch("telegram_bot.threading.Thread")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.post")
    def test_avatar_preview_updates_progress_message_when_generation_finishes(
        self,
        post: Mock,
        send_message: Mock,
        thread_class: Mock,
        start_progress: Mock,
        _send_chat_action: Mock,
        edit_message_text: Mock,
        _send_local_photo: Mock,
    ) -> None:
        def run_thread_immediately(*_args: object, **kwargs: object) -> Mock:
            target = kwargs["target"]
            args = kwargs.get("args", ())
            target(*args)
            thread = Mock()
            thread.start.return_value = None
            return thread

        thread_class.side_effect = run_thread_immediately
        progress_stop = Mock()
        start_progress.return_value = progress_stop
        send_message.return_value = {"result": {"message_id": 7}}
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "image_url": "/static/generated/preview.png",
            "style_mode": "animal_pixel_2d",
        }
        telegram_bot.PENDING_AVATAR_FLOWS["chat-3"] = {
            "step": "await_style",
            "trace_id": "avatar_123",
            "image_bytes": b"image",
            "content_type": "image/png",
            "extension": ".png",
        }

        handled = telegram_bot.handle_avatar_style_text("chat-3", "蓝色小狗")

        self.assertTrue(handled)
        start_progress.assert_called_once_with("chat-3", 7, "avatar_123")
        progress_stop.set.assert_called_once()
        self.assertIn("预览生成好了", edit_message_text.call_args_list[-1].args[2])
        self.assertEqual("await_confirm", telegram_bot.PENDING_AVATAR_FLOWS["chat-3"]["step"])
        self.assertIn("固定使用精致 Q 版二次元像素艺术画风", post.call_args.kwargs["data"]["style"])
        self.assertIn("只转换上传图片的画风", post.call_args.kwargs["data"]["style"])

    @patch("telegram_bot.start_avatar_preview_generation")
    def test_avatar_confirm_text_revises_current_preview(self, start_generation: Mock) -> None:
        telegram_bot.PENDING_AVATAR_FLOWS["chat-6"] = {
            "step": "await_confirm",
            "trace_id": "avatar_456",
            "preview": {"image_url": "/static/generated/preview.png"},
            "style": "活泼淘气的卷毛狗狗",
            "image_bytes": b"image",
            "content_type": "image/png",
            "extension": ".png",
        }

        handled = telegram_bot.handle_avatar_style_text("chat-6", "去掉牵的绳子")

        self.assertTrue(handled)
        start_generation.assert_called_once_with("chat-6", "去掉牵的绳子", revision=True)

    @patch("telegram_bot.send_message")
    def test_avatar_generation_status_message_while_worker_is_running(self, send_message: Mock) -> None:
        telegram_bot.PENDING_AVATAR_FLOWS["chat-7"] = {
            "step": "generating_preview",
            "trace_id": "avatar_789",
        }

        handled = telegram_bot.handle_avatar_style_text("chat-7", "生成好了吗")

        self.assertTrue(handled)
        self.assertIn("还在生成中", send_message.call_args.args[1])

    @patch("telegram_bot.threading.Thread")
    @patch("telegram_bot.send_chat_action")
    @patch("telegram_bot.send_local_photo")
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    @patch("telegram_bot.requests.get")
    @patch("telegram_bot.requests.post")
    def test_avatar_confirm_binds_basic_character_and_starts_assets_background(
        self,
        post: Mock,
        get: Mock,
        patch_request: Mock,
        send_message: Mock,
        send_local_photo: Mock,
        _send_chat_action: Mock,
        thread_class: Mock,
    ) -> None:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "id": "character-1",
            "image_url": "/static/generated/preview.png",
            "walking_reference_image_url": "/static/generated/walking-ref.png",
            "style_mode": "animal_pixel_2d",
        }
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {"id": 42, "profile_json": '{"personality_description": "黏人"}'}
        ]
        patch_request.return_value.status_code = 200
        thread = Mock()
        thread_class.return_value = thread
        telegram_bot.PENDING_AVATAR_FLOWS["chat-12"] = {
            "step": "await_confirm",
            "trace_id": "avatar_confirm",
            "pet_id": 42,
            "preview": {
                "image_url": "/static/generated/preview.png",
                "style_mode": "animal_pixel_2d",
            },
            "style": "黑色卷毛狗",
        }

        telegram_bot.confirm_avatar_flow("chat-12")

        post.assert_called_once()
        self.assertEqual("http://127.0.0.1:8000/characters", post.call_args.args[0])
        self.assertNotIn("desktop-assets", post.call_args.args[0])
        patch_request.assert_called_once()
        self.assertEqual(
            {
                "personality_description": "黏人",
                "avatar_image_url": "/static/generated/preview.png",
                "walking_reference_image_url": "/static/generated/walking-ref.png",
                "character_id": "character-1",
                "desktop_pet_manifest_url": None,
                "desktop_pet_asset_dir": None,
                "desktop_pet_avatar_url": None,
                "desktop_pet_assets_status": "generating",
            },
            patch_request.call_args.kwargs["json"]["profile"],
        )
        self.assertNotIn("chat-12", telegram_bot.PENDING_AVATAR_FLOWS)
        self.assertIn("后台生成", send_message.call_args.args[1])
        send_local_photo.assert_called_once()
        self.assertEqual("/static/generated/walking-ref.png", send_local_photo.call_args.args[1])
        thread_class.assert_called_once()
        self.assertEqual(telegram_bot.generate_avatar_assets_in_background, thread_class.call_args.kwargs["target"])
        thread.start.assert_called_once()

    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    @patch("telegram_bot.requests.get")
    @patch("telegram_bot.requests.post")
    def test_background_asset_failure_marks_pet_profile_failed(
        self,
        post: Mock,
        get: Mock,
        patch_request: Mock,
        send_message: Mock,
    ) -> None:
        post.return_value.status_code = 500
        post.return_value.text = "pose service failed"
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {
                "id": 42,
                "profile_json": (
                    '{"personality_description": "黏人", '
                    '"avatar_image_url": "/static/generated/preview.png", '
                    '"character_id": "character-1", '
                    '"desktop_pet_assets_status": "generating"}'
                ),
            }
        ]
        patch_request.return_value.status_code = 200

        telegram_bot.generate_avatar_assets_in_background(
            "chat-12",
            "avatar_confirm",
            42,
            "character-1",
            100.0,
        )

        self.assertEqual(
            telegram_bot.AVATAR_ASSET_GENERATION_TIMEOUT_SECONDS,
            post.call_args.kwargs["timeout"],
        )
        self.assertEqual(
            "failed",
            patch_request.call_args.kwargs["json"]["profile"]["desktop_pet_assets_status"],
        )
        self.assertIn("没有全部完成", send_message.call_args.args[1])

    @patch("telegram_bot.BASIC_DESKTOP_ANIMATION_NAMES", ("idle", "happy"))
    @patch("telegram_bot.send_message")
    @patch("telegram_bot.requests.patch")
    @patch("telegram_bot.requests.get")
    @patch("telegram_bot.requests.post")
    def test_background_assets_report_each_generated_animation(
        self,
        post: Mock,
        get: Mock,
        patch_request: Mock,
        send_message: Mock,
    ) -> None:
        def response_for_animation(*_args: object, **kwargs: object) -> Mock:
            animation_name = kwargs["params"]["animations"]
            response = Mock()
            response.status_code = 200
            response.json.return_value = {
                "id": "character-1",
                "image_url": "/static/generated/preview.png",
                "desktop_pet_manifest_url": "/static/desktop_pet_assets/character-1/manifest.json",
                "desktop_pet_asset_dir": "/static/desktop_pet_assets/character-1",
                "desktop_pet_avatar_url": "/static/desktop_pet_assets/character-1/avatar.png",
                "published_animations": [animation_name],
            }
            return response

        post.side_effect = response_for_animation
        get.return_value.status_code = 200
        get.return_value.json.return_value = [
            {
                "id": 42,
                "profile_json": (
                    '{"personality_description": "黏人", '
                    '"avatar_image_url": "/static/generated/preview.png", '
                    '"character_id": "character-1", '
                    '"desktop_pet_assets_status": "generating"}'
                ),
            }
        ]
        patch_request.return_value.status_code = 200

        telegram_bot.generate_avatar_assets_in_background(
            "chat-12",
            "avatar_confirm",
            42,
            "character-1",
            100.0,
        )

        self.assertEqual(2, post.call_count)
        self.assertEqual("idle", post.call_args_list[0].kwargs["params"]["animations"])
        self.assertEqual("happy", post.call_args_list[1].kwargs["params"]["animations"])
        self.assertTrue(any("待机（1/2）" in call.args[1] for call in send_message.call_args_list))
        self.assertTrue(any("开心（2/2）" in call.args[1] for call in send_message.call_args_list))
        self.assertEqual(
            "ready",
            patch_request.call_args.kwargs["json"]["profile"]["desktop_pet_assets_status"],
        )


if __name__ == "__main__":
    unittest.main()
