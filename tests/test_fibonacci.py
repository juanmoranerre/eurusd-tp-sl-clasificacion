"""
test_fibonacci.py — Tests para src/features/fibonacci.py
"""

import numpy as np
import pandas as pd
import pytest

from src.features.fibonacci import (
    FibSet,
    add_fibonacci_features,
    fib_levels_from_swing,
    retracement_features,
)
from config.strategy_config import FIB_ENTRY_MIN, FIB_ENTRY_PREF_LOW, FIB_ENTRY_PREF_HIGH


def _make_df(n=20):
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame(
        {"open": 1.08, "high": 1.09, "low": 1.07, "close": 1.085, "volume": 1.0},
        index=idx,
    )


T0 = pd.Timestamp("2024-01-01")
T1 = pd.Timestamp("2024-01-02")


class TestFibSet:
    def test_bullish_range(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        assert abs(fs.range - 0.04) < 1e-10

    def test_bearish_range(self):
        fs = FibSet("bearish", origin=1.12, extreme=1.08, anchor_from=T0, anchor_to=T1)
        assert abs(fs.range - 0.04) < 1e-10

    def test_price_at_0_is_extreme(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        assert abs(fs.price_at(0.0) - 1.12) < 1e-10

    def test_price_at_1_is_origin(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        assert abs(fs.price_at(1.0) - 1.08) < 1e-10

    def test_price_at_50pct(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        # 50% = (1.12 + 1.08) / 2 = 1.10
        assert abs(fs.price_at(0.5) - 1.10) < 1e-10

    def test_all_prices_returns_dict(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        prices = fs.all_prices()
        assert isinstance(prices, dict)
        assert all(isinstance(v, float) for v in prices.values())

    def test_in_entry_zone_at_50pct(self):
        # origin=1.08, extreme=1.12, price at 50% = 1.10
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        price_50 = fs.price_at(0.5)
        assert fs.in_entry_zone(price_50)

    def test_not_in_entry_zone_below_50pct(self):
        # price at 30% (retracement of 0.30 < FIB_ENTRY_MIN=0.5)
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        price_30 = fs.price_at(0.3)
        assert not fs.in_entry_zone(price_30)

    def test_in_preferred_zone_at_65pct(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        price_65 = fs.price_at(0.65)
        assert fs.in_preferred_zone(price_65)

    def test_not_in_preferred_zone_at_80pct(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        price_80 = fs.price_at(0.8)
        assert not fs.in_preferred_zone(price_80)

    def test_retracement_ratio_known_value(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        price_60 = fs.price_at(0.60)
        ratio = fs.retracement_ratio(price_60)
        assert abs(ratio - 0.60) < 1e-8

    def test_retracement_ratio_zero_range(self):
        fs = FibSet("bullish", origin=1.08, extreme=1.08, anchor_from=T0, anchor_to=T1)
        assert fs.retracement_ratio(1.08) is None

    def test_default_levels(self):
        from config.strategy_config import FIB_LEVELS
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        assert fs.levels == FIB_LEVELS

    def test_raises_invalid_direction(self):
        with pytest.raises(ValueError):
            fib_levels_from_swing(1.08, 1.12, "sideways", T0, T1)


class TestAddFibonacciFeatures:
    def test_returns_dataframe(self):
        df = _make_df()
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        result = add_fibonacci_features(df, fs)
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns_added(self):
        df = _make_df()
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        result = add_fibonacci_features(df, fs)
        for col in ["fib_retracement", "fib_in_entry_zone", "fib_in_pref_zone"]:
            assert col in result.columns

    def test_level_columns_added(self):
        df = _make_df()
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        result = add_fibonacci_features(df, fs)
        for label in ["0", "50", "60", "75", "90", "100"]:
            assert f"fib_level_{label}" in result.columns

    def test_same_length(self):
        df = _make_df()
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        result = add_fibonacci_features(df, fs)
        assert len(result) == len(df)

    def test_level_values_constant(self):
        df = _make_df()
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        result = add_fibonacci_features(df, fs)
        # El nivel 50% siempre es 1.10 (no varía fila a fila)
        assert (result["fib_level_50"] == 1.10).all()

    def test_custom_prefix(self):
        df = _make_df()
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        result = add_fibonacci_features(df, fs, prefix="myprefix")
        assert "myprefix_retracement" in result.columns

    def test_retracement_non_negative(self):
        df = _make_df()
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=T0, anchor_to=T1)
        result = add_fibonacci_features(df, fs)
        assert (result["fib_retracement"].dropna() >= 0).all()


class TestRetraceFeatures:
    def test_nan_before_anchor_to(self):
        idx = pd.date_range("2024-01-01 00:00", periods=10, freq="15min")
        df = pd.DataFrame({"open": 1.08, "high": 1.09, "low": 1.07, "close": 1.085}, index=idx)
        anchor_to = idx[5]
        fs = FibSet("bullish", origin=1.08, extreme=1.12, anchor_from=idx[0], anchor_to=anchor_to)
        result = retracement_features(df, fs)
        assert result.iloc[:5].isna().all()
        assert result.iloc[5:].notna().all()
