# Competition Readiness Audit

Audit date: 2026-10-05

## Executive assessment

CellScope AI is ready for a source-code submission and local demonstration. Its strongest competition qualities are end-to-end integration, reproducibility, inspectable agent routing, and unusually candid external validation. The principal weakness is scientific generalization: frozen v2 performs well on compatible simulated BBBC031 images but poorly on real multichannel BBBC008 foreground segmentation.

This audit does not claim a public deployment, clinical utility, or broad microscopy validity.

## Judging dimensions

| Dimension | Evidence | Current strength | Remaining risk |
|---|---|---|---|
| Problem relevance | Image, table, evidence, and report workflow | Clear end-to-end research story | No validated organ-on-a-chip dataset |
| Technical execution | FastAPI, deterministic tools, state graph, offline retrieval | Fully working local product; browser-tested | Rules-based agent is less flexible than a learned planner |
| Scientific rigor | Frozen config, grouped split, external dataset, failure artifacts | Protocol and limitations are reproducible | BBBC008 frozen Dice is only 0.2289 |
| Responsible AI | Structured evidence sections, citations, refusal path, disclaimers | Unsupported claims are constrained | Curated knowledge base is intentionally small |
| User experience | Responsive dashboard and self-contained report | Core workflows pass browser smoke testing | No authentication, projects, or persistence |
| Reproducibility | Pinned dependencies, download hashes, JSON results, tests | 16 automated tests pass; Docker build and health route verified | No continuous deployment workflow |
| Communication | README, report, write-up, video script, screenshots | Submission narrative matches measured evidence | Public repository and deployment URLs still need insertion |

## Verified release gates

- Synthetic microscopy regression: Dice 1.0, IoU 1.0, count MAE 0.
- BBBC031 well-grouped held-out evaluation: 162 images, zero failures, Dice 0.996559, count MAE 0.3951.
- BBBC008 unchanged frozen-v2 evaluation: 12 of 12 fields, zero failures, Dice 0.228931, recall 0.131836.
- Offline retrieval evaluation: recall@3 1.0 across five declared cases; citation metadata completeness 1.0.
- Automated tests: 16 passed; only third-party Matplotlib/Pyparsing deprecation warnings remain.
- Browser smoke test: microscopy, CSV, assistant, report download, and desktop/mobile rendering passed without console errors.
- Docker runtime: image build completed; the isolated container returned the expected `/health` payload.
- Static publication scan: no user-specific absolute paths, obvious private-key markers, or credential patterns are intended in tracked source.

## Submission blockers

No code blocker is known. Before public submission:

1. Add the public repository URL and, if applicable, deployment URL to `docs/KAGGLE_WRITEUP.md`.
2. Re-run `python -m pytest -q` and the browser smoke test after any link or deployment changes.
3. Confirm the competition permits the non-commercial share-alike terms governing BBBC008-derived displayed artifacts.

## Recommended next scientific work

Pre-register a channel-normalization or channel-selection policy on a development dataset that is separate from BBBC008, then test it once on a new real-microscopy holdout. Add illumination correction and scale-aware parameters only through a development protocol. Do not reinterpret the current post-hoc 0.5037 result as held-out evidence.
