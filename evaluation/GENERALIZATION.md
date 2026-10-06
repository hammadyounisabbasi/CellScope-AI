# CellScope Generalization Scorecard

## Results across declared evaluations

| Metric | Synthetic regression | BBBC031 held-out | BBBC008 real microscopy |
|---|---:|---:|---:|
| Images | 1 | 162 | 12 |
| Dataset role | Software regression | Simulated in-domain benchmark | External domain-shift test |
| Dice | 1.000000 | 0.996559 | 0.228931 |
| IoU | 1.000000 | 0.993151 | 0.131833 |
| Foreground precision | Not recorded | 0.999901 | 0.999711 |
| Foreground recall | Not recorded | 0.993248 | 0.131836 |
| Count MAE | 0.0000 | 0.3951 | Not supported by annotations |
| Count RMSE | Not calculated | 0.6939 | Not supported by annotations |
| Mean runtime/image | Not compared | 0.5649 s | 0.1016 s |

The synthetic regression result only checks software behavior. BBBC031 is a clean simulated dataset used for development and held-out in-domain testing. BBBC008 is genuinely acquired microscopy and exposes severe intensity/modality shift. Its low frozen-v2 recall prevents any universal segmentation claim.

## What CellScope can reliably claim

- The deterministic pipeline produces measurable masks, overlays, counts, and region properties reproducibly.
- Under the declared well-grouped BBBC031 protocol, v2 achieved Dice 0.9966 and count MAE 0.3951 on 162 held-out simulated images.
- When transferred unchanged to 12 real BBBC008 fields, v2 achieved Dice 0.2289 and recall 0.1318, demonstrating limited external generalization.
- Generic per-channel normalization improved the same BBBC008 fields to Dice 0.5037 in a post-hoc experiment, but remained inadequate.
- CSV analytics, offline retrieval, deterministic graph orchestration, and HTML reporting function without a paid API.

## What CellScope cannot yet claim

- Clinical diagnostic or patient-level validity.
- Universal microscopy segmentation accuracy.
- Validated organ-on-a-chip performance; no organ-on-a-chip dataset has been evaluated.
- Reliable cell counts on BBBC008; its public annotations do not provide count ground truth.
- Drug efficacy, toxicity, phenotype, prognosis, or causal-effect prediction.
- Independent validation of the post-hoc channel-normalization experiment.
- Learned-model superiority; Cellpose was not added because the current deterministic external baseline must first be strengthened and independently re-evaluated.
