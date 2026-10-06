import csv
import zipfile

import numpy as np

from backend.app.vision.analyzer import _segment_improved
from scripts.download_bbbc031 import valid_download


def test_semicolon_ground_truth_validation(tmp_path):
    path = tmp_path / "ground_truth.csv"
    path.write_text(
        "ImageName;CellIdx;LocationX;LocationY;ProcessID\nimage_1;1;10;20;4\n",
        encoding="utf-8",
    )
    assert valid_download("ground-truth", path)


def test_zip_integrity_validation(tmp_path):
    path = tmp_path / "dataset.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Images/example.png", b"content")
    assert valid_download("full", path)


def test_improved_segmenter_preserves_colored_objects():
    rgb = np.zeros((160, 240, 3), dtype=np.uint8)
    yy, xx = np.ogrid[:160, :240]
    for x, y, channel in ((45, 45, 0), (120, 80, 1), (195, 115, 2)):
        rgb[(xx - x) ** 2 + (yy - y) ** 2 <= 14**2, channel] = 220
    labels, threshold = _segment_improved(rgb)
    assert labels.max() == 3
    assert 0 < threshold < 1

