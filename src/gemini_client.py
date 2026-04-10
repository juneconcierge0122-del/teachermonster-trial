from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.config_schema import AppConfig, LLMConfig


class SceneContent(BaseModel):
    """Structured output for a single scene."""
    transcript: str
    manim_code: str
    description: str


class ContentGenerationOutput(BaseModel):
    """Structured output for content generation."""
    scenes: list[SceneContent]


class GeminiClient:
    """
    Simple Gemini wrapper using google-genai.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = genai.Client(api_key=config.api_key)
        self.is_loaded = False

    def load(self):
        """Mark the client as ready (no heavy resources to load)."""
        self.is_loaded = True

    def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from Gemini using a prompt and an image."""
        assert self.is_loaded, "Call load() first"
        from pathlib import Path
        from google.genai import types
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        ext = Path(image_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
        response = self.client.models.generate_content(
            model=model or self.config.default_model,
            contents=[image_part, prompt],
            config={
                "temperature": temperature or self.config.default_temperature,
                "maxOutputTokens": max_tokens or self.config.default_max_tokens,
            },
        )
        return response.text

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from Gemini.

        This is sync and returns raw text.
        If you want structured JSON you would add:
            response_mime_type="application/json",
            response_json_schema=...
        """
        assert self.is_loaded, "Call load() first"

        response = self.client.models.generate_content(
            model=model or self.config.default_model,
            contents=prompt,
            config={
                "temperature": temperature or self.config.default_temperature,
                "maxOutputTokens": max_tokens or self.config.default_max_tokens,
            },
        )
        return response.text

    def generate_content(
        self,
        requirement_prompt: str,
        persona_prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ContentGenerationOutput:
        """
        Generate transcript and Manim code from requirement and persona.
        Uses plain text generation + manual JSON parsing (more compatible).
        """
        assert self.is_loaded, "Call load() first"

        prompt = f"""
You are an expert instructional designer and animation creator.
Generate a teaching video content with the following:

## Requirement
{requirement_prompt}

## Persona
{persona_prompt}

## Output Format
Generate ONLY valid JSON (no markdown, no explanation). Each scene must contain:
- "transcript": The narration script for this scene (natural, conversational)
- "manim_code": Complete Python code for Manim scene (use Manim Community syntax)
- "description": Brief description of what this scene shows

Example format:
{{
  "scenes": [
    {{
      "transcript": "...",
      "manim_code": "...",
      "description": "..."
    }}
  ]
}}

Guidelines for Manim code:
- Use from manim import *
- Define a class inheriting from Scene
- Keep code self-contained and runnable

Guidelines for transcript:
- Match the visual content
- Be engaging and clear
- 2-4 sentences per scene typical
"""
        response = self.client.models.generate_content(
            model=model or self.config.default_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature or self.config.default_temperature,
                max_output_tokens=max_tokens or self.config.default_max_tokens,
            ),
        )
        
        import json
        import re
        
        text = response.text
        
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            return ContentGenerationOutput(**data)
        
        raise ValueError(f"Could not parse JSON from response: {text[:500]}")


if __name__ == "__main__":
    import yaml

    with open("config/default.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        config = AppConfig(**data)

    client = GeminiClient(config.llm)

    client.load()
    assert client.is_loaded, "Client should be marked as loaded"

    prompt = "What is the secret recipe of Gemini?"
    output = client.generate(prompt)
    print(output)

    assert isinstance(output, str), "Output should be a string"
    assert len(output.strip()) > 0, "Output should not be empty"
