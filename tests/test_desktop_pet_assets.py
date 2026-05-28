import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from desktop_pet_assets import (
    ANIMATION_SPECS,
    BASIC_DESKTOP_ANIMATION_NAMES,
    animation_specs_for,
    build_desktop_pet_assets,
    publish_existing_behavior_assets,
    publish_existing_behavior_poses,
    _frames_for_animation,
    _remove_flat_background,
    _save_gif,
)


class DesktopPetAssetsTest(unittest.TestCase):
    def test_remove_flat_background_preserves_existing_alpha_outline(self):
        image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        for y in range(4, 12):
            for x in range(4, 12):
                image.putpixel((x, y), (40, 40, 40, 255))
        image.putpixel((3, 8), (10, 10, 10, 255))

        result = _remove_flat_background(image)

        self.assertEqual((10, 10, 10, 255), result.getpixel((3, 8)))
        self.assertEqual(0, result.getpixel((0, 0))[3])

    def test_saved_gif_keeps_transparent_corners(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "idle.gif"
            frame = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            frame.putpixel((3, 8), (255, 0, 0, 8))
            frame.putpixel((4, 8), (12, 12, 12, 80))
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
                    self.assertEqual(0, saved_frame.convert("RGBA").getpixel((3, 8))[3])
                    edge = saved_frame.convert("RGBA").getpixel((4, 8))
                    self.assertGreater(edge[3], 0)
                    self.assertFalse(edge[0] > 180 and edge[1] < 40 and edge[2] > 180)
                    self.assertFalse(edge[0] > 180 and edge[1] < 40 and edge[2] < 80)

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
            expected = set(BASIC_DESKTOP_ANIMATION_NAMES)
            self.assertEqual(expected, set(manifest["animations"]))
            self.assertEqual("basic", manifest["generation_scope"])
            self.assertEqual("generated_behavior_pose", manifest["pose_sources"]["sleep"]["source"])
            self.assertEqual("sleep_pose.png", manifest["animations"]["sleep"]["pose"])
            self.assertNotIn("feed", manifest["animations"])
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

    def test_builds_behavior_frame_gif_from_generated_frame_sequence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "static"
            source = static / "generated" / "source.png"
            source.parent.mkdir(parents=True)
            self._write_marker_image(source, (220, 40, 40, 255))

            def fake_frame_generator(character, spec, output_dir):
                paths = []
                for index in range(1, spec.frame_count + 1):
                    path = output_dir / f"{spec.name}_model_frame_{index}.png"
                    self._write_marker_image(path, (40 * index, 180, 90, 255))
                    paths.append(path)
                return paths

            with (
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
            ):
                build_desktop_pet_assets(
                    {
                        "id": "character-1",
                        "image_url": "/static/generated/source.png",
                    },
                    frame_sequence_generator=fake_frame_generator,
                )

            asset_dir = static / "desktop_pet_assets" / "character-1"
            manifest = json.loads((asset_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("generated_behavior_frame_sequence", manifest["pose_sources"]["walk_right"]["source"])
            self.assertEqual(set(BASIC_DESKTOP_ANIMATION_NAMES), set(manifest["animations"]))
            self.assertEqual(4, len(manifest["animations"]["walk_right"]["frames"]))
            self.assertTrue((asset_dir / "walk_right_frame_1.png").exists())
            self.assertTrue((asset_dir / "walk_right_frame_4.png").exists())

            with Image.open(asset_dir / "walk_right.gif") as image:
                self.assertEqual(4, sum(1 for _ in ImageSequence.Iterator(image)))

    def test_walk_left_frame_sequence_is_mirrored_from_walk_right(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "static"
            source = static / "generated" / "source.png"
            source.parent.mkdir(parents=True)
            self._write_marker_image(source, (220, 40, 40, 255))
            generated_specs = []

            def fake_frame_generator(character, spec, output_dir):
                generated_specs.append(spec.name)
                paths = []
                for index in range(1, spec.frame_count + 1):
                    path = output_dir / f"{spec.name}_model_frame_{index}.png"
                    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                    for y in range(28, 68):
                        for x in range(18, 46):
                            image.putpixel((x, y), (220, 40, 40, 255))
                    for y in range(36, 56):
                        for x in range(58, 66):
                            image.putpixel((x, y), (40, 40, 220, 255))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(path)
                    paths.append(path)
                return paths

            with (
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
            ):
                build_desktop_pet_assets(
                    {
                        "id": "character-1",
                        "image_url": "/static/generated/source.png",
                    },
                    frame_sequence_generator=fake_frame_generator,
                    animation_names=["walk_right", "walk_left"],
                )

            asset_dir = static / "desktop_pet_assets" / "character-1"
            self.assertEqual(["walk_right"], generated_specs)
            right = Image.open(asset_dir / "walk_right_frame_1.png").convert("RGBA")
            left = Image.open(asset_dir / "walk_left_frame_1.png").convert("RGBA")
            self.assertEqual(list(ImageOps.mirror(right).getdata()), list(left.getdata()))
            manifest = json.loads((asset_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("mirrored_from_walk_right", manifest["pose_sources"]["walk_left"]["source"])

    def test_can_request_full_extended_animation_pack_explicitly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "static"
            source = static / "generated" / "source.png"
            source.parent.mkdir(parents=True)
            self._write_marker_image(source, (220, 40, 40, 255))

            def fake_sheet_generator(character, spec, output_dir):
                path = output_dir / f"{spec.name}_model_sheet.png"
                self._write_marker_sheet(path, spec.frame_count)
                return path

            with (
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
            ):
                build_desktop_pet_assets(
                    {
                        "id": "character-1",
                        "image_url": "/static/generated/source.png",
                    },
                    frame_sheet_generator=fake_sheet_generator,
                    animation_names=[spec.name for spec in ANIMATION_SPECS],
                )

            asset_dir = static / "desktop_pet_assets" / "character-1"
            manifest = json.loads((asset_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("custom", manifest["generation_scope"])
            self.assertEqual({spec.name for spec in ANIMATION_SPECS}, set(manifest["animations"]))
            self.assertIn("feed", manifest["animations"])

    def test_basic_animation_specs_are_the_default_desktop_companion_set(self):
        self.assertEqual(
            list(BASIC_DESKTOP_ANIMATION_NAMES),
            [spec.name for spec in animation_specs_for()],
        )
        self.assertNotIn("relax", BASIC_DESKTOP_ANIMATION_NAMES)

    def test_fallback_frames_do_not_apply_programmatic_motion(self):
        pose = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        for y in range(28, 78):
            for x in range(34, 62):
                pose.putpixel((x, y), (40, 180, 90, 255))

        frames = _frames_for_animation("walk_right", pose)

        boxes = []
        for frame in frames:
            bbox = frame.getchannel("A").getbbox()
            self.assertIsNotNone(bbox)
            boxes.append(bbox)
        self.assertEqual([boxes[0], boxes[0], boxes[0], boxes[0]], boxes)
        for frame in frames:
            self.assertEqual(list(pose.getdata()), list(frame.getdata()))

    def test_idle_fallback_frames_do_not_shift_subject(self):
        pose = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        for y in range(28, 78):
            for x in range(34, 62):
                pose.putpixel((x, y), (40, 180, 90, 255))

        frames = _frames_for_animation("idle", pose)

        boxes = [frame.getchannel("A").getbbox() for frame in frames]
        self.assertEqual(2, len(frames))
        self.assertEqual([boxes[0], boxes[0]], boxes)
        self.assertNotEqual(list(frames[0].getdata()), list(frames[1].getdata()))

    def test_publishes_only_existing_behavior_poses_as_partial_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "static"
            source = static / "generated" / "source.png"
            source.parent.mkdir(parents=True)
            self._write_marker_image(source, (220, 40, 40, 255))
            asset_dir = static / "desktop_pet_assets" / "character-1"
            self._write_marker_image(asset_dir / "sleep_model_pose.png", (40, 40, 220, 255))
            self._write_marker_image(asset_dir / "walk_right_model_pose.png", (40, 180, 90, 255))

            with (
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
            ):
                result = publish_existing_behavior_poses(
                    {
                        "id": "character-1",
                        "image_url": "/static/generated/source.png",
                    }
                )

            manifest = json.loads((asset_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("behavior-pose-gif-partial", manifest["format"])
            self.assertEqual("partial_ready", manifest["generation_status"])
            self.assertEqual({"idle", "sleep", "walk_right"}, set(manifest["animations"]))
            self.assertEqual(["idle", "sleep", "walk_right"], result["published_animations"])
            self.assertNotIn("feed", manifest["animations"])
            self.assertEqual("generated_behavior_pose", manifest["pose_sources"]["sleep"]["source"])

    def test_publishes_existing_behavior_frame_sequence_as_partial_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "static"
            source = static / "generated" / "source.png"
            source.parent.mkdir(parents=True)
            self._write_marker_image(source, (220, 40, 40, 255))
            asset_dir = static / "desktop_pet_assets" / "character-1"
            for animation_name in ("idle", "walk_right"):
                for index in range(1, 5):
                    self._write_marker_image(
                        asset_dir / f"{animation_name}_model_frame_{index}.png",
                        (40 * index, 180, 90, 255),
                    )

            with (
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
            ):
                result = publish_existing_behavior_assets(
                    {
                        "id": "character-1",
                        "image_url": "/static/generated/source.png",
                    }
                )

            manifest = json.loads((asset_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("behavior-frame-gif-partial", manifest["format"])
            self.assertEqual("partial_ready", manifest["generation_status"])
            self.assertEqual({"idle", "walk_right"}, set(manifest["animations"]))
            self.assertEqual(["idle", "walk_right"], result["published_animations"])
            self.assertEqual("generated_behavior_frame_sequence", manifest["pose_sources"]["idle"]["source"])
            self.assertEqual(4, len(manifest["animations"]["walk_right"]["frames"]))
            self.assertTrue((asset_dir / "walk_right.gif").exists())

    def test_publish_keeps_existing_long_gif_for_generated_frame_sequence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            static = root / "static"
            source = static / "generated" / "source.png"
            source.parent.mkdir(parents=True)
            self._write_marker_image(source, (220, 40, 40, 255))
            asset_dir = static / "desktop_pet_assets" / "character-1"
            frames = []
            for index in range(1, 5):
                path = asset_dir / f"walk_right_model_frame_{index}.png"
                self._write_marker_image(path, (40 * index, 180, 90, 255))
                frames.append(Image.open(path).convert("RGBA"))
            _save_gif(asset_dir / "walk_right.gif", frames + frames, duration=90)

            with (
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
            ):
                publish_existing_behavior_assets(
                    {
                        "id": "character-1",
                        "image_url": "/static/generated/source.png",
                    }
                )

            with Image.open(asset_dir / "walk_right.gif") as image:
                self.assertEqual(8, sum(1 for _ in ImageSequence.Iterator(image)))

    @staticmethod
    def _write_marker_image(path: Path, color: tuple[int, int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        for y in range(18, 78):
            for x in range(18, 78):
                image.putpixel((x, y), color)
        image.save(path)

    @staticmethod
    def _write_marker_sheet(path: Path, frame_count: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame_width = 96
        image = Image.new("RGBA", (frame_width * frame_count, 96), (0, 0, 0, 0))
        colors = [
            (220, 40, 40, 255),
            (40, 180, 90, 255),
            (40, 40, 220, 255),
            (220, 180, 40, 255),
        ]
        for index in range(frame_count):
            color = colors[index % len(colors)]
            offset = index * frame_width
            for y in range(18, 78):
                for x in range(18, 78):
                    image.putpixel((offset + x, y), color)
        image.save(path)


if __name__ == "__main__":
    unittest.main()
