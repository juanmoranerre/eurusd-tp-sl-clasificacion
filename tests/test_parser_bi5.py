"""
Tests para src/data/parser_bi5.py

Valores de referencia verificados en la corrección del parser (2026-11-01):
  Archivo: data/raw/m1/2019/00/03/BID_candles_min_1.bi5  (jueves 3 enero 2019)
  Formato Dukascopy: (ts, open, CLOSE, low, HIGH, vol) — no OHLC canónico.
  Primer registro: ts=0s  O=1.13122  H=1.13175  L=1.13099  C=1.13173  V=346.92

NOTA: Los valores de H y C cambiaron respecto a la primera auditoría porque
el campo binario en posición 2 es CLOSE y el de posición 4 es HIGH.
Con el orden correcto los invariantes OHLC se cumplen en el 100% de los
registros activos del dataset (2019-2026).
"""

import datetime
import lzma
import struct
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.parser_bi5 import (
    PRICE_FACTOR,
    RECORD_SIZE,
    RECORDS_PER_DAY,
    date_from_path,
    parse_file,
)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "m1"

# Valores corregidos (2026-11-01) — orden real Dukascopy: (ts, o, c, l, h, vol)
# Antes de la corrección HIGH y CLOSE estaban intercambiados en el parser.
KNOWN_DATE  = datetime.date(2019, 1, 3)
KNOWN_PATH  = DATA_DIR / "2019" / "00" / "03" / "BID_candles_min_1.bi5"
KNOWN_OPEN  = 1.13122  # unchanged
KNOWN_HIGH  = 1.13175  # corrected (was 1.13173, que era close)
KNOWN_LOW   = 1.13099  # unchanged
KNOWN_CLOSE = 1.13173  # corrected (was 1.13175, que era high)
KNOWN_VOL   = 346.92
PRICE_TOL   = 1e-5
VOL_TOL     = 0.1


# ─────────────────────────────────────────────────────────────────────────────
# Constantes del formato
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatConstants:

    def test_record_size_is_24(self):
        assert RECORD_SIZE == 24

    def test_records_per_day(self):
        assert RECORDS_PER_DAY == 1440

    def test_price_factor(self):
        assert PRICE_FACTOR == 100_000.0


# ─────────────────────────────────────────────────────────────────────────────
# Día conocido (validación contra audit)
# ─────────────────────────────────────────────────────────────────────────────

