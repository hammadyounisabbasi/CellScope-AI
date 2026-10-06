# Evaluation

`python evaluation/run_evaluation.py` runs an intentionally transparent synthetic-fixture check and writes `results.json`. It measures mask Dice/IoU, count MAE, and three offline retrieval cases. These values are engineering regression signals, not biological performance claims.

## Real BBBC031 benchmark

The external benchmark is implemented and executed separately from the fixture:

```bash
python scripts/download_bbbc031.py
python evaluation/bbbc031_benchmark.py --stage baseline
python evaluation/bbbc031_benchmark.py --stage tune
python evaluation/bbbc031_benchmark.py --stage final
python evaluation/generate_bbbc031_artifacts.py
```

See `bbbc031_protocol.json`, `bbbc031_results.json`, and `BBBC031_RESULTS.md`. The full external dataset stays under ignored `data/raw/` paths.
