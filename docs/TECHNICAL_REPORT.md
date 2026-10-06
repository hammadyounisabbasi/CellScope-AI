# CellScope AI — Technical Report

## Abstract

CellScope AI is an end-to-end research assistant for microscopy measurement, experiment-table analysis, scientific retrieval, grounded interpretation, and structured reporting. Its deterministic CellScope v2 segmentation pipeline achieved Dice 0.9966 on 162 held-out simulated BBBC031 images under a well-grouped protocol. Unchanged transfer to 12 real BBBC008 fluorescence fields achieved Dice 0.2289, revealing severe channel/intensity domain shift. This negative external result bounds the system's claims and motivates modality-aware validation. CellScope operates without paid services and is not a medical diagnostic system.

## 1. Introduction

Cellular experiments produce images, tables, and literature questions that are often analyzed in disconnected tools. CellScope preserves structured intermediate results so narrative output can be traced to measurements, statistics, or retrieved evidence.

## 2. Problem Definition

The system accepts microscopy images and CSV experiments, computes objective measurements, performs exploratory comparisons, retrieves documented sources, answers context-aware questions, and exports a report. It must reject unsafe inputs and avoid converting association or model output into unsupported biological conclusions.

## 3. Scientific Motivation

Rapid, reproducible triage can help research teams locate images, samples, and hypotheses requiring expert review. The value depends on exposing failure modes, especially domain shift, rather than presenting a benchmark score as universal confidence.

## 4. Related Background

Otsu thresholding selects a global threshold from an intensity histogram [2]. Mathematical morphology and watershed are established deterministic tools for foreground cleanup and touching-object separation. The Broad Bioimage Benchmark Collection provides annotated datasets for image-analysis validation [1]. Isolation Forest identifies unusual feature vectors by random partitioning [5].

## 5. System Overview

CellScope contains a FastAPI service, Pydantic schemas, deterministic image and table pipelines, offline TF-IDF retrieval, a conditional state graph, HTML report generation, and a responsive no-build frontend. Each module exchanges structured JSON.

## 6. Data Sources

BBBC031 v1 contains 216 simulated RGB fluorescence fields, separate cell-body and nucleus masks, and 8,640 annotations. It is CC BY 3.0 [3]. BBBC008 v1 contains 12 real HT29 fluorescence fields with Hoechst/DNA and phalloidin/actin channels plus cleaned binary foreground masks. It is CC BY-NC-SA 3.0 [4]. Official archives are downloaded by validated scripts and excluded from Git.

## 7. BBBC031 Benchmark

Six complete wells (54 images) were selected for development with seed 31031; 18 wells (162 images) were held out. Sites from one well never crossed splits. Whole-cell semantic ground truth was the union of cell-body and nucleus masks. Counts came from 40 one-based CSV annotations per image. Protocol v1.0.1 records exact hashes, wells, metrics, and a pre-result correction to the observed plate layout and coordinate convention.

The original v1 baseline achieved held-out Dice 0.803990, IoU 0.678138, count MAE 6.6481, and count RMSE 8.7655. Its weighted grayscale signal omitted blue nuclei, yielding strict center recall zero.

## 8. External Real-Data Validation

Frozen v2 was evaluated unchanged on all 12 BBBC008 fields. DNA was mapped to blue, actin to green, and red to zero without resizing or contrast normalization. The target was the union of channel-specific foreground masks. Only semantic metrics were reported because no instance identities or human counts are supplied.

Frozen v2 achieved Dice 0.228931, IoU 0.131833, precision 0.999711, and recall 0.131836 with zero failures. It predicted 4.04% foreground versus 28.73% truth. This is evidence of weak external generalization.

## 9. Microscopy Method

CellScope Deterministic Pipeline v2 computes the maximum RGB channel, rescales intensity, applies global Otsu thresholding, removes objects and holes below 72 pixels, performs disk-1 opening, computes an Euclidean distance transform, places local-maxima markers at least 16 pixels apart, and applies marker-controlled watershed. Exact parameters are frozen in `evaluation/cellscope_v2_config.json`.

## 10. Experiment Analytics

The CSV engine detects numeric/categorical columns, missing values, candidate identifiers, and a likely grouping variable. It produces descriptive statistics, two-group Mann–Whitney U tests, Cohen's d, Spearman correlations, Isolation Forest anomaly candidates, histograms, and box plots. P-values are unadjusted and exploratory; correlations are labeled non-causal.

## 11. Scientific Retrieval

The offline knowledge base stores curated summaries with ID, title, URL, and section metadata. TF-IDF unigram/bigram vectors and cosine similarity retrieve up to three chunks above a score floor. The executable five-query evaluation records recall@3, metadata completeness, and unsupported-answer behavior. No paper title is generated dynamically.

## 12. Agentic Workflow

An explicit deterministic state graph contains an intent/context analyzer, microscopy tool, experiment tool, scientific retrieval tool, evidence interpretation node, and response composer. Conditional edges depend on question terms and available state. The response includes a workflow trace. Quantitative claims originate only from structured analysis results. Output sections explicitly identify measured results, statistical observations, retrieved evidence, and AI interpretation.

## 13. System Architecture

The browser calls REST endpoints for image analysis, experiment analysis, chat, reports, health, and system information. FastAPI validates requests and delegates to pure analysis services. The application works without an LLM or external database. Static frontend files are served from the same process using relative HTML asset links.

## 14. Implementation

