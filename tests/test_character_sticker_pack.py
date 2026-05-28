import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import character_agent


class CharacterStickerPackTest(unittest.TestCase):
    def test_create_character_generates_walking_reference_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static"
            generated = static / "generated"
            generated.mkdir(parents=True)
            source = generated / "avatar.png"
            source_image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            for y in range(18, 46):
                for x in range(18, 46):
                    source_image.putpixel((x, y), (220, 80, 80, 255))
            source_image.save(source)
            store = root / "characters.json"

            with (
                patch.object(character_agent, "CHARACTER_STORE", store),
                patch.object(character_agent, "STATIC_DIR", static),
                patch.object(character_agent, "generate_image_from_reference", return_value="walking-ref.png") as generate_image,
            ):
                result = character_agent.create_character(
                    "/static/generated/avatar.png",
                    "animal_pixel_2d",
                    "黑色卷毛狗",
                )

        self.assertEqual("/static/generated/walking-ref.png", result["walking_reference_image_url"])
        self.assertTrue(generate_image.call_args.kwargs["require_transparent_png"])
        self.assertIn("species-accurate locomotion reference", generate_image.call_args.kwargs["prompt"])
        self.assertIn("Do not preserve the reference image's sitting pose", generate_image.call_args.kwargs["prompt"])
        self.assertIn("Do not force an animal, octopus, slime, fish, or non-humanoid creature into a human standing pose", generate_image.call_args.kwargs["prompt"])
        self.assertIn("If the character is an octopus or tentacled creature", generate_image.call_args.kwargs["prompt"])
        self.assertIn("mollusk", generate_image.call_args.kwargs["prompt"])
        self.assertIn("arms/tentacles crawl", generate_image.call_args.kwargs["prompt"])
        self.assertIn("If the character is a fish", generate_image.call_args.kwargs["prompt"])
        self.assertIn("tail-fin swimming", generate_image.call_args.kwargs["prompt"])
        self.assertIn("Do not invent human legs", generate_image.call_args.kwargs["prompt"])
        self.assertIn("Transparent PNG only", generate_image.call_args.kwargs["prompt"])

    def test_wan_walk_uses_walking_reference_image_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            class Spec:
                name = "walk_right"
                frame_count = 4
                duration = 90

            with patch("wan_video_agent.generate_wan_animation_gif", return_value=[output_dir / "frame.png"]) as generate_gif:
                result = character_agent._generate_wan_desktop_behavior_frames(
                    {
                        "image_url": "/static/generated/avatar.png",
                        "walking_reference_image_url": "/static/generated/walking-ref.png",
                    },
                    Spec(),
                    output_dir,
                )

        self.assertEqual([output_dir / "frame.png"], result)
        self.assertEqual("/static/generated/walking-ref.png", generate_gif.call_args.kwargs["image_url"])

    def test_wan_idle_keeps_base_character_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            class Spec:
                name = "idle"
                frame_count = 4
                duration = 90

            with patch("wan_video_agent.generate_wan_animation_gif", return_value=[output_dir / "frame.png"]) as generate_gif:
                character_agent._generate_wan_desktop_behavior_frames(
                    {
                        "image_url": "/static/generated/avatar.png",
                        "walking_reference_image_url": "/static/generated/walking-ref.png",
                    },
                    Spec(),
                    output_dir,
                )

        self.assertEqual("/static/generated/avatar.png", generate_gif.call_args.kwargs["image_url"])

    def test_wan_sleep_uses_generated_sleep_reference_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static"
            output_dir = static / "desktop_pet_assets" / "character-1"
            output_dir.mkdir(parents=True)
            sleep_reference = output_dir / "sleep_model_pose.png"
            sleep_reference.write_bytes(b"png")

            class Spec:
                name = "sleep"
                frame_count = 4
                duration = 120
                pose_name = "sleep"
                prompt = "sleeping curled up"

            with (
                patch.object(character_agent, "STATIC_DIR", static),
                patch.object(
                    character_agent,
                    "_generate_desktop_behavior_pose",
                    return_value=sleep_reference,
                ) as generate_pose,
                patch("wan_video_agent.generate_wan_animation_gif", return_value=[output_dir / "frame.png"]) as generate_gif,
            ):
                result = character_agent._generate_wan_desktop_behavior_frames(
                    {
                        "image_url": "/static/generated/avatar.png",
                        "walking_reference_image_url": "/static/generated/walking-ref.png",
                    },
                    Spec(),
                    output_dir,
                )

        self.assertEqual([output_dir / "frame.png"], result)
        self.assertEqual("/static/desktop_pet_assets/character-1/sleep_model_pose.png", generate_gif.call_args.kwargs["image_url"])
        generate_pose.assert_called_once()

    def test_build_wan_walk_generates_missing_walking_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static"
            generated = static / "generated"
            generated.mkdir(parents=True)
            source = generated / "avatar.png"
            source_image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            for y in range(18, 46):
                for x in range(18, 46):
                    source_image.putpixel((x, y), (220, 80, 80, 255))
            source_image.save(source)
            store = root / "characters.json"
            store.write_text(
                json.dumps(
                    [
                        {
                            "id": "character-1",
                            "image_url": "/static/generated/avatar.png",
                            "style_mode": "animal_pixel_2d",
                            "description": "蓝色章鱼",
                            "created_at": "2026-05-21T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            def fake_wan_frames(character, spec, output_dir):
                path = output_dir / f"{spec.name}_model_frame_1.png"
                image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                for y in range(20, 44):
                    for x in range(20, 44):
                        image.putpixel((x, y), (40, 120, 220, 255))
                image.save(path)
                return [path for _ in range(spec.frame_count)]

            with (
                patch.object(character_agent, "CHARACTER_STORE", store),
                patch.object(character_agent, "STATIC_DIR", static),
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
                patch.object(character_agent, "generate_image_from_reference", return_value="walking-ref.png") as generate_image,
                patch.object(character_agent, "_generate_wan_desktop_behavior_frames", side_effect=fake_wan_frames),
            ):
                result = character_agent.build_character_desktop_assets(
                    "character-1",
                    animation_names=["walk_right"],
                )

        self.assertEqual("/static/generated/walking-ref.png", result["walking_reference_image_url"])
        self.assertEqual(1, generate_image.call_count)

    def test_build_character_desktop_assets_can_use_gpt_frame_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static"
            generated = static / "generated"
            generated.mkdir(parents=True)
            source = generated / "avatar.png"
            source_image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            for y in range(18, 46):
                for x in range(18, 46):
                    source_image.putpixel((x, y), (220, 80, 80, 255))
            source_image.save(source)
            store = root / "characters.json"
            store.write_text(
                json.dumps(
                    [
                        {
                            "id": "character-1",
                            "image_url": "/static/generated/avatar.png",
                            "style_mode": "animal_pixel_2d",
                            "description": "蓝色章鱼",
                            "created_at": "2026-05-21T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            def write_generated(name: str) -> None:
                path = generated / name
                image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                for y in range(20, 44):
                    for x in range(20, 44):
                        image.putpixel((x, y), (40, 120, 220, 255))
                image.save(path)

            generated_names = [f"frame-{index}.png" for index in range(1, 5)]
            for name in generated_names:
                write_generated(name)

            with (
                patch.object(character_agent, "CHARACTER_STORE", store),
                patch.object(character_agent, "STATIC_DIR", static),
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
                patch.object(
                    character_agent,
                    "generate_image_from_reference",
                    side_effect=generated_names,
                ) as generate_image,
            ):
                result = character_agent.build_character_desktop_assets(
                    "character-1",
                    animation_names=["idle"],
                    provider="gpt",
                )

        self.assertEqual(4, generate_image.call_count)
        for call in generate_image.call_args_list:
            self.assertTrue(call.kwargs["require_transparent_png"])
            self.assertIn("Family-friendly, non-sexualized desktop mascot sprite", call.kwargs["prompt"])
            self.assertIn("standalone complete transparent PNG", call.kwargs["prompt"])
            self.assertIn("Swift window across the screen", call.kwargs["prompt"])
            self.assertIn("four frames total", call.kwargs["prompt"])
            self.assertIn("draw the character sitting", call.kwargs["prompt"])
            self.assertIn("in-place stepping loop", call.kwargs["prompt"])
            self.assertNotIn("horizontal sprite-strip", call.kwargs["prompt"])
        self.assertIn("toward the left", generate_image.call_args_list[0].kwargs["prompt"])
        self.assertIn("back toward the center", generate_image.call_args_list[1].kwargs["prompt"])
        self.assertIn("toward the right", generate_image.call_args_list[2].kwargs["prompt"])
        self.assertIn("back toward the center", generate_image.call_args_list[3].kwargs["prompt"])
        self.assertEqual(
            "/static/desktop_pet_assets/character-1/manifest.json",
            result["desktop_pet_manifest_url"],
        )

    def test_build_character_desktop_assets_uses_wan_provider_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static"
            generated = static / "generated"
            generated.mkdir(parents=True)
            source = generated / "avatar.png"
            source_image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            for y in range(18, 46):
                for x in range(18, 46):
                    source_image.putpixel((x, y), (220, 80, 80, 255))
            source_image.save(source)
            store = root / "characters.json"
            store.write_text(
                json.dumps(
                    [
                        {
                            "id": "character-1",
                            "image_url": "/static/generated/avatar.png",
                            "style_mode": "animal_pixel_2d",
                            "description": "蓝色章鱼",
                            "created_at": "2026-05-21T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            def fake_wan_frames(character, spec, output_dir):
                paths = []
                for index in range(1, spec.frame_count + 1):
                    path = output_dir / f"{spec.name}_model_frame_{index}.png"
                    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                    for y in range(20, 44):
                        for x in range(20, 44):
                            image.putpixel((x, y), (40 * index, 120, 220, 255))
                    image.save(path)
                    paths.append(path)
                return paths

            with (
                patch.object(character_agent, "CHARACTER_STORE", store),
                patch.object(character_agent, "STATIC_DIR", static),
                patch("desktop_pet_assets.PROJECT_ROOT", root),
                patch("desktop_pet_assets.STATIC_DIR", static),
                patch("desktop_pet_assets.ASSET_ROOT", static / "desktop_pet_assets"),
                patch.object(
                    character_agent,
                    "_generate_wan_desktop_behavior_frames",
                    side_effect=fake_wan_frames,
                ) as generate_wan,
            ):
                result = character_agent.build_character_desktop_assets(
                    "character-1",
                    animation_names=["idle"],
                )

        self.assertEqual(1, generate_wan.call_count)
        self.assertEqual("wan", result["desktop_pet_asset_provider"])
        self.assertEqual(
            "/static/desktop_pet_assets/character-1/manifest.json",
            result["desktop_pet_manifest_url"],
        )

    def test_generate_character_sticker_pack_creates_twelve_stickers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static"
            generated = static / "generated"
            generated.mkdir(parents=True)
            source = generated / "avatar.png"
            source.write_bytes(b"reference")
            store = root / "characters.json"
            store.write_text(
                json.dumps(
                    [
                        {
                            "id": "character-1",
                            "image_url": "/static/generated/avatar.png",
                            "style_mode": "animal_pixel_2d",
                            "description": "蓝色章鱼",
                            "created_at": "2026-05-21T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with patch.object(character_agent, "CHARACTER_STORE", store), patch.object(
                character_agent,
                "STATIC_DIR",
                static,
            ), patch.object(
                character_agent,
                "generate_image_from_reference",
                side_effect=[f"sticker-{index}.png" for index in range(1, 13)],
            ) as generate_image:
                result = character_agent.generate_character_sticker_pack("character-1")

        self.assertEqual("character-1", result["character_id"])
        self.assertEqual(12, len(result["stickers"]))
        self.assertEqual(12, generate_image.call_count)
        self.assertEqual("/static/generated/sticker-1.png", result["stickers"][0]["image_url"])
        self.assertEqual("/static/generated/sticker-12.png", result["stickers"][-1]["image_url"])


if __name__ == "__main__":
    unittest.main()
