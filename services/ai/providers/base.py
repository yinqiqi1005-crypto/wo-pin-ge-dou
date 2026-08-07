from dataclasses import dataclass
from typing import Protocol

from services.ai.schemas import ImageAnalysis


@dataclass(frozen=True)
class AnalysisProviderResult:
    analysis: ImageAnalysis
    provider: str
    model_name: str
    prompt_version: str
    latency_ms: int
    internal_cost: float = 0


class AnalysisProvider(Protocol):
    provider_name: str
    model_name: str

    def analyze(self, image_bytes: bytes, *, media_type: str) -> AnalysisProviderResult: ...
