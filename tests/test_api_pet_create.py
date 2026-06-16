import unittest
from unittest.mock import patch

from api import (
    CharacterStickerPackRequest,
    VirtualPetTickRequest,
    PetFriendshipInviteAcceptRequest,
    PetFriendshipInviteCreateRequest,
    PetCreateRequest,
    PetMemoryRequest,
    OwnerTelegramRequest,
    PetRelationshipMuteRequest,
    PetRelationshipRequest,
    create_character_sticker_pack,
    create_character_desktop_assets,
    accept_pet_friendship_invite_endpoint,
    create_pet_friendship_invite_endpoint,
    create_pet_endpoint,
    create_pet_memory_endpoint,
    create_telegram_owner_endpoint,
    delete_pet_memory_endpoint,
    delete_pet_endpoint,
    delete_pet_relationship_endpoint,
    list_pet_memories_endpoint,
    list_pet_friendships_endpoint,
    list_pet_relationships_endpoint,
    mute_pet_relationship_endpoint,
    tick_virtual_pet_endpoint,
    upsert_pet_relationship_endpoint,
)


class ApiPetCreateTest(unittest.TestCase):
    @patch("api.create_pet")
    def test_create_pet_passes_profile_through(self, create_pet) -> None:
        create_pet.return_value = {"id": 7, "name": "小月"}
        payload = PetCreateRequest(
            name="小月",
            owner_id=3,
            species="cat",
            personality="gentle",
            owner_call_name="妈",
            pet_mode="virtual",
            profile={
                "personality_description": "亲人但慢热",
                "traits_description": "银灰色，尾巴蓬松",
            },
        )

        result = create_pet_endpoint(payload)

        self.assertEqual({"id": 7, "name": "小月"}, result)
        self.assertEqual(3, create_pet.call_args.kwargs["owner_id"])
        self.assertEqual(payload.profile, create_pet.call_args.kwargs["profile"])

    @patch("api.create_owner_for_telegram_chat")
    def test_create_telegram_owner_endpoint_passes_chat_identity(self, create_owner) -> None:
        create_owner.return_value = {"id": 4, "telegram_chat_id": "chat-1"}
        payload = OwnerTelegramRequest(
            telegram_chat_id="chat-1",
            display_name="小明",
        )

        result = create_telegram_owner_endpoint(payload)

        self.assertEqual({"id": 4, "telegram_chat_id": "chat-1"}, result)
        create_owner.assert_called_once_with(
            telegram_chat_id="chat-1",
            display_name="小明",
        )

    @patch("api.notifier_from_env")
    @patch("api.tick_virtual_pet")
    def test_virtual_pet_tick_endpoint_can_suppress_backend_notifier(
        self,
        tick_virtual_pet,
        notifier_from_env,
    ) -> None:
        tick_virtual_pet.return_value = {"pet_id": 7, "event_result": None}

        result = tick_virtual_pet_endpoint(
            7,
            VirtualPetTickRequest(minutes=10),
            notify=False,
        )

        self.assertEqual({"pet_id": 7, "event_result": None}, result)
        notifier_from_env.assert_not_called()
        self.assertIsNone(tick_virtual_pet.call_args.kwargs["notifier"])

    @patch("api.build_character_desktop_assets")
    def test_character_desktop_assets_passes_requested_animations(self, build_assets) -> None:
        build_assets.return_value = {"id": "character-1"}

        result = create_character_desktop_assets("character-1", animations="idle, walk_right")

        self.assertEqual({"id": "character-1"}, result)
        build_assets.assert_called_once_with(
            "character-1",
            animation_names=["idle", "walk_right"],
            provider=None,
        )

    @patch("api.build_character_desktop_assets")
    def test_character_desktop_assets_can_request_provider(self, build_assets) -> None:
        build_assets.return_value = {"id": "character-1"}

        result = create_character_desktop_assets("character-1", animations="idle", provider="wan")

        self.assertEqual({"id": "character-1"}, result)
        build_assets.assert_called_once_with(
            "character-1",
            animation_names=["idle"],
            provider="wan",
        )

    @patch("api.delete_pet")
    def test_delete_pet_endpoint_returns_deleted_pet(self, delete_pet) -> None:
        delete_pet.return_value = {"id": 7, "name": "小月"}

        result = delete_pet_endpoint(7)

        self.assertEqual({"id": 7, "name": "小月"}, result)
        delete_pet.assert_called_once_with(7)

    @patch("api.upsert_pet_relationship")
    def test_upsert_relationship_endpoint_passes_payload(self, upsert) -> None:
        upsert.return_value = {"from_pet_id": 1, "to_pet_id": 2}
        payload = PetRelationshipRequest(
            labels=["likes_staying_near_target"],
            note="黑米喜欢贴着 Qing Qing。",
            muted=True,
        )

        result = upsert_pet_relationship_endpoint(1, 2, payload)

        self.assertEqual({"from_pet_id": 1, "to_pet_id": 2}, result)
        upsert.assert_called_once_with(
            from_pet_id=1,
            to_pet_id=2,
            labels=["likes_staying_near_target"],
            note="黑米喜欢贴着 Qing Qing。",
            muted=True,
        )

    @patch("api.list_pet_relationships")
    def test_list_relationships_endpoint_passes_filters(self, list_relationships) -> None:
        list_relationships.return_value = [{"from_pet_id": 1, "to_pet_id": 2}]

        result = list_pet_relationships_endpoint(
            pet_id=1,
            from_pet_id=1,
            to_pet_id=2,
        )

        self.assertEqual([{"from_pet_id": 1, "to_pet_id": 2}], result)
        list_relationships.assert_called_once_with(
            pet_id=1,
            from_pet_id=1,
            to_pet_id=2,
        )

    @patch("api.create_pet_friendship_invite")
    def test_create_friendship_invite_endpoint_passes_payload(self, create_invite) -> None:
        create_invite.return_value = {"token": "friend-token"}
        payload = PetFriendshipInviteCreateRequest(
            inviter_owner_id=3,
            inviter_pet_id=7,
        )

        result = create_pet_friendship_invite_endpoint(payload)

        self.assertEqual({"token": "friend-token"}, result)
        create_invite.assert_called_once_with(inviter_owner_id=3, inviter_pet_id=7)

    @patch("api.accept_pet_friendship_invite")
    def test_accept_friendship_invite_endpoint_passes_payload(self, accept_invite) -> None:
        accept_invite.return_value = {"id": 9, "status": "active"}
        payload = PetFriendshipInviteAcceptRequest(
            receiver_owner_id=4,
            receiver_pet_id=8,
        )

        result = accept_pet_friendship_invite_endpoint("friend-token", payload)

        self.assertEqual({"id": 9, "status": "active"}, result)
        accept_invite.assert_called_once_with(
            token="friend-token",
            receiver_owner_id=4,
            receiver_pet_id=8,
        )

    @patch("api.list_pet_friendships")
    def test_list_friendships_endpoint_passes_filters(self, list_friendships) -> None:
        list_friendships.return_value = [{"id": 9}]

        result = list_pet_friendships_endpoint(owner_id=3, pet_id=7)

        self.assertEqual([{"id": 9}], result)
        list_friendships.assert_called_once_with(owner_id=3, pet_id=7)

    @patch("api.set_pet_relationship_muted")
    def test_mute_relationship_endpoint_passes_payload(self, set_muted) -> None:
        set_muted.return_value = {"from_pet_id": 1, "to_pet_id": 2, "muted": True}
        payload = PetRelationshipMuteRequest(muted=True)

        result = mute_pet_relationship_endpoint(1, 2, payload)

        self.assertEqual({"from_pet_id": 1, "to_pet_id": 2, "muted": True}, result)
        set_muted.assert_called_once_with(1, 2, True)

    @patch("api.delete_pet_relationship")
    def test_delete_relationship_endpoint_returns_deleted_edge(self, delete_relationship) -> None:
        delete_relationship.return_value = {"from_pet_id": 1, "to_pet_id": 2}

        result = delete_pet_relationship_endpoint(1, 2)

        self.assertEqual({"from_pet_id": 1, "to_pet_id": 2}, result)
        delete_relationship.assert_called_once_with(1, 2)

    @patch("api.create_pet_memory")
    def test_create_pet_memory_endpoint_passes_payload(self, create_memory) -> None:
        create_memory.return_value = {
            "id": 9,
            "memory_type": "owner_shared",
            "participant_pet_ids": [1, 2],
        }
        payload = PetMemoryRequest(
            memory_type="owner_shared",
            title="海边照片",
            content="主人分享了一张晚霞照片。",
            source="telegram",
            emotional_tone="warm",
            importance=4,
            visibility="home",
            use_class="recallable",
            recall_policy="owner_asked_only",
            participant_pet_ids=[1, 2],
            participants=[{"pet_id": 1, "role": "shared_with"}],
            metadata={"telegram_message_id": 123},
        )

        result = create_pet_memory_endpoint(payload)

        self.assertEqual(
            {"id": 9, "memory_type": "owner_shared", "participant_pet_ids": [1, 2]},
            result,
        )
        create_memory.assert_called_once_with(
            memory_type="owner_shared",
            title="海边照片",
            content="主人分享了一张晚霞照片。",
            source="telegram",
            emotional_tone="warm",
            importance=4,
            visibility="home",
            use_class="recallable",
            recall_policy="owner_asked_only",
            participant_pet_ids=[1, 2],
            participants=[{"pet_id": 1, "role": "shared_with"}],
            metadata={"telegram_message_id": 123},
        )

    @patch("api.delete_pet_memory")
    def test_delete_pet_memory_endpoint_returns_deleted_memory(self, delete_memory) -> None:
        delete_memory.return_value = {"id": 9, "title": "称呼偏好"}

        result = delete_pet_memory_endpoint(9, owner_id=3)

        self.assertEqual({"id": 9, "title": "称呼偏好"}, result)
        delete_memory.assert_called_once_with(9, owner_id=3)

    @patch("api.list_pet_memories")
    def test_list_pet_memories_endpoint_passes_filters(self, list_memories) -> None:
        list_memories.return_value = [{"id": 9, "memory_type": "co_experienced"}]

        result = list_pet_memories_endpoint(
            pet_id=1,
            memory_type="co_experienced",
            visibility="home",
            owner_id=3,
            limit=8,
        )

        self.assertEqual([{"id": 9, "memory_type": "co_experienced"}], result)
        list_memories.assert_called_once_with(
            pet_id=1,
            memory_type="co_experienced",
            visibility="home",
            owner_id=3,
            limit=8,
        )

    @patch("api.generate_character_sticker_pack")
    def test_character_sticker_pack_endpoint_generates_requested_pack(self, generate_pack) -> None:
        generate_pack.return_value = {
            "character_id": "character-1",
            "stickers": [{"image_url": "/static/generated/one.png", "prompt": "开心"}],
        }
        payload = CharacterStickerPackRequest(theme="日常陪伴")

        result = create_character_sticker_pack("character-1", payload)

        self.assertEqual("character-1", result["character_id"])
        generate_pack.assert_called_once_with("character-1", theme="日常陪伴")


if __name__ == "__main__":
    unittest.main()
