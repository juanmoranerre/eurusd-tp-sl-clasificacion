"""
Tests para src/data/loader.py

Cubre:
  - discover_files: cobertura, orden cronológico, conversión mes 0-indexado
  - is_flat_day: detección de días planos
  - load_range: carga de rangos, flags is_flat_day, manejo de errores
"""

import datetime
import lzma
import struct
from pathlib import Path

import pandas as pd
import pytest

from src.data.loader import discover_files, is_flat_day, load_range

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "m1"


# ─────────────────────────────────────────────────────────────────────────────
# discover_files
# ─────────────────────────────────────────────────────────────────────────────

class TestDiscoverFiles:

    def test_total_file_count(self):
        """Debe descubrir exactamente 2846 archivos."""
        files = discover_files(DATA_DIR)
        assert len(files) == 2846

    def test_sorted_chronologically(self):
        files = discover_files(DATA_DIR)
        dates = [d for d, _ in files]
        assert dates == sorted(dates)

    def test_first_date_is_2019_01_01(self):
        files = discover_files(DATA_DIR)
        assert files[0][0] == datetime.date(2019, 1, 1)

    def test_last_date_is_2026_10_16(self):
        files = discover_files(DATA_DIR)
        assert files[-1][0] == datetime.date(2026, 10, 16)

    def test_no_duplicate_dates(self):
        files = discover_files(DATA_DIR)
        dates = [d for d, _ in files]
        assert len(dates) == len(set(dates))

    def test_all_paths_exist(self):
        files = discover_files(DATA_DIR)
        missing = [str(p) for _, p in files if not p.exists()]
        assert missing == [], f"Archivos no encontrados: {missing[:5]}"

    def test_month_00_maps_to_january(self):
        """El directorio '00' debe dar fechas de enero (month=1)."""
        files = discover_files(DATA_DIR)
        jan_2019 = [d for d, _ in files if d.year == 2019 and d.month == 1]
        assert len(jan_2019) == 31

    def test_month_11_maps_to_december(self):
        """El directorio '11' debe dar fechas de diciembre (month=12)."""
        files = discover_files(DATA_DIR)
        dec_2019 = [d for d, _ in files if d.year == 2019 and d.month == 12]
        assert len(dec_2019) == 31

    def test_range_filter_start(self):
        start = datetime.date(2023, 1, 1)
        files = discover_files(DATA_DIR, start=start)
        assert all(d >= start for d, _ in files)

    def test_range_filter_end(self):
        end = datetime.date(2019, 12, 31)
        files = discover_files(DATA_DIR, end=end)
        assert all(d <= end for d, _ in files)

    def test_range_filter_single_year(self):
        files = discover_files(
            DATA_DIR,
            start=datetime.date(2021, 1, 1),
            end=datetime.date(2021, 12, 31),
        )
        assert len(files) == 365
        assert all(d.year == 2021 for d, _ in files)

    def test_range_filter_leap_year(self):
        files = discover_files(
            DATA_DIR,
            start=datetime.date(2020, 1, 1),
            end=datetime.date(2020, 12, 31),
        )
        assert len(files) == 366  # 2020 es bisiesto


# ─────────────────────────────────────────────────────────────────────────────
# is_flat_day
# ─────────────────────────────────────────────────────────────────────────────

class TestIsFlatDay:

    def test_flat_all_identical(self):
        df = pd.DataFrame({
            "open":  [1.13, 1.13, 1.13],
            "high":  [1.13, 1.13, 1.13],
            "low":   [1.13, 1.13, 1.13],
            "close": [1.13, 1.13, 1.13],
        })
        assert is_flat_day(df) is True

    def test_active_varying_prices(self):
        df = pd.DataFrame({
            "open":  [1.13,  1.14],
            "high":  [1.135, 1.145],
            "low":   [1.128, 1.138],
            "close": [1.132, 1.142],
        })
        assert is_flat_day(df) is False

    def test_one_different_record_is_not_flat(self):
        """Un único registro distinto convierte el día en activo."""
        df = pd.DataFrame({
            "open":  [1.13, 1.14, 1.13],
            "high":  [1.13, 1.13, 1.13],
            "low":   [1.13, 1.13, 1.13],
            "close": [1.13, 1.13, 1.13],
        })
        assert is_flat_day(df) is False

    def test_real_saturday_is_flat(self):
        """2019-01-05 (sábado) debe ser detectado como día plano."""
        from src.data.parser_bi5 import parse_file
        path = DATA_DIR / "2019" / "00" / "05" / "BID_candles_min_1.bi5"
        df = parse_file(path, datetime.date(2019, 1, 5))
        assert is_flat_day(df) is True

    def test_real_weekday_is_not_flat(self):
        """2019-01-03 (jueves) no debe ser día plano."""
        from src.data.parser_bi5 import parse_file
        path = DATA_DIR / "2019" / "00" / "03" / "BID_candles_min_1.bi5"
        df = parse_file(path, datetime.date(2019, 1, 3))
        assert is_flat_day(df) is False