class TestKnownDay:

    def test_record_count(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert len(df) == 1440

    def test_first_record_open(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert abs(df["open"].iloc[0] - KNOWN_OPEN) < PRICE_TOL

    def test_first_record_high(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert abs(df["high"].iloc[0] - KNOWN_HIGH) < PRICE_TOL

    def test_first_record_low(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert abs(df["low"].iloc[0] - KNOWN_LOW) < PRICE_TOL

    def test_first_record_close(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert abs(df["close"].iloc[0] - KNOWN_CLOSE) < PRICE_TOL

    def test_first_record_volume(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert abs(df["volume"].iloc[0] - KNOWN_VOL) < VOL_TOL


# ─────────────────────────────────────────────────────────────────────────────
# Reconstrucción de fechas UTC
# ─────────────────────────────────────────────────────────────────────────────

class TestDatetimeReconstruction:

    def test_first_record_is_midnight_utc(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        expected = pd.Timestamp("2019-01-03 00:00:00", tz="UTC")
        assert df["datetime"].iloc[0] == expected

    def test_second_record_is_60s_later(self):
        """Los timestamps son en SEGUNDOS (0, 60, 120, ...) → intervalos de 1 minuto."""
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        delta = df["datetime"].iloc[1] - df["datetime"].iloc[0]
        assert delta == pd.Timedelta(minutes=1)

    def test_last_record_is_2359_utc(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        expected = pd.Timestamp("2019-01-03 23:59:00", tz="UTC")
        assert df["datetime"].iloc[-1] == expected

    def test_datetime_is_tz_aware(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert df["datetime"].dt.tz is not None

    def test_datetime_timezone_is_utc(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert str(df["datetime"].dt.tz) == "UTC"

    def test_month_is_january_not_zero(self):
        """El directorio 00 debe mapearse a enero (month=1), no a month=0."""
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert df["datetime"].iloc[0].month == 1

    def test_year_is_correct(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert df["datetime"].iloc[0].year == 2019

    def test_day_is_correct(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert df["datetime"].iloc[0].day == 3


# ─────────────────────────────────────────────────────────────────────────────
# Columnas y tipos
# ─────────────────────────────────────────────────────────────────────────────

class TestSchema:

    def test_all_columns_present(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        for col in ["datetime", "open", "high", "low", "close", "volume"]:
            assert col in df.columns, f"Falta columna: {col}"

    def test_price_columns_are_float64(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        for col in ["open", "high", "low", "close", "volume"]:
            assert df[col].dtype == np.float64, f"{col} no es float64"

    def test_datetime_column_is_datetime(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert pd.api.types.is_datetime64_any_dtype(df["datetime"])


# ─────────────────────────────────────────────────────────────────────────────
# Sanidad OHLCV
# ─────────────────────────────────────────────────────────────────────────────

class TestOHLCSanity:
    """
    Con el orden de campos corregido, todos los invariantes OHLC estándar
    se cumplen en los datos activos de Dukascopy EUR/USD (2019-2026).
    """

    def test_high_gte_low(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        active = df[df["high"] != df["low"]]  # excluir registros planos
        assert (active["high"] >= active["low"]).all()

    def test_high_gte_open(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        active = df[df["high"] != df["low"]]
        assert (active["high"] >= active["open"]).all()

    def test_high_gte_close(self):
        """Con el orden de campos corregido, H >= C en todos los registros activos."""
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        active = df[df["high"] != df["low"]]
        violations = (active["close"] > active["high"]).sum()
        assert violations == 0, (
            f"El parser corregido no debe producir violaciones H < C. "
            f"Se encontraron {violations}. Verificar orden de campos en _RECORD_DTYPE."
        )

    def test_low_lte_open(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        active = df[df["high"] != df["low"]]
        assert (active["low"] <= active["open"]).all()

    def test_low_lte_close(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        active = df[df["high"] != df["low"]]
        assert (active["low"] <= active["close"]).all()

    def test_prices_in_eurusd_range(self):
        """EUR/USD histórico 2019-2026 debe estar en [0.8, 2.0]."""
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        for col in ["open", "high", "low", "close"]:
            assert (df[col] > 0.8).all(), f"{col} por debajo de 0.8"
            assert (df[col] < 2.0).all(), f"{col} por encima de 2.0"

    def test_volume_non_negative(self):
        df = parse_file(KNOWN_PATH, KNOWN_DATE)
        assert (df["volume"] >= 0).all()


# ─────────────────────────────────────────────────────────────────────────────
# Días planos (fin de semana / festivo)
# ─────────────────────────────────────────────────────────────────────────────

class TestFlatDays:

    def test_saturday_has_1440_records(self):
        """2019-01-05 (sábado) debe tener 1440 registros."""
        path = DATA_DIR / "2019" / "00" / "05" / "BID_candles_min_1.bi5"
        df = parse_file(path, datetime.date(2019, 1, 5))
        assert len(df) == 1440

    def test_saturday_ohlc_identical(self):
        """Sábados tienen OHLC idéntico en todos los registros."""
        path = DATA_DIR / "2019" / "00" / "05" / "BID_candles_min_1.bi5"
        df = parse_file(path, datetime.date(2019, 1, 5))
        assert (df["open"] == df["high"]).all()
        assert (df["high"] == df["low"]).all()
        assert (df["low"]  == df["close"]).all()

    def test_saturday_date_is_correct(self):
        """El datetime del primer registro debe ser 2019-01-05 (sábado)."""
        path = DATA_DIR / "2019" / "00" / "05" / "BID_candles_min_1.bi5"
        df = parse_file(path, datetime.date(2019, 1, 5))
        assert df["datetime"].iloc[0] == pd.Timestamp("2019-01-05 00:00:00", tz="UTC")


# ─────────────────────────────────────────────────────────────────────────────
# Manejo de errores
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorHandling:

    def test_empty_file_returns_empty_df(self, tmp_path):
        empty = tmp_path / "empty.bi5"
        empty.write_bytes(b"")
        df = parse_file(empty, datetime.date(2019, 1, 1))
        assert df.empty

    def test_empty_file_has_correct_columns(self, tmp_path):
        empty = tmp_path / "empty.bi5"
        empty.write_bytes(b"")
        df = parse_file(empty, datetime.date(2019, 1, 1))
        for col in ["datetime", "open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_corrupt_file_raises_value_error(self, tmp_path):
        bad = tmp_path / "corrupt.bi5"
        bad.write_bytes(b"\x00\x01\x02\x03" * 50)
        with pytest.raises(ValueError, match="LZMA"):
            parse_file(bad, datetime.date(2019, 1, 1))

    def test_corrupt_file_error_mentions_path(self, tmp_path):
        bad = tmp_path / "named_corrupt.bi5"
        bad.write_bytes(b"\xFF" * 100)
        with pytest.raises(ValueError) as exc_info:
            parse_file(bad, datetime.date(2019, 1, 1))
        assert "named_corrupt.bi5" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip sintético
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticRoundTrip:

    def test_single_record_roundtrip(self, tmp_path):
        """
        Construir un BI5 de 1 registro con orden binario real Dukascopy:
        (ts, open, CLOSE, low, HIGH, vol) y verificar que el parser
        devuelve las columnas OHLC correctas.
        """
        ts_s = 3_600   # 01:00:00 UTC
        o = 113_122    # open
        c = 113_173    # close  ← posición 2 en el binario
        l = 113_099    # low
        h = 113_175    # high   ← posición 4 en el binario
        v = 346.92

        # Orden binario Dukascopy: ts, o, c, l, h, v
        record = struct.pack(">IIIIIf", ts_s, o, c, l, h, v)
        f = tmp_path / "synth.bi5"
        f.write_bytes(lzma.compress(record))

        df = parse_file(f, datetime.date(2019, 1, 3))
        assert len(df) == 1
        assert df["datetime"].iloc[0] == pd.Timestamp("2019-01-03 01:00:00", tz="UTC")
        assert abs(df["open"].iloc[0]   - o / PRICE_FACTOR) < PRICE_TOL
        assert abs(df["high"].iloc[0]   - h / PRICE_FACTOR) < PRICE_TOL  # pos 4
        assert abs(df["low"].iloc[0]    - l / PRICE_FACTOR) < PRICE_TOL
        assert abs(df["close"].iloc[0]  - c / PRICE_FACTOR) < PRICE_TOL  # pos 2
        assert abs(df["volume"].iloc[0] - v) < 0.01
        # Invariante OHLC con valores correctos
        assert df["high"].iloc[0] >= df["close"].iloc[0]
        assert df["high"].iloc[0] >= df["open"].iloc[0]
        assert df["low"].iloc[0]  <= df["close"].iloc[0]
        assert df["low"].iloc[0]  <= df["open"].iloc[0]

    def test_multi_record_chronological_order(self, tmp_path):
        """Varios registros deben mantenerse en orden cronológico."""
        timestamps = [0, 60, 120]   # 00:00, 00:01, 00:02
        # Orden binario Dukascopy: (ts, open, close, low, high, vol)
        records = b"".join(
            struct.pack(">IIIIIf", ts, 113_000, 113_050, 112_900, 113_100, 100.0)
            for ts in timestamps
        )
        f = tmp_path / "multi.bi5"
        f.write_bytes(lzma.compress(records))

        df = parse_file(f, datetime.date(2020, 6, 15))
        assert len(df) == 3
        assert list(df["datetime"]) == [
            pd.Timestamp("2020-06-15 00:00:00", tz="UTC"),
            pd.Timestamp("2020-06-15 00:01:00", tz="UTC"),
            pd.Timestamp("2020-06-15 00:02:00", tz="UTC"),
        ]
        # Invariante OHLC en todos los registros
        assert (df["high"] >= df["low"]).all()
        assert (df["high"] >= df["open"]).all()
        assert (df["high"] >= df["close"]).all()


# ─────────────────────────────────────────────────────────────────────────────
# date_from_path
# ─────────────────────────────────────────────────────────────────────────────

class TestDateFromPath:

    def test_january_from_month_00(self):
        p = Path("data/raw/m1/2019/00/03/BID_candles_min_1.bi5")
        assert date_from_path(p) == datetime.date(2019, 1, 3)

    def test_december_from_month_11(self):
        p = Path("data/raw/m1/2022/11/25/BID_candles_min_1.bi5")
        assert date_from_path(p) == datetime.date(2022, 12, 25)

    def test_june_from_month_05(self):
        p = Path("data/raw/m1/2020/05/15/BID_candles_min_1.bi5")
        assert date_from_path(p) == datetime.date(2020, 6, 15)

    def test_invalid_path_raises(self):
        p = Path("not/a/valid/path.bi5")
        with pytest.raises(ValueError):
            date_from_path(p)
