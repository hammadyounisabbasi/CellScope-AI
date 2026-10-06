"""Generate compact BBBC008 domain-shift comparison figures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.vision.analyzer import _segment_improved
from evaluation.external_validation import discover_fields, load_field, robust_channel_normalization


RESULTS = ROOT / "evaluation" / "external_validation_results.json"
OUTPUT = ROOT / "reports" / "external_validation"


def select(rows: list[dict]) -> list[tuple[str, dict]]:
    ordered = sorted(rows, key=lambda row: row["dice"])
    candidates = [
        ("worst", ordered[0]),
        ("median", ordered[len(ordered) // 2]),
        ("best", ordered[-1]),
        ("densest_touching_proxy", max(rows, key=lambda row: row["truth_foreground_fraction"])),
    ]
    seen: set[str] = set()
    output = []
    for label, row in candidates:
        if row["image"] not in seen:
            seen.add(row["image"])
            output.append((label, row))
    return output


def render(label: str, frozen_row: dict, generalized_row: dict, field: dict) -> Path:
    rgb, truth = load_field(field)
    frozen, _ = _segment_improved(rgb)
    normalized = robust_channel_normalization(rgb)
    generalized, _ = _segment_improved(normalized)
    frozen_mask, generalized_mask = frozen > 0, generalized > 0

    def disagreement(prediction: np.ndarray) -> np.ndarray:
        canvas = np.zeros((*truth.shape, 3), dtype=np.uint8)
        canvas[np.logical_and(truth, prediction)] = [36, 190, 150]
        canvas[np.logical_and(truth, ~prediction)] = [245, 158, 11]
        canvas[np.logical_and(~truth, prediction)] = [239, 68, 68]
        return canvas

    panels = [
        rgb,
        rgb[..., 2],
        rgb[..., 1],
        truth,
        frozen_mask,
        disagreement(frozen_mask),
        normalized,
        generalized_mask,
        disagreement(generalized_mask),
    ]
    titles = [
        "Raw composite", "DNA / Hoechst", "Actin / phalloidin", "Ground truth union",
        f"Frozen v2 (Dice {frozen_row['dice']:.3f})", "Frozen agreement / FN / FP",
        "Robust channel normalization", f"Exploratory (Dice {generalized_row['dice']:.3f})",
        "Exploratory agreement / FN / FP",
    ]
    fig, axes = plt.subplots(3, 3, figsize=(12, 12))
    for axis, panel, title in zip(axes.flat, panels, titles, strict=True):
        axis.imshow(panel, cmap="gray" if panel.ndim == 2 else None)
        axis.set_title(title)
        axis.axis("off")
    fig.suptitle(f"BBBC008 {label}: {field['id']}")
    fig.tight_layout()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"{label}_{field['id']}.png"
    fig.savefig(target, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return target


def main() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    frozen = results["frozen_v2"]["per_image"]
    generalized = {row["image"]: row for row in results["generalization_experiment"]["per_image"]}
    fields = {str(field["id"]): field for field in discover_fields()}
    manifest = []
    for label, row in select(frozen):
        target = render(label, row, generalized[row["image"]], fields[row["image"]])
        manifest.append({"category": label, "image": row["image"], "artifact": str(target.relative_to(ROOT)), "frozen": row, "generalization": generalized[row["image"]]})
        print(target)
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
