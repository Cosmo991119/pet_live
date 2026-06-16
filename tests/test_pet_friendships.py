import tempfile
import unittest
from pathlib import Path

from pet_db import (
    accept_pet_friendship_invite,
    create_owner_for_telegram_chat,
    create_pet,
    create_pet_friendship_invite,
    init_db,
    list_pet_friendships,
)


class PetFriendshipTest(unittest.TestCase):
    def test_owner_invite_can_be_accepted_by_another_owner_pet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            first_owner = create_owner_for_telegram_chat("chat-a", "小明", db_path=db_path)
            second_owner = create_owner_for_telegram_chat("chat-b", "小红", db_path=db_path)
            heimi = create_pet(
                name="黑米",
                owner_id=first_owner["id"],
                species="dog",
                personality="gentle",
                owner_call_name="妈",
                db_path=db_path,
            )
            qingqing = create_pet(
                name="青青",
                owner_id=second_owner["id"],
                species="cat",
                personality="cool",
                owner_call_name="妈",
                db_path=db_path,
            )

            invite = create_pet_friendship_invite(
                inviter_owner_id=first_owner["id"],
                inviter_pet_id=heimi["id"],
                token="friend-token",
                db_path=db_path,
            )
            friendship = accept_pet_friendship_invite(
                token="friend-token",
                receiver_owner_id=second_owner["id"],
                receiver_pet_id=qingqing["id"],
                db_path=db_path,
            )

            self.assertEqual("friend-token", invite["token"])
            self.assertEqual("accepted", friendship["invite_status"])
            self.assertEqual(50, friendship["affinity"])
            self.assertEqual(heimi["id"], friendship["pet_a_id"])
            self.assertEqual(qingqing["id"], friendship["pet_b_id"])
            self.assertEqual("chat-a", friendship["owner_a_chat_id"])
            self.assertEqual("chat-b", friendship["owner_b_chat_id"])
            self.assertEqual(
                [friendship["id"]],
                [item["id"] for item in list_pet_friendships(owner_id=first_owner["id"], db_path=db_path)],
            )

    def test_friendship_invite_rejects_wrong_owner_and_same_owner_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            first_owner = create_owner_for_telegram_chat("chat-a", db_path=db_path)
            second_owner = create_owner_for_telegram_chat("chat-b", db_path=db_path)
            heimi = create_pet(
                name="黑米",
                owner_id=first_owner["id"],
                species="dog",
                personality="gentle",
                owner_call_name="妈",
                db_path=db_path,
            )
            same_home_pet = create_pet(
                name="团子",
                owner_id=first_owner["id"],
                species="cat",
                personality="gentle",
                owner_call_name="妈",
                db_path=db_path,
            )

            with self.assertRaises(ValueError):
                create_pet_friendship_invite(
                    inviter_owner_id=second_owner["id"],
                    inviter_pet_id=heimi["id"],
                    token="wrong-owner",
                    db_path=db_path,
                )

            create_pet_friendship_invite(
                inviter_owner_id=first_owner["id"],
                inviter_pet_id=heimi["id"],
                token="same-owner",
                db_path=db_path,
            )
            with self.assertRaises(ValueError):
                accept_pet_friendship_invite(
                    token="same-owner",
                    receiver_owner_id=first_owner["id"],
                    receiver_pet_id=same_home_pet["id"],
                    db_path=db_path,
                )


if __name__ == "__main__":
    unittest.main()
