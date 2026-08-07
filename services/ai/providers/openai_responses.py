import base64
import json
from time import monotonic

from openai import OpenAI

from services.ai.prompts import ANALYSIS_PROMPT_VERSION, build_analysis_prompt
from services.ai.schemas import ImageAnalysis

from .base import AnalysisProviderResult


class OpenAIResponsesAnalysisProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        client=None,
    ):
        if not api_key and client is None:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        self.model_name = model_name
        self.client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )

    def analyze(self, image_bytes: bytes, *, media_type: str) -> AnalysisProviderResult:
        started = monotonic()
        image_url = f"data:{media_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        response = self.client.responses.create(
            model=self.model_name,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": build_analysis_prompt()},
                        {"type": "input_image", "image_url": image_url, "detail": "low"},
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "bead_image_analysis",
                    "strict": True,
                    "schema": ImageAnalysis.model_json_schema(),
                }
            },
        )
        analysis = ImageAnalysis.model_validate(json.loads(response.output_text))
        return AnalysisProviderResult(
            analysis=analysis,
            provider=self.provider_name,
            model_name=self.model_name,
            prompt_version=ANALYSIS_PROMPT_VERSION,
            latency_ms=max(1, int((monotonic() - started) * 1000)),
        )
