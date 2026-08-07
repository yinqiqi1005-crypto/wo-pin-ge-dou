import json
from types import SimpleNamespace

from services.ai.providers.openai_responses import OpenAIResponsesAnalysisProvider

from .test_analysis_schema import valid_analysis_data


class RecordingResponses:
    def __init__(self, output):
        self.output = output
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=json.dumps(self.output, ensure_ascii=False))


def test_openai_provider_sends_image_and_strict_schema_and_parses_result():
    responses = RecordingResponses(valid_analysis_data())
    client = SimpleNamespace(responses=responses)
    provider = OpenAIResponsesAnalysisProvider(
        model_name="configured-model",
        api_key="",
        base_url="https://example.invalid/v1",
        timeout_seconds=1,
        client=client,
    )

    result = provider.analyze(b"image-content", media_type="image/png")

    request = responses.kwargs
    assert request["model"] == "configured-model"
    content = request["input"][0]["content"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True
    assert result.analysis.primary_subject == "一只猫"
