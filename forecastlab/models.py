"""Recursive forecasts: future target values never enter prediction features."""
import math
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

MODEL_NAMES = ("seasonal_naive", "moving_average", "ridge", "xgboost")
FEATURE_NAMES = ["lag_1", "lag_7", "lag_14", "lag_28", "mean_7", "mean_28", "std_7",
                 "weekday_sin", "weekday_cos", "year_sin", "year_cos", "time_index"]


def features(history, date, index):
    h = np.asarray(history, dtype=float)
    if len(h) < 28:
        raise ValueError("Features need at least 28 historical days.")
    return [h[-1], h[-7], h[-14], h[-28], h[-7:].mean(), h[-28:].mean(), h[-7:].std(),
            math.sin(2 * math.pi * date.dayofweek / 7), math.cos(2 * math.pi * date.dayofweek / 7),
            math.sin(2 * math.pi * date.dayofyear / 365.25), math.cos(2 * math.pi * date.dayofyear / 365.25), index]


def fit_model(name, dates, values):
    if name not in MODEL_NAMES:
        raise ValueError("Unknown model")
    if name in ("seasonal_naive", "moving_average"):
        return None
    x = np.asarray([features(values[:i], dates[i], i) for i in range(28, len(values))])
    y = np.asarray(values[28:], dtype=float)
    if name == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=20.0))
    else:
        model = XGBRegressor(n_estimators=140, max_depth=3, learning_rate=.05,
                             subsample=1.0, colsample_bytree=1.0, reg_lambda=5,
                             objective="reg:squarederror", random_state=42, n_jobs=1)
    model.fit(x, y)
    return model


def predict(name, model, dates, values, horizon):
    history = list(np.asarray(values, dtype=float))
    future = pd.date_range(pd.Timestamp(dates[-1]), periods=horizon + 1)[1:]
    result = []
    for date in future:
        if name == "seasonal_naive":
            value = history[-7]
        elif name == "moving_average":
            value = float(np.mean(history[-28:]))
        else:
            value = float(model.predict(np.asarray([features(history, date, len(history))]))[0])
        value = max(0.0, value)
        if not np.isfinite(value):
            raise ValueError("Model produced a non-finite forecast.")
        result.append(value)
        history.append(value)
    return np.asarray(result)


def metrics(actual, predicted):
    y, p = np.asarray(actual), np.asarray(predicted)
    errors = np.abs(y - p)
    denominator = float(np.abs(y).sum())
    return {"mae": float(errors.mean()), "rmse": float(np.sqrt(np.mean((y - p) ** 2))),
            "wape": float(errors.sum() / denominator) if denominator else None,
            "bias": float((p - y).mean()), "absolute_error_sum": float(errors.sum()),
            "actual_sum": denominator, "n": len(y)}


def calibration_radius(errors, coverage=.8):
    """Finite-sample corrected residual quantile; temporal exchangeability is not guaranteed."""
    errors = np.sort(np.asarray(errors, dtype=float))
    if not len(errors):
        raise ValueError("Calibration errors are required.")
    rank = min(len(errors), math.ceil((len(errors) + 1) * coverage))
    return float(errors[rank - 1])
