import sqlite3
import tempfile
import unittest
from pathlib import Path

from pet_db import (
    create_owner_for_telegram_chat,
    create_pet,
    delete_pet,
    delete_pet_relationship,
    get_pet,
    get_pet_relationship,
    init_db,
    list_pet_relationships,
    list_pets,
    save_virtual_pet_state,
    set_pet_relationship_muted,
    upsert_pet_relationship,
)


class PetDbDeleteTest(unittest.TestCase):
    def test_pets_are_scoped_by_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            first_owner = create_owner_for_telegram_chat(
                "chat-a",
                display_name="Owner A",
                db_path=db_path,
            )
            second_owner = create_owner_for_telegram_chat(
                "chat-b",
                display_name="Owner B",
                db_path=db_path,
            )
            first_pet = create_pet(
                name="黑米",
                species="dog",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                owner_id=first_owner["id"],
                db_path=db_path,
            )
            create_pet(
                name="青青",
                species="cat",
                personality="cool",
                owner_call_name="妈",
                pet_mode="virtual",
                owner_id=second_owner["id"],
                db_path=db_path,
            )

            self.assertEqual(
                ["黑米"],
                [pet["name"] for pet in list_pets(owner_id=first_owner["id"], db_path=db_path)],
            )
            self.assertEqual(
                ["青青"],
                [pet["name"] for pet in list_pets(owner_id=second_owner["id"], db_path=db_path)],
            )
            self.assertIsNone(
                get_pet(first_pet["id"], owner_id=second_owner["id"], db_path=db_path)
            )

    def test_delete_pet_removes_pet_and_virtual_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            pet = create_pet(
                name="小月",
                species="cat",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            save_virtual_pet_state(
                pet_id=pet["id"],
                state={"mood": "happy"},
                current_time="2026-05-19T17:40:00",
                db_path=db_path,
            )

            deleted = delete_pet(pet["id"], db_path=db_path)

            self.assertEqual("小月", deleted["name"])
            self.assertIsNone(get_pet(pet["id"], db_path=db_path))

    def test_directed_pet_relationship_crud_and_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            heimi = create_pet(
                name="黑米",
                species="dog",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            qingqing = create_pet(
                name="Qing Qing",
                species="cat",
                personality="cool",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )

            relationship = upsert_pet_relationship(
                from_pet_id=heimi["id"],
                to_pet_id=qingqing["id"],
                labels=["likes_staying_near_target", "often_replies_to_target"],
                note="黑米喜欢贴着 Qing Qing。",
                db_path=db_path,
            )

            self.assertEqual(heimi["id"], relationship["from_pet_id"])
            self.assertEqual(qingqing["id"], relationship["to_pet_id"])
            self.assertEqual(
                ["likes_staying_near_target", "often_replies_to_target"],
                relationship["labels"],
            )
            self.assertFalse(relationship["muted"])

            reverse = upsert_pet_relationship(
                from_pet_id=qingqing["id"],
                to_pet_id=heimi["id"],
                labels=["quiet_around_target"],
                note="Qing Qing 在黑米旁边比较安静。",
                muted=True,
                db_path=db_path,
            )
            self.assertEqual(qingqing["id"], reverse["from_pet_id"])
            self.assertTrue(reverse["muted"])

            updated = upsert_pet_relationship(
                from_pet_id=heimi["id"],
                to_pet_id=qingqing["id"],
                labels=["pulls_target_to_play"],
                note="黑米常拉 Qing Qing 玩。",
                db_path=db_path,
            )
            self.assertEqual(["pulls_target_to_play"], updated["labels"])
            self.assertEqual(
                2,
                len(list_pet_relationships(db_path=db_path)),
            )

            muted = set_pet_relationship_muted(
                heimi["id"], qingqing["id"], True, db_path=db_path
            )
            self.assertTrue(muted["muted"])

            with self.assertRaises(ValueError):
                upsert_pet_relationship(
                    from_pet_id=heimi["id"],
                    to_pet_id=heimi["id"],
                    labels=["quiet_around_target"],
                    db_path=db_path,
                )

            with self.assertRaises(ValueError):
                upsert_pet_relationship(
                    from_pet_id=heimi["id"],
                    to_pet_id=qingqing["id"],
                    labels=["depends_on_target"],
                    db_path=db_path,
                )

            deleted = delete_pet_relationship(
                heimi["id"], qingqing["id"], db_path=db_path
            )
            self.assertEqual("黑米", deleted["from_pet_name"])
            self.assertIsNone(
                get_pet_relationship(heimi["id"], qingqing["id"], db_path=db_path)
            )

    def test_delete_pet_removes_relationship_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            first = create_pet(
                name="小月",
                species="cat",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            second = create_pet(
                name="黑米",
                species="dog",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            upsert_pet_relationship(
                first["id"],
                second["id"],
                labels=["likes_staying_near_target"],
                db_path=db_path,
            )
            upsert_pet_relationship(
                second["id"],
                first["id"],
                labels=["often_replies_to_target"],
                db_path=db_path,
            )

            delete_pet(first["id"], db_path=db_path)

            self.assertEqual([], list_pet_relationships(db_path=db_path))

    def test_database_rejects_duplicate_directed_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            first = create_pet(
                name="小月",
                species="cat",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            second = create_pet(
                name="黑米",
                species="dog",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )
            upsert_pet_relationship(
                first["id"],
                second["id"],
                labels=["quiet_around_target"],
                db_path=db_path,
            )

            with sqlite3.connect(db_path) as conn:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO pet_relationships (
                            from_pet_id,
                            to_pet_id,
                            labels_json,
                            note,
                            muted
                        )
                        VALUES (?, ?, ?, ?, 0)
                        """,
                        (
                            first["id"],
                            second["id"],
                            '["quiet_around_target"]',
                            "",
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
