import pytest
import os
import tempfile
import asyncio
from unittest.mock import Mock, patch, MagicMock
from src.tts.tts import TTSModule


@pytest.fixture
def tts_module():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield TTSModule(output_root=tmpdir)


class TestTTSModule:
    def test_init(self):
        tts = TTSModule(output_root="/tmp/test")
        assert tts.output_root == "/tmp/test"
        assert tts.is_loaded is False
        assert tts.voice == "en-US-AriaNeural"

    def test_load(self, tts_module):
        tts_module.load()
        assert tts_module.is_loaded is True

    def test_run_without_load_raises(self, tts_module):
        with pytest.raises(AssertionError):
            tts_module.run(["test"])

    def test_cleanup_old_files(self, tts_module):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "audio"), exist_ok=True)
            open(os.path.join(tmpdir, "audio", "1.mp3"), "w").close()
            open(os.path.join(tmpdir, "audio", "2.mp3"), "w").close()
            open(os.path.join(tmpdir, "audio", "other.txt"), "w").close()

            TTSModule._cleanup_old_files(os.path.join(tmpdir, "audio"), "")

            remaining = os.listdir(os.path.join(tmpdir, "audio"))
            assert "other.txt" in remaining
            assert "1.mp3" not in remaining
            assert "2.mp3" not in remaining

    def test_even_distribute_timings(self, tts_module):
        timings = tts_module._even_distribute_timings(4, 8.0)
        assert len(timings) == 4
        assert timings[0] == (0.0, 2.0)
        assert timings[-1] == (6.0, 8.0)

    def test_even_distribute_timings_empty(self, tts_module):
        timings = tts_module._even_distribute_timings(0, 5.0)
        assert timings == []