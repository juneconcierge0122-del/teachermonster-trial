"""
FastAPI server for video generation API.

This server implements the POST /v1/video/generate endpoint.

New Architecture (all API-based):
1. Gemini API → transcript + manim code
2. Manim CLI → video segments
3. edge-tts API → audio (no ASR)
4. MoviePy → final video
"""

import asyncio
import os
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from scripts.T2V_pipeline import VideoGenerationPipeline
from src import AppConfig, GeminiClient


# =============================
# Request/Response Models
# =============================


class VideoGenerateRequest(BaseModel):
    request_id: str
    course_requirement: str
    student_persona: str


class VideoGenerateResponse(BaseModel):
    video_url: str
    subtitle_url: str
    supplementary_url: Optional[str] = None


# =============================
# Helper Functions
# =============================


def format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_subtitle(
    scripts: list[str],
    word_timings: list[list[tuple[float, float]]],
    output_path: str,
) -> str:
    """
    Generate SRT subtitle file from scripts and word timings.

    Args:
        scripts: List of narration scripts, one per slide
        word_timings: List of word timings per slide, where each timing is (start, end)
        output_path: Path where SRT file should be saved

    Returns:
        Path to the generated SRT file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    subtitle_entries = []
    entry_index = 1
    cumulative_time = 0.0

    for _slide_idx, (script, timings) in enumerate(
        zip(scripts, word_timings, strict=True)
    ):
        words = script.split()

        if not words or not timings:
            continue

        # Group words into phrases for better readability
        # For simplicity, we'll create one subtitle entry per slide
        # You can modify this to group words more intelligently
        slide_start = cumulative_time
        slide_end = cumulative_time

        # Find the end time of the last word in this slide
        if timings:
            slide_end = max(end for _, end in timings) + cumulative_time

        # Create subtitle entry for this slide
        start_time = format_srt_time(slide_start)
        end_time = format_srt_time(slide_end)

        subtitle_entries.append(
            f"{entry_index}\n{start_time} --> {end_time}\n{script}\n\n"
        )

        entry_index += 1
        cumulative_time = slide_end

    # Write SRT file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(subtitle_entries))

    return output_path


# =============================
# FastAPI App
# =============================

app = FastAPI(
    title="Teaching Video Generation API",
    version="1.0.0",
    description=(
        "API for generating teaching videos based on course requirements and student personas"
    ),
)

# Global pipeline instance (loaded once at startup)
pipeline: Optional[VideoGenerationPipeline] = None
app_config: Optional[AppConfig] = None


@app.on_event("startup")
async def startup_event():
    """Load pipeline and models on server startup."""
    global pipeline, app_config

    # Load config
    config_path = os.getenv("CONFIG_PATH", "config/default.yaml")
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        app_config = AppConfig(**data)

    # Initialize client and pipeline
    client = GeminiClient(app_config.llm)
    pipeline = VideoGenerationPipeline(
        llm_client=client,
        app_config=app_config,
        output_video_name="final_video.mp4",  # Will be overridden per request
    )

    # Load all models (this may take time)
    print("Loading pipeline models...")
    pipeline.load()
    print("Pipeline loaded successfully!")


@app.post("/v1/video/generate", response_model=VideoGenerateResponse)
async def generate_video(request: VideoGenerateRequest, ori_req: Request):
    """
    Generate a teaching video based on course requirements and student persona.

    This endpoint:
    1. Generates video outlines
    2. Creates slides
    3. Generates TTS audio
    4. Creates cursor trajectories
    5. Renders final MP4 video
    6. Generates SRT subtitles
    """
    if ori_req.headers.get("X-Dry-Run") == "true":
        print("[Log] Dry Run / Connection Test received.")
        return {
            "video_url": "https://example.com/test.mp4",
            "subtitle_url": "https://example.com/test.srt",
            "supplementary_url": None
        }
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not loaded")

    try:
        # Create output directory for this request
        output_config = app_config.output if app_config else None
        output_base = (
            output_config.final_video_dir if output_config else None
        ) or "./output"

        request_output_dir = os.path.join(output_base, request.request_id)
        os.makedirs(request_output_dir, exist_ok=True)

        # Create a pipeline instance for this request with unique output paths
        request_pipeline = VideoGenerationPipeline(
            llm_client=pipeline.llm_client,
            app_config=app_config,
            output_video_name=f"{request.request_id}.mp4",
            final_video_dir=request_output_dir,
        )
        request_pipeline.load()

        # Run pipeline (this is CPU/IO intensive, so we run it in a thread pool)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            request_pipeline.run,
            request.course_requirement,  # requirement_prompt
            request.student_persona,  # persona_prompt
        )

        # Generate subtitle file
        subtitle_path = os.path.join(request_output_dir, f"{request.request_id}.srt")
        generate_srt_subtitle(
            scripts=result["scripts"],
            word_timings=result["word_timings"],
            output_path=subtitle_path,
        )

        # Generate supplementary PDF if slides are available
        supplementary_url = None
        slides_folder = result.get("slides_folder")
        if slides_folder and os.path.exists(slides_folder):
            # For now, we'll just reference the slides folder
            # In production, you might want to create a PDF from the slides
            supplementary_url = f"/v1/files/{request.request_id}/slides"

        # Construct URLs (in production, these would be actual storage URLs)
        # For now, we'll use relative paths that can be served via file endpoints
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        video_url = f"{base_url}/v1/files/{request.request_id}/video"
        subtitle_url = f"{base_url}/v1/files/{request.request_id}/subtitle"

        return VideoGenerateResponse(
            video_url=video_url,
            subtitle_url=subtitle_url,
            supplementary_url=supplementary_url,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Video generation failed: {str(e)}"
        ) from e


@app.get("/v1/files/{request_id}/video")
async def get_video(request_id: str):
    """Serve the generated video file."""
    output_config = app_config.output if app_config else None
    output_base = (
        output_config.final_video_dir if output_config else None
    ) or "./output"

    video_path = os.path.join(output_base, request_id, f"{request_id}.mp4")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"{request_id}.mp4",
    )


@app.get("/v1/files/{request_id}/subtitle")
async def get_subtitle(request_id: str):
    """Serve the generated subtitle file."""
    output_config = app_config.output if app_config else None
    output_base = (
        output_config.final_video_dir if output_config else None
    ) or "./output"

    subtitle_path = os.path.join(output_base, request_id, f"{request_id}.srt")

    if not os.path.exists(subtitle_path):
        raise HTTPException(status_code=404, detail="Subtitle not found")

    return FileResponse(
        subtitle_path,
        media_type="text/srt",
        filename=f"{request_id}.srt",
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "pipeline_loaded": pipeline is not None,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
