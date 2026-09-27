import json
import joblib
import numpy as np
import pandas as pd
import pytest
from forecastlab.data import make_demo, validate_csv
from forecastlab.pipeline import run_pipeline, validate_training
from forecastlab.models import predict


@pytest.fixture
def frame():
    df, _ = validate_csv(make_demo(days=180).query("series_id == 'Daily orders'").to_csv(index=False).encode())
    return df


def test_temporal_isolation_artifacts_and_model_reload(frame, tmp_path):
    first = run_pipeline(frame, 7, tmp_path / 'a')
    altered = frame.copy()
    altered.loc[altered.index[-7:], 'value'] *= 5
    second = run_pipeline(altered, 7, tmp_path / 'b')
    a, b = first['series'][0], second['series'][0]
    # Changing only holdout labels cannot influence selection or calibration.
    assert a['model'] == b['model']
    assert a['interval_radius'] == b['interval_radius']
    pd.testing.assert_frame_equal(pd.read_csv(tmp_path/'a/comparison.csv'), pd.read_csv(tmp_path/'b/comparison.csv'))
    assert a['holdout']['mae'] != b['holdout']['mae']
    for fold in a['folds']:
        assert fold['train_end'] < fold['test_start'] <= fold['test_end']
    assert a['folds'][2]['test_end'] < a['folds'][3]['test_start']
    assert a['folds'][4]['test_end'] < a['folds'][5]['test_start']
    bundles = joblib.load(tmp_path/'a/models.joblib')
    bundle = bundles['Daily orders']
    reproduced = predict(bundle['model_name'], bundle['model'], bundle['dates'], bundle['values'], 7)
    forecast = pd.read_csv(tmp_path/'a/forecasts.csv')
    np.testing.assert_allclose(reproduced, forecast.prediction)
    assert forecast.date.min() > frame.date.max().strftime('%Y-%m-%d')
    assert (forecast.lower <= forecast.prediction).all()
    assert (forecast.upper >= forecast.prediction).all()
    # Independent recomputation from exported predictions.
    holdout = pd.read_csv(tmp_path/'a/holdout.csv')
    errors = (holdout.actual-holdout.prediction).abs()
    assert a['holdout']['mae'] == pytest.approx(errors.sum()/len(holdout))
    assert a['holdout']['wape'] == pytest.approx(errors.sum()/holdout.actual.sum())


def test_zero_series_serializes_without_nan(frame, tmp_path):
    frame['value'] = 0.
    result = run_pipeline(frame, 7, tmp_path)
    json.dumps(result, allow_nan=False)
    assert result['aggregate_holdout']['wape'] is None
    assert result['aggregate_holdout']['mae'] == 0
    assert result['holdout_coverage'] == 1


def test_short_history_is_rejected(frame):
    with pytest.raises(ValueError, match='252 daily rows required'):
        validate_training(frame, 28)
