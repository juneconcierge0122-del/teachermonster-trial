# Teaching Monster

AI-powered educational video generation pipeline using Gemini, Manim, and edge-tts.

## Pipeline Architecture

```
Request → Gemini API → Transcript + Manim Code
       → Manim CLI → Video Segments
       → edge-tts → Audio + SRT
       → MoviePy → Final Video
```

## Folder Structure

```
src/
├── gemini_client.py       # Gemini API wrapper
├── content_generator.py   # Generates transcript + Manim code
├── manim_renderer.py     # Renders Manim code to video
├── server.py             # FastAPI REST API
├── config_schema.py      # Configuration schema
└── tts/
    └── tts.py            # edge-tts for audio + SRT

scripts/
└── T2V_pipeline.py       # Pipeline orchestration

tests/
├── test_gemini_client.py
├── test_manim_renderer.py
└── test_tts.py

config/
└── default.yaml          # Configuration file
```

## APIs Used

| Service | Purpose |
|---------|---------|
| Gemini 2.5 Pro | Content generation (transcript + Manim code) |
| edge-tts | Text-to-speech audio + SRT subtitles |
| Manim CLI | Animation rendering |
| MoviePy | Video compositing |

## Prerequisites

- **Gemini API Key**: Get from [Google AI Studio](https://aistudio.google.com/welcome)
- **Python 3.10+**
- **FFmpeg**: Required for video processing
- **Manim**: `pip install manim`

## Environment Setup

```bash
pip install -r requirements.txt
```

## Running Tests

```bash
pytest tests/ -v
```

## Running the Pipeline

### CLI
```bash
python -m scripts.T2V_pipeline \
  -r "Explain quantum entanglement" \
  -p "Enthusiastic science teacher"
```

### API Server
```bash
uvicorn src.server:app --host 0.0.0.0 --port 8000
```

### API Request
```bash
curl -X POST http://localhost:8000/v1/video/generate \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-001",
    "course_requirement": "Explain quantum entanglement",
    "student_persona": "Curious undergraduate physics student"
  }'
```

## Configuration

Edit `config/default.yaml`:
```yaml
llm:
  provider: gemini
  default_model: gemini-2.5-pro
  default_temperature: 0.7
  default_max_tokens: 8192
  api_key: YOUR_API_KEY

output:
  tmp_dir: ./tmp/
  final_video_dir: ./output
```