from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubjectRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def stays_inside_image(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Subject region must stay inside the image.")
        return self


class AnalysisRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid_size: Literal[30, 50, 70]
    color_limit: Literal[12, 18, 24, 30, 36]
    background_mode: Literal["keep", "simplify", "remove"]
    reason: str = Field(min_length=1, max_length=240)


class ImageAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quality_level: Literal["good", "usable", "poor", "unusable"]
    suitability_level: Literal["suitable", "try", "not_suitable", "unprocessable"]
    primary_subject: str = Field(max_length=120)
    subject_count: int = Field(ge=0, le=20)
    subject_region: SubjectRegion
    confidence_level: Literal["high", "medium", "low"]
    issues: list[str] = Field(max_length=3)
    recommendations: AnalysisRecommendation
    requires_subject_confirmation: bool
