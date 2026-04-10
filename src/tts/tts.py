import asyncio
import os
import wave
from typing import List, Tuple

import numpy as np
import edge_tts


class TTSModule:
    """
    Text-to-Speech module using edge-tts.
    Uses SubMaker to generate audio + SRT simultaneously.

    Input:
        list[str]: Each string is narration for one scene.

    Output:
        audio_dir: Folder containing audio files (1.mp3, 2.mp3, ...)
        subtitle_dir: Folder containing SRT files (1.srt, 2.srt, ...)
        timings: List of word timings (evenly distributed)
    """

    def __init__(self, output_root: str = "./tmp"):
        self.output_root = output_root
        self.is_loaded = False
        self.voice = "en-US-AriaNeural"

    def load(self):
        self.is_loaded = True

    @staticmethod
    def _cleanup_old_files(output_dir: str, prefix: str):
        os.makedirs(output_dir, exist_ok=True)
        for fn in os.listdir(output_dir):
            if fn.startswith(prefix) and (fn.endswith(".mp3") or fn.endswith(".srt")):
                try:
                    os.remove(os.path.join(output_dir, fn))
                except OSError:
                    pass

    @staticmethod
    def _write_dummy_audio(path_mp3: str, duration_sec: float) -> None:
        import struct
        sr = 22050
        n = max(1, int(duration_sec * sr))
        amp = 0.2
        freq = 440.0
        with wave.open(path_mp3, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            for i in range(n):
                t = i / sr
                s = amp * np.sin(2 * np.pi * freq * t)
                wf.writeframes(struct.pack("<h", int(s * 32767)))

    async def _generate_audio_with_srt_async(self, text: str, output_base: str):
        """Generate audio and SRT using SubMaker."""
        communicate = edge_tts.Communicate(text, self.voice, boundary="SentenceBoundary")
        submaker = edge_tts.SubMaker()
        audio_bytes = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.append(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)

        mp3_path = output_base + ".mp3"
        srt_path = output_base + ".srt"

        with open(mp3_path, "wb") as f:
            for b in audio_bytes:
                f.write(b)

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(submaker.get_srt())

        return mp3_path, srt_path

    def _generate_audio_with_srt(self, text: str, output_base: str) -> Tuple[str, str]:
        """Sync wrapper for async generation."""
        return asyncio.run(self._generate_audio_with_srt_async(text, output_base))

    def _get_audio_duration(self, mp3_path: str) -> float:
        try:
            import soundfile as sf
            import subprocess
            
            wav_path = mp3_path + ".wav"
            subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, "-ar", "16000", "-ac", "1", wav_path],
                capture_output=True,
                check=True,
            )
            data, sr = sf.read(wav_path)
            duration = float(len(data)) / float(sr)
            os.remove(wav_path)
            return duration
        except:
            return 3.0

    def _even_distribute_timings(self, word_count: int, total_duration: float) -> List[Tuple[float, float]]:
        """Evenly distribute word timings."""
        if word_count == 0:
            return []
        per_word = total_duration / word_count
        return [(i * per_word, (i + 1) * per_word) for i in range(word_count)]

    def run(self, scripts: List[str]) -> Tuple[str, str, List[List[Tuple[float, float]]]]:
        """
        Generate TTS audio with SRT subtitles.

        Returns:
            Tuple of:
                - audio_dir: Path to folder with mp3 files
                - subtitle_dir: Path to folder with srt files
                - timings: List of word timings per scene
        """
        assert self.is_loaded, "Call load() before run()"

        audio_dir = os.path.join(self.output_root, "audio")
        subtitle_dir = os.path.join(self.output_root, "subtitle")

        self._cleanup_old_files(audio_dir, "")
        self._cleanup_old_files(subtitle_dir, "")

        all_timings: List[List[Tuple[float, float]]] = []

        for idx, script in enumerate(scripts, start=1):
            mp3_path = os.path.join(audio_dir, f"{idx}.mp3")
            srt_path = os.path.join(subtitle_dir, f"{idx}.srt")
            output_base = os.path.join(audio_dir, str(idx))

            if not isinstance(script, str) or script.strip() == "":
                self._write_dummy_audio(mp3_path, 0.25)
                all_timings.append([])
                continue

            try:
                self._generate_audio_with_srt(script, output_base)

                if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) <= 0:
                    duration = 3.0
                    self._write_dummy_audio(mp3_path, duration)
                else:
                    duration = self._get_audio_duration(mp3_path)

                word_count = len(script.split())
                timings = self._even_distribute_timings(word_count, duration)
                all_timings.append(timings)

            except Exception as e:
                print(f"TTS error for scene {idx}: {e}")
                self._write_dummy_audio(mp3_path, 3.0)
                words = script.split()
                if words:
                    total = 3.0
                    per = total / len(words)
                    timings = [(i * per, (i + 1) * per) for i in range(len(words))]
                else:
                    timings = []
                all_timings.append(timings)

        return audio_dir, subtitle_dir, all_timings