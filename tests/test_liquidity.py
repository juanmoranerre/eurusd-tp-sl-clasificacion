"""
test_liquidity.py — Tests para src/features/liquidity.py
"""

import numpy as np
import pandas as pd
import pytest

from src.features.liquidity import (
    add_liquidity_features,
    detect_equal_levels,
    detect_liquidity_sweeps,
    prev_day_levels,
    prev_week_levels,
    session_levels,
    swing_liquidity,
)


def _utc_df(start: str, n: int, freq: str = "1h") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC").tz_localize(None)
    rng = np.random.default_rng(0)
    h = 1.085 + rng.uniform(0, 0.005, n)
    l = 1.080 - rng.uniform(0, 0.005, n)
    c = (h + l) / 2
    o = c - 0.0002
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1.0}, index=idx)


class TestPrevDayLevels:
    def test_adds_pdh_pdl(self):
        df = _utc_df("2024-01-01", 72)  # 3 días H1
        result = prev_day_levels(df)
        assert "pdh" in result.columns
        assert "pdl" in result.columns

    def test_pdh_no_lookahead(self):
        df = _utc_df("2024-01-01", 72)
        result = prev_day_levels(df)
        # Las primeras 24 horas (día 1) no tienen día previo → NaN
        first_day = result.iloc[:24]
        assert first_day["pdh"].isna().all()

    def test_pdh_second_day_is_first_day_max(self):
        df = _utc_df("2024-01-01", 72)
        result = prev_day_levels(df)
        first_day_max = df.iloc[:24]["high"].max()
        # Segundo día (barras 24-47): pdh debe ser el máximo del día 1
        second_day_pdh = result.iloc[24]["pdh"]
        assert abs(second_day_pdh - first_day_max) < 1e-10

    def test_same_length(self):
        df = _utc_df("2024-01-01", 48)
        result = prev_day_levels(df)
        assert len(result) == len(df)

    def test_raises_non_datetime_index(self):
        df = pd.DataFrame({"open": [1.], "high": [1.], "low": [1.], "close": [1.]}, index=[0])
        with pytest.raises(TypeError):
            prev_day_levels(df)


class TestPrevWeekLevels:
    def test_adds_pwh_pwl(self):
        df = _utc_df("2024-01-01", 240)  # 10 días H1
        result = prev_week_levels(df)
        assert "pwh" in result.columns
        assert "pwl" in result.columns

    def test_same_length(self):
        df = _utc_df("2024-01-01", 240)
        result = prev_week_levels(df)
        assert len(result) == len(df)


class TestDetectEqualLevels:
    def test_detects_equal_highs(self):
        # Crear dos barras con el mismo high dentro de la tolerancia
        idx = pd.date_range("2024-01-01", periods=5, freq="1h")
        h = np.array([1.09, 1.08, 1.09, 1.08, 1.085])  # barras 0 y 2 tienen h≈1.09
        l = h - 0.005
        c = (h + l) / 2
        df = pd.DataFrame({"open": c, "high": h, "low": l, "close": c}, index=idx)
        result = detect_equal_levels(df, lookback=5, tolerance_pips=0.5)
        # Barra 2 tiene high=1.09 igual que barra 0 → EQH en barra 2
        assert result["eqh"].iloc[2]

    def test_detects_equal_lows(self):
        idx = pd.date_range("2024-01-01", periods=5, freq="1h")
        l = np.array([1.08, 1.09, 1.08, 1.085, 1.09])  # barras 0 y 2 tienen l≈1.08
        h = l + 0.005
        c = (h + l) / 2
        df = pd.DataFrame({"open": c, "high": h, "low": l, "close": c}, index=idx)
        result = detect_equal_levels(df, lookback=5, tolerance_pips=0.5)
        assert result["eql"].iloc[2]

    def test_no_false_positives_large_difference(self):
        idx = pd.date_range("2024-01-01", periods=5, freq="1h")
        h = np.array([1.08, 1.09, 1.10, 1.11, 1.12])
        l = h - 0.005
        c = (h + l) / 2
        df = pd.DataFrame({"open": c, "high": h, "low": l, "close": c}, index=idx)
        result = detect_equal_levels(df, lookback=5, tolerance_pips=0.5)
        assert not result["eqh"].any()

    def test_adds_columns(self):
        df = _utc_df("2024-01-01", 20)
        result = detect_equal_levels(df, lookback=10)
        for col in ["eqh", "eql", "eqh_level", "eql_level"]:
            assert col in result.columns


