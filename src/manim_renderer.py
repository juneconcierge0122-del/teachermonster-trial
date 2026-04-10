import os
import re
import subprocess
import shutil
from typing import List, Optional
from pathlib import Path


class ManimRenderer:
    """
    Manim Renderer Module.

    Executes Manim code and produces video segments.

    Input:
        scenes: List of dicts with manim_code for each scene

    Output:
        folder_path: Folder containing rendered video segments (1.mp4, 2.mp4, ...)
    """

    def __init__(self, output_root: str = "./tmp/manim/flash-without-dub", quality: str = "medium"):
        self.output_root = output_root
        self.quality = quality
        self.is_loaded = True

    def load(self):
        """No heavy resources to load."""
        pass

    def _cleanup_old_files(self):
        """Clean up old rendered files."""
        if os.path.exists(self.output_root):
            for fn in os.listdir(self.output_root):
                if fn.endswith((".mp4", ".png", ".json")):
                    try:
                        os.remove(os.path.join(self.output_root, fn))
                    except OSError:
                        pass

    def run(self, scenes: List[dict]) -> str:
        """
        Render Manim scenes to video segments.

        Args:
            scenes: List of dicts with key "manim_code"

        Returns:
            Path to folder containing rendered video files
        """
        os.makedirs(self.output_root, exist_ok=True)
        self._cleanup_old_files()

        for idx, scene in enumerate(scenes, start=1):
            manim_code = scene.get("manim_code", "")
            if not manim_code:
                print(f"Warning: No manim_code for scene {idx}")
                continue

            self._render_scene(manim_code, idx)

        return self.output_root

    def _render_scene(self, manim_code: str, scene_idx: int) -> Optional[str]:
        """Render a single Manim scene."""
        scripts_dir = os.path.join(self.output_root, "..", "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        
        manim_file = os.path.join(scripts_dir, f"scene_{scene_idx}.py")

        full_code = self._prepare_manim_code(manim_code, scene_idx)
        
        with open(manim_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        scene_class = self._extract_scene_class(full_code)
        
        render_cmd = [
            "manim",
            manim_file,
            scene_class,
            "-ql" if self.quality == "low" else "-qm" if self.quality == "medium" else "-qh",
            "--disable_caching",
            "--media_dir", self.output_root,
        ]

        try:
            result = subprocess.run(
                render_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                print(f"Manim render warning for scene {scene_idx}: {result.stderr[:200]}")

            video_path = self._find_rendered_video(scene_class)
            if video_path:
                final_path = os.path.join(self.output_root, f"{scene_idx}.mp4")
                shutil.move(video_path, final_path)
                return final_path

        except subprocess.TimeoutExpired:
            print(f"Manim render timeout for scene {scene_idx}")
        except FileNotFoundError:
            print("Manim not installed. Install with: pip install manim")
        except Exception as e:
            print(f"Manim render error for scene {scene_idx}: {e}")

        return None

    def _prepare_manim_code(self, manim_code: str, scene_idx: int) -> str:
        """Prepare manim code - add imports if missing, handle class wrapping."""
        lines = manim_code.strip().split("\n")
        
        has_import = any("from manim import" in line for line in lines)
        has_class = any(line.strip().startswith("class ") for line in lines)
        
        if not has_import:
            code = "from manim import *\n\n" + manim_code
        else:
            code = manim_code
            
        if has_class:
            return code
        
        return f"""from manim import *

class Scene_{scene_idx}(Scene):
    def construct(self):
{self._indent_code(manim_code, 4)}
"""

    def _extract_scene_class(self, code: str) -> str:
        """Extract the scene class name from code."""
        match = re.search(r'class\s+(\w+)\s*\(', code)
        if match:
            return match.group(1)
        return "Scene"

    def _find_rendered_video(self, scene_class: str) -> Optional[str]:
        """Find the rendered video file for a scene."""
        search_dirs = [
            self.output_root,
            os.path.join(self.output_root, "videos"),
        ]

        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue

            for root, dirs, files in os.walk(search_dir):
                for f in files:
                    if f.endswith(".mp4") and scene_class in f:
                        return os.path.join(root, f)

        return None

    @staticmethod
    def _indent_code(code: str, spaces: int) -> str:
        """Indent code by specified number of spaces."""
        lines = code.split("\n")
        indent = " " * spaces
        return "\n".join(f"{indent}{line}" if line.strip() else line for line in lines)