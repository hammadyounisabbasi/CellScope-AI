from __future__ import annotations

import base64
import io
import math
import uuid
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from skimage import color, exposure, feature, filters, measure, morphology, segmentation
from scipy import ndimage as ndi

from backend.app.core.errors import AnalysisError, UploadValidationError


SUPPORTED_IMAGE_FORMATS = {"PNG", "JPEG", "TIFF"}


def _png_b64(array: np.ndarray, mode: str | None = None) -> str:
    image = Image.fromarray(array, mode=mode)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _normalize_grayscale(array: np.ndarray) -> np.ndarray:
    if array.ndim == 3:
        array = color.rgb2gray(array[..., :3])
    else:
        array = array.astype(np.float64)
        maximum = float(array.max()) if array.size else 0.0
        if maximum > 1:
            array /= maximum
    return exposure.rescale_intensity(array, out_range=(0.0, 1.0)).astype(np.float32)


def decode_image(content: bytes) -> tuple[np.ndarray, np.ndarray]:
    if not content:
        raise UploadValidationError("The uploaded image is empty.")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in SUPPORTED_IMAGE_FORMATS:
                raise UploadValidationError(
                    f"Unsupported image format: {image.format or 'unknown'}."
                )
            rgb = np.asarray(image.convert("RGB"))
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError("The file is not a valid PNG, JPEG, or TIFF image.") from exc
    if rgb.shape[0] < 16 or rgb.shape[1] < 16:
        raise UploadValidationError("Images must be at least 16 x 16 pixels.")
    return rgb, _normalize_grayscale(rgb)


def _segment(gray: np.ndarray, min_object_size: int | None = None) -> tuple[np.ndarray, float]:
    """Original v1 grayscale baseline retained for reproducible comparison."""
    threshold = float(filters.threshold_otsu(gray))
    bright = gray > threshold
    dark = gray < threshold
    # Fluorescence is normally bright foreground. For brightfield, choose the
    # minority polarity when the bright mask would classify most of the frame.
    binary = dark if bright.mean() > 0.70 and dark.mean() < 0.50 else bright
    auto_min = max(8, int(gray.size * 0.00004))
    minimum = min_object_size or auto_min
    binary = morphology.remove_small_objects(binary, min_size=minimum)
    binary = morphology.remove_small_holes(binary, area_threshold=minimum)
    binary = morphology.binary_opening(binary, morphology.disk(1))

    distance = ndi.distance_transform_edt(binary)
    local_max = morphology.local_maxima(filters.gaussian(distance, sigma=1.0))
    markers = measure.label(local_max)
    if markers.max() == 0:
        labels = measure.label(binary)
    else:
        labels = segmentation.watershed(-distance, markers, mask=binary)
    labels = morphology.remove_small_objects(labels, min_size=minimum)
    return measure.label(labels > 0), threshold


def _segment_improved(rgb: np.ndarray) -> tuple[np.ndarray, float]:
    """BBBC031-development-selected v2 segmentation configuration.

    The max-RGB signal preserves red, green, and blue fluorescent objects that
    weighted grayscale can suppress. Constants were selected on six BBBC031
    development wells; held-out results are recorded separately.
    """
    signal = rgb.astype(np.float32).max(axis=2) / 255.0
    signal = exposure.rescale_intensity(signal, out_range=(0.0, 1.0))
    threshold = float(filters.threshold_otsu(signal))
    minimum = 72
    binary = signal > threshold
    binary = morphology.remove_small_objects(binary, min_size=minimum)
    binary = morphology.remove_small_holes(binary, area_threshold=minimum)
    binary = morphology.binary_opening(binary, morphology.disk(1))
    distance = ndi.distance_transform_edt(binary)
    coordinates = feature.peak_local_max(
        filters.gaussian(distance, sigma=1.0),
        min_distance=16,
        labels=binary,
        exclude_border=False,
    )
    markers = np.zeros(binary.shape, dtype=np.int32)
    if coordinates.size:
        markers[tuple(coordinates.T)] = np.arange(1, len(coordinates) + 1)
    markers = measure.label(markers > 0)
    labels = (
        segmentation.watershed(-distance, markers, mask=binary)
        if markers.max()
        else measure.label(binary)
    )
    labels = morphology.remove_small_objects(labels, min_size=minimum)
    return measure.label(labels > 0), threshold


