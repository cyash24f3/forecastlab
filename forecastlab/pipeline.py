"""Three selection folds → two calibration folds → one untouched test fold → final refit."""
from datetime import datetime, timezone
import json
import platform
from importlib.metadata import version
import joblib
import numpy as np
import pandas as pd
from .models import MODEL_NAMES, FEATURE_NAMES, fit_model, predict, metrics, calibration_radius


def minimum_rows(horizon):
    return 84 + 6 * horizon


def validate_training(df, horizon):
    if not 7 <= horizon <= 28:
        raise ValueError("Horizon must be between 7 and 28 days.")
    for name, g in df.groupby("series_id"):
        if len(g) < minimum_rows(horizon):
            raise ValueError(f"{name}: {minimum_rows(horizon)} daily rows required for a {horizon}-day horizon; found {len(g)}.")


def run_pipeline(df, horizon, output, progress=lambda message: None):
    validate_training(df, horizon)
    output.mkdir(parents=True, exist_ok=True)
    forecasts, evaluation, comparisons, series_results, bundles = [], [], [], [], {}
    for name, g in df.groupby("series_id", sort=True):
        dates = pd.DatetimeIndex(g.date)
        values = g.value.to_numpy(dtype=float)
        n = len(values)
        first_cut = n - 6 * horizon
        folds = []
        selection = {m: {"actual": [], "predicted": []} for m in MODEL_NAMES}
        for fold in range(3):
            cut = first_cut + fold * horizon
            folds.append({"purpose": "selection", "train_end": str(dates[cut-1].date()),
                          "test_start": str(dates[cut].date()), "test_end": str(dates[cut+horizon-1].date())})
            for model_name in MODEL_NAMES:
                progress(f"{name}: selection fold {fold+1}/3 · {model_name}")
                model = fit_model(model_name, dates[:cut], values[:cut])
                p = predict(model_name, model, dates[:cut], values[:cut], horizon)
                selection[model_name]["actual"].extend(values[cut:cut+horizon])
                selection[model_name]["predicted"].extend(p)
        scores = {m: metrics(v["actual"], v["predicted"]) for m, v in selection.items()}
        # Per-series MAE and WAPE induce the same ordering for a fixed target window.
        chosen = min(MODEL_NAMES, key=lambda m: scores[m]["mae"])
        for model_name in MODEL_NAMES:
            comparisons.append({"series_id": name, "model": model_name, "selected": model_name == chosen,
                                **scores[model_name]})
        residuals = []
        for fold in range(3, 5):
            cut = first_cut + fold * horizon
            progress(f"{name}: interval calibration {fold-2}/2")
            model = fit_model(chosen, dates[:cut], values[:cut])
            p = predict(chosen, model, dates[:cut], values[:cut], horizon)
            residuals.extend(np.abs(values[cut:cut+horizon] - p))
            folds.append({"purpose": "calibration", "train_end": str(dates[cut-1].date()),
                          "test_start": str(dates[cut].date()), "test_end": str(dates[cut+horizon-1].date())})
        radius = calibration_radius(residuals)
        cut = n - horizon
        progress(f"{name}: untouched holdout evaluation")
        model = fit_model(chosen, dates[:cut], values[:cut])
        p = predict(chosen, model, dates[:cut], values[:cut], horizon)
        baseline = predict("seasonal_naive", None, dates[:cut], values[:cut], horizon)
        y = values[cut:]
        lower, upper = np.maximum(0, p - radius), p + radius
        for i in range(horizon):
            evaluation.append({"series_id": name, "date": str(dates[cut+i].date()), "actual": float(y[i]),
                               "prediction": float(p[i]), "baseline": float(baseline[i]),
                               "lower": float(lower[i]), "upper": float(upper[i]), "model": chosen})
        folds.append({"purpose": "holdout", "train_end": str(dates[cut-1].date()),
                      "test_start": str(dates[cut].date()), "test_end": str(dates[-1].date())})
        test_metrics = metrics(y, p)
        base_metrics = metrics(y, baseline)
        coverage = float(np.mean((y >= lower) & (y <= upper)))
        final_model = fit_model(chosen, dates, values)
        final = predict(chosen, final_model, dates, values, horizon)
        future = pd.date_range(dates[-1], periods=horizon + 1)[1:]
        for i, date in enumerate(future):
            forecasts.append({"series_id": name, "date": str(date.date()), "prediction": float(final[i]),
                              "lower": float(max(0, final[i] - radius)), "upper": float(final[i] + radius),
                              "model": chosen})
        importance = None
        if chosen == "xgboost":
            importance = dict(zip(FEATURE_NAMES, map(float, final_model.feature_importances_)))
        series_results.append({"series_id": name, "model": chosen, "holdout": test_metrics,
                               "baseline": base_metrics, "coverage": coverage, "interval_radius": radius,
                               "calibration_points": len(residuals), "folds": folds, "feature_importance": importance})
        bundles[name] = {"model_name": chosen, "model": final_model, "dates": dates,
                         "values": values, "interval_radius": radius, "horizon": horizon}
    ev = pd.DataFrame(evaluation)
    aggregate = metrics(ev.actual, ev.prediction)
    base = metrics(ev.actual, ev.baseline)
    summary = {"created_at": datetime.now(timezone.utc).isoformat(), "horizon": horizon,
               "nominal_coverage": .8, "series": series_results, "aggregate_holdout": aggregate,
               "aggregate_baseline": base,
               "aggregate_note": "Pooled numeric error diagnostics; meaningful as business aggregates only when series share units. The UI reports each series separately.",
               "holdout_coverage": float(((ev.actual >= ev.lower) & (ev.actual <= ev.upper)).mean()),
               "mae_improvement_pct": 100 * (1 - aggregate["mae"] / base["mae"]) if base["mae"] else None,
               "methodology": "3 rolling selection folds, 2 subsequent calibration folds, 1 final holdout. Each fold forecasts recursively. Selected models are refit on all data only after holdout scoring.",
               "interval_note": "Nominal 80% empirical absolute-residual bands pooled across horizons within each series. Temporal dependence and refitting can reduce coverage; these are not guaranteed or simultaneous intervals.",
               "versions": {p: version(p) for p in ["numpy", "pandas", "scikit-learn", "xgboost"]},
               "python": platform.python_version()}
    pd.DataFrame(forecasts).to_csv(output / "forecasts.csv", index=False)
    ev.to_csv(output / "holdout.csv", index=False)
    pd.DataFrame(comparisons).to_csv(output / "comparison.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    joblib.dump(bundles, output / "models.joblib")
    progress("Artifacts saved")
    return summary
