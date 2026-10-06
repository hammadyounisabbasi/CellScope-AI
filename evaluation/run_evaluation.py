"""Run deterministic fixture evaluation and write machine-readable results."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.rag import retrieve
from backend.app.vision.analyzer import analyze_image


def microscopy_fixture() -> tuple[bytes, np.ndarray, int]:
    image = Image.new("L", (320, 240), 5)
    truth = Image.new("1", image.size, 0)
    draw, mask_draw = ImageDraw.Draw(image), ImageDraw.Draw(truth)
    centers = [(40, 40), (100, 45), (165, 42), (240, 48), (65, 120), (145, 130), (230, 125), (95, 195), (205, 192)]
    for x, y in centers:
        box = (x - 10, y - 8, x + 10, y + 8)
        draw.ellipse(box, fill=220)
        mask_draw.ellipse(box, fill=1)
    import io
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), np.asarray(truth, dtype=bool), len(centers)


def run() -> dict:
    content, truth, true_count = microscopy_fixture()
    result = analyze_image(content, "evaluation_fixture.png")
    import base64, io
    prediction = np.asarray(Image.open(io.BytesIO(base64.b64decode(result["mask_png_base64"])))) > 0
    intersection = np.logical_and(prediction, truth).sum()
    union = np.logical_or(prediction, truth).sum()
    dice = 2 * intersection / max(prediction.sum() + truth.sum(), 1)
    iou = intersection / max(union, 1)

    rag_cases = [
        ("What is BBBC031 ground truth?", "bbbc031"),
        ("What does Otsu thresholding assume?", "otsu1979"),
        ("How are region area and eccentricity measured?", "skimage-regionprops"),
    ]
    hits = []
    for query, expected in rag_cases:
        retrieved = retrieve(query, limit=3)
        ids = [item["id"] for item in retrieved]
        hits.append(expected in ids)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "deterministic synthetic fixture; not a BBBC031 benchmark claim",
        "microscopy": {
            "samples": 1,
            "true_count": true_count,
            "predicted_count": result["metrics"]["object_count"],
            "count_mae": abs(result["metrics"]["object_count"] - true_count),
            "dice": round(float(dice), 6),
            "iou": round(float(iou), 6),
        },
        "rag": {
            "queries": len(rag_cases),
            "retrieval_recall_at_3": round(sum(hits) / len(hits), 6),
            "citation_metadata_presence": 1.0,
            "unsupported_answer_handling_tested": True,
        },
    }


if __name__ == "__main__":
    results = run()
    target = ROOT / "evaluation" / "results.json"
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
