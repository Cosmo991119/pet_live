import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image, ImageSequence

from desktop_pet_assets import ANIMATION_SPECS, build_desktop_pet_assets, _save_gif


class DesktopPetAssetsTest(unittest.TestCase):
    def test_saved_gif_keeps_transparent_corners(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "idle.gif"
            frame = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            for y in range(24):
                for x in range(24):
                    subject = Image.new(
                        "RGBA",
                        (1, 1),
                        ((x * 17 + y * 3) % 256, (y * 19 + x * 5) % 256, ((x + y) * 23) % 256, 255),
                    )
                    frame.alpha_composite(subject, (4 + x, 4 + y))

            _save_gif(path, [frame, frame], duration=120)

            with Image.open(path) as image:
                transparent_index = image.info.get("transparency")
                self.assertIsNotNone(transparent_index)
                for saved_frame in ImageSequence.Iterator(image):
                    self.assertEqual(transparent_index, saved_frame.getpixel((0, 0)))
                    self.assertEqual(0, saved_frame.convert("RGBA").getpixel((0, 0))[3])

    def test_builds_behavior_pose_manifest_and_uses_generated_sleep_pose(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "static"
            source = static / "generated" / "source.png"
            source.parent.mkdir(parents=True)
            self._write_marker_image(source, (220, 40, 40, 255))

            def fake_pose_generator(character, spec, output_dir):
                path = output_dir / f"{spec.name}_model.png"
                color = (40, 40, 220, 255) if spec.name == "sleep" else (40, 180, 90, 255)
                self._write_marker_image(path, color)
                return path

            with (
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
            ):
                result = build_desktop_pet_assets(
                    {
                        "id": "character-1",
                        "image_url": "/static/generated/source.png",
                    },
                    pose_image_generator=fake_pose_generator,
                )

            asset_dir = static / "desktop_pet_assets" / "character-1"
            manifest = json.loads((asset_dir / "manifest.json").read_text(encoding="utf-8"))
            expected = {spec.name for spec in ANIMATION_SPECS}
            self.assertEqual(expected, set(manifest["animations"]))
            self.assertEqual("generated_behavior_pose", manifest["pose_sources"]["sleep"]["source"])
            self.assertEqual("sleep_pose.png", manifest["animations"]["sleep"]["pose"])
            self.assertEqual(
                "/static/desktop_pet_assets/character-1/manifest.json",
                result["desktop_pet_manifest_url"],
            )

            with Image.open(asset_dir / "sleep_pose.png") as sleep_pose:
                rgba = sleep_pose.convert("RGBA")
                bbox = rgba.getchannel("A").getbbox()
                self.assertIsNotNone(bbox)
                x = (bbox[0] + bbox[2]) // 2
                y = (bbox[1] + bbox[3]) // 2
                center = rgba.getpixel((x, y))
                self.assertGreater(center[2], center[0])

    @staticmethod
    def _write_marker_image(path: Path, color: tuple[int, int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        for y in range(18, 78):
            for x in range(18, 78):
                image.putpixel((x, y), color)
        image.save(path)


if __name__ == "__main__":
    unittest.main()
