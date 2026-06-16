import tempfile
import unittest
from pathlib import Path

from pet_db import (
    complete_assistant_item,
    create_assistant_item,
    create_owner_for_telegram_chat,
    create_pet,
    init_db,
    list_assistant_items,
)


class PetWorkItemsTest(unittest.TestCase):
    def test_owner_can_manage_simple_assistant_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pet_agent.db"
            init_db(db_path)
            owner = create_owner_for_telegram_chat("owner-a", db_path=db_path)
            other_owner = create_owner_for_telegram_chat("owner-b", db_path=db_path)
            pet = create_pet(
                name="龙虾",
                owner_id=owner["id"],
                species="other",
                personality="gentle",
                owner_call_name="主人",
                pet_mode="virtual",
                db_path=db_path,
            )

            note = create_assistant_item(
                owner_id=owner["id"],
                pet_id=pet["id"],
                item_type="note",
                title="记一下明天改登录页文案",
                body="按钮要更短一点",
                source="telegram",
                db_path=db_path,
            )
            todo = create_assistant_item(
                owner_id=owner["id"],
                pet_id=pet["id"],
                item_type="todo",
                title="写周报",
                source="telegram",
                db_path=db_path,
            )
            alarm = create_assistant_item(
                owner_id=owner["id"],
                pet_id=pet["id"],
                item_type="alarm",
                title="喝水",
                due_at="2026-05-29T16:30:00+08:00",
                source="telegram",
                db_path=db_path,
            )
            create_assistant_item(
                owner_id=other_owner["id"],
                item_type="todo",
                title="不应该出现在 owner-a 的列表里",
                db_path=db_path,
            )

            self.assertEqual("open", note["status"])
            self.assertEqual("telegram", note["source"])
            self.assertEqual([note["id"]], [
                item["id"]
                for item in list_assistant_items(
                    owner_id=owner["id"],
                    item_type="note",
                    db_path=db_path,
                )
            ])
            self.assertEqual([alarm["id"]], [
                item["id"]
                for item in list_assistant_items(
                    owner_id=owner["id"],
                    status="open",
                    due_before="2026-05-29T16:31:00+08:00",
                    db_path=db_path,
                )
            ])

            completed = complete_assistant_item(
                todo["id"],
                owner_id=owner["id"],
                db_path=db_path,
            )

            self.assertEqual("done", completed["status"])
            self.assertEqual([], list_assistant_items(
                owner_id=owner["id"],
                item_type="todo",
                status="open",
                db_path=db_path,
            ))
            self.assertEqual([todo["id"]], [
                item["id"]
                for item in list_assistant_items(
                    owner_id=owner["id"],
                    item_type="todo",
                    status="done",
                    db_path=db_path,
                )
            ])

            with self.assertRaises(ValueError):
                complete_assistant_item(
                    alarm["id"],
                    owner_id=other_owner["id"],
                    db_path=db_path,
                )


if __name__ == "__main__":
    unittest.main()
