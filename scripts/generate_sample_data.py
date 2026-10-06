"""Generate deterministic sample microscopy and CSV data for demos and tests."""

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"


def generate() -> None:
    SAMPLE.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    image = Image.new("L", (640, 420), color=8)
    draw = ImageDraw.Draw(image)
    for _ in range(58):
        x = int(rng.integers(20, 620))
        y = int(rng.integers(20, 400))
        rx = int(rng.integers(6, 14))
        ry = int(rng.integers(6, 14))
        intensity = int(rng.integers(150, 245))
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=intensity)
    noise = rng.normal(0, 5, (420, 640))
    array = np.clip(np.asarray(image.filter(ImageFilter.GaussianBlur(1.2))) + noise, 0, 255).astype("uint8")
    Image.fromarray(array).save(SAMPLE / "synthetic_cells.png")

    rows = []
    for group, shift in (("control", 0.0), ("treated", 9.0)):
        for index in range(30):
            rows.append(
                {
                    "sample_id": f"{group[:1].upper()}{index + 1:02d}",
                    "group": group,
                    "cell_area": round(float(rng.normal(80 + shift, 8)), 3),
                    "circularity": round(float(np.clip(rng.normal(0.82 - shift / 100, 0.05), 0, 1)), 4),
                    "intensity": round(float(rng.normal(120 + shift * 1.5, 12)), 3),
                }
            )
    pd.DataFrame(rows).to_csv(SAMPLE / "experiment.csv", index=False)


if __name__ == "__main__":
    generate()
    print(f"Sample data written to {SAMPLE}")

