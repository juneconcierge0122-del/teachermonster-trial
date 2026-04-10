import os
import json
from typing import List, Tuple

from src.gemini_client import GeminiClient, ContentGenerationOutput


class ContentGenerator:
    """
    Content Generator Module.

    Generates transcript and Manim code from requirement and persona using Gemini.

    Input:
        requirement_prompt: str - Main topic/requirement
        persona_prompt: str - Tone/style description

    Output:
        scenes: List of dicts with transcript, manim_code, description
        transcripts: List of transcript strings
    """

    def __init__(self, llm_client: GeminiClient, output_root: str = "./tmp"):
        self.llm = llm_client
        self.output_root = output_root
        self.is_loaded = False

    def load(self):
        """Load the LLM client."""
        self.llm.load()
        self.is_loaded = True

    def run(
        self,
        requirement_prompt: str,
        persona_prompt: str,
    ) -> Tuple[List[dict], List[str]]:
        """
        Generate content (transcripts and Manim code).

        Returns:
            Tuple of:
                - scenes_struct: List of dicts with {transcript, manim_code, description}
                - transcripts: List of transcript strings
        """
        assert self.is_loaded, "Call load() first"

        result: ContentGenerationOutput = self.llm.generate_content(
            requirement_prompt=requirement_prompt,
            persona_prompt=persona_prompt,
        )

        scenes_struct = []
        transcripts = []

        for scene in result.scenes:
            scenes_struct.append({
                "transcript": scene.transcript,
                "manim_code": scene.manim_code,
                "description": scene.description,
            })
            transcripts.append(scene.transcript)

        self._save_outputs(scenes_struct, transcripts)

        return scenes_struct, transcripts

    def _save_outputs(self, scenes_struct: List[dict], transcripts: List[str]):
        """Save outputs to folder structure."""
        transcript_dir = os.path.join(self.output_root, "transcript")
        manim_scripts_dir = os.path.join(self.output_root, "manim", "scripts")

        os.makedirs(transcript_dir, exist_ok=True)
        os.makedirs(manim_scripts_dir, exist_ok=True)

        with open(os.path.join(transcript_dir, "scenes.json"), "w", encoding="utf-8") as f:
            json.dump(scenes_struct, f, ensure_ascii=False, indent=2)

        with open(os.path.join(transcript_dir, "transcripts.json"), "w", encoding="utf-8") as f:
            json.dump(transcripts, f, ensure_ascii=False, indent=2)

        for idx, scene in enumerate(scenes_struct, start=1):
            script_path = os.path.join(manim_scripts_dir, f"scene_{idx}.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(scene.get("manim_code", ""))