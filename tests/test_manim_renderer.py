import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from src.manim_renderer import ManimRenderer


@pytest.fixture
def renderer():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ManimRenderer(output_root=tmpdir)


class TestManimRenderer:
    def test_init(self):
        renderer = ManimRenderer(output_root="/tmp/test", quality="low")
        assert renderer.output_root == "/tmp/test"
        assert renderer.quality == "low"
        assert renderer.is_loaded is True

    def test_load(self, renderer):
        renderer.load()

    def test_prepare_manim_code_adds_import(self, renderer):
        code = "circle = Circle()"
        result = renderer._prepare_manim_code(code, 1)
        assert "from manim import *" in result

    def test_prepare_manim_code_keeps_existing_import(self, renderer):
        code = "from manim import *\ncircle = Circle()"
        result = renderer._prepare_manim_code(code, 1)
        assert result.startswith("from manim import *")
        assert "class Scene_1" in result

    def test_prepare_manim_code_wraps_without_class(self, renderer):
        code = "circle = Circle()"
        result = renderer._prepare_manim_code(code, 1)
        assert "class Scene_1" in result
        assert "def construct" in result

    def test_prepare_manim_code_keeps_existing_class(self, renderer):
        code = "from manim import *\nclass MyScene(Scene):\n    pass"
        result = renderer._prepare_manim_code(code, 1)
        assert "class MyScene" in result
        assert "class Scene_1" not in result

    def test_extract_scene_class(self, renderer):
        code = "class MyAwesomeScene(Scene):"
        assert renderer._extract_scene_class(code) == "MyAwesomeScene"

    def test_extract_scene_class_default(self, renderer):
        code = "def construct(self):"
        assert renderer._extract_scene_class(code) == "Scene"

    def test_indent_code(self, renderer):
        code = "line1\n  line2\nline3"
        result = renderer._indent_code(code, 4)
        assert result.startswith("    line1")
        assert "    line2" in result

    def test_run_returns_output_path(self, renderer):
        scenes = [{"manim_code": "from manim import *\nclass Test(Scene):\n    pass"}]
        result = renderer.run(scenes)
        assert result == renderer.output_root