class TestDetectLiquiditySweeps:
    def test_bsl_sweep_candidate(self):
        # Wick supera el nivel Y close regresa por debajo → sweep_candidate + rejection_confirm
        idx = pd.date_range("2024-01-01", periods=3, freq="1h")
        df = pd.DataFrame({
            "open": [1.08, 1.085, 1.08],
            "high": [1.09, 1.11, 1.085],   # barra 1 wick supera 1.10
            "low":  [1.078, 1.082, 1.078],
            "close": [1.085, 1.083, 1.082],  # close regresa por debajo de 1.10
            "pdh":  [np.nan, 1.10, 1.10],   # nivel BSL en 1.10
        }, index=idx)
        result = detect_liquidity_sweeps(df, "pdh", direction="bsl")
        assert result["pdh_sweep_candidate"].iloc[1]
        # high > level AND close < level → también rejection_confirm (PD-012)
        assert result["pdh_rejection_confirm"].iloc[1]

    def test_bsl_sweep_only_no_rejection(self):
        # Wick supera el nivel pero close CIERRA por encima → solo sweep_candidate
        idx = pd.date_range("2024-01-01", periods=2, freq="1h")
        df = pd.DataFrame({
            "open":  [1.09, 1.09],
            "high":  [1.09, 1.105],
            "low":   [1.088, 1.088],
            "close": [1.089, 1.102],  # close > 1.10 → NO rejection
            "pdh":   [1.10, 1.10],
        }, index=idx)
        result = detect_liquidity_sweeps(df, "pdh", direction="bsl")
        assert result["pdh_sweep_candidate"].iloc[1]
        assert not result["pdh_rejection_confirm"].iloc[1]

    def test_bsl_rejection_confirm(self):
        idx = pd.date_range("2024-01-01", periods=2, freq="1h")
        df = pd.DataFrame({
            "open":  [1.09, 1.09],
            "high":  [1.09, 1.105],
            "low":   [1.088, 1.088],
            "close": [1.089, 1.095],  # close < 1.10 → rejection
            "pdh":   [1.10, 1.10],
        }, index=idx)
        result = detect_liquidity_sweeps(df, "pdh", direction="bsl")
        assert result["pdh_rejection_confirm"].iloc[1]

    def test_ssl_sweep_candidate(self):
        idx = pd.date_range("2024-01-01", periods=2, freq="1h")
        df = pd.DataFrame({
            "open":  [1.08, 1.08],
            "high":  [1.082, 1.082],
            "low":   [1.079, 1.075],  # low < 1.078 (ssl level)
            "close": [1.08, 1.076],
            "pdl":   [1.078, 1.078],
        }, index=idx)
        result = detect_liquidity_sweeps(df, "pdl", direction="ssl")
        assert result["pdl_sweep_candidate"].iloc[1]

    def test_raises_unknown_direction(self):
        df = _utc_df("2024-01-01", 5)
        df["pdh"] = 1.09
        with pytest.raises(ValueError):
            detect_liquidity_sweeps(df, "pdh", direction="unknown")

    def test_raises_missing_level_column(self):
        df = _utc_df("2024-01-01", 5)
        with pytest.raises(ValueError):
            detect_liquidity_sweeps(df, "nonexistent", direction="bsl")


class TestAddLiquidityFeatures:
    def test_returns_dataframe(self):
        df = _utc_df("2024-01-01", 72)
        result = add_liquidity_features(df)
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns_present(self):
        df = _utc_df("2024-01-01", 72)
        result = add_liquidity_features(df)
        for col in ["pdh", "pdl", "pwh", "pwl", "eqh", "eql"]:
            assert col in result.columns

    def test_same_length(self):
        df = _utc_df("2024-01-01", 72)
        result = add_liquidity_features(df)
        assert len(result) == len(df)

    def test_does_not_modify_original(self):
        df = _utc_df("2024-01-01", 72)
        cols_before = set(df.columns)
        _ = add_liquidity_features(df)
        assert set(df.columns) == cols_before
