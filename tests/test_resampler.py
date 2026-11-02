"""
Tests para src/data/resampler.py

Verifica:
  - Agregación OHLCV correcta (primer open, max high, min low, último close, suma vol)
  - Etiquetado temporal: inicio del período (label='left')
  - is_flat_period: True solo cuando todos los M1 del período son días planos
  - Sin períodos vacíos ni duplicados
  - Número de barras correcto para períodos conocidos
  - Invariantes OHLC en datos reales
  - Manejo de errores (DataFrame vacío, columnas faltantes)
"""

import datetime
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.resampler import (
    SUPPORTED_TIMEFRAMES,
    build_all_timeframes,
    build_timeframe,
    resample_ohlcv,
    validate_ohlcv_invariants,
)

PROJECT_ROOT = Path(__file__).parent.parent
M1_PARQUET = PROJECT_ROOT / "data" / "processed" / "eurusd_m1_bid.parquet"

PRICE_TOL = 1e-5


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_synthetic_m1(
    date: datetime.date,
    n: int = 60,
    base_price: float = 1.10000,
    flat: bool = False,
) -> pd.DataFrame:
    """
    Crear un DataFrame M1 sintético para un número de minutos dado.
    Si flat=True, todos los registros tienen OHLC idéntico (simula fin de semana).
    """
    start = pd.Timestamp(date, tz="UTC")
    datetimes = [start + pd.Timedelta(minutes=i) for i in range(n)]

    if flat:
        opens  = [base_price] * n
        highs  = [base_price] * n
        lows   = [base_price] * n
        closes = [base_price] * n
        vols   = [0.0] * n
    else:
        rng = np.random.default_rng(42)
        opens  = base_price + rng.normal(0, 0.0002, n)
        highs  = opens + rng.uniform(0.0001, 0.0005, n)
        lows   = opens - rng.uniform(0.0001, 0.0005, n)
        closes = base_price + rng.normal(0, 0.0002, n)
        vols   = rng.uniform(50, 500, n)

    return pd.DataFrame({
        "datetime":    datetimes,
        "open":        opens,
        "high":        highs,
        "low":         lows,
        "close":       closes,
        "volume":      vols,
        "is_flat_day": [flat] * n,
    })


@pytest.fixture(scope="module")
def m1_one_week():
    """5 días activos (lunes a viernes 2019-01-07 → 2019-01-11) de 1440 min cada uno."""
    from src.data.loader import load_range
    df, _ = load_range(
        PROJECT_ROOT / "data" / "raw" / "m1",
        start=datetime.date(2019, 1, 7),
        end=datetime.date(2019, 1, 11),
    )
    return df


@pytest.fixture(scope="module")
def m1_full():
    """Dataset M1 completo (cargado una vez por módulo de test)."""
    if not M1_PARQUET.exists():
        pytest.skip("Parquet M1 no encontrado. Ejecutar scripts/build_dataset.py primero.")
    return pd.read_parquet(M1_PARQUET)


# ── resample_ohlcv: errores ────────────────────────────────────────────────────

