import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

import image_style_agent


def _compact(text: str) -> str:
    return " ".join(text.split())


class ImageStyleAgentTest(unittest.TestCase):
    def test_pixel_avatar_prompt_injects_fixed_chibi_pixel_style(self) -> None:
        prompt = image_style_agent._build_prompt("保留黄色手机和红白玩偶", "animal_pixel_2d")
        compact_prompt = _compact(prompt)

        self.assertIn("Fixed pixel avatar style override", prompt)
        self.assertIn("fixed chibi pixel style only", prompt)
        self.assertIn("Fixed style reference: refined chibi anime pixel-art sticker", prompt)
        self.assertIn("Q-version anime pixel art", prompt)
        self.assertIn("polished high-resolution pixel-art finish", prompt)
        self.assertIn("crisp square pixel edges", prompt)
        self.assertIn("subtle anti-aliasing", prompt)
        self.assertIn("big-head-small-body chibi proportions", prompt)
        self.assertIn("modern cute but slightly cool temperament", prompt)
        self.assertIn("game character standing illustration", prompt)
        self.assertIn("Style Transfer Scope: this is a style conversion, not a redesign", prompt)
        self.assertIn("Subject Selection", prompt)
        self.assertIn("most prominent\nforeground subject", prompt)
        self.assertIn("include a held plush/object", prompt)
        self.assertIn("Preserve the source image's pose", prompt)
        self.assertIn("held-object placement", prompt)
        self.assertIn("clean hand-placed sprite clusters", prompt)
        self.assertIn("controlled thin dark outlines", prompt)
        self.assertIn("blocky hair and\nclothing highlights", prompt)
        self.assertIn("nearest-neighbor-like clarity", prompt)
        self.assertIn("Transparent background only", prompt)
        self.assertIn("Transparent PNG contract", prompt)
        self.assertIn("real alpha channel", prompt)
        self.assertIn("All four corners and the margin around the character", prompt)
        self.assertIn("Do not fake transparency", prompt)
        self.assertIn("No beach, room, scenery, floor", prompt)
        self.assertIn("floor, ground plane, base", prompt)
        self.assertIn("lower-body design and pose logic", prompt)
        self.assertIn("Preserve important source accessories", prompt)
        self.assertIn("keep it as a hand or arm", prompt)
        self.assertIn("same skin tone", prompt)
        self.assertIn("Do not crop the head", prompt)
        self.assertIn("Do not zoom in", prompt)
        self.assertNotIn("pure white solid background", compact_prompt)
        self.assertNotIn("octopus-girl", prompt)
        self.assertNotIn("left orange/red-haired", prompt)
        self.assertIn("保留黄色手机和红白玩偶", prompt)

    def test_pixel_avatar_base_style_uses_current_style_language(self) -> None:
        character_prompt = image_style_agent._build_prompt("红色外套，活泼", "character_pixel_2d")
        animal_prompt = image_style_agent._build_prompt("蓝色小猫，黏人", "animal_pixel_2d")

        for prompt in (character_prompt, animal_prompt):
            compact_prompt = _compact(prompt)
            self.assertIn("Q-version anime pixel art", prompt)
            self.assertIn("big-head-small-body proportions", compact_prompt)
            self.assertIn("crisp square pixel edges", prompt)
            self.assertIn("subtle anti-aliasing", prompt)
            self.assertIn("low-saturation graphic shadows", prompt)
            self.assertIn("transparent background only", compact_prompt.lower())
            self.assertIn("heavy black borders", prompt)
            self.assertIn("dirty smudges", compact_prompt)
            self.assertNotIn("reference-image-1 style", compact_prompt)
            self.assertNotIn("Animalization rules", prompt)
            self.assertNotIn("Use thick dark/black pixel outlines", prompt)

    def test_animal_pixel_prompt_is_style_transfer_not_default_animalization(self) -> None:
        prompt = image_style_agent._build_prompt("保留手机和手表", "animal_pixel_2d")

        self.assertIn("This mode is for style transfer", prompt)
        self.assertIn("Do not animalize, redesign, or turn the\nsubject into a generic mascot", prompt)
        self.assertIn("Preserve the primary subject's pose logic", prompt)
        self.assertIn("held objects, accessories", prompt)
        self.assertIn("No invented animal traits", prompt)
        self.assertIn("保留手机和手表", prompt)

    def test_animal_pixel_prompt_keeps_primary_subject_and_held_plush(self) -> None:
        prompt = image_style_agent._build_prompt("保留右侧人物和怀里的红白玩偶", "animal_pixel_2d")

        self.assertIn("If the uploaded image contains multiple people, pets, toys, or characters", prompt)
        self.assertIn("follow the user's text\n  for subject selection", prompt)
        self.assertIn("include the held plush/object", prompt)
        self.assertIn("Do not merge\nidentity features from unrelated background subjects", prompt)
        self.assertIn("保留右侧人物和怀里的红白玩偶", prompt)

    @patch("image_style_agent._save_generated_image_data")
    @patch("image_style_agent._client")
    @patch.dict("image_style_agent.os.environ", {}, clear=True)
    def test_gpt_image_edit_omits_unsupported_response_format(self, client_factory: Mock, save_image: Mock) -> None:
        save_image.return_value = "generated.png"
        image_item = Mock()
        image_item.b64_json = "encoded"
        image_item.url = None
        client = Mock()
        client.images.edit.return_value.data = [image_item]
        client_factory.return_value = client

        result = image_style_agent.generate_image_from_reference(
            image_bytes=b"image",
            filename="input.jpg",
            content_type="image/jpeg",
            prompt="make a pet avatar",
        )

        self.assertEqual("generated.png", result)
        self.assertEqual("gpt-image-1.5", client.images.edit.call_args.kwargs["model"])
        self.assertEqual("transparent", client.images.edit.call_args.kwargs["background"])
        self.assertEqual("png", client.images.edit.call_args.kwargs["output_format"])
        self.assertEqual("high", client.images.edit.call_args.kwargs["input_fidelity"])
        self.assertNotIn("response_format", client.images.edit.call_args.kwargs)

    @patch("image_style_agent._save_generated_image_data")
    @patch("image_style_agent._client")
    @patch.dict("image_style_agent.os.environ", {"OPENAI_IMAGE_BACKGROUND": "white", "OPENAI_IMAGE_OUTPUT_FORMAT": "jpeg"})
    def test_transparent_generation_ignores_env_background_overrides(
        self,
        client_factory: Mock,
        save_image: Mock,
    ) -> None:
        save_image.return_value = "generated.png"
        image_item = Mock()
        image_item.b64_json = "encoded"
        image_item.url = None
        client = Mock()
        client.images.edit.return_value.data = [image_item]
        client_factory.return_value = client

        image_style_agent.generate_image_from_reference(
            image_bytes=b"image",
            filename="input.jpg",
            content_type="image/jpeg",
            prompt="make a transparent pet avatar",
        )

        self.assertEqual("transparent", client.images.edit.call_args.kwargs["background"])
        self.assertEqual("png", client.images.edit.call_args.kwargs["output_format"])

    def test_transparent_png_validation_rejects_opaque_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opaque.png"
            Image.new("RGBA", (32, 32), (255, 255, 255, 255)).save(path)

            with self.assertRaisesRegex(ValueError, "真实透明背景"):
                image_style_agent._validate_transparent_png(path)

    def test_transparent_png_validation_accepts_cutout_with_margin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cutout.png"
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            for y in range(18, 46):
                for x in range(18, 46):
                    image.putpixel((x, y), (20, 20, 20, 255))
            image.save(path)

            image_style_agent._validate_transparent_png(path)

    @patch.dict("image_style_agent.os.environ", {"OPENAI_IMAGE_MODEL": "dall-e-2"})
    @patch("image_style_agent._save_generated_image_data")
    @patch("image_style_agent._client")
    def test_dalle_edit_keeps_response_format(self, client_factory: Mock, save_image: Mock) -> None:
        save_image.return_value = "generated.png"
        image_item = Mock()
        image_item.b64_json = "encoded"
        image_item.url = None
        client = Mock()
        client.images.edit.return_value.data = [image_item]
        client_factory.return_value = client

        image_style_agent.generate_image_from_reference(
            image_bytes=b"image",
            filename="input.png",
            content_type="image/png",
            prompt="make a pet avatar",
        )

        self.assertEqual("b64_json", client.images.edit.call_args.kwargs["response_format"])


if __name__ == "__main__":
    unittest.main()
