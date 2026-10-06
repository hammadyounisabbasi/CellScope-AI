from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.agents import answer_question
from backend.app.analytics import analyze_experiment
from backend.app.core.config import get_settings
from backend.app.core.errors import AnalysisError, UploadValidationError
from backend.app.reports import generate_report
from backend.app.schemas import (
    ChatRequest,
    ChatResponse,
    ExperimentAnalysisResponse,
    ImageAnalysisResponse,
    ReportRequest,
    ReportResponse,
)
from backend.app.vision import analyze_image


router = APIRouter(prefix="/api")


def safe_filename(name: str | None) -> str:
    basename = (name or "upload").replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", basename)
    return cleaned[:120] or "upload"


async def read_limited(upload: UploadFile) -> bytes:
    limit = get_settings().max_upload_bytes
    content = await upload.read(limit + 1)
    await upload.close()
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"Upload exceeds {get_settings().max_upload_mb} MB.")
    return content


@router.post("/images/analyze", response_model=ImageAnalysisResponse)
async def image_analysis(file: Annotated[UploadFile, File(...)]) -> dict:
    filename = safe_filename(file.filename)
    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff")):
        raise HTTPException(status_code=415, detail="Use PNG, JPEG, TIF, or TIFF images.")
    try:
        return analyze_image(await read_limited(file), filename)
    except (UploadValidationError, AnalysisError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/analyze", response_model=ExperimentAnalysisResponse)
async def experiment_analysis(file: Annotated[UploadFile, File(...)]) -> dict:
    filename = safe_filename(file.filename)
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Only CSV uploads are supported.")
    try:
        return analyze_experiment(await read_limited(file), filename)
    except (UploadValidationError, AnalysisError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    return answer_question(
        request.question,
        request.image_analysis,
        request.experiment_analysis,
        [turn.model_dump() for turn in request.conversation_history],
    )


@router.post("/reports/generate", response_model=ReportResponse)
def report(request: ReportRequest) -> dict:
    if not any((request.image_analysis, request.experiment_analysis, request.assistant_answer)):
        raise HTTPException(status_code=422, detail="At least one analysis result is required.")
    return generate_report(
        request.title,
        request.image_analysis,
        request.experiment_analysis,
        request.assistant_answer,
    )


@router.get("/system/info")
def system_info() -> dict:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.version,
        "mode": "deterministic-offline",
        "capabilities": ["microscopy", "experiment-statistics", "offline-rag", "reports"],
        "limits": {"max_upload_mb": settings.max_upload_mb, "csv_rows": 100_000},
        "disclaimer": "For research assistance only; not a medical diagnostic system.",
    }