# ─────────────────────────────────────────────────────────────────────────────
# load_range
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadRange:

    def test_single_active_day_record_count(self):
        df, stats = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 3),
            end=datetime.date(2019, 1, 3),
        )
        assert len(df) == 1440
        assert stats["loaded"] == 1
        assert stats["errors"] == 0

    def test_single_active_day_no_flat_flag(self):
        df, _ = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 3),
            end=datetime.date(2019, 1, 3),
        )
        assert not df["is_flat_day"].any()

    def test_single_weekend_day_flat_flag(self):
        """2019-01-05 (sábado) debe tener is_flat_day=True en todos los registros."""
        df, stats = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 5),
            end=datetime.date(2019, 1, 5),
        )
        assert len(df) == 1440
        assert df["is_flat_day"].all()
        assert stats["flat_days"] == 1
        assert stats["active_days"] == 0

    def test_stats_counts_flat_and_active(self):
        # Semana del 1-6 enero 2019: mar(1,nuevo año=festivo?), mier(2), jue(3), vie(4), sab(5), dom(6)
        # Jan 1 = Tuesday (festivo), Jan 5 = Saturday, Jan 6 = Sunday
        df, stats = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 1),
            end=datetime.date(2019, 1, 7),
        )
        assert stats["loaded"] == 7
        assert stats["flat_days"] + stats["active_days"] == 7
        assert stats["errors"] == 0

    def test_is_flat_day_column_present(self):
        df, _ = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 3),
            end=datetime.date(2019, 1, 4),
        )
        assert "is_flat_day" in df.columns

    def test_chronological_order(self):
        df, _ = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 3),
            end=datetime.date(2019, 1, 7),
        )
        assert df["datetime"].is_monotonic_increasing

    def test_no_duplicate_datetime(self):
        df, _ = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 3),
            end=datetime.date(2019, 1, 7),
        )
        assert df["datetime"].nunique() == len(df)

    def test_stats_total_records(self):
        _, stats = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 3),
            end=datetime.date(2019, 1, 5),   # 3 días × 1440 = 4320
        )
        assert stats["total_records"] == 3 * 1440

    def test_stats_date_range(self):
        _, stats = load_range(
            DATA_DIR,
            start=datetime.date(2019, 1, 3),
            end=datetime.date(2019, 1, 5),
        )
        assert stats["date_start"] == datetime.date(2019, 1, 3)
        assert stats["date_end"]   == datetime.date(2019, 1, 5)

    def test_corrupt_file_counted_in_errors(self, tmp_path):
        """Un archivo corrupto debe registrarse en stats['errors'] sin abortar."""
        # Crear directorio falso con archivo corrupto
        fake_dir = tmp_path / "2019" / "00" / "03"
        fake_dir.mkdir(parents=True)
        (fake_dir / "BID_candles_min_1.bi5").write_bytes(b"\x00" * 100)

        _, stats = load_range(tmp_path)
        assert stats["errors"] == 1
        assert len(stats["error_files"]) == 1

    def test_no_files_returns_empty_df(self, tmp_path):
        """Directorio sin archivos BI5 debe devolver DataFrame vacío."""
        (tmp_path / "2099").mkdir()
        df, stats = load_range(tmp_path)
        assert df.empty
        assert stats["loaded"] == 0
