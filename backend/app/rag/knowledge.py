"""Small, redistributable metadata-first knowledge base for offline retrieval."""

DOCUMENTS = [
    {
        "id": "bbbc031",
        "title": "BBBC031: Simulated 24-well plate with synthetic cells",
        "url": "https://bbbc.broadinstitute.org/BBBC031",
        "section": "Dataset description and ground truth",
        "text": (
            "BBBC031 contains 216 synthetic fluorescence microscopy images, nine per well, "
            "with 8,640 simulated cells. Images are 950 by 950 RGB PNG files. Binary masks of "
            "nuclei and cells and a cell-level ground-truth CSV are provided. It models shape and "
            "protein-expression perturbations and is licensed CC BY 3.0."
        ),
    },
    {
        "id": "bbbc008",
        "title": "BBBC008: Human HT29 colon-cancer cells",
        "url": "https://bbbc.broadinstitute.org/BBBC008",
        "section": "Images, ground truth, and license",
        "text": (
            "BBBC008 contains 12 real fluorescence microscopy fields of human HT29 cells. "
            "Hoechst channel 1 labels DNA and phalloidin channel 3 labels actin. Foreground masks "
            "were initialized by thresholding and cleaned by hand. Images and masks are licensed "
            "CC BY-NC-SA 3.0. The binary masks support semantic foreground evaluation but do not "
            "provide instance identities or human cell counts."
        ),
    },
    {
        "id": "ljosa2012",
        "title": "Annotated high-throughput microscopy image sets for validation",
        "url": "https://doi.org/10.1038/nmeth.2083",
        "section": "Benchmarking motivation",
        "text": (
            "The Broad Bioimage Benchmark Collection provides annotated microscopy image sets "
            "and expected results for developing and validating life-science image-analysis algorithms."
        ),
    },
    {
        "id": "otsu1979",
        "title": "A Threshold Selection Method from Gray-Level Histograms",
        "url": "https://doi.org/10.1109/TSMC.1979.4310076",
        "section": "Method",
        "text": (
            "Otsu thresholding chooses a global intensity threshold by maximizing between-class "
            "variance. Its assumptions can fail with uneven illumination, weak contrast, or complex backgrounds."
        ),
    },
    {
        "id": "skimage-regionprops",
        "title": "scikit-image region properties documentation",
        "url": "https://scikit-image.org/docs/stable/auto_examples/segmentation/plot_regionprops.html",
        "section": "Region measurement",
        "text": (
            "Region properties quantify labeled objects, including area, perimeter, eccentricity, "
            "centroid, bounding box, and intensity-derived measurements."
        ),
    },
    {
        "id": "isolation-forest",
        "title": "Isolation Forest",
        "url": "https://doi.org/10.1109/ICDM.2008.17",
        "section": "Anomaly detection",
        "text": (
            "Isolation Forest identifies unusual observations by random recursive partitioning. "
            "Anomaly labels identify candidates for investigation and are not biological conclusions."
        ),
    },
]
