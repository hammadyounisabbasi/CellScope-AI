import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def cell_image() -> bytes:
    image = Image.new("L", (256, 256), 5)
    draw = ImageDraw.Draw(image)
    for x, y in [(45, 50), (100, 60), (170, 48), (62, 140), (140, 150), (205, 180)]:
        draw.ellipse((x - 11, y - 9, x + 11, y + 9), fill=220)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def csv_data() -> bytes:
    rows = ["sample_id,group,area,intensity"]
    for index in range(12):
        rows.append(f"C{index},control,{50 + index % 3},{100 + index}")
    for index in range(12):
        rows.append(f"T{index},treated,{65 + index % 3},{125 + index}")
    return ("\n".join(rows) + "\n").encode()

