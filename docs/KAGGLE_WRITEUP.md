# CellScope AI: Evidence-First Microscopy Research Workspace

## Project overview

CellScope AI is a local-first research workspace that connects three tasks that are usually fragmented: microscopy segmentation, experiment-table analysis, and literature-grounded interpretation. A FastAPI backend serves a dependency-light HTML/CSS/JavaScript interface, deterministic analysis tools, an auditable research-agent graph, and an exportable HTML report.

The central design rule is simple: computation comes before narration. Numeric claims shown by the assistant are derived from structured tool outputs, while literature context is retrieved from a small, inspectable offline knowledge base with source metadata.

## The problem

Cell-imaging projects often require researchers to move between an image-analysis program, statistical notebooks, papers, and a reporting tool. That creates opportunities for transcription errors, context loss, and overconfident interpretation. CellScope AI keeps the evidence chain visible in one workflow without presenting research measurements as clinical conclusions.

## What we built

- Deterministic microscopy segmentation using grayscale conversion, Otsu thresholding, morphology, distance transforms, peak detection, and watershed separation.
- Per-object measurements and visual overlays, with explicit method and reliability notes.
- CSV schema inspection, descriptive statistics, group comparisons, effect sizes, correlations, missingness summaries, and anomaly candidates.
- A deterministic state-graph research agent whose trace shows which analysis, retrieval, and composition nodes ran.
- Offline TF-IDF retrieval with citations and metadata, plus graceful refusal when the evidence base is unrelated.
- A self-contained HTML report with embedded microscopy and experiment visuals.
- Reproducible evaluation scripts, frozen configuration, tests, Docker assets, and documented limitations.

## Validation

We evaluated the frozen CellScope v2 configuration on two official Broad Bioimage Benchmark Collection datasets and kept the results separate from a synthetic software-regression fixture.

On the well-grouped BBBC031 held-out set (162 images), v2 achieved mean Dice 0.9966, mean IoU 0.9932, detection F1 0.9988, and count MAE 0.3951, with zero processing failures. This dataset closely matches the pipeline's bright-cell-on-dark-background assumptions.

We then froze every production parameter before evaluating all 12 fields of BBBC008, a real two-channel HT29 fluorescence dataset with manually cleaned semantic foreground masks. With raw channel composition and no retuning, mean Dice was 0.2289 and mean IoU was 0.1318. Precision remained 0.9997 while recall fell to 0.1318, showing severe under-segmentation under channel-intensity and morphology shift.

An explicitly post-hoc normalization experiment improved BBBC008 mean Dice to 0.5037, but it used the same 12 images and is not an independent benchmark or part of the production configuration. We report it only as evidence for a future, pre-registered robustness study.

## What the results mean

The strong BBBC031 result supports the implementation under a compatible acquisition regime. The BBBC008 failure is equally important: it demonstrates that a single global threshold over a raw RGB maximum is not generally robust to heterogeneous multichannel fluorescence. CellScope AI therefore exposes its method, configuration, visual mask, and limitations instead of turning a segmentation score into a universal biological claim.

The current system is appropriate for research exploration and reproducible demonstrations. It is not a diagnostic device, does not identify cell types, and does not establish treatment efficacy or causality.

## Reproducibility

The repository includes the exact frozen v2 configuration, download and integrity-check scripts, evaluation protocols, machine-readable results, tests, and qualitative artifact generation. Dataset archives are not redistributed. Official sources and licenses are documented so another researcher can reproduce the evaluations locally.

## Links

- Source repository: add the public repository URL before submission.
- Live demo: add the deployment URL if a hosted instance is published.
- Technical report: [`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md)
- External validation: [`../evaluation/EXTERNAL_VALIDATION.md`](../evaluation/EXTERNAL_VALIDATION.md)
- Reproduction guide: [`../README.md`](../README.md)

## Closing

CellScope AI's contribution is not a claim that one algorithm solves microscopy. It is a compact, inspectable workflow for measuring images and experiments, grounding interpretation, surfacing failures, and exporting the evidence trail needed for the next investigation.
