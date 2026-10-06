# External Validation Dataset: BBBC008 v1

## Selection rationale

BBBC008 v1 was selected as an independent real-microscopy test because it is small enough to reproduce, uses genuine acquired fluorescence images, provides manually cleaned semantic foreground masks, and differs substantially from the simulated colored cells used to select CellScope v2. It was not selected to maximize performance.

## Source and license

- Dataset: Broad Bioimage Benchmark Collection BBBC008 v1
- Official page: <https://bbbc.broadinstitute.org/BBBC008>
- Images: <https://data.broadinstitute.org/bbbc/BBBC008/BBBC008_v1_images.zip>
- Foreground masks: <https://data.broadinstitute.org/bbbc/BBBC008/BBBC008_v1_foreground.zip>
- License: Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported, attributed by the source to David Root and Anne Carpenter.

The non-commercial restriction must be retained when redistributing derived material. The source archives are ignored by Git and downloaded using `python scripts/download_bbbc008.py`.

## Biological and imaging context

The samples are human HT29 colon-cancer cells acquired by fluorescence microscopy. Hoechst channel 1 labels DNA/nuclei. Phalloidin channel 3 labels actin/cytoplasm. The pH3 phenotype channel described by the source is not included because it is not required for foreground segmentation.

## Structure

- 12 fields of view.
- 512×512 pixels per field.
- Two grayscale 8-bit TIFF inputs per field: channel 1 and channel 3.
- Two corresponding 1-bit TIFF foreground masks per field.
- Filenames encode one of two source wells and one of six slices.

Apple `__MACOSX` metadata entries in the archives are ignored as non-dataset files; no scientific sample is excluded.

## Ground truth

The BBBC page states that foreground masks began with thresholding and were subsequently cleaned by hand. Channel 1 and channel 3 masks correspond to their respective stains. For CellScope's visible whole-cell foreground task, the declared target is their pixelwise union.

The masks are binary semantic annotations. They do not provide instance identities, cell centers, or human cell counts. Therefore Dice, IoU, foreground precision, and foreground recall are supported; instance IoU, count MAE, and detection F1 are not.

## Preprocessing and compatibility

Each pair is composed into an RGB image without resizing or contrast enhancement: red is zero, green is raw actin channel 3, and blue is raw DNA channel 1. Frozen CellScope v2 then operates unchanged on the maximum RGB signal. This composition exposes the two biological channels to the existing RGB API without tuning algorithm parameters.

## Known limitations

- Only 12 fields are available, so uncertainty and diversity are limited.
- The masks combine automated initialization with manual cleanup rather than independent full manual tracing.
- HT29 fluorescence does not represent brightfield, DIC, 3D, live-cell, tissue, or organ-on-a-chip modalities.
- The CC BY-NC-SA license restricts commercial reuse.
- The dataset supports semantic foreground validation, not cell counting or phenotype prediction.
