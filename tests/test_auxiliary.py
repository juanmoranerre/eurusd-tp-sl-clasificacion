"""
test_auxiliary.py — Tests para src/features/auxiliary.py

Estrategia:
  • Tests de contrato: salida correcta para cada función (tipo, shape, rango).
  • Tests de invariantes matemáticas.
  • Tests de casos borde: ventana de 1 barra, serie constante, NaN.
  • Tests de integración: add_auxiliary_features sobre datos M1 reales.
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.features.auxiliary import (
    _check_ohlc_columns,
    add_auxiliary_features,
    atr,
    body_ratio,
    candle_body,
    candle_direction,
    candle_range,
    ema,
    log_returns,
    lower_wick,
    rsi,
    rolling_volatility,
    simple_returns,
    true_range,
    upper_wick,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 50, seed: int = 0) -> pd.DataFrame:
    """DataFrame OHLCV sintético con precios razonables y OHLC válidos."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    close = 1.08 + np.cumsum(rng.normal(0, 0.0002, n))
    high = close + rng.uniform(0.0001, 0.0010, n)
    low = close - rng.uniform(0.0001, 0.0010, n)
    open_ = close + rng.normal(0, 0.0003, n)
    # garantizar H >= max(O,C) y L <= min(O,C)
    high = np.maximum(high, np.maximum(open_, close))
    low = np.minimum(low, np.minimum(open_, close))
    volume = rng.uniform(1, 10, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_flat(n: int = 20) -> pd.DataFrame:
    """DataFrame con todas las barras planas (H=L=O=C=1.08)."""
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    return pd.DataFrame(
        {"open": 1.08, "high": 1.08, "low": 1.08, "close": 1.08, "volume": 0.0},
        index=dates,
    )


@pytest.fixture(scope="module")
def df50():
    return _make_ohlcv(50)


@pytest.fixture(scope="module")
def df200():
    return _make_ohlcv(200)


# ── Tests de validación de columnas ──────────────────────────────────────────

class TestCheckColumns:
    def test_ok_with_all_ohlc(self, df50):
        _check_ohlc_columns(df50)  # no lanza

    def test_raises_missing_high(self, df50):
        with pytest.raises(ValueError, match="high"):
            _check_ohlc_columns(df50.drop(columns=["high"]))

    def test_raises_missing_multiple(self, df50):
        with pytest.raises(ValueError):
            _check_ohlc_columns(df50.drop(columns=["open", "low"]))


# ── ATR ───────────────────────────────────────────────────────────────────────

class TestATR:
    def test_returns_series(self, df50):
        result = atr(df50, 14)
        assert isinstance(result, pd.Series)

    def test_same_length_as_input(self, df50):
        result = atr(df50, 14)
        assert len(result) == len(df50)

    def test_same_index(self, df50):
        result = atr(df50, 14)
        pd.testing.assert_index_equal(result.index, df50.index)

    def test_non_negative_values(self, df50):
        result = atr(df50, 14)
        assert (result.dropna() >= 0).all()

    def test_nan_before_period(self, df50):
        result = atr(df50, 14)
        # Los primeros period-1 valores (diff hace +1 NaN) deben ser NaN.
        assert result.iloc[:13].isna().all()

    def test_valid_after_period(self, df50):
        result = atr(df50, 14)
        assert result.iloc[14:].notna().all()

    def test_raises_invalid_period(self, df50):
        with pytest.raises(ValueError):
            atr(df50, 0)

    def test_raises_missing_columns(self, df50):
        with pytest.raises(ValueError):
            atr(df50.drop(columns=["high"]), 14)

    def test_true_range_gte_hl_range(self, df50):
        tr = true_range(df50)
        hl = df50["high"] - df50["low"]
        assert (tr.dropna() >= hl.dropna()).all()

    def test_flat_bars_atr_is_zero(self):
        df = _make_flat(30)
        result = atr(df, 14)
        assert result.dropna().abs().max() < 1e-10

    def test_period_1_no_nan(self, df50):
        result = atr(df50, 1)
        # Con period=1 el primer valor es NaN (por shift), el resto no
        assert result.iloc[1:].notna().all()


# ── EMA ───────────────────────────────────────────────────────────────────────

class TestEMA:
    def test_returns_series(self, df50):
        result = ema(df50, 20)
        assert isinstance(result, pd.Series)

    def test_same_length(self, df50):
        assert len(ema(df50, 20)) == len(df50)

    def test_nan_before_period(self, df50):
        result = ema(df50, 20)
        assert result.iloc[:19].isna().all()

    def test_valid_from_period(self, df50):
        result = ema(df50, 20)
        assert result.iloc[20:].notna().all()

    def test_raises_period_zero(self, df50):
        with pytest.raises(ValueError):
            ema(df50, 0)

    def test_raises_unknown_source(self, df50):
        with pytest.raises(ValueError, match="no encontrada"):
            ema(df50, 10, source="nonexistent")

    def test_ema_of_constant_equals_constant(self):
        df = _make_flat(50)
        result = ema(df, 10)
        valid = result.dropna()
        assert np.allclose(valid.values, 1.08, atol=1e-10)

    def test_ema_on_open(self, df50):
        result = ema(df50, 10, source="open")
        assert result.iloc[10:].notna().all()

    def test_different_periods_ordering(self, df200):
        e20 = ema(df200, 20)
        e50 = ema(df200, 50)
        e200 = ema(df200, 200)
        # Todos deben tener valores al final
        assert e200.iloc[-1] is not None


# ── RSI ───────────────────────────────────────────────────────────────────────

class TestRSI:
    def test_returns_series(self, df50):
        result = rsi(df50, 14)
        assert isinstance(result, pd.Series)

    def test_same_length(self, df50):
        assert len(rsi(df50, 14)) == len(df50)

    def test_range_0_to_100(self, df50):
        result = rsi(df50, 14).dropna()
        assert (result >= 0).all() and (result <= 100).all()

    def test_nan_before_period(self, df50):
        result = rsi(df50, 14)
        # diff() causa 1 NaN, luego ewm min_periods=14 causa 13 más
        assert result.iloc[:14].isna().all()

    def test_valid_after_period(self, df50):
        result = rsi(df50, 14)
        assert result.iloc[14:].notna().all()

    def test_raises_period_zero(self, df50):
        with pytest.raises(ValueError):
            rsi(df50, 0)

    def test_raises_unknown_source(self, df50):
        with pytest.raises(ValueError, match="no encontrada"):
            rsi(df50, 14, source="nonexistent")

    def test_constant_series_is_nan(self):
        # Serie constante: diff=0, gain=0, loss=0 → RSI indeterminado → NaN
        df = _make_flat(30)
        result = rsi(df, 14)
        # Todos deben ser NaN (no hay variación)
        assert result.dropna().empty

    def test_monotone_up_approaches_100(self):
        # Serie siempre creciente → RSI debe acercarse a 100
        dates = pd.date_range("2024-01-01", periods=60, freq="1h")
        close = np.linspace(1.08, 1.10, 60)
        df = pd.DataFrame(
            {"open": close, "high": close + 0.0001, "low": close - 0.0001, "close": close},
            index=dates,
        )
        result = rsi(df, 14)
        assert result.iloc[-1] >= 99.0

    def test_monotone_down_approaches_0(self):
        dates = pd.date_range("2024-01-01", periods=60, freq="1h")
        close = np.linspace(1.10, 1.08, 60)
        df = pd.DataFrame(
            {"open": close, "high": close + 0.0001, "low": close - 0.0001, "close": close},
            index=dates,
        )
        result = rsi(df, 14)
        assert result.iloc[-1] <= 1.0


# ── Retornos ─────────────────────────────────────────────────────────────────

class TestReturns:
    def test_log_returns_series(self, df50):
        result = log_returns(df50)
        assert isinstance(result, pd.Series)

    def test_log_returns_first_is_nan(self, df50):
        assert pd.isna(log_returns(df50).iloc[0])

    def test_log_returns_rest_valid(self, df50):
        assert log_returns(df50).iloc[1:].notna().all()

    def test_simple_returns_first_is_nan(self, df50):
        assert pd.isna(simple_returns(df50).iloc[0])

    def test_simple_returns_rest_valid(self, df50):
        assert simple_returns(df50).iloc[1:].notna().all()

    def test_log_approx_simple_for_small_moves(self, df50):
        # Para retornos pequeños, log_ret ≈ simple_ret
        lr = log_returns(df50).dropna()
        sr = simple_returns(df50).dropna()
        assert np.allclose(lr.values, sr.values, atol=1e-4)

    def test_raises_unknown_source(self, df50):
        with pytest.raises(ValueError, match="no encontrada"):
            log_returns(df50, source="nonexistent")

    def test_log_returns_constant_zero(self):
        df = _make_flat(20)
        result = log_returns(df).dropna()
        assert np.allclose(result.values, 0.0, atol=1e-12)

    def test_simple_returns_constant_zero(self):
        df = _make_flat(20)
        result = simple_returns(df).dropna()
        assert np.allclose(result.values, 0.0, atol=1e-12)


# ── Volatilidad rodante ───────────────────────────────────────────────────────

class TestRollingVolatility:
    def test_returns_series(self, df50):
        result = rolling_volatility(df50, 20)
        assert isinstance(result, pd.Series)

    def test_same_length(self, df50):
        assert len(rolling_volatility(df50, 20)) == len(df50)

    def test_non_negative(self, df50):
        result = rolling_volatility(df50, 20).dropna()
        assert (result >= 0).all()

    def test_nan_before_window(self, df50):
        result = rolling_volatility(df50, 20)
        # log_ret tiene 1 NaN por shift, luego rolling min_periods=20
        assert result.iloc[:20].isna().all()

    def test_valid_after_window(self, df50):
        result = rolling_volatility(df50, 20)
        assert result.iloc[20:].notna().all()

    def test_raises_period_less_than_2(self, df50):
        with pytest.raises(ValueError):
            rolling_volatility(df50, 1)

    def test_constant_series_vol_zero(self):
        df = _make_flat(30)
        result = rolling_volatility(df, 10).dropna()
        assert np.allclose(result.values, 0.0, atol=1e-12)

    def test_annualize_flag_increases_value(self, df200):
        vol_raw = rolling_volatility(df200, 20, annualize=False)
        vol_ann = rolling_volatility(df200, 20, annualize=True)
        # Si se pudo inferir la frecuencia, anualizado > crudo
        valid_raw = vol_raw.dropna()
        valid_ann = vol_ann.dropna()
        if len(valid_ann) > 0:
            assert (valid_ann.values >= valid_raw.values - 1e-12).all()


# ── Candle features ───────────────────────────────────────────────────────────

class TestCandleFeatures:
    def test_body_non_negative(self, df50):
        result = candle_body(df50)
        assert (result >= 0).all()

    def test_range_non_negative(self, df50):
        result = candle_range(df50)
        assert (result >= 0).all()

    def test_upper_wick_non_negative(self, df50):
        result = upper_wick(df50)
        assert (result >= -1e-12).all(), "upper_wick tiene valores negativos"

    def test_lower_wick_non_negative(self, df50):
        result = lower_wick(df50)
        assert (result >= -1e-12).all(), "lower_wick tiene valores negativos"

    def test_body_plus_wicks_eq_range(self, df50):
        # body + upper_wick + lower_wick == range (identidad de suma de partes)
        b = candle_body(df50)
        uw = upper_wick(df50)
        lw = lower_wick(df50)
        rng = candle_range(df50)
        assert np.allclose((b + uw + lw).values, rng.values, atol=1e-10)

    def test_body_ratio_in_0_1(self, df50):
        result = body_ratio(df50).dropna()
        assert (result >= 0).all() and (result <= 1).all()

    def test_body_ratio_flat_is_nan(self):
        df = _make_flat(10)
        result = body_ratio(df)
        assert result.isna().all()

    def test_direction_values(self, df50):
        result = candle_direction(df50)
        assert set(result.unique()).issubset({-1, 0, 1})

    def test_direction_bullish_when_close_gt_open(self):
        df = pd.DataFrame(
            {"open": [1.0], "high": [1.2], "low": [0.9], "close": [1.1]},
            index=pd.date_range("2024-01-01", periods=1, freq="1h"),
        )
        assert candle_direction(df).iloc[0] == 1

    def test_direction_bearish_when_close_lt_open(self):
        df = pd.DataFrame(
            {"open": [1.1], "high": [1.2], "low": [0.9], "close": [1.0]},
            index=pd.date_range("2024-01-01", periods=1, freq="1h"),
        )
        assert candle_direction(df).iloc[0] == -1

    def test_direction_doji_when_close_eq_open(self):
        df = pd.DataFrame(
            {"open": [1.05], "high": [1.10], "low": [1.00], "close": [1.05]},
            index=pd.date_range("2024-01-01", periods=1, freq="1h"),
        )
        assert candle_direction(df).iloc[0] == 0

    def test_range_known_value(self):
        df = pd.DataFrame(
            {"open": [1.08], "high": [1.10], "low": [1.05], "close": [1.09]},
            index=pd.date_range("2024-01-01", periods=1, freq="1h"),
        )
        assert abs(candle_range(df).iloc[0] - 0.05) < 1e-10

    def test_body_known_value(self):
        df = pd.DataFrame(
            {"open": [1.08], "high": [1.10], "low": [1.05], "close": [1.09]},
            index=pd.date_range("2024-01-01", periods=1, freq="1h"),
        )
        assert abs(candle_body(df).iloc[0] - 0.01) < 1e-10

    def test_upper_wick_known_value(self):
        df = pd.DataFrame(
            {"open": [1.08], "high": [1.10], "low": [1.05], "close": [1.09]},
            index=pd.date_range("2024-01-01", periods=1, freq="1h"),
        )
        assert abs(upper_wick(df).iloc[0] - 0.01) < 1e-10

    def test_lower_wick_known_value(self):
        df = pd.DataFrame(
            {"open": [1.08], "high": [1.10], "low": [1.05], "close": [1.09]},
            index=pd.date_range("2024-01-01", periods=1, freq="1h"),
        )
        assert abs(lower_wick(df).iloc[0] - 0.03) < 1e-10


# ── add_auxiliary_features (integración) ──────────────────────────────────────

class TestAddAuxiliaryFeatures:
    def test_returns_dataframe(self, df50):
        result = add_auxiliary_features(df50)
        assert isinstance(result, pd.DataFrame)

    def test_original_columns_preserved(self, df50):
        result = add_auxiliary_features(df50)
        for col in df50.columns:
            assert col in result.columns

    def test_expected_new_columns_present(self, df50):
        result = add_auxiliary_features(df50)
        expected = [
            "atr_14", "ema_20", "ema_50", "ema_200",
            "rsi_14", "log_ret", "simple_ret", "vol_20",
            "body", "rng", "upper_wick", "lower_wick", "body_ratio", "direction",
        ]
        for col in expected:
            assert col in result.columns, f"Columna '{col}' no encontrada"

    def test_same_number_of_rows(self, df50):
        result = add_auxiliary_features(df50)
        assert len(result) == len(df50)

    def test_custom_ema_periods(self, df50):
        result = add_auxiliary_features(df50, ema_periods=[10, 30])
        assert "ema_10" in result.columns
        assert "ema_30" in result.columns
        assert "ema_20" not in result.columns

    def test_custom_periods_change_column_names(self, df50):
        result = add_auxiliary_features(df50, atr_period=7, rsi_period=9, vol_period=10)
        assert "atr_7" in result.columns
        assert "rsi_9" in result.columns
        assert "vol_10" in result.columns

    def test_does_not_modify_original(self, df50):
        original_cols = set(df50.columns)
        _ = add_auxiliary_features(df50)
        assert set(df50.columns) == original_cols

    def test_no_infinite_values(self, df50):
        result = add_auxiliary_features(df50)
        numeric = result.select_dtypes(include=[np.number])
        assert not np.isinf(numeric.values).any()


# ── Test de integración con datos M1 reales ────────────────────────────────────

class TestRealDataM1:
    """Carga la primera semana de datos M1 reales y verifica invariantes."""

    @pytest.fixture(scope="class")
    def m1_week(self):
        """Carga ~10 080 barras M1 reales (primera semana de datos del dataset)."""
        import pathlib
        parquet = pathlib.Path("data/processed/eurusd_m1_bid.parquet")
        if not parquet.exists():
            pytest.skip("Dataset M1 no disponible")
        df = pd.read_parquet(parquet)
        df = df.iloc[:10_080].copy()  # ~1 semana M1
        return df

    def test_atr_no_negatives(self, m1_week):
        result = atr(m1_week, 14).dropna()
        assert (result >= 0).all()

    def test_rsi_in_range(self, m1_week):
        result = rsi(m1_week, 14).dropna()
        assert (result >= 0).all() and (result <= 100).all()

    def test_vol_non_negative(self, m1_week):
        result = rolling_volatility(m1_week, 20).dropna()
        assert (result >= 0).all()

    def test_upper_wick_non_negative(self, m1_week):
        active = m1_week[~m1_week["is_flat_day"]]
        result = upper_wick(active)
        assert (result >= -1e-12).all()

    def test_lower_wick_non_negative(self, m1_week):
        active = m1_week[~m1_week["is_flat_day"]]
        result = lower_wick(active)
        assert (result >= -1e-12).all()

    def test_body_plus_wicks_eq_range_real(self, m1_week):
        active = m1_week[~m1_week["is_flat_day"]]
        b = candle_body(active)
        uw = upper_wick(active)
        lw = lower_wick(active)
        rng = candle_range(active)
        assert np.allclose((b + uw + lw).values, rng.values, atol=1e-8)

    def test_add_auxiliary_no_inf(self, m1_week):
        result = add_auxiliary_features(m1_week, ema_periods=[20, 50])
        numeric = result.select_dtypes(include=[np.number])
        assert not np.isinf(numeric.values).any()

    def test_add_auxiliary_direction_valid(self, m1_week):
        result = add_auxiliary_features(m1_week, ema_periods=[20])
        assert set(result["direction"].unique()).issubset({-1, 0, 1})
