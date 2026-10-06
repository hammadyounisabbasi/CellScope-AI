"""Evaluate frozen CellScope v2 on real BBBC008 fluorescence microscopy."""

from __future__ import annotations

import json
import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.vision.analyzer import _segment_improved


DATA_ROOT = ROOT / "data" / "raw" / "bbbc008" / "extracted"
PROTOCOL = ROOT / "evaluation" / "external_validation_protocol.json"
RESULTS = ROOT / "evaluation" / "external_validation_results.json"
FIELD_PATTERN = re.compile(r"(.+)_channel([13])\.tif$", re.IGNORECASE)


def _scientific_tiffs(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.tif") if "__MACOSX" not in path.parts and not path.name.startswith("._"))


def discover_fields() -> list[dict[str, Path | str]]:
    image_files = _scientific_tiffs(DATA_ROOT / "images")
    mask_files = _scientific_tiffs(DATA_ROOT / "foreground")
    images: dict[tuple[str, str], Path] = {}
    masks: dict[tuple[str, str], Path] = {}
    for collection, files in ((images, image_files), (masks, mask_files)):
        for path in files:
            match = FIELD_PATTERN.match(path.name)
            if not match:
                continue
            collection[(match.group(1), match.group(2))] = path
    field_ids = sorted({key[0] for key in images} | {key[0] for key in masks})
    fields: list[dict[str, Path | str]] = []
    for field_id in field_ids:
        needed = {
            "dna_image": images.get((field_id, "1")),
            "actin_image": images.get((field_id, "3")),
            "dna_mask": masks.get((field_id, "1")),
            "actin_mask": masks.get((field_id, "3")),
        }
        missing = [name for name, path in needed.items() if path is None]
        if missing:
            raise FileNotFoundError(f"Incomplete BBBC008 field {field_id}: {missing}")
        fields.append({"id": field_id, **needed})
    if len(fields) != 12:
        raise ValueError(f"Expected 12 complete BBBC008 fields, found {len(fields)}")
    return fields


def load_field(field: dict[str, Path | str]) -> tuple[np.ndarray, np.ndarray]:
    dna = np.asarray(Image.open(field["dna_image"]).convert("L"))
    actin = np.asarray(Image.open(field["actin_image"]).convert("L"))
    dna_mask = np.asarray(Image.open(field["dna_mask"])) > 0
    actin_mask = np.asarray(Image.open(field["actin_mask"])) > 0
    shapes = {dna.shape, actin.shape, dna_mask.shape, actin_mask.shape}
    if len(shapes) != 1:
        raise ValueError(f"Dimension mismatch for {field['id']}: {sorted(shapes)}")
    rgb = np.zeros((*dna.shape, 3), dtype=np.uint8)
    rgb[..., 1] = actin
    rgb[..., 2] = dna
    return rgb, np.logical_or(dna_mask, actin_mask)


def metric_row(field_id: str, prediction: np.ndarray, truth: np.ndarray, runtime: float) -> dict[str, Any]:
    tp = int(np.logical_and(prediction, truth).sum())
    fp = int(np.logical_and(prediction, ~truth).sum())
    fn = int(np.logical_and(~prediction, truth).sum())
    dice = 2 * tp / max(2 * tp + fp + fn, 1)
    iou = tp / max(tp + fp + fn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "image": field_id,
        "dice": round(dice, 8),
        "iou": round(iou, 8),
        "foreground_precision": round(precision, 8),
        "foreground_recall": round(recall, 8),
        "truth_foreground_fraction": round(float(truth.mean()), 8),
        "predicted_foreground_fraction": round(float(prediction.mean()), 8),
        "runtime_seconds": round(runtime, 6),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = ["dice", "iou", "foreground_precision", "foreground_recall", "truth_foreground_fraction", "predicted_foreground_fraction"]
    runtimes = np.array([row["runtime_seconds"] for row in rows])
    return {
        "images": len(rows),
        **{f"mean_{metric}": round(mean(row[metric] for row in rows), 8) for metric in metrics},
        "runtime_total_seconds": round(float(runtimes.sum()), 6),
        "runtime_mean_seconds": round(float(runtimes.mean()), 6),
        "runtime_p95_seconds": round(float(np.percentile(runtimes, 95)), 6),
    }


def evaluate(segmenter: Callable[[np.ndarray], np.ndarray], label: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    fields = discover_fields()
    for index, field in enumerate(fields, start=1):
        try:
            rgb, truth = load_field(field)
            started = time.perf_counter()
            labels = segmenter(rgb)
            runtime = time.perf_counter() - started
            rows.append(metric_row(str(field["id"]), labels > 0, truth, runtime))
        except Exception as exc:
            failures.append({"image": str(field["id"]), "error": f"{type(exc).__name__}: {exc}"})
        print(f"\r{label}: {index}/{len(fields)}", end="", flush=True)
    print()
    return {"aggregate": aggregate(rows), "per_image": rows, "failures": failures}


def frozen_segmenter(rgb: np.ndarray) -> np.ndarray:
    labels, _ = _segment_improved(rgb)
    return labels


def robust_channel_normalization(rgb: np.ndarray) -> np.ndarray:
    """Normalize each nonempty fluorescence channel using robust percentiles."""
    normalized = np.zeros_like(rgb)
    for channel_index in range(rgb.shape[2]):
        channel = rgb[..., channel_index].astype(np.float32)
        if not np.any(channel):
            continue
        low, high = np.percentile(channel, (1.0, 99.5))
        if high <= low:
            continue
        scaled = np.clip((channel - low) / (high - low), 0, 1)
        normalized[..., channel_index] = np.round(scaled * 255).astype(np.uint8)
    return normalized


def generalized_segmenter(rgb: np.ndarray) -> np.ndarray:
    labels, _ = _segment_improved(robust_channel_normalization(rgb))
    return labels


def run_frozen() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    frozen = evaluate(frozen_segmenter, "frozen v2")
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "External real-microscopy semantic validation; not clinical validation",
        "dataset": protocol["dataset"],
        "protocol_file": "evaluation/external_validation_protocol.json",
        "frozen_config": "evaluation/cellscope_v2_config.json",
        "frozen_v2": frozen,
        "generalization_experiment": None,
    }
    RESULTS.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(frozen["aggregate"], indent=2))
    if frozen["failures"]:
        print(json.dumps(frozen["failures"], indent=2))


def run_generalization() -> None:
    if not RESULTS.is_file():
        raise FileNotFoundError("Run frozen external evaluation before the generalization experiment.")
    output = json.loads(RESULTS.read_text(encoding="utf-8"))
    if "frozen_v2" not in output:
        raise ValueError("Frozen v2 results are missing and will not be inferred or overwritten.")
    experiment = evaluate(generalized_segmenter, "robust-channel experiment")
    output["generalization_experiment"] = {
        "name": "CellScope v2 + per-channel robust normalization",
        "status": "post-hoc exploratory; not production and not independent validation",
        "preprocessing": "For each nonempty channel: subtract 1st percentile, divide by 99.5th minus 1st percentile, clip to [0,1], convert to uint8. Then run frozen v2 unchanged.",
        **experiment,
    }
    RESULTS.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(experiment["aggregate"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["frozen", "generalization"], default="frozen")
    args = parser.parse_args()
    {"frozen": run_frozen, "generalization": run_generalization}[args.stage]()
