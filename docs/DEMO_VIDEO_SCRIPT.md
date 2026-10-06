# CellScope AI — Five-Minute Demo Script

## 0:00–0:30 — Research problem

“Cell-imaging studies produce microscopy, experiment tables, and literature questions, but early analysis is often split across disconnected tools. CellScope AI brings those steps into one evidence-first workspace. It is research software, not a diagnostic system.”

Show the landing page and the four-stage strip: quantify, compare, ground, report.

## 0:30–1:35 — Microscopy analysis

Upload `data/sample/synthetic_cells.png`. While it runs, explain that the backend—not the browser—performs deterministic Otsu thresholding, morphology, and watershed separation.

Show the original image beside the overlay and binary mask. Call out count, area, circularity, eccentricity, intensity, foreground fraction, and focus score. Point to the method and reliability note: segmented objects are algorithmic regions and are not automatically verified cells.

## 1:35–2:25 — Experiment analytics

Upload `data/sample/experiment.csv`. Show the detected schema, missingness, group summaries, effect sizes, unadjusted p-values, correlations, plots, and anomaly candidates.

Say: “These results describe this uploaded table. They are exploratory associations, not causal claims, and multiple-testing correction is not automatically implied.”

## 2:25–3:20 — Auditable research assistant

Ask: “What measurable differences were found, and what should we validate next?” Show the structured answer sections and expand the workflow trace. Explain that the graph routes through analysis and retrieval nodes and that quantitative statements come from structured session results.

Then ask: “What is BBBC031 ground truth?” Show the retrieved source metadata. Ask an unrelated question such as “What does quantum gravity predict?” and show the evidence-limited response rather than an invented answer.

## 3:20–4:20 — Honest external validation

Open the Evaluation section. First show the strong, well-grouped BBBC031 held-out result: Dice 0.9966 and count MAE 0.3951.

Then show the unchanged frozen-v2 result on all 12 BBBC008 fields: Dice 0.2289, IoU 0.1318, precision 0.9997, and recall 0.1318. Open one qualitative artifact and point to the missed foreground. Explain that different channel intensities and morphology caused severe under-segmentation.

Mention the post-hoc normalized result, Dice 0.5037, only as a hypothesis-generating experiment on the same images—not as an independent benchmark and not as the deployed configuration.

## 4:20–4:50 — Report

Generate the HTML report. Show its embedded image and experiment visuals, methods, quantitative findings, reliability notes, next investigations, references, and workflow evidence. Emphasize that the report remains self-contained when downloaded.

## 4:50–5:00 — Close

“CellScope AI puts computation before narration: measure, validate, ground, and report. Just as importantly, it makes domain-shift failures visible instead of hiding them.”

## Recording checklist

- Start with the API running and browser zoom at 100%.
- Use a clean browser session and perform actual uploads.
- Keep the evaluation artifacts and report ready in separate tabs.
- Do not edit results into the recording or describe post-hoc results as held-out.
- Replace submission-link placeholders before publishing.
- Target 4:45–4:55 total duration.
