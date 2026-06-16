import json
import tempfile
import unittest
from pathlib import Path

from launch_desktop_pet import build_desktop_pet_command


class LaunchDesktopPetTest(unittest.TestCase):
    def test_build_command_passes_assistant_api_context_to_swift_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "static" / "desktop_pet_assets" / "character" / "manifest.json"
            avatar = root / "static" / "desktop_pet_assets" / "character" / "avatar.png"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
            avatar.write_bytes(b"png")
            pet = {
                "id": 7,
                "owner_id": 42,
                "name": "龙虾",
                "profile_json": json.dumps(
                    {
                        "desktop_pet_manifest_url": "/static/desktop_pet_assets/character/manifest.json",
                        "desktop_pet_avatar_url": "/static/desktop_pet_assets/character/avatar.png",
                    }
                ),
            }

            command = build_desktop_pet_command(
                pet,
                offset_index=2,
                api_base_url="http://127.0.0.1:8000",
                project_root=root,
            )

            self.assertEqual("swift", command[0])
            self.assertEqual(str(root / "desktop_pet_mac.swift"), command[1])
            self.assertIn("--api-base", command)
            self.assertIn("http://127.0.0.1:8000", command)
            self.assertIn("--pet-id", command)
            self.assertIn("7", command)
            self.assertIn("--owner-id", command)
            self.assertIn("42", command)
            self.assertIn("--manifest", command)
            self.assertIn(str(manifest.resolve()), command)
            self.assertIn("--image", command)
            self.assertIn(str(avatar.resolve()), command)


if __name__ == "__main__":
    unittest.main()