Python 3.12, FastAPI, Pydantic, NumPy, pandas, SciPy, scikit-image, scikit-learn, Pillow, and matplotlib form the backend. The frontend is semantic HTML, CSS, and vanilla JavaScript. Dataset downloads use the Python standard library, SHA-256 reporting, ZIP integrity checks, safe extraction, and valid-file reuse.

## 15. Experiments

Experiments include a nine-object synthetic software fixture, BBBC031 baseline, a 12-configuration development-only search, one final held-out BBBC031 run, unchanged-v2 BBBC008 transfer, and a separately labeled post-hoc channel-normalization experiment. BBBC008 frozen results were saved before the exploratory preprocessing was executed.

## 16. Results

| Metric | BBBC031 baseline | BBBC031 v2 | BBBC008 frozen v2 | BBBC008 exploratory |
|---|---:|---:|---:|---:|
| Images | 162 | 162 | 12 | 12 |
| Dice | 0.803990 | 0.996559 | 0.228931 | 0.503731 |
| IoU | 0.678138 | 0.993151 | 0.131833 | 0.347458 |
| Precision | 0.999940 | 0.999901 | 0.999711 | 0.999113 |
| Recall | 0.678167 | 0.993248 | 0.131836 | 0.347573 |
| Count MAE | 6.6481 | 0.3951 | Unsupported | Unsupported |

The exploratory BBBC008 result used the evaluation fields themselves and is not independent validation or a production score.

## 17. Error Analysis

BBBC031 v2 returned exact counts for 105/162 images; remaining errors ranged from −2 to +2 and involved touching-cell merges, extra watershed splits, thin protrusions, and small regions. On BBBC008, high precision with low recall dominated every field. The worst frozen field reached Dice 0.1287. Representative figures show raw channels, truth, predictions, and disagreement maps.

## 18. Generalization

BBBC031 and BBBC008 differ in simulation realism, channel scales, background, confluence, morphology, and contrast. BBBC008 Hoechst nuclei often approach saturation while actin cytoplasm is dim and spatially variable; frozen max-RGB plus global Otsu selects the small bright mode. Robust per-channel percentile normalization raised Dice to 0.5037 but remained inadequate. A future improvement requires independent development/test real-microscopy datasets, not more tuning on these 12 fields.

## 19. Explainability

The API returns method name, threshold, object measurements, mask, overlay, reliability notes, statistical fields, anomaly scores, retrieved sources, selected tools, and workflow trace. Benchmark metrics appear only in evaluation contexts and are not presented as confidence for an uploaded image.

## 20. Reliability

Pinned direct dependencies, deterministic seeds, frozen configurations, archive hashes, explicit protocols, per-image result files, bounded inputs, and a no-key default improve repeatability. External validation demonstrates that reproducibility does not imply generalization.

## 21. Limitations

The external dataset is small and limited to one cell line and fluorescence setup. v2 is not reliable across raw channel-scale changes. Counts lack external validation on BBBC008. The RAG corpus is small. Statistical tests are exploratory. PDF export and pretrained segmentation are not included. No organ-on-a-chip, clinical, patient, treatment-efficacy, or toxicity outcome has been validated.

## 22. Reproducibility

The README gives clean-environment commands. Scripts generate samples, download both official datasets, run each benchmark stage, execute RAG evaluation, and regenerate artifacts. Raw data is ignored. The frontend needs no Node build. The Docker image and Compose configuration were built successfully, and an isolated container returned the expected health response.

## 23. Ethical Considerations

The system, UI, API, and reports state that outputs are for research assistance only. Anomaly candidates must not be called abnormalities or disease findings. External data licenses and non-commercial restrictions must be retained. Uploaded files are parsed in memory and not executed.

## 24. Potential Scientific Impact

An auditable bridge from image/table inputs to reviewable evidence can standardize early analysis and help teams identify experiments requiring deeper validation. The system's strongest contribution is a measurable workflow with visible uncertainty rather than a claim of autonomous scientific truth.

## 25. Future Work

Use a larger real-microscopy development/test benchmark to design illumination correction and scale estimation; externally validate counts; evaluate Cellpose as an optional comparison only under a reproducible protocol; expand licensed literature coverage; add multiple-testing correction and repeated-measures designs; and verify container deployment.

## 26. Conclusion

CellScope AI is a functioning end-to-end research system with strong in-domain simulated performance, transparent external failure, deterministic agentic orchestration, and reproducible artifacts. It is competition-ready as an honest research prototype, not a universal or clinical segmentation system.

## References

1. Ljosa V, Sokolnicki KL, Carpenter AE. Annotated high-throughput microscopy image sets for validation. *Nature Methods*. 2012;9:637. <https://doi.org/10.1038/nmeth.2083>
2. Otsu N. A Threshold Selection Method from Gray-Level Histograms. *IEEE Transactions on Systems, Man, and Cybernetics*. 1979;9(1):62–66. <https://doi.org/10.1109/TSMC.1979.4310076>
3. Broad Bioimage Benchmark Collection. BBBC031 v1: Simulated 24-well plate with synthetic cells. <https://bbbc.broadinstitute.org/BBBC031>
4. Broad Bioimage Benchmark Collection. BBBC008 v1: Human HT29 colon-cancer cells. <https://bbbc.broadinstitute.org/BBBC008>
5. Liu FT, Ting KM, Zhou Z-H. Isolation Forest. *2008 IEEE International Conference on Data Mining*. <https://doi.org/10.1109/ICDM.2008.17>
