import hashlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageSequence

import wan_video_agent


class WanVideoAgentTest(unittest.TestCase):
    def test_static_url_to_public_url_requires_public_base(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "PET_AGENT_PUBLIC_BASE_URL"):
                wan_video_agent.static_url_to_public_url("/static/generated/avatar.png")

    def test_static_url_to_public_url_joins_public_base(self) -> None:
        with patch.dict(os.environ, {"PET_AGENT_PUBLIC_BASE_URL": "https://example.test/app"}, clear=True):
            self.assertEqual(
                "https://example.test/app/static/generated/avatar.png",
                wan_video_agent.static_url_to_public_url("/static/generated/avatar.png"),
            )

    def test_static_url_to_public_url_uploads_to_cloudflare_r2_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "static" / "desktop_pet_assets" / "character-1" / "wan_green_reference.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"png-bytes")

            response = types.SimpleNamespace(status_code=200, text="", raise_for_status=lambda: None)
            with (
                patch.object(wan_video_agent, "PROJECT_ROOT", root),
                patch.object(wan_video_agent.requests, "put", return_value=response) as put,
                patch.dict(
                    os.environ,
                    {
                        "CLOUDFLARE_R2_ACCOUNT_ID": "https://account-id.r2.cloudflarestorage.com",
                        "CLOUDFLARE_R2_ACCESS_KEY_ID": "access-key",
                        "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "secret-key",
                        "CLOUDFLARE_R2_BUCKET": "pet-assets",
                        "CLOUDFLARE_R2_PUBLIC_BASE_URL": "https://pub-example.r2.dev",
                        "CLOUDFLARE_R2_KEY_PREFIX": "agent-demo/wan",
                    },
                    clear=True,
                ),
            ):
                result = wan_video_agent.static_url_to_public_url(
                    "/static/desktop_pet_assets/character-1/wan_green_reference.png"
                )

            digest = hashlib.sha256(b"png-bytes").hexdigest()[:16]
            object_key = f"agent-demo/wan/static/desktop_pet_assets/character-1/wan_green_reference-{digest}.png"
            self.assertEqual(
                f"https://pub-example.r2.dev/{object_key}",
                result,
            )
            put.assert_called_once()
            request_url = put.call_args.args[0]
            self.assertEqual(
                f"https://account-id.r2.cloudflarestorage.com/pet-assets/{object_key}",
                request_url,
            )
            self.assertEqual(b"png-bytes", put.call_args.kwargs["data"])
            headers = put.call_args.kwargs["headers"]
            self.assertEqual("image/png", headers["content-type"])
            self.assertIn("Credential=access-key/", headers["Authorization"])
            self.assertIn("/auto/s3/aws4_request", headers["Authorization"])

    def test_create_green_screen_reference_composites_transparent_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static"
            source = static / "generated" / "avatar.png"
            source.parent.mkdir(parents=True)
            image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
            image.putpixel((6, 6), (10, 20, 30, 255))
            image.save(source)

            with patch.object(wan_video_agent, "PROJECT_ROOT", root):
                result = wan_video_agent.create_green_screen_reference(
                    "/static/generated/avatar.png",
                    static / "desktop_pet_assets" / "character-1",
                )

            output = root / result.lstrip("/")
            self.assertEqual("/static/desktop_pet_assets/character-1/wan_green_reference.png", result)
            saved = Image.open(output).convert("RGB")
            self.assertEqual((0, 255, 0), saved.getpixel((0, 0)))
            self.assertEqual((10, 20, 30), saved.getpixel((6, 6)))

    def test_default_animation_prompts_are_specific_and_loopable(self) -> None:
        expected = {
            "idle": "首帧和尾帧一致",
            "walk_right": "向右移动的动作",
            "walk_left": "向左移动的动作",
            "sleep": "身体轻微起伏",
            "happy": "头上冒开心泡泡",
        }

        for animation_name, phrase in expected.items():
            prompt = wan_video_agent.wan_prompt_for_animation(animation_name)
            self.assertIn(phrase, prompt)
            self.assertIn("首帧和尾帧一致", prompt)
            self.assertIn("背景必须是纯绿色 #00FF00", prompt)
            self.assertIn("角色之外只能出现纯绿色背景", prompt)
            self.assertIn("不要添加文字、场景、地面、阴影、反光、渐变、光晕或额外角色", prompt)
            self.assertNotIn("{GREEN_SCREEN_CONTRACT}", prompt)
        self.assertIn("手臂自然下垂", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertIn("手臂自然下垂", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("正常四足动物步态", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertIn("不要添加人类手臂或人腿", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("章鱼、鱿鱼、鱼类、水母、海马", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("海洋或水生动物", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("游动姿势", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertIn("章鱼、鱿鱼或其他腕足触手类海洋动物", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("游动漂移", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("腕足像柔软飘带一样自然展开、收拢和波动", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertIn("身体悬浮滑行", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("不要让腕足吸附地面或像脚一样交替走路", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertIn("腕足、触手、鱼鳍、尾巴或身体波动", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("尾巴和尾鳍左右摆动", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertIn("不要添加人类腿、脚、鞋或手", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertNotIn("腕足交替支撑爬行", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertNotIn("贴地蠕动", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("不要保留参考图里的坐姿", wan_video_agent.wan_prompt_for_animation("walk_left"))
        self.assertIn("不要坐着滑动", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("第一帧就必须是符合物种设定的移动姿势", wan_video_agent.wan_prompt_for_animation("walk_right"))
        self.assertIn("眼神变亮", wan_video_agent.wan_prompt_for_animation("happy"))

    def test_video_to_gif_extracts_frames_and_keeps_transparent_corners(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for color in ((220, 40, 40), (40, 120, 220), (60, 180, 80)):
                image = Image.new("RGB", (64, 64), (255, 255, 255))
                for y in range(18, 46):
                    for x in range(18, 46):
                        image.putpixel((x, y), color)
                frames.append(image)

            frame_paths = [root / "idle_model_frame_1.png", root / "idle_model_frame_2.png"]
            with patch.object(wan_video_agent, "_iter_video_frames", return_value=[np.array(frame) for frame in frames]):
                result = wan_video_agent.video_to_gif(
                    video_path=root / "wan.mp4",
                    gif_path=root / "idle.gif",
                    frame_paths=frame_paths,
                    fps=24,
                    duration_ms=440,
                )

            self.assertEqual(frame_paths, result)
            for path in frame_paths:
                self.assertTrue(path.exists())
                image = Image.open(path).convert("RGBA")
                self.assertEqual(0, image.getpixel((0, 0))[3])

            with Image.open(root / "idle.gif") as image:
                self.assertEqual(3, sum(1 for _ in ImageSequence.Iterator(image)))
                self.assertEqual(440, image.info.get("duration"))

    def test_video_to_gif_can_target_full_five_second_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for index in range(75):
                image = Image.new("RGB", (64, 64), (0, 255, 0))
                for y in range(18, 46):
                    for x in range(18, 46):
                        image.putpixel((x, y), ((index * 3) % 255, 120, 220))
                frames.append(image)

            with patch.object(wan_video_agent, "_iter_video_frames", return_value=[np.array(frame) for frame in frames]):
                wan_video_agent.video_to_gif(
                    video_path=root / "wan.mp4",
                    gif_path=root / "idle.gif",
                    frame_paths=[root / "idle_model_frame_1.png"],
                    fps=24,
                    duration_ms=100,
                    target_duration_ms=5000,
                )

            with Image.open(root / "idle.gif") as image:
                durations = [
                    frame.info.get("duration", image.info.get("duration", 0))
                    for frame in ImageSequence.Iterator(image)
                ]
            self.assertEqual(75, len(durations))
            self.assertEqual(5000, sum(durations))
            self.assertEqual({60, 70}, set(durations))

    def test_remove_green_screen_makes_green_background_transparent(self) -> None:
        image = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
        for y in range(5, 11):
            for x in range(5, 11):
                image.putpixel((x, y), (40, 40, 90, 255))
        image.putpixel((4, 8), (20, 180, 30, 200))

        result = wan_video_agent._remove_green_screen(image)

        self.assertEqual(0, result.getpixel((0, 0))[3])
        self.assertEqual(0, result.getpixel((4, 8))[3])
        self.assertEqual(255, result.getpixel((8, 8))[3])

    def test_generate_wan_video_url_uses_kf2v_flash_model(self) -> None:
        calls = {}

        class FakeResponse:
            status_code = 200
            code = ""
            message = ""

            def __init__(self, output: object) -> None:
                self.output = output

        class FakeVideoSynthesis:
            @staticmethod
            def call(**kwargs: object) -> FakeResponse:
                calls["call"] = kwargs
                return FakeResponse(types.SimpleNamespace(video_url="https://example.test/wan.mp4"))

        fake_dashscope = types.SimpleNamespace(
            api_key="",
            base_http_api_url="",
            VideoSynthesis=FakeVideoSynthesis,
        )

        with patch.dict(
            sys.modules,
            {"dashscope": fake_dashscope},
        ), patch.dict(os.environ, {"DASHSCOPE_API_KEY": "dashscope-key"}, clear=True):
            video_url = wan_video_agent.generate_wan_video_url(
                image_url="https://example.test/avatar.png",
                prompt="一只猫在草地上奔跑",
            )

        self.assertEqual("https://example.test/wan.mp4", video_url)
        self.assertEqual("dashscope-key", fake_dashscope.api_key)
        self.assertEqual("https://dashscope.aliyuncs.com/api/v1", fake_dashscope.base_http_api_url)
        self.assertEqual(
            {
                "api_key": "dashscope-key",
                "model": "wan2.2-kf2v-flash",
                "prompt": "一只猫在草地上奔跑",
                "first_frame_url": "https://example.test/avatar.png",
                "last_frame_url": "https://example.test/avatar.png",
                "resolution": "720P",
                "prompt_extend": True,
            },
            calls["call"],
        )

    def test_generate_wan_video_url_wraps_flash_task_creation_errors(self) -> None:
        class FakeVideoSynthesis:
            @staticmethod
            def call(**kwargs: object) -> object:
                raise RuntimeError("Arrearage Access denied")

        fake_dashscope = types.SimpleNamespace(
            api_key="",
            base_http_api_url="",
            VideoSynthesis=FakeVideoSynthesis,
        )

        with patch.dict(
            sys.modules,
            {"dashscope": fake_dashscope},
        ), patch.dict(os.environ, {"DASHSCOPE_API_KEY": "dashscope-key"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Wan 图生视频任务失败.*Arrearage"):
                wan_video_agent.generate_wan_video_url(
                    image_url="https://example.test/avatar.png",
                    prompt="一只章鱼向右游动",
                )


if __name__ == "__main__":
    unittest.main()