class TestResampleErrors:

    def test_empty_dataframe_raises(self):
        empty = pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume", "is_flat_day"])
        with pytest.raises(ValueError, match="vacío"):
            resample_ohlcv(empty, "15min")

    def test_missing_column_raises(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        df = df.drop(columns=["volume"])
        with pytest.raises(ValueError, match="Faltan columnas"):
            resample_ohlcv(df, "15min")

    def test_unsupported_tf_raises(self):
        with pytest.raises(ValueError, match="no soportada"):
            build_timeframe(_make_synthetic_m1(datetime.date(2020, 1, 6), n=60), "m5")


# ── resample_ohlcv: agregación OHLCV ─────────────────────────────────────────

class TestOHLCVAggregation:

    def test_open_is_first(self):
        """El open de la barra superior es el open del primer M1 del período."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        # Primera barra: minutos 0-14
        expected_open = df["open"].iloc[0]
        assert abs(m15["open"].iloc[0] - expected_open) < PRICE_TOL

    def test_high_is_max(self):
        """El high de la barra es el máximo de todos los highs M1 del período."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        expected_high = df.iloc[:15]["high"].max()
        assert abs(m15["high"].iloc[0] - expected_high) < PRICE_TOL

    def test_low_is_min(self):
        """El low de la barra es el mínimo de todos los lows M1 del período."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        expected_low = df.iloc[:15]["low"].min()
        assert abs(m15["low"].iloc[0] - expected_low) < PRICE_TOL

    def test_close_is_last(self):
        """El close de la barra es el close del último M1 del período."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        expected_close = df["close"].iloc[14]   # minuto 14 = último de la primera barra M15
        assert abs(m15["close"].iloc[0] - expected_close) < PRICE_TOL

    def test_volume_is_sum(self):
        """El volumen de la barra es la suma de los volúmenes M1 del período."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        expected_vol = df["volume"].iloc[:15].sum()
        assert abs(m15["volume"].iloc[0] - expected_vol) < 0.01

    def test_bar_count_m15_from_60_minutes(self):
        """60 minutos → exactamente 4 barras M15."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        assert len(m15) == 4

    def test_bar_count_h1_from_60_minutes(self):
        """60 minutos → exactamente 1 barra H1."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        h1 = resample_ohlcv(df, "1h")
        assert len(h1) == 1

    def test_bar_count_h4_from_240_minutes(self):
        """240 minutos → exactamente 1 barra H4."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=240)
        h4 = resample_ohlcv(df, "4h")
        assert len(h4) == 1


# ── resample_ohlcv: etiquetado temporal ──────────────────────────────────────

class TestTemporalLabeling:

    def test_m15_label_is_bar_start(self):
        """La etiqueta de cada barra M15 es el inicio del período (00:00, 00:15, ...)."""
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=30)
        m15 = resample_ohlcv(df, "15min")
        expected_first = pd.Timestamp("2020-01-06 00:00:00", tz="UTC")
        expected_second = pd.Timestamp("2020-01-06 00:15:00", tz="UTC")
        assert m15["datetime"].iloc[0] == expected_first
        assert m15["datetime"].iloc[1] == expected_second

    def test_h1_label_is_bar_start(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=120)
        h1 = resample_ohlcv(df, "1h")
        expected = pd.Timestamp("2020-01-06 00:00:00", tz="UTC")
        assert h1["datetime"].iloc[0] == expected

    def test_h4_label_is_bar_start(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=240)
        h4 = resample_ohlcv(df, "4h")
        expected = pd.Timestamp("2020-01-06 00:00:00", tz="UTC")
        assert h4["datetime"].iloc[0] == expected

    def test_datetime_is_tz_aware(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        assert m15["datetime"].dt.tz is not None

    def test_datetime_timezone_utc(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        assert str(m15["datetime"].dt.tz) == "UTC"

    def test_chronological_order(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=240)
        m15 = resample_ohlcv(df, "15min")
        assert m15["datetime"].is_monotonic_increasing

    def test_no_duplicate_datetimes(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=240)
        m15 = resample_ohlcv(df, "15min")
        assert m15["datetime"].nunique() == len(m15)


# ── resample_ohlcv: is_flat_period ────────────────────────────────────────────

class TestFlatPeriod:

    def test_flat_day_produces_flat_periods(self):
        """Un día plano (is_flat_day=True en todos los M1) produce is_flat_period=True."""
        df_flat = _make_synthetic_m1(datetime.date(2020, 1, 4), n=60, flat=True)
        m15 = resample_ohlcv(df_flat, "15min")
        assert m15["is_flat_period"].all()

    def test_active_day_produces_active_periods(self):
        """Un día activo produce is_flat_period=False."""
        df_active = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60, flat=False)
        m15 = resample_ohlcv(df_active, "15min")
        assert not m15["is_flat_period"].any()

    def test_mixed_day_partial_flat(self):
        """
        Un período con mezcla de minutos planos y activos produce is_flat_period=False.
        """
        # Primera mitad plana, segunda activa
        df_flat   = _make_synthetic_m1(datetime.date(2020, 1, 6), n=30, flat=True)
        df_active = _make_synthetic_m1(datetime.date(2020, 1, 6), n=30, flat=False)
        # Ajustar datetime de la parte activa (comienza en el minuto 30)
        df_active = df_active.copy()
        df_active["datetime"] = df_active["datetime"] + pd.Timedelta(minutes=30)
        df_mixed = pd.concat([df_flat, df_active], ignore_index=True)
        df_mixed = df_mixed.sort_values("datetime").reset_index(drop=True)

        m15 = resample_ohlcv(df_mixed, "15min")
        # Barras 00:00-00:14 y 00:15-00:29: todas flat → is_flat_period=True
        assert m15.iloc[0]["is_flat_period"] is True or m15.iloc[0]["is_flat_period"] == True
        assert m15.iloc[1]["is_flat_period"] is True or m15.iloc[1]["is_flat_period"] == True
        # Barras 00:30-00:44 y 00:45-00:59: todas activas → is_flat_period=False
        assert m15.iloc[2]["is_flat_period"] is False or m15.iloc[2]["is_flat_period"] == False


# ── resample_ohlcv: schema de salida ─────────────────────────────────────────

class TestOutputSchema:

    def test_all_columns_present(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        for col in ["datetime", "open", "high", "low", "close", "volume", "is_flat_period"]:
            assert col in m15.columns

    def test_price_columns_float64(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        for col in ["open", "high", "low", "close"]:
            assert m15[col].dtype == np.float64, f"{col} no es float64"

    def test_is_flat_period_is_bool(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        assert m15["is_flat_period"].dtype == bool


# ── Datos reales: una semana ──────────────────────────────────────────────────

class TestRealDataOneWeek:

    def test_m15_bar_count_one_full_day(self, m1_one_week):
        """Un día activo de 1440 minutos → 96 barras M15."""
        one_day = m1_one_week[m1_one_week["datetime"].dt.date == datetime.date(2019, 1, 7)]
        m15 = resample_ohlcv(one_day, "15min")
        assert len(m15) == 96

    def test_h1_bar_count_one_full_day(self, m1_one_week):
        """Un día activo de 1440 minutos → 24 barras H1."""
        one_day = m1_one_week[m1_one_week["datetime"].dt.date == datetime.date(2019, 1, 7)]
        h1 = resample_ohlcv(one_day, "1h")
        assert len(h1) == 24

    def test_h4_bar_count_one_full_day(self, m1_one_week):
        """Un día activo de 1440 minutos → 6 barras H4."""
        one_day = m1_one_week[m1_one_week["datetime"].dt.date == datetime.date(2019, 1, 7)]
        h4 = resample_ohlcv(one_day, "4h")
        assert len(h4) == 6

    def test_ohlc_invariants_m15(self, m1_one_week):
        """Invariantes OHLC correctos en datos reales M15."""
        m15 = resample_ohlcv(m1_one_week, "15min")
        result = validate_ohlcv_invariants(m15, "M15-1semana")
        assert result["ok"], f"Violaciones: {result['violations']}"

    def test_ohlc_invariants_h1(self, m1_one_week):
        h1 = resample_ohlcv(m1_one_week, "1h")
        result = validate_ohlcv_invariants(h1, "H1-1semana")
        assert result["ok"], f"Violaciones: {result['violations']}"

    def test_ohlc_invariants_h4(self, m1_one_week):
        h4 = resample_ohlcv(m1_one_week, "4h")
        result = validate_ohlcv_invariants(h4, "H4-1semana")
        assert result["ok"], f"Violaciones: {result['violations']}"

    def test_prices_in_eurusd_range_m15(self, m1_one_week):
        """Precios EUR/USD M15 en rango razonable."""
        m15 = resample_ohlcv(m1_one_week, "15min")
        active = m15[~m15["is_flat_period"]]
        for col in ["open", "high", "low", "close"]:
            assert (active[col] > 0.8).all()
            assert (active[col] < 2.0).all()


# ── build_timeframe / build_all_timeframes ────────────────────────────────────

class TestBuildTimeframe:

    def test_build_m15(self, m1_one_week):
        df = build_timeframe(m1_one_week, "m15")
        assert len(df) > 0
        assert "is_flat_period" in df.columns

    def test_build_all_returns_all_keys(self, m1_one_week):
        result = build_all_timeframes(m1_one_week)
        assert set(result.keys()) == set(SUPPORTED_TIMEFRAMES.keys())

    def test_build_subset(self, m1_one_week):
        result = build_all_timeframes(m1_one_week, timeframes=["m15", "h1"])
        assert set(result.keys()) == {"m15", "h1"}

    def test_unsupported_name_raises(self):
        with pytest.raises(ValueError, match="no soportada"):
            build_timeframe(
                _make_synthetic_m1(datetime.date(2020, 1, 6), n=60),
                "m5",
            )


# ── validate_ohlcv_invariants ─────────────────────────────────────────────────

class TestValidateInvariants:

    def test_valid_data_returns_ok(self):
        df = _make_synthetic_m1(datetime.date(2020, 1, 6), n=60)
        m15 = resample_ohlcv(df, "15min")
        result = validate_ohlcv_invariants(m15)
        assert result["ok"]

    def test_invalid_data_returns_not_ok(self):
        """DataFrame con high < close explícito."""
        df = pd.DataFrame({
            "datetime":        [pd.Timestamp("2020-01-06", tz="UTC")],
            "open":            [1.10],
            "high":            [1.10],
            "low":             [1.09],
            "close":           [1.11],  # close > high → violación
            "volume":          [100.0],
            "is_flat_period":  [False],
        })
        result = validate_ohlcv_invariants(df)
        assert not result["ok"]
        assert result["violations"]["H < C"] == 1


# ── Dataset completo: invariantes globales ────────────────────────────────────

class TestFullDatasetInvariants:
    """
    Tests de integración que usan el dataset M1 completo.
    Tardan más pero son la verificación definitiva.
    """

    def test_m15_full_dataset_ohlc_valid(self, m1_full):
        m15 = resample_ohlcv(m1_full, "15min")
        result = validate_ohlcv_invariants(m15, "M15-full")
        assert result["ok"], f"Violaciones en M15 completo: {result['violations']}"

    def test_h1_full_dataset_ohlc_valid(self, m1_full):
        h1 = resample_ohlcv(m1_full, "1h")
        result = validate_ohlcv_invariants(h1, "H1-full")
        assert result["ok"]

    def test_h4_full_dataset_ohlc_valid(self, m1_full):
        h4 = resample_ohlcv(m1_full, "4h")
        result = validate_ohlcv_invariants(h4, "H4-full")
        assert result["ok"]

    def test_m15_bar_count_range(self, m1_full):
        """
        El dataset M1 cubre 2019-01-01 a 2026-10-16.
        Aproximadamente 2846 días × 96 barras/día = ~273.000 barras M15.
        """
        m15 = resample_ohlcv(m1_full, "15min")
        assert 250_000 < len(m15) < 290_000, f"Número inesperado de barras M15: {len(m15)}"

    def test_m15_chronological(self, m1_full):
        m15 = resample_ohlcv(m1_full, "15min")
        assert m15["datetime"].is_monotonic_increasing

    def test_m15_no_duplicates(self, m1_full):
        m15 = resample_ohlcv(m1_full, "15min")
        assert m15["datetime"].nunique() == len(m15)
