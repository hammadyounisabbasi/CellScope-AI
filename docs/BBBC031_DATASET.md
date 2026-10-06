# BBBC031 Dataset and Evaluation Interpretation

## Dataset

BBBC031 v1 is a synthetic high-content fluorescence microscopy benchmark from the Broad Bioimage Benchmark Collection. It contains 24 simulated wells arranged as four rows by six columns (`A01` through `D06`), with nine sites per well: 216 RGB PNG images and 8,640 simulated cells. Each image is 950×950 pixels and contains 40 cells.

- Official page: <https://bbbc.broadinstitute.org/BBBC031>
- Image/mask archive: `BBBC031_v1_dataset.zip`
- Cell annotations: `BBBC031_v1_DatasetGroundTruth.csv`
- License: Creative Commons Attribution 3.0 Unported, attributed by the source to Peter Horvath and Abel Szkalisity.

The official archive and CSV are downloaded by `python scripts/download_bbbc031.py`. The script validates ZIP integrity, reports SHA-256 hashes, safely extracts paths, and skips valid existing files. Dataset files are ignored by Git.

## Observed directory structure

```text
data/raw/bbbc031/
├── BBBC031_v1_dataset.zip
├── BBBC031_v1_DatasetGroundTruth.csv
└── extracted/BBBC031_v1_dataset/
    ├── Images/   # 216 RGB PNG source images
    └── Masks/    # 216 CELLMASK TIFF + 216 NUCLMASK TIFF
```

The source PNG filenames end in `_CELLMASK.png`, but visual and pixel inspection confirms that these are the RGB microscopy images, not binary masks. Binary masks are the TIFF files under `Masks/`.

## Channels and masks

The PNG images contain colored cell bodies and blue nuclei on black background. Each image has two 8-bit binary masks:

- `CELLMASK.tiff`: cell-body foreground, excluding the nucleus region.
- `NUCLMASK.tiff`: nucleus foreground.

The two masks are disjoint. Because CellScope analyzes the visible whole cell rather than only cytoplasm or only nuclei, semantic ground truth is pre-declared as their pixelwise union. Reporting against `CELLMASK` alone would incorrectly penalize predicted nucleus pixels as false positives.

## Cell annotations and coordinates

The semicolon-delimited CSV contains 8,640 rows and 11 columns: image name, cell index, X/Y location, RGB parameters, shape parameter, process ID, and two regression-plane coordinates. There are exactly 40 rows per image. Coordinates range from 1 through 950, so they are one-based. After subtracting one, all 8,640 points land inside nucleus foreground; without conversion, only 8,614 are in bounds. `LocationX` maps to array column and `LocationY` to array row.

The CSV row count is the count ground truth. The binary TIFFs are semantic masks and do not encode instance IDs. Consequently, the benchmark does **not** claim instance-mask IoU. Object-level evaluation uses annotated centers: a center is detected when it lies inside predicted foreground, and a predicted labeled object can match at most one center for precision/F1 accounting.

## Preprocessing

Baseline preprocessing is exactly the production v1 analyzer: Pillow RGB decoding, scikit-image RGB-to-gray conversion, intensity rescaling, global Otsu thresholding, morphology, distance transform, regional-maxima markers, and watershed. No resizing or cropping is performed.

Development-only candidate improvements use the maximum RGB channel to avoid suppressing strongly red or blue synthetic cells, optional Gaussian denoising, declared size filters, and peak-local-max watershed markers. The search space was written to `evaluation/bbbc031_protocol.json` before baseline execution.

## Evaluation protocol

Splitting is grouped by well to prevent the nine sites from one simulated well appearing in both development and held-out test data. A fixed seed selects six development wells (54 images); the remaining 18 wells form the test set (162 images). Protocol v1.0.0 was amended before a valid baseline after archive inspection corrected the plate layout and one-based coordinate convention; no performance result informed that correction. Exact wells, hashes, exclusions, algorithm configuration, metrics, and selection rules are frozen in `evaluation/bbbc031_protocol.json`.

Metrics include semantic Dice/IoU/precision/recall, count MAE/RMSE/MAPE, annotated-center detection recall, predicted-object precision/F1, and count-based over/under-segmentation indicators. Per-image results and failures are retained.

## Known limitations

- BBBC031 is simulated and cannot establish clinical or real-tissue validity.
- Every image contains 40 cells, so count metrics do not test variation in biological density.
- Binary masks do not supply cell instance identities.
- Some cell bodies touch image boundaries; full morphology may lie outside the field of view.
- Development/test sites share the same generator and plate, despite well-grouped splitting.
- The colored-cell simulation differs from many grayscale fluorescence, brightfield, and organ-on-a-chip modalities.
