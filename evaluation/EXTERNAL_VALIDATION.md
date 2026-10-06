# BBBC008 External Real-Microscopy Validation

## Purpose

This evaluation tests the frozen CellScope Deterministic Pipeline v2 without parameter changes on genuine fluorescence microscopy from BBBC008. It measures domain transfer from simulated BBBC031 cells to real HT29 images. It does not establish clinical validity.

## Protocol

All 12 official 512×512 fields were evaluated. Hoechst/DNA channel 1 was mapped to blue, phalloidin/actin channel 3 to green, and red to zero. Raw uint8 values were retained without resizing, denoising, or channel normalization. Ground truth was the union of the two official binary foreground masks. Only semantic Dice, IoU, precision, recall, and runtime are supported.

The protocol and frozen v2 configuration were written before execution:

- `evaluation/external_validation_protocol.json`
- `evaluation/cellscope_v2_config.json`

## Frozen v2 results

| Metric | Result |
|---|---:|
| Images / failures | 12 / 0 |
| Mean Dice | 0.228931 |
| Mean IoU | 0.131833 |
| Foreground precision | 0.999711 |
| Foreground recall | 0.131836 |
| Truth foreground fraction | 0.287315 |
| Predicted foreground fraction | 0.040443 |
| Mean runtime | 0.1016 s/image |
| Runtime p95 | 0.1345 s/image |

The high precision and very low recall show conservative, severe under-segmentation. Frozen v2 mostly selected the brightest nuclear and actin regions while missing dim cytoplasm.

## Domain-shift analysis

BBBC031 uses clean, high-contrast simulated RGB cell bodies and nuclei. In BBBC008, raw channel scales differ: Hoechst nuclei often reach saturation while actin cytoplasm is dim, spatially variable, and affected by background. The frozen max-RGB signal is therefore dominated by bright nuclei. Global Otsu thresholding selects a small foreground mode, explaining the predicted foreground fraction of 4.0% versus 28.7% truth.

Performance also varies with density and morphology. The worst field, `A24...slice6`, reached Dice 0.1287 and recall 0.0688. The best frozen field, `L15...slice5`, reached Dice 0.4268. Dense, touching-cell regions remain poorly recovered because a single global threshold cannot represent low-contrast actin boundaries.

Representative artifacts under `reports/external_validation/` show raw channels, ground truth, frozen prediction, exploratory preprocessing, and teal/amber/red disagreement maps.

## Exploratory generalization preprocessing

After frozen results were saved, one post-hoc experiment independently normalized each nonempty channel using its 1st and 99.5th percentiles, then ran frozen v2 unchanged.

| Metric | Frozen v2 | Exploratory normalization |
|---|---:|---:|
| Mean Dice | 0.228931 | 0.503731 |
| Mean IoU | 0.131833 | 0.347458 |
| Foreground precision | 0.999711 | 0.999113 |
| Foreground recall | 0.131836 | 0.347573 |
| Predicted foreground fraction | 0.040443 | 0.091653 |
| Mean runtime | 0.1016 s | 0.1161 s |

The improvement confirms channel-scale mismatch, but recall remains inadequate. This experiment used the same 12 fields for assessment and is neither independent validation nor production selection. It was not promoted into CellScope v2.

## Reproduction

```bash
python scripts/download_bbbc008.py
python evaluation/external_validation.py --stage frozen
python evaluation/external_validation.py --stage generalization
python evaluation/generate_external_artifacts.py
```

Exact per-image results and failures are in `evaluation/external_validation_results.json`.

