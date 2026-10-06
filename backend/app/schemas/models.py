from typing import Any, Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    id: str
    title: str
    url: str
    section: str


class Reliability(BaseModel):
    level: Literal["high", "moderate", "low", "experimental"]
    notes: list[str]


class ImageMetrics(BaseModel):
    object_count: int
    foreground_fraction: float
    density_per_megapixel: float
    mean_area_px: float
    median_area_px: float
    std_area_px: float
    mean_perimeter_px: float
    mean_eccentricity: float
    mean_circularity: float
    mean_intensity: float
    focus_score: float


class ImageAnalysisResponse(BaseModel):
    analysis_id: str
    filename: str
    width: int
    height: int
    method: str
    threshold: float
    metrics: ImageMetrics
    objects: list[dict[str, Any]]
    overlay_png_base64: str
    mask_png_base64: str
    reliability: Reliability
    disclaimer: str


class ExperimentAnalysisResponse(BaseModel):
    analysis_id: str
    filename: str
    rows: int
    columns: int
    schema_summary: dict[str, Any]
    descriptive_statistics: dict[str, Any]
    group_comparisons: list[dict[str, Any]]
    correlations: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    charts: list[dict[str, str]]
    observations: list[str]
    reliability: Reliability
    disclaimer: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    image_analysis: dict[str, Any] | None = None
    experiment_analysis: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]
    sources: list[Source]
    evidence_sufficient: bool
    workflow_trace: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str


class ReportRequest(BaseModel):
    title: str = Field(default="CellScope AI Experiment Report", max_length=200)
    image_analysis: dict[str, Any] | None = None
    experiment_analysis: dict[str, Any] | None = None
    assistant_answer: dict[str, Any] | None = None


class ReportResponse(BaseModel):
    report_id: str
    filename: str
    content_type: str
    html: str
