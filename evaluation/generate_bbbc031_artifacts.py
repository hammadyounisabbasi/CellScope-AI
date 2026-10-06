"""Generate a small ranked BBBC031 error-analysis gallery from executed results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from skimage import segmentation

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.bbbc031_benchmark import (
    DATASET_ROOT,
    discover_samples,
    load_ground_truth,
    segment_baseline,
    segment_candidate,
)


RESULTS = ROOT / "evaluation" / "bbbc031_results.json"
OUTPUT = ROOT / "reports" / "bbbc031"


def selected_examples(rows: list[dict]) -> list[tuple[str, dict]]:
    ordered = sorted(rows, key=lambda row: row["dice"])
    candidates = [
        ("worst_dice", ordered[0]),
        ("median_dice", ordered[len(ordered) // 2]),
        ("best_dice", ordered[-1]),
        ("largest_oversegmentation", max(rows, key=lambda row: row["count_error"])),
        ("largest_undersegmentation", min(rows, key=lambda row: row["count_error"])),
    ]
    seen: set[str] = set()
    return [(label, row) for label, row in candidates if not (row["image"] in seen or seen.add(row["image"]))]


def render(label: str, row: dict, config: dict, sample) -> Path:
    rgb = np.asarray(Image.open(sample.image).convert("RGB"))
    truth = load_ground_truth(sample)
    baseline = segment_baseline(rgb)
    improved = segment_candidate(rgb, config)
    prediction = improved > 0
    disagreement = np.zeros((*truth.shape, 3), dtype=np.uint8)
    disagreement[np.logical_and(truth, prediction)] = [36, 190, 150]
    disagreement[np.logical_and(truth, ~prediction)] = [245, 158, 11]
    disagreement[np.logical_and(~truth, prediction)] = [239, 68, 68]

    overlay = rgb.copy()
    overlay[segmentation.find_boundaries(improved, mode="outer")] = [45, 212, 191]
    panels = [rgb, truth, baseline > 0, prediction, overlay, disagreement]
    titles = ["Original RGB", "Ground truth union", "Baseline mask", "Improved mask", "Improved boundaries", "Agreement / FN / FP"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 9))
    for axis, panel, title in zip(axes.flat, panels, titles, strict=True):
        axis.imshow(panel, cmap="gray" if panel.ndim == 2 else None)
        axis.set_title(title)
        axis.axis("off")
    fig.suptitle(
        f"{label}: {sample.name}\nDice={row['dice']:.4f}, IoU={row['iou']:.4f}, "
        f"count={row['predicted_count']}/{row['true_count']}, error={row['count_error']:+d}"
    )
    fig.tight_layout()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"{label}_{sample.name}.png"
    fig.savefig(target, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return target


def main() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    rows = results["improved"]["per_image"]
    config = results["improved"]["configuration"]
    samples = {sample.name: sample for sample in discover_samples()}
    manifest = []
    for label, row in selected_examples(rows):
        target = render(label, row, config, samples[row["image"]])
        manifest.append({"category": label, "image": row["image"], "artifact": str(target.relative_to(ROOT)), "metrics": row})
        print(target)
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
