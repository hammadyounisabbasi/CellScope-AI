# BBBC031 v1 Benchmark Results

## Goal

This benchmark measures the production CellScope v1 microscopy pipeline and a development-selected v2 improvement on the official BBBC031 v1 synthetic fluorescence dataset. It is separate from `evaluation/results.json`, which remains a small software-regression fixture.

BBBC031 is a benchmark dataset. These results do not establish clinical validity or performance on real organ-on-a-chip imagery.

## Data and protocol

- 216 RGB images, 950×950 pixels; 24 wells × 9 sites.
- 8,640 cell annotations; exactly 40 cells per image.
- Semantic target: union of cell-body and nucleus binary masks.
- Development: 6 whole wells / 54 images.
- Held-out test: 18 whole wells / 162 images.
- Fixed seed: 31031. Sites from one well never cross splits.
- Protocol, hashes, exact wells, metrics, and amendment history: `evaluation/bbbc031_protocol.json`.

The v1.0.0 protocol layout assumption was corrected to the observed `A01–D06` plate and one-based annotation coordinates before a valid baseline was produced. No performance result informed that structural correction.

## Algorithms

**Baseline:** the original production v1 implementation: weighted RGB-to-gray conversion, intensity rescaling, global Otsu threshold, 36-pixel cleanup, disk-1 opening, distance transform, all regional maxima, and watershed.

**Improved:** max-RGB intensity, global Otsu threshold, 72-pixel cleanup, disk-1 opening, and marker-controlled watershed with peak minimum distance 16. The configuration was selected from the pre-declared 12-candidate search on development wells only. No Gaussian smoothing was selected.

## Held-out results

| Metric | Baseline v1 | Improved v2 |
|---|---:|---:|
| Images / failures | 162 / 0 | 162 / 0 |
| Mean Dice | 0.803990 | **0.996559** |
| Mean IoU | 0.678138 | **0.993151** |
| Foreground precision | 0.999940 | 0.999901 |
| Foreground recall | 0.678167 | **0.993248** |
| Count MAE | 6.6481 | **0.3951** |
| Count RMSE | 8.7655 | **0.6939** |
| Count MAPE | 16.620% | **0.988%** |
| Mean predicted count (truth=40) | 43.4136 | **39.7284** |
| Annotated-center recall | 0.000000 | **1.000000** |
| Predicted-object precision | 0.000000 | **0.997572** |
| Detection F1 | 0.000000 | **0.998769** |
| Mean runtime per image | 0.6667 s | **0.5649 s** |
| Runtime p95 | 1.2673 s | **0.8331 s** |

Baseline center recall is genuinely zero under the pre-declared strict rule because weighted grayscale suppresses the blue nuclei and leaves holes at all annotated nucleus centers. The surrounding cell bodies are often detected, which explains why semantic Dice is nonzero. The metric definition was not relaxed after observing this weakness.

## Error analysis

The improved method returned the exact count for 105/162 held-out images (64.8%). It under-counted 48 images and over-counted 9. Errors were tightly bounded: six images had −2 cells, 42 had −1, eight had +1, and one had +2.

Fifty-three images contained at least one predicted object covering more than one annotated center, indicating touching-cell merges. The worst Dice sample was `ProcessPlateSparse_wC02_s08_z1_t1` (Dice 0.98835, count 42/40). Its false negatives occur mainly in thin protrusions and irregular low-area regions; its +2 count is consistent with extra watershed splits. The largest under-count example `ProcessPlateSparse_wA04_s08_z1_t1` produced 38/40 despite Dice 0.9970; closely spaced cells and the fixed 16-pixel marker distance explain the two merges. Boundary-truncated cells are otherwise retained because peak detection does not exclude borders.

Representative comparisons contain original RGB, ground truth, baseline, improved prediction, boundaries, and a disagreement map (teal agreement, amber false negative, red false positive):

- `reports/bbbc031/worst_dice_ProcessPlateSparse_wC02_s08_z1_t1.png`
- `reports/bbbc031/median_dice_ProcessPlateSparse_wB03_s08_z1_t1.png`
- `reports/bbbc031/best_dice_ProcessPlateSparse_wB02_s06_z1_t1.png`
- `reports/bbbc031/largest_undersegmentation_ProcessPlateSparse_wA04_s08_z1_t1.png`

## Limitations

- BBBC031 is synthetic and visually clean; strong performance should not be extrapolated to real microscopy.
- All images contain 40 cells, limiting density generalization.
- The masks are semantic, not instance-labeled. Instance-mask IoU is therefore not reported.
- Point-based detection uses supplied one-based cell centers converted to zero-based indices.
- The improvement is color-aware and may not benefit single-channel or differently stained images.
- Development and test wells share one simulation process even though well-level grouping prevents site leakage.

## Reproduction

```bash
python scripts/download_bbbc031.py
python evaluation/bbbc031_benchmark.py --stage baseline
python evaluation/bbbc031_benchmark.py --stage tune
python evaluation/bbbc031_benchmark.py --stage final
python evaluation/generate_bbbc031_artifacts.py
```

Machine-readable results are in `evaluation/bbbc031_results.json`; the baseline and development search remain in separate JSON files for auditability.

