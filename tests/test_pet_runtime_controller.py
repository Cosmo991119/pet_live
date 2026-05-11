import tempfile
import unittest
from pathlib import Path

from pet_db import create_pet, init_db
from pet_runtime_controller import PetRuntimeController


class DummyProcess:
    pid = 43210

    def poll(self):
        return None


class PetRuntimeControllerTest(unittest.TestCase):
    def test_launches_desktop_pet_from_local_profile_without_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "pet_agent.db"
            manifest = root / "static" / "desktop_pet_assets" / "character" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
            init_db(db_path)
            pet = create_pet(
                name="Qing Qing",
                pet_mode="virtual",
                species="other",
                personality="cool",
                owner_call_name="姐姐",
                profile={
                    "desktop_pet_manifest_url": "/static/desktop_pet_assets/character/manifest.json"
                },
                db_path=db_path,
            )
            calls = []

            def fake_popen(command, **kwargs):
                calls.append((command, kwargs))
                return DummyProcess()

            controller = PetRuntimeController(
                project_root=root,
                default_pet_id=str(pet["id"]),
                db_path=db_path,
                popen=fake_popen,
            )

            result = controller.launch_desktop_companion(chat_id="test-chat")

            self.assertTrue(result.ok)
            self.assertEqual("DESKTOP_LAUNCHED", result.code)
            self.assertEqual(43210, result.pid)
            self.assertEqual(1, len(calls))
            self.assertEqual(str(root / "launch_desktop_pet.py"), calls[0][0][1])
            self.assertEqual(["--pet-id", str(pet["id"])], calls[0][0][2:])

    def test_missing_manifest_returns_product_error_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "pet_agent.db"
            init_db(db_path)
            pet = create_pet(
                name="Qing Qing",
                pet_mode="virtual",
                species="other",
                personality="cool",
                owner_call_name="姐姐",
                profile={"desktop_pet_manifest_url": "/static/missing/manifest.json"},
                db_path=db_path,
            )
            controller = PetRuntimeController(
                project_root=root,
                default_pet_id=str(pet["id"]),
                db_path=db_path,
            )

            result = controller.launch_desktop_companion(chat_id="test-chat")

            self.assertFalse(result.ok)
            self.assertEqual("DESKTOP_ASSETS_MISSING", result.code)


if __name__ == "__main__":
    unittest.main()
