import numpy as np
import pandas as pd
import pytest
from forecastlab.data import validate_csv, make_demo, MAX_BYTES


def raw(df):
    return df.to_csv(index=False).encode()


def sample():
    return pd.DataFrame({'date': pd.date_range('2025-01-01', periods=180).strftime('%Y-%m-%d'),
                         'series_id': 'signal', 'value': np.arange(180, dtype=float)})


def test_demo_deterministic_and_valid():
    assert raw(make_demo()) == raw(make_demo())
    frame, q = validate_csv(raw(make_demo()))
    assert len(frame) == 1680 and q['series_count'] == 3
    assert q['missing_days'] == 0 and len(q['sha256']) == 64


@pytest.mark.parametrize('case', ['duplicate', 'missing_day', 'negative', 'nan', 'infinity', 'bad_date',
                                  'bad_id', 'non_numeric', 'missing_column', 'too_large_value'])
def test_invalid_data_rejected(case):
    df = sample()
    if case == 'duplicate':
        df = pd.concat([df, df.iloc[:1]])
    elif case == 'missing_day':
        df = df.drop(9)
    elif case == 'negative':
        df.loc[0, 'value'] = -1
    elif case == 'nan':
        df.loc[0, 'value'] = np.nan
    elif case == 'infinity':
        df.loc[0, 'value'] = np.inf
    elif case == 'bad_date':
        df.loc[0, 'date'] = '2025-02-30'
    elif case == 'bad_id':
        df.loc[0, 'series_id'] = '<script>'
    elif case == 'non_numeric':
        df['value'] = 'foo'
    elif case == 'missing_column':
        df = df.drop(columns=['value'])
    elif case == 'too_large_value':
        df.loc[0, 'value'] = 1e10
    with pytest.raises(ValueError):
        validate_csv(raw(df))


def test_size_limit():
    with pytest.raises(ValueError, match='5 MiB'):
        validate_csv(b'x' * (MAX_BYTES + 1))


def test_zero_values_preserved():
    df = sample()
    df['value'] = 0
    result, quality = validate_csv(raw(df))
    assert result.value.sum() == 0
    assert quality['series'][0]['zero_share'] == 1
    assert len(quality['warnings']) == 2


def test_numeric_series_id_keeps_leading_zero():
    df = sample()
    df['series_id'] = '001'
    result, _ = validate_csv(raw(df))
    assert result.series_id.iloc[0] == '001'
