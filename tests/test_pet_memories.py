import tempfile
import unittest
from pathlib import Path

from pet_db import (
    create_pet,
    create_pet_memory,
    delete_pet,
    get_pet_memory,
    init_db,
    list_pet_memories,
)


class PetMemoriesTest(unittest.TestCase):
    def test_create_owner_shared_memory_records_truthful_recall_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            qingqing = create_pet(
                name="Qing Qing",
                species="cat",
                personality="gentle",
                owner_call_name="妈",
                pet_mode="virtual",
                db_path=db_path,
            )

            memory = create_pet_memory(
                memory_type="owner_shared",
                title="海边照片",
                content="主人分享了一张今天在海边看到晚霞的照片。",
                source="telegram",
                participant_pet_ids=[qingqing["id"]],
                emotional_tone="warm",
                db_path=db_path,
            )

            self.assertEqual("owner_shared", memory["memory_type"])
            self.assertEqual([qingqing["id"]], memory["participant_pet_ids"])
            self.assertEqual("shared_with", memory["participants"][0]["role"])
            self.assertIn("must not claim physical presence", memory["recall_guidance"])

            listed = list_pet_memories(pet_id=qingqing["id"], db_path=db_path)
            self.assertEqual([memory["id"]], [item["id"] for item in listed])

            self.assertEqual(
                [memory["id"]],
                [
                    item["id"]
                    for item in list_pet_memories(
                        pet_id=qingqing["id"],
                        visibility="home",
                        db_path=db_path,
                    )
                ],
            )
            self.assertEqual(
                [],
                list_pet_memories(
                    pet_id=qingqing["id"],
                    visibility="private",
                    db_path=db_path,
                ),
            )

    def test_create_co_experienced_memory_marks_specific_participants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            heimi = create_pet(
                name="黑米",
                species="dog",
                personality="energetic",
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

            memory = create_pet_memory(
                memory_type="co_experienced",
                title="一起守夜",
                content="主人明确把黑米加入了今晚一起守夜的共同经历。",
                source="manual",
                participant_pet_ids=[heimi["id"], heimi["id"]],
                db_path=db_path,
            )

            self.assertEqual([heimi["id"]], memory["participant_pet_ids"])
            self.assertEqual("participant", memory["participants"][0]["role"])
            self.assertIn("Only participant pets may recall", memory["recall_guidance"])
            self.assertEqual([], list_pet_memories(pet_id=qingqing["id"], db_path=db_path))

    def test_memory_validation_and_delete_cleanup(self) -> None:
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

            with self.assertRaises(ValueError):
                create_pet_memory(
                    memory_type="dreamed_story",
                    content="不支持的记忆类型",
                    participant_pet_ids=[pet["id"]],
                    db_path=db_path,
                )

            memory = create_pet_memory(
                memory_type="pet_milestone",
                content="小月第一次主动完成了桌面陪伴启动。",
                source="desktop",
                participant_pet_ids=[pet["id"]],
                db_path=db_path,
            )
            self.assertIsNotNone(get_pet_memory(memory["id"], db_path=db_path))

            delete_pet(pet["id"], db_path=db_path)

            self.assertIsNone(get_pet_memory(memory["id"], db_path=db_path))


if __name__ == "__main__":
    unittest.main()
