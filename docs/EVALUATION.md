# Measured evaluation results

These results were produced by the delivered code with the recorded dependency versions, a 14-day horizon, and the included datasets. They are not promised performance for a different dataset or future deployment.

## Final holdout, by series

| Dataset | Series | Selected model | MAE | Seasonal naive MAE | WAPE | Observed band coverage |
|---|---|---|---:|---:|---:|---:|
| synthetic-demo | Daily orders | ridge | 14.26 | 27.36 | 4.90% | 100.0% |
| synthetic-demo | Support requests | ridge | 11.83 | 14.93 | 7.49% | 57.1% |
| synthetic-demo | Web traffic | ridge | 19.95 | 44.36 | 3.70% | 92.9% |
| public-bike-rentals | Bike rentals | ridge | 2403.02 | 2522.43 | 94.61% | 28.6% |

The nominal interval level is 80%. Coverage is measured over only 14 holdout observations per series. Small test windows are noisy and do not establish long-term performance.

## Synthetic example

Three deterministic fictional series have 560 daily observations each. The final holdout is 2026-09-13 through 2026-09-26. Future predictions cover 2026-09-27 through 2026-10-10.

The demo demonstrates application mechanics. Its errors and baseline improvements cannot substantiate real business impact. The lower coverage on support requests is retained and visible; the nominal band level is not relabeled to hide this outcome.

## Public historical example

The UCI Bike Sharing example contains 731 daily total rental counts from 2011-01-01 through 2012-12-31. Its holdout is 2012-12-18 through 2012-12-31. The subsequent January 2013 forecasts are historical demonstrations, not current forecasts.

The selected Ridge model performs poorly in absolute terms, even though its MAE is slightly lower than the seasonal baseline. WAPE is approximately 94.6%, and observed band coverage is 28.6%. This is a failed accuracy/coverage outcome for this test period, not evidence that the system is ready for operational rental planning.

Possible limitations include omitted future-known calendar variables, weather information unavailable at the forecast origin, nonstationarity, recursive error propagation, and a short evaluation horizon. These are hypotheses and modeling limitations, not established causal explanations for the observed errors.

No model was changed to improve this displayed final test result after inspecting it. Future model revisions should use development windows and be assessed on a newly reserved test period.

## Inspect the evidence

The CSV/JSON files under `examples/results/` contain the actual selection comparisons, final holdout predictions, future predictions, source manifests, and summary metrics. They are generated outputs, not hand-written chart fixtures.

- `comparison.csv` contains only selection-window metrics, not holdout scores.
- `holdout.csv` includes actual values, selected-model predictions, baseline predictions, and bands.
- `forecasts.csv` contains predictions after the dataset's last observation.
- `summary.json` records fold boundaries and library versions.
- `manifest.json` identifies the dataset snapshot and source hash.

Recompute MAE as the mean of `abs(actual - prediction)` in the holdout CSV. Recompute WAPE as the sum of those absolute errors divided by the sum of actual values. The test suite independently checks these calculations.

For source attribution and transformation details, see `examples/bike-rentals.source.json` and `THIRD_PARTY_NOTICES.md`.
