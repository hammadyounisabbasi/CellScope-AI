"""Reproducible baseline, development search, and held-out BBBC031 evaluation."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from statistics import mean
from typing import Any, Callable

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from skimage import exposure, feature, filters, measure, morphology, segmentation

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.vision.analyzer import _segment, decode_image


PROTOCOL_PATH = ROOT / "evaluation" / "bbbc031_protocol.json"
DATASET_ROOT = ROOT / "data" / "raw" / "bbbc031" / "extracted" / "BBBC031_v1_dataset"
ANNOTATIONS_PATH = ROOT / "data" / "raw" / "bbbc031" / "BBBC031_v1_DatasetGroundTruth.csv"
BASELINE_PATH = ROOT / "evaluation" / "bbbc031_baseline_results.json"
SEARCH_PATH = ROOT / "evaluation" / "bbbc031_dev_search.json"
RESULTS_PATH = ROOT / "evaluation" / "bbbc031_results.json"
WELL_PATTERN = re.compile(r"_w([A-P]\d{2})_")


@dataclass(frozen=True)
class Sample:
    name: str
    well: str
    image: Path
    cell_mask: Path
    nucleus_mask: Path
    points_xy: tuple[tuple[int, int], ...]


def load_protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def discover_samples() -> list[Sample]:
    if not DATASET_ROOT.exists() or not ANNOTATIONS_PATH.exists():
        raise FileNotFoundError("BBBC031 is missing. Run: python scripts/download_bbbc031.py")
    annotations = pd.read_csv(ANNOTATIONS_PATH, sep=";")
    grouped = annotations.groupby("ImageName", sort=True)
    samples: list[Sample] = []
    for name, rows in grouped:
        match = WELL_PATTERN.search(name)
        if not match:
            raise ValueError(f"Cannot parse well from {name}")
        image = DATASET_ROOT / "Images" / f"{name}_CELLMASK.png"
        cell = DATASET_ROOT / "Masks" / f"{name}_CELLMASK.tiff"
        nucleus = DATASET_ROOT / "Masks" / f"{name}_NUCLMASK.tiff"
        missing = [str(path) for path in (image, cell, nucleus) if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing files for {name}: {missing}")
        points = tuple((int(x) - 1, int(y) - 1) for x, y in zip(rows.LocationX, rows.LocationY, strict=True))
        samples.append(Sample(name, match.group(1), image, cell, nucleus, points))
    if len(samples) != 216:
        raise ValueError(f"Expected 216 annotated samples, found {len(samples)}")
    return samples


def load_ground_truth(sample: Sample) -> np.ndarray:
    cell = np.asarray(Image.open(sample.cell_mask)) > 0
    nucleus = np.asarray(Image.open(sample.nucleus_mask)) > 0
    if cell.shape != nucleus.shape:
        raise ValueError(f"Mask shape mismatch for {sample.name}")
    return np.logical_or(cell, nucleus)


def segment_baseline(rgb: np.ndarray) -> np.ndarray:
    import io

    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="PNG")
    _, gray = decode_image(buffer.getvalue())
    labels, _ = _segment(gray)
    return labels


def segment_candidate(rgb: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    signal = rgb.astype(np.float32).max(axis=2) / 255.0
    signal = exposure.rescale_intensity(signal, out_range=(0.0, 1.0))
    sigma = float(config["gaussian_sigma"])
    if sigma > 0:
        signal = filters.gaussian(signal, sigma=sigma, preserve_range=True)
    threshold = float(filters.threshold_otsu(signal))
    binary = signal > threshold
    minimum = int(config["minimum_object_size"])
    binary = morphology.remove_small_objects(binary, min_size=minimum)
    binary = morphology.remove_small_holes(binary, area_threshold=minimum)
    binary = morphology.binary_opening(binary, morphology.disk(1))
    distance = ndi.distance_transform_edt(binary)
    coordinates = feature.peak_local_max(
        filters.gaussian(distance, sigma=1.0),
        min_distance=int(config["peak_min_distance"]),
        labels=binary,
        exclude_border=False,
    )
    markers = np.zeros(binary.shape, dtype=np.int32)
    if coordinates.size:
        markers[tuple(coordinates.T)] = np.arange(1, len(coordinates) + 1)
    markers = measure.label(markers > 0)
    labels = segmentation.watershed(-distance, markers, mask=binary) if markers.max() else measure.label(binary)
    labels = morphology.remove_small_objects(labels, min_size=minimum)
    return measure.label(labels > 0)


def image_metrics(sample: Sample, labels: np.ndarray, truth: np.ndarray, seconds: float) -> dict[str, Any]:
    prediction = labels > 0
    tp = int(np.logical_and(prediction, truth).sum())
    fp = int(np.logical_and(prediction, ~truth).sum())
    fn = int(np.logical_and(~prediction, truth).sum())
    predicted_count = int(labels.max())
    true_count = len(sample.points_xy)
    dice = 2 * tp / max(2 * tp + fp + fn, 1)
    iou = tp / max(tp + fp + fn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)

    center_labels = [int(labels[y, x]) for x, y in sample.points_xy]
    detected_centers = [label for label in center_labels if label > 0]
    unique_matches, match_counts = np.unique(detected_centers, return_counts=True)
    matched_predictions = len(unique_matches)
    point_recall = len(detected_centers) / max(true_count, 1)
    object_precision = matched_predictions / max(predicted_count, 1)
    detection_f1 = 2 * point_recall * object_precision / max(point_recall + object_precision, 1e-12)
    merged_objects = int((match_counts > 1).sum()) if len(match_counts) else 0
    error = predicted_count - true_count
    return {
        "image": sample.name,
        "well": sample.well,
        "true_count": true_count,
        "predicted_count": predicted_count,
        "count_error": error,
        "absolute_count_error": abs(error),
        "absolute_percentage_count_error": abs(error) / max(true_count, 1),
        "dice": round(dice, 8),
        "iou": round(iou, 8),
        "foreground_precision": round(precision, 8),
        "foreground_recall": round(recall, 8),
        "point_recall": round(point_recall, 8),
        "object_precision": round(object_precision, 8),
        "detection_f1": round(detection_f1, 8),
        "merged_objects": merged_objects,
        "merged_object_rate": round(merged_objects / max(predicted_count, 1), 8),
        "oversegmentation_rate": round(max(error, 0) / max(true_count, 1), 8),
        "undersegmentation_rate": round(max(-error, 0) / max(true_count, 1), 8),
        "runtime_seconds": round(seconds, 6),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    mean_fields = [
        "dice", "iou", "foreground_precision", "foreground_recall",
        "absolute_count_error", "absolute_percentage_count_error", "point_recall",
        "object_precision", "detection_f1", "merged_object_rate",
        "oversegmentation_rate", "undersegmentation_rate",
    ]
    result = {f"mean_{field}": round(mean(float(row[field]) for row in rows), 8) for field in mean_fields}
    errors = np.array([row["count_error"] for row in rows], dtype=float)
    runtimes = np.array([row["runtime_seconds"] for row in rows], dtype=float)
    result.update(
        {
            "images": len(rows),
            "count_mae": result.pop("mean_absolute_count_error"),
            "count_rmse": round(float(np.sqrt(np.mean(errors**2))), 8),
            "count_mape": result.pop("mean_absolute_percentage_count_error"),
            "mean_predicted_count": round(mean(row["predicted_count"] for row in rows), 8),
            "runtime_total_seconds": round(float(runtimes.sum()), 6),
            "runtime_mean_seconds": round(float(runtimes.mean()), 6),
            "runtime_p95_seconds": round(float(np.percentile(runtimes, 95)), 6),
        }
    )
    return result


def evaluate(
    samples: list[Sample],
    segmenter: Callable[[np.ndarray], np.ndarray],
    label: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for index, sample in enumerate(samples, start=1):
        try:
            rgb = np.asarray(Image.open(sample.image).convert("RGB"))
            truth = load_ground_truth(sample)
            started = time.perf_counter()
            labels = segmenter(rgb)
            elapsed = time.perf_counter() - started
            if labels.shape != truth.shape:
                raise ValueError(f"Prediction shape {labels.shape} != truth shape {truth.shape}")
            rows.append(image_metrics(sample, labels, truth, elapsed))
        except Exception as exc:  # retain per-sample failures in machine output
            failures.append({"image": sample.name, "error": f"{type(exc).__name__}: {exc}"})
        if index % 10 == 0 or index == len(samples):
            print(f"\r{label}: {index}/{len(samples)}", end="", flush=True)
    print()
    return rows, failures


def subset(samples: list[Sample], wells: list[str]) -> list[Sample]:
    wanted = set(wells)
    return [sample for sample in samples if sample.well in wanted]


def metadata(protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": protocol["dataset"],
        "protocol_file": "evaluation/bbbc031_protocol.json",
        "protocol_version": protocol["protocol_version"],
    }


def run_baseline() -> None:
    protocol, samples = load_protocol(), discover_samples()
    dev = subset(samples, protocol["split"]["development_wells"])
    test = subset(samples, protocol["split"]["held_out_test_wells"])
    dev_rows, dev_failures = evaluate(dev, segment_baseline, "baseline development")
    test_rows, test_failures = evaluate(test, segment_baseline, "baseline held-out test")
    output = {
        **metadata(protocol),
        "algorithm": "production_v1_baseline",
        "configuration": protocol["baseline"]["configuration"],
        "development": {"aggregate": aggregate(dev_rows), "per_image": dev_rows},
        "held_out_test": {"aggregate": aggregate(test_rows), "per_image": test_rows},
        "failures": dev_failures + test_failures,
    }
    BASELINE_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"development": output["development"]["aggregate"], "held_out_test": output["held_out_test"]["aggregate"], "failures": len(output["failures"])}, indent=2))


def run_tuning() -> None:
    protocol, samples = load_protocol(), discover_samples()
    dev = subset(samples, protocol["split"]["development_wells"])
    search = protocol["development_only_search"]
    configs = [
        {"signal": "max_rgb", "gaussian_sigma": sigma, "minimum_object_size": size, "peak_min_distance": distance}
        for sigma, size, distance in product(search["gaussian_sigma"], search["minimum_object_size"], search["peak_min_distance"])
    ]
    candidates = []
    for index, config in enumerate(configs, start=1):
        rows, failures = evaluate(dev, lambda rgb, c=config: segment_candidate(rgb, c), f"candidate {index}/{len(configs)}")
        summary = aggregate(rows)
        score = summary["mean_dice"] + 0.25 * (1 - min(summary["count_mape"], 1.0))
        candidates.append({"configuration": config, "selection_score": round(score, 8), "aggregate": summary, "failures": failures})
    candidates.sort(key=lambda item: (-item["selection_score"], item["aggregate"]["count_mae"], item["aggregate"]["runtime_mean_seconds"], json.dumps(item["configuration"], sort_keys=True)))
    output = {**metadata(protocol), "selection_uses": "development wells only", "candidates": candidates, "selected": candidates[0]}
    SEARCH_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["selected"], indent=2))


def run_final() -> None:
    if not BASELINE_PATH.exists() or not SEARCH_PATH.exists():
        raise FileNotFoundError("Run --stage baseline and --stage tune before final evaluation.")
    protocol, samples = load_protocol(), discover_samples()
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    search = json.loads(SEARCH_PATH.read_text(encoding="utf-8"))
    selected = search["selected"]["configuration"]
    test = subset(samples, protocol["split"]["held_out_test_wells"])
    rows, failures = evaluate(test, lambda rgb: segment_candidate(rgb, selected), "improved held-out test")
    output = {
        **metadata(protocol),
        "scope": "Real BBBC031 v1 benchmark; simulated microscopy benchmark, not clinical validation",
        "images_available": len(samples),
        "development_images": protocol["split"]["development_images"],
        "held_out_test_images": protocol["split"]["held_out_test_images"],
        "baseline": {
            "algorithm": baseline["algorithm"],
            "configuration": baseline["configuration"],
            "development": baseline["development"]["aggregate"],
            "held_out_test": baseline["held_out_test"]["aggregate"],
            "per_image": baseline["held_out_test"]["per_image"],
        },
        "improved": {
            "algorithm": "max-RGB Otsu + morphology + peak-local-max watershed",
            "configuration": selected,
            "development": search["selected"]["aggregate"],
            "held_out_test": aggregate(rows),
            "per_image": rows,
        },
        "failures": baseline["failures"] + failures,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"baseline_test": output["baseline"]["held_out_test"], "improved_test": output["improved"]["held_out_test"], "failures": len(output["failures"])}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["baseline", "tune", "final"])
    args = parser.parse_args()
    {"baseline": run_baseline, "tune": run_tuning, "final": run_final}[args.stage]()
