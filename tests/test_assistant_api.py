import unittest
from unittest.mock import patch

from fastapi import HTTPException

from api import (
    AssistantItemCompleteRequest,
    AssistantItemRequest,
    complete_assistant_item_endpoint,
    create_assistant_item_endpoint,
    list_assistant_items_endpoint,
)


class AssistantApiTest(unittest.TestCase):
    @patch("api.create_assistant_item")
    def test_create_assistant_item_endpoint_passes_payload(self, create_item) -> None:
        create_item.return_value = {"id": 3, "item_type": "alarm", "title": "喝水"}
        payload = AssistantItemRequest(
            owner_id=9,
            pet_id=2,
            item_type="alarm",
            title="喝水",
            body="桌面龙虾提醒",
            due_at="2026-05-29T16:30:00+08:00",
            duration_minutes=30,
            source="telegram",
        )

        result = create_assistant_item_endpoint(payload)

        self.assertEqual({"id": 3, "item_type": "alarm", "title": "喝水"}, result)
        create_item.assert_called_once_with(
            owner_id=9,
            pet_id=2,
            item_type="alarm",
            title="喝水",
            body="桌面龙虾提醒",
            due_at="2026-05-29T16:30:00+08:00",
            duration_minutes=30,
            source="telegram",
        )

    @patch("api.list_assistant_items")
    def test_list_assistant_items_endpoint_passes_filters(self, list_items) -> None:
        list_items.return_value = [{"id": 5, "title": "写周报"}]

        result = list_assistant_items_endpoint(
            owner_id=9,
            item_type="todo",
            status="open",
            due_before="2026-05-29T17:00:00+08:00",
            limit=10,
        )

        self.assertEqual([{"id": 5, "title": "写周报"}], result)
        list_items.assert_called_once_with(
            owner_id=9,
            item_type="todo",
            status="open",
            due_before="2026-05-29T17:00:00+08:00",
            limit=10,
        )

    @patch("api.complete_assistant_item")
    def test_complete_assistant_item_endpoint_passes_status(self, complete_item) -> None:
        complete_item.return_value = {"id": 5, "status": "dismissed"}

        result = complete_assistant_item_endpoint(
            5,
            AssistantItemCompleteRequest(owner_id=9, status="dismissed"),
        )

        self.assertEqual({"id": 5, "status": "dismissed"}, result)
        complete_item.assert_called_once_with(
            5,
            owner_id=9,
            status="dismissed",
        )

    @patch("api.complete_assistant_item")
    def test_complete_assistant_item_endpoint_reports_bad_status_as_400(self, complete_item) -> None:
        complete_item.side_effect = ValueError("status must be one of ['done']")

        with self.assertRaises(HTTPException) as ctx:
            complete_assistant_item_endpoint(
                5,
                AssistantItemCompleteRequest(owner_id=9, status="open"),
            )

        self.assertEqual(400, ctx.exception.status_code)


if __name__ == "__main__":
    unittest.main()