def analyze_image(content: bytes, filename: str) -> dict[str, Any]:
    rgb, gray = decode_image(content)
    labels, threshold = _segment_improved(rgb)
    props = measure.regionprops(labels, intensity_image=gray)
    if not props:
        raise AnalysisError(
            "No objects survived segmentation. Try an image with stronger foreground contrast."
        )

    areas = np.array([p.area for p in props], dtype=float)
    perimeters = np.array([p.perimeter for p in props], dtype=float)
    circularities = 4 * math.pi * areas / np.maximum(perimeters**2, 1e-9)
    height, width = gray.shape

    overlay = Image.fromarray(rgb).convert("RGBA")
    boundary = segmentation.find_boundaries(labels, mode="outer")
    overlay_array = np.asarray(overlay).copy()
    overlay_array[boundary] = [0, 245, 212, 255]
    overlay = Image.fromarray(overlay_array)
    draw = ImageDraw.Draw(overlay)

    objects: list[dict[str, Any]] = []
    for prop, circularity in zip(props, circularities, strict=True):
        min_row, min_col, max_row, max_col = prop.bbox
        draw.rectangle((min_col, min_row, max_col, max_row), outline=(255, 193, 7, 180), width=1)
        objects.append(
            {
                "label": int(prop.label),
                "area_px": round(float(prop.area), 3),
                "perimeter_px": round(float(prop.perimeter), 3),
                "eccentricity": round(float(prop.eccentricity), 4),
                "circularity": round(float(np.clip(circularity, 0, 1)), 4),
                "mean_intensity": round(float(prop.mean_intensity), 4),
                "centroid": [round(float(v), 2) for v in prop.centroid],
                "bbox": [int(v) for v in prop.bbox],
            }
        )

    laplacian = ndi.laplace(gray)
    focus_score = float(np.var(laplacian))
    foreground = labels > 0
    reliability_notes = [
        "Deterministic max-RGB Otsu thresholding, morphology, distance transform, and marker-controlled watershed were used.",
        "Counts are segmented objects, not independently verified biological cell identities.",
    ]
    if focus_score < 0.0005:
        reliability_notes.append("Low edge variance suggests blur; segmentation may be unreliable.")
    if foreground.mean() > 0.65:
        reliability_notes.append("Foreground occupies most of the image; polarity or confluence may affect counts.")

    mask = (foreground.astype(np.uint8) * 255)
    return {
        "analysis_id": str(uuid.uuid4()),
        "filename": filename,
        "width": width,
        "height": height,
        "method": "Max-RGB Otsu + morphology + marker-controlled watershed (v2)",
        "threshold": round(threshold, 6),
        "metrics": {
            "object_count": len(props),
            "foreground_fraction": round(float(foreground.mean()), 6),
            "density_per_megapixel": round(len(props) / (gray.size / 1_000_000), 3),
            "mean_area_px": round(float(areas.mean()), 3),
            "median_area_px": round(float(np.median(areas)), 3),
            "std_area_px": round(float(areas.std()), 3),
            "mean_perimeter_px": round(float(perimeters.mean()), 3),
            "mean_eccentricity": round(float(np.mean([p.eccentricity for p in props])), 4),
            "mean_circularity": round(float(np.clip(circularities, 0, 1).mean()), 4),
            "mean_intensity": round(float(np.mean([p.mean_intensity for p in props])), 4),
            "focus_score": round(focus_score, 8),
        },
        "objects": objects[:500],
        "overlay_png_base64": _png_b64(np.asarray(overlay.convert("RGB"))),
        "mask_png_base64": _png_b64(mask),
        "reliability": {"level": "moderate", "notes": reliability_notes},
        "disclaimer": "Research use only. This output is not a medical diagnosis.",
    }
