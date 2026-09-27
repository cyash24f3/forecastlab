import numpy as np
import pandas as pd
import pytest
from forecastlab.models import features, predict, fit_model, metrics, calibration_radius


def test_features_are_only_past_values():
    h = np.arange(1, 31)
    x = features(h, pd.Timestamp('2025-01-01'), 30)
    assert x[:4] == [30, 24, 17, 3]
    assert x[4] == np.mean(h[-7:])
    assert x[5] == np.mean(h[-28:])


def test_seasonal_naive_repeats_week_without_future_actuals():
    dates = pd.date_range('2025-01-01', periods=35)
    values = np.arange(35)
    prediction = predict('seasonal_naive', None, dates, values, 14)
    np.testing.assert_array_equal(prediction, np.tile(np.arange(28, 35), 2))


@pytest.mark.parametrize('name', ['ridge', 'xgboost'])
def test_learned_models_predict_finite_nonnegative(name):
    dates = pd.date_range('2025-01-01', periods=100)
    values = 30 + np.sin(np.arange(100)/7) * 10
    model = fit_model(name, dates, values)
    p = predict(name, model, dates, values, 14)
    assert len(p) == 14 and np.isfinite(p).all() and (p >= 0).all()


def test_metrics_hand_calculated_and_zero_denominator():
    m = metrics([10, 20], [8, 24])
    assert m['mae'] == 3
    assert m['wape'] == .2
    assert m['bias'] == 1
    assert m['rmse'] == pytest.approx(np.sqrt(10))
    assert metrics([0, 0], [1, 2])['wape'] is None


def test_calibration_uses_finite_sample_rank():
    assert calibration_radius(np.arange(1, 11), .8) == 9
    assert calibration_radius([0, 0], .8) == 0
