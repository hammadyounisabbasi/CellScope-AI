import numpy as np

from evaluation.external_validation import metric_row, robust_channel_normalization


def test_external_semantic_metrics_perfect_prediction():
    truth = np.zeros((16, 16), dtype=bool)
    truth[4:12, 5:11] = True
    row = metric_row("fixture", truth.copy(), truth, 0.01)
    assert row["dice"] == 1.0
    assert row["iou"] == 1.0
    assert row["foreground_precision"] == 1.0
    assert row["foreground_recall"] == 1.0


def test_robust_channel_normalization_is_channelwise():
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    rgb[5:15, 5:15, 1] = 50
    rgb[7:13, 7:13, 2] = 200
    normalized = robust_channel_normalization(rgb)
    assert normalized[..., 0].max() == 0
    assert normalized[..., 1].max() == 255
    assert normalized[..., 2].max() == 255

