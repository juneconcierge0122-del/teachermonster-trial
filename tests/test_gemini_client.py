import pytest
from unittest.mock import Mock, patch, MagicMock
from src.gemini_client import GeminiClient, ContentGenerationOutput, SceneContent
from src.config_schema import LLMConfig


@pytest.fixture
def llm_config():
    return LLMConfig(
        api_key="test_key",
        default_model="gemini-2.0-flash",
        default_temperature=0.7,
        default_max_tokens=2048,
    )


@pytest.fixture
def client(llm_config):
    return GeminiClient(llm_config)


class TestGeminiClient:
    def test_init(self, client, llm_config):
        assert client.config == llm_config
        assert client.is_loaded is False

    def test_load(self, client):
        client.load()
        assert client.is_loaded is True

    def test_generate_without_load_raises(self, client):
        with pytest.raises(AssertionError):
            client.generate("test prompt")

    @pytest.mark.skip(reason="Requires mock setup for google.genai")
    @patch("google.genai.Client")
    def test_generate(self, mock_client_cls, client):
        client.load()
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_models = Mock()
        mock_models.generate_content.return_value = mock_response
        mock_client_cls.return_value.models = mock_models

        result = client.generate("test prompt")
        assert result == "Test response"

    @pytest.mark.skip(reason="Requires mock setup for google.genai")
    @patch("google.genai.Client")
    def test_generate_with_custom_params(self, mock_client_cls, client):
        client.load()
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_models = Mock()
        mock_models.generate_content.return_value = mock_response
        mock_client_cls.return_value.models = mock_models

        result = client.generate("test prompt", temperature=0.5, max_tokens=1000)
        call_kwargs = mock_models.generate_content.call_args[1]
        assert call_kwargs["config"]["temperature"] == 0.5
        assert call_kwargs["config"]["maxOutputTokens"] == 1000


class TestContentGenerationOutput:
    def test_scene_content_model(self):
        scene = SceneContent(
            transcript="Hello world",
            manim_code="from manim import *",
            description="Test scene"
        )
        assert scene.transcript == "Hello world"
        assert scene.manim_code == "from manim import *"

    def test_content_generation_output(self):
        output = ContentGenerationOutput(
            scenes=[
                SceneContent(transcript="test", manim_code="code", description="desc")
            ]
        )
        assert len(output.scenes) == 1