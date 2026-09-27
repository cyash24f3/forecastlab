# Modeling and evaluation specification

## Scope

Daily, contiguous, nonnegative univariate series. Each series is modeled independently. Dates are calendar dates without time-of-day/timezone conversion. Targets may be fractional counts/volumes, so predictions are not rounded until presentation or integer inventory ordering.

No external regressors are accepted in v1. Observed sales/rental counts are not necessarily unconstrained demand: stockouts, unavailable capacity, or service closure can censor observations.

## Data contract

See `data.py` for authoritative checks. Missing observations, duplicate dates, invalid dates, non-finite values, and negative values are rejected. Outliers are retained; a surprising value is not automatically an error. Zero values remain zero. No random row splits are used.

## Model inputs

A training row at date t uses only values strictly before t:

- Lags 1, 7, 14, and 28.
- Trailing means of the previous 7 and 28 days.
- Population standard deviation of the previous 7 days.
- Sine/cosine of weekday, period 7.
- Sine/cosine of day of year, period 365.25.
- Integer time index from the start of the series.

The first 28 rows have no training features. The earliest fold retains at least 84 observed rows, leaving at least 56 supervised samples.

## Candidate settings

| Candidate | Fixed configuration |
|---|---|
| Seasonal naive | Repeat the most recent seven days recursively |
| Moving average | Mean of the previous 28 available values at each recursive step |
| Ridge | StandardScaler fitted on training features only; Ridge alpha 20 |
| XGBoost | 140 trees, depth 3, learning rate .05, L2 regularization 5, squared-error objective, full row/column sampling, seed 42, one thread |

These settings are fixed design choices, not hyperparameters selected on the final holdout. The model chosen per series minimizes aggregate selection-fold MAE. In a tie, candidate order favors the simpler baseline.

The same actual observations underpin all candidates' selection metrics. WAPE therefore induces the same ranking as MAE for a fixed series with nonzero total demand.

## Temporal layout

Let N be series length and H be the forecast horizon (7–28).

- First cutoff: `N - 6H`.
- Selection cutoffs: `N - 6H`, `N - 5H`, `N - 4H`.
- Calibration cutoffs: `N - 3H`, `N - 2H`.
- Holdout cutoff: `N - H`.
- Every fit uses indices `[0, cutoff)`; every forecast covers `[cutoff, cutoff+H)`.
- Minimum history: `N >= 84 + 6H`.

No forecast call receives future labels. Recursive features append predictions for future time steps. Once an entire window has passed, its actual observations are legitimately available to fit the next origin.

A leakage regression test changes only final holdout values. It verifies unchanged selection scores, selected model, and calibration width. Holdout errors must change.

## Metrics

For actual values y and predictions p across n points:

- `MAE = sum(abs(p - y)) / n`.
- `RMSE = sqrt(sum((p - y)^2) / n)`.
- `WAPE = sum(abs(p - y)) / sum(abs(y))`; undefined if the denominator is zero.
- `Bias = sum(p - y) / n`; positive means overforecasting.
- `Coverage = count(lower <= y <= upper) / n`.
- `MAE improvement % = 100 × (1 - selected_MAE / baseline_MAE)`; undefined when baseline MAE is zero.

The UI uses per-series metrics. Summary/MLflow pooled diagnostics sum point errors across series; they are not valid business aggregates when series units differ. Do not interpret combined website visits, orders, and support requests as one demand measure. WAPE can exceed 100% and is not classification accuracy.

## Interval calibration

For the selected model, collect 2H absolute forecast residuals from the two calibration windows. Let `r = min(n, ceil((n + 1) × .8))`. Use the r-th ordered residual as a constant per-series radius q.

Future daily band: `[max(0, prediction - q), prediction + q]`.

This uses a finite-sample corrected quantile inspired by split-conformal residual calibration, but temporal residuals are not guaranteed exchangeable, the model is refit, and residuals across lead times are pooled. **No distribution-free or time-series coverage guarantee is claimed.** Holdout coverage is measured honestly and can be far from 80%.

Bands are marginal daily estimates, not simultaneous paths. Do not add upper/lower bands to claim a valid total-demand interval or a service-level guarantee. The final model is fitted to more observations than the calibration models; stale residual widths may be inappropriate after a regime change.

## Planning

### Capacity

For each day, expected scenario demand equals `forecast × multiplier`.

`overflow = max(0, expected - capacity)`.

Total overflow is the sum of daily overflow, with no cross-day carry-over. The demand multiplier is an explicit assumption, not a learned estimate of the effect of a business intervention.

### Inventory

`protection period = lead time + review period`.

`target stock = expected demand over protection period + user-entered safety stock`.

`inventory position = on-hand + on-order`.

`recommended order = ceil(max(0, target stock - inventory position))`.

Lead time plus review period must fit the forecast horizon. Existing inbound orders are assumed to arrive within the protection period. No backorders, lead-time uncertainty, shelf-life limits, minimum order quantities, holding costs, or order costs are modeled.

The pre-delivery shortfall indicator compares lead-time expected demand with on-hand stock and deliberately excludes on-order stock because arrival dates are not supplied. It is a potential shortfall under that assumption, not a precise stockout prediction.

## Improvements requiring new validation

- Add future-known holiday/calendar covariates with clear provenance.
- Support exogenous variables only with forecast-origin availability checks.
- Compare direct multi-horizon models and intermittent-demand methods.
- Add more untouched origins for robust performance estimates.
- Consider horizon-specific or adaptive intervals with enough calibration data.
- Add drift/label monitoring after repeated real deployment observations.

Once a holdout has informed a model change, treat it as development data and reserve a new test period. Do not repeatedly optimize against the displayed public-data holdout and still describe it as untouched.
