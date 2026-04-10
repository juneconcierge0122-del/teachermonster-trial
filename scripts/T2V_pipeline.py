"""
VideoGenerationPipeline Module - New Architecture

This module implements the new pipeline:
1. Content Generator (Gemini API) → transcript + manim code
2. Manim Renderer → video segments (flash-without-dub)
3. edge-tts API → audio + SRT subtitles
4. MoviePy → composite final video

Folder Structure:
  tmp/
    transcript/    → scenes.json, transcripts.json
    manim/
      scripts/    → scene_1.py, scene_2.py, ...
      flash-without-dub/ → 1.mp4, 2.mp4, ...
    audio/        → 1.mp3, 2.mp3, ...
    subtitle/     → 1.srt, 2.srt, ...
    final/        → final_video.mp4
  output/
    final_video.mp4
"""

import argparse
import os
import shutil
from typing import List

import yaml
from PIL import Image
from moviepy.editor import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
)
import json

from src import AppConfig, GeminiClient
from src.content_generator import ContentGenerator
from src.manim_renderer import ManimRenderer
from src.tts.tts import TTSModule


class VideoGenerationPipeline:
    """
    End-to-end pipeline with built-in renderer.
    """

    def __init__(
        self,
        llm_client,
        app_config: AppConfig,
        output_video_name: str = "final_video.mp4",
        final_video_dir: str = "./output",
        tmp_dir: str = "./tmp",
    ):
        self.app_config = app_config
        self.llm_client = llm_client
        self.tmp_dir = tmp_dir
        self.final_video_dir = final_video_dir
        self.video_output_name = output_video_name

        os.makedirs(tmp_dir, exist_ok=True)
        os.makedirs(final_video_dir, exist_ok=True)

        self.fps = 15

        self.content_generator = ContentGenerator(llm_client, output_root=tmp_dir)
        self.manim_renderer = ManimRenderer(
            output_root=os.path.join(tmp_dir, "manim", "flash-without-dub")
        )
        self.tts_module = TTSModule(output_root=tmp_dir)

    def load(self):
        """Initialize heavy resources."""
        self.content_generator.load()
        self.manim_renderer.load()
        self.tts_module.load()

    def run(
        self,
        requirement_prompt: str,
        persona_prompt: str,
    ) -> dict:
        """
        Orchestrates the full generation process from text to MP4.
        """
        # =============================
        # Step 1: Content Generation (Gemini)
        # =============================
        scenes_struct, transcripts = self.content_generator.run(
            requirement_prompt=requirement_prompt,
            persona_prompt=persona_prompt,
        )

        # =============================
        # Step 2: Manim Rendering
        # =============================
        manim_folder = self.manim_renderer.run(scenes_struct)

        video_paths = []
        for idx in range(1, len(scenes_struct) + 1):
            vid_path = os.path.join(manim_folder, f"{idx}.mp4")
            if os.path.exists(vid_path):
                video_paths.append(vid_path)

        if not video_paths:
            print("Warning: No Manim videos generated. Using placeholder.")
            for idx in range(1, len(scenes_struct) + 1):
                placeholder = self._create_placeholder_image(idx, scenes_struct[idx-1].get("description", ""))
                video_paths.append(placeholder)

        # =============================
        # Step 3: TTS Generation (edge-tts)
        # =============================
        audio_dir, subtitle_dir, word_timings = self.tts_module.run(transcripts)

        audio_paths = [
            os.path.join(audio_dir, f"{i}.mp3") for i in range(1, len(transcripts) + 1)
        ]

        # =============================
        # Step 4: Video Compositing
        # =============================
        final_dir = os.path.join(self.tmp_dir, "final")
        os.makedirs(final_dir, exist_ok=True)

        video_clips = []

        for slide_idx in range(len(video_paths)):
            vid_path = video_paths[slide_idx]
            audio_path = audio_paths[slide_idx]

            if not os.path.exists(audio_path):
                print(f"Warning: Audio not found for scene {slide_idx + 1}")
                continue

            audio_clip = AudioFileClip(audio_path).set_fps(44100)
            slide_duration = audio_clip.duration

            if vid_path.endswith(".mp4"):
                base_clip = VideoFileClip(vid_path).set_duration(slide_duration)
            else:
                from moviepy.editor import ImageClip
                base_clip = ImageClip(vid_path).set_duration(slide_duration)

            video_clips.append(base_clip.set_audio(audio_clip))

        if not video_clips:
            raise ValueError("No video clips to composite")

        final_video = concatenate_videoclips(video_clips, method="compose")
        final_output_path = os.path.join(final_dir, self.video_output_name)
        final_video.write_videofile(
            final_output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
        )

        final_video.close()
        for clip in video_clips:
            clip.close()
            if hasattr(clip, "audio") and clip.audio:
                clip.audio.close()

        # =============================
        # Step 5: Copy to output folder
        # =============================
        output_path = os.path.join(self.final_video_dir, self.video_output_name)
        shutil.copy(final_output_path, output_path)

        return {
            "scenes": scenes_struct,
            "transcripts": transcripts,
            "manim_folder": manim_folder,
            "audio_folder": audio_dir,
            "subtitle_folder": subtitle_dir,
            "word_timings": word_timings,
            "final_video_path": output_path,
        }

    def _create_placeholder_image(self, idx: int, description: str) -> str:
        """Create a placeholder image when Manim rendering fails."""
        manim_folder = self.manim_renderer.output_root
        from PIL import Image, ImageDraw, ImageFont

        width, height = 1280, 720
        img = Image.new("RGB", (width, height), color="#1a1a2e")
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()

        draw.text((width // 2 - 100, height // 2 - 50), f"Scene {idx}", fill="white", font=font_title)

        desc_text = (description[:50] + "...") if len(description) > 50 else description
        draw.text((width // 2 - 200, height // 2 + 20), desc_text, fill="#888888", font=font_text)

        placeholder_path = os.path.join(manim_folder, f"{idx}.png")
        img.save(placeholder_path)
        return placeholder_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run pipeline with prompts and video path"
    )

    parser.add_argument(
        "-r",
        "--requirement-prompt",
        type=str,
        default="Explain machine learning basics",
        help="Main requirement prompt",
    )

    parser.add_argument(
        "-p",
        "--persona-prompt",
        type=str,
        default="Friendly instructor",
        help="Persona prompt",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config/default.yaml",
        help="Generation config",
    )

    parser.add_argument(
        "-o",
        "--output-video-name",
        type=str,
        default="final_video.mp4",
        help="Output video file name",
    )

    parser.add_argument(
        "-d",
        "--final-video-dir",
        type=str,
        default=None,
        help="Directory for final video output",
    )

    args = parser.parse_args()

    print("\n=== Input ===")
    print(f"Requirement prompt: {args.requirement_prompt}")
    print(f"Persona prompt: {args.persona_prompt}")

    print("\n=== Loading ===")
    with open(args.config, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        config = AppConfig(**data)

    client = GeminiClient(config.llm)

    pipeline = VideoGenerationPipeline(
        llm_client=client,
        app_config=config,
        output_video_name=args.output_video_name,
        final_video_dir=args.final_video_dir or config.output.final_video_dir,
    )

    pipeline.load()

    print("\n=== Run ===")
    assets = pipeline.run(
        requirement_prompt=args.requirement_prompt,
        persona_prompt=args.persona_prompt,
    )

    print("\n=== Final Output ===")
    print("Final video:", assets["final_video_path"])