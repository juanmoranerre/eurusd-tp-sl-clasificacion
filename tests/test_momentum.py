"""
test_momentum.py — Tests para src/features/momentum.py
"""

import numpy as np
import pandas as pd
import pytest

from src.features.momentum import (
    add_momentum_features,
    body_to_range_ratio,
    close_position,
    directional_momentum,
    displacement_score,
    range_to_atr_ratio,
    speed_score,
)


def _make_df(n: int = 20, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    o = 1.08 + rng.uniform(-0.005, 0.005, n)
    c = o + rng.uniform(-0.003, 0.003, n)
    h = np.maximum(o, c) + rng.uniform(0, 0.002, n)
    l = np.minimum(o, c) - rng.uniform(0, 0.002, n)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1.0}, index=idx)


class TestBodyToRangeRatio:
    def test_returns_series(self):
        df = _make_df()
        result = body_to_range_ratio(df)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        df = _make_df()
        result = body_to_range_ratio(df)
        assert len(result) == len(df)

    def test_values_in_0_to_1(self):
        df = _make_df()
        result = body_to_range_ratio(df).dropna()
        assert (result >= 0).all() and (result <= 1).all()

    def test_doji_is_zero(self):
        idx = pd.date_range("2024-01-01", periods=1, freq="15min")
        df = pd.DataFrame({"open": [1.08], "high": [1.09], "low": [1.07], "close": [1.08]}, index=idx)
        result = body_to_range_ratio(df)
        assert result.iloc[0] == 0.0

    def test_full_body_is_one(self):
        # Open=Low, Close=High → cuerpo = rango
        idx = pd.date_range("2024-01-01", periods=1, freq="15min")
        df = pd.DataFrame({"open": [1.07], "high": [1.09], "low": [1.07], "close": [1.09]}, index=idx)
        result = body_to_range_ratio(df)
        assert abs(result.iloc[0] - 1.0) < 1e-10


class TestRangeToATRRatio:
    def test_returns_series(self):
        df = _make_df()
        result = range_to_atr_ratio(df)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        df = _make_df()
        result = range_to_atr_ratio(df)
        assert len(result) == len(df)

    def test_values_non_negative(self):
        df = _make_df()
        result = range_to_atr_ratio(df).dropna()
        assert (result >= 0).all()

    def test_large_bar_gives_ratio_above_one(self):
        # Una barra mucho más grande que el ATR debe tener ratio > 1
        idx = pd.date_range("2024-01-01", periods=20, freq="15min")
        o = np.ones(20) * 1.08
        c = o + 0.0001  # barras pequeñas para establecer ATR bajo
        h = c + 0.0001
        l = o - 0.0001
        # última barra: rango enorme
        h[-1] = 1.10
        l[-1] = 1.06
        c[-1] = 1.08
        df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)
        result = range_to_atr_ratio(df)
        assert result.iloc[-1] > 1.0


class TestClosePosition:
    def test_returns_series(self):
        df = _make_df()
        result = close_position(df)
        assert isinstance(result, pd.Series)

    def test_values_in_0_to_1(self):
        df = _make_df()
        result = close_position(df).dropna()
        assert (result >= 0).all() and (result <= 1).all()

    def test_close_at_high(self):
        idx = pd.date_range("2024-01-01", periods=1, freq="15min")
        df = pd.DataFrame({"open": [1.07], "high": [1.09], "low": [1.07], "close": [1.09]}, index=idx)
        result = close_position(df)
        assert abs(result.iloc[0] - 1.0) < 1e-10

    def test_close_at_low(self):
        idx = pd.date_range("2024-01-01", periods=1, freq="15min")
        df = pd.DataFrame({"open": [1.09], "high": [1.09], "low": [1.07], "close": [1.07]}, index=idx)
        result = close_position(df)
        assert result.iloc[0] == 0.0


class TestDirectionalMomentum:
    def test_bullish_bar_is_positive(self):
        idx = pd.date_range("2024-01-01", periods=1, freq="15min")
        df = pd.DataFrame({"open": [1.08], "high": [1.09], "low": [1.07], "close": [1.085]}, index=idx)
        result = directional_momentum(df)
        assert result.iloc[0] == 1

    def test_bearish_bar_is_negative(self):
        idx = pd.date_range("2024-01-01", periods=1, freq="15min")
        df = pd.DataFrame({"open": [1.085], "high": [1.09], "low": [1.07], "close": [1.08]}, index=idx)
        result = directional_momentum(df)
        assert result.iloc[0] == -1

    def test_doji_is_zero(self):
        idx = pd.date_range("2024-01-01", periods=1, freq="15min")
        df = pd.DataFrame({"open": [1.08], "high": [1.09], "low": [1.07], "close": [1.08]}, index=idx)
        result = directional_momentum(df)
        assert result.iloc[0] == 0


class TestSpeedScore:
    def test_returns_series(self):
        df = _make_df()
        result = speed_score(df)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        df = _make_df()
        result = speed_score(df)
        assert len(result) == len(df)

    def test_fast_bar_above_one(self):
        # Barras pequeñas seguidas de una barra grande → speed > 1
        idx = pd.date_range("2024-01-01", periods=10, freq="15min")
        o = np.ones(10) * 1.08
        c = o + 0.0001
        h = c + 0.0001
        l = o - 0.0001
        h[-1] = 1.10
        l[-1] = 1.06
        c[-1] = 1.08
        df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)
        result = speed_score(df, lookback=5)
        assert result.iloc[-1] > 1.0


class TestDisplacementScore:
    def test_returns_series(self):
        df = _make_df()
        result = displacement_score(df)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        df = _make_df()
        result = displacement_score(df)
        assert len(result) == len(df)

    def test_values_in_0_to_1(self):
        df = _make_df()
        result = displacement_score(df)
        assert (result >= 0).all() and (result <= 1).all()

    def test_strong_bar_has_high_score(self):
        # Barra con cuerpo completo, rango 2x ATR, cierre en extremo → score alto
        idx = pd.date_range("2024-01-01", periods=20, freq="15min")
        o = np.ones(20) * 1.08
        c = o + 0.0002  # barras pequeñas
        h = c + 0.0001
        l = o - 0.0001
        # última barra: alcista fuerte, cierre en el máximo
        o[-1] = 1.08
        h[-1] = 1.095
        l[-1] = 1.08
        c[-1] = 1.095
        df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)
        result = displacement_score(df)
        assert result.iloc[-1] > 0.5

    def test_raises_missing_columns(self):
        df = pd.DataFrame({"open": [1.08], "high": [1.09]})
        with pytest.raises(ValueError, match="Faltan columnas"):
            displacement_score(df)

    def test_name_attribute(self):
        df = _make_df()
        result = displacement_score(df)
        assert result.name == "displacement_score"


class TestAddMomentumFeatures:
    def test_returns_dataframe(self):
        df = _make_df()
        result = add_momentum_features(df)
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns_added(self):
        df = _make_df()
        result = add_momentum_features(df)
        for col in [
            "body_range_ratio",
            "range_atr_ratio",
            "close_position",
            "directional_momentum",
            "speed_score",
            "displacement_score",
        ]:
            assert col in result.columns

    def test_same_length(self):
        df = _make_df()
        result = add_momentum_features(df)
        assert len(result) == len(df)

    def test_does_not_modify_original(self):
        df = _make_df()
        cols_before = set(df.columns)
        _ = add_momentum_features(df)
        assert set(df.columns) == cols_before

    def test_displacement_score_bounded(self):
        df = _make_df()
        result = add_momentum_features(df)
        scores = result["displacement_score"]
        assert (scores >= 0).all() and (scores <= 1).all()
