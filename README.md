# Teaching Monster

## Pipeline Architecture

```
Request → ngrok → FastAPI (Pod)
         → Gemini API → Transcript + Manim Code
         → Manim CLI → Video Segments (flash-without-dub)
         → edge-tts API → Audio + SRT
         → MoviePy → Final Video → Response
```

## Folder Structure

```
tmp/
├── transcript/                   # 文字稿
│   ├── scenes.json              # Gemini 回傳的完整結構
│   └── transcripts.json         # 純文字稿陣列
│
├── manim/                        # Manim 相關
│   ├── scripts/                 # LLM 生成的程式碼
│   │   ├── scene_1.py
│   │   ├── scene_2.py
│   │   └── ...
│   └── flash-without-dub/       # 原始影片（無配音）
│       ├── 1.mp4
│       ├── 2.mp4
│       └── ...
│
├── audio/                       # TTS 音訊
│   ├── 1.mp3
│   ├── 2.mp3
│   └── ...
│
├── subtitle/                    # SRT 字幕
│   ├── 1.srt
│   ├── 2.srt
│   └── ...
│
└── final/                       # 最終合成（中繼）
    └── final_video.mp4

output/                         # 最終輸出
└── final_video.mp4
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
pip install edge-tts
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

output:
  tmp_dir: ./tmp/
  final_video_dir: ./output
```

## Module Structure

| Module | Description |
|--------|-------------|
| `src/gemini_client.py` | Gemini API wrapper |
| `src/content_generator.py` | Generates transcript + Manim code |
| `src/manim_renderer.py` | Renders Manim code to video |
| `src/tts/tts.py` | edge-tts for audio + SRT |
| `scripts/T2V_pipeline.py` | Pipeline orchestration |
| `src/server.py` | FastAPI REST API |