"""
test_sessions.py — Tests para src/features/sessions.py

Estrategia:
  • Timestamps sintéticos con fechas y horas conocidas, incluidas semanas de cambio DST.
  • Verificar ventanas horarias en ambas zonas (LK, NY AM).
  • Verificar conversiones correctas con DST para EE.UU. vs RU en semanas diferentes.
  • Tests de contrato: tipo de salida, shape, no-lookahead (índice no se modifica).
  • Integración: primera semana de datos M1 reales.
"""

import pandas as pd
import pytest

from src.features.sessions import (
    add_session_features,
    any_session,
    in_session,
    london_killzone,
    local_time_info,
    newyork_am_forex_alt,
    newyork_am_open,
    session_bar_counts,
)
from config.strategy_config import LONDON_KILLZONE, NEWYORK_AM_OPEN, NEWYORK_AM_FOREX_ALT


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _utc_ts(dt_str: str) -> pd.DataFrame:
    """DataFrame mínimo con un único timestamp UTC."""
    idx = pd.DatetimeIndex([pd.Timestamp(dt_str)])
    return pd.DataFrame({"close": [1.08]}, index=idx)


def _utc_range(start: str, periods: int, freq: str = "15min") -> pd.DataFrame:
    """DataFrame con rango de timestamps UTC."""
    idx = pd.date_range(start, periods=periods, freq=freq)
    return pd.DataFrame({"open": 1.08, "high": 1.09, "low": 1.07, "close": 1.08}, index=idx)


# ── London Killzone: 02:00–05:00 America/New_York ─────────────────────────────
# En horario EST (UTC-5): corresponde a 07:00–10:00 UTC
# En horario EDT (UTC-4): corresponde a 06:00–09:00 UTC

class TestLondonKillzone:
    def test_inside_winter_est(self):
        # 2024-01-15 07:30 UTC = 02:30 EST → dentro de LK
        df = _utc_ts("2024-01-15 07:30")
        assert london_killzone(df).iloc[0]

    def test_outside_winter_before(self):
        # 2024-01-15 06:59 UTC = 01:59 EST → fuera de LK
        df = _utc_ts("2024-01-15 06:59")
        assert not london_killzone(df).iloc[0]

    def test_outside_winter_after(self):
        # 2024-01-15 10:01 UTC = 05:01 EST → fuera de LK
        df = _utc_ts("2024-01-15 10:01")
        assert not london_killzone(df).iloc[0]

    def test_inside_summer_edt(self):
        # 2024-06-15 08:30 UTC = 04:30 EDT → dentro de LK (06:00–09:00 UTC en verano)
        df = _utc_ts("2024-06-15 08:30")
        assert london_killzone(df).iloc[0]

    def test_outside_summer_after(self):
        # 2024-06-15 09:01 UTC = 05:01 EDT → fuera de LK
        df = _utc_ts("2024-06-15 09:01")
        assert not london_killzone(df).iloc[0]

    def test_boundary_start_inclusive(self):
        # Exactamente 02:00 EST = 07:00 UTC (enero, invierno)
        df = _utc_ts("2024-01-15 07:00")
        assert london_killzone(df).iloc[0]

    def test_boundary_end_exclusive(self):
        # Exactamente 05:00 EST = 10:00 UTC (enero, invierno)
        df = _utc_ts("2024-01-15 10:00")
        assert not london_killzone(df).iloc[0]

    def test_returns_series(self):
        df = _utc_range("2024-01-15 06:00", 20)
        result = london_killzone(df)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        df = _utc_range("2024-01-15 06:00", 48)
        assert len(london_killzone(df)) == len(df)

    def test_same_index(self):
        df = _utc_range("2024-01-15 06:00", 20)
        pd.testing.assert_index_equal(london_killzone(df).index, df.index)

    def test_weekend_no_session(self):
        # Sábado: aunque sea horario LK, el mercado está cerrado
        # El filtro de sesión no filtra fines de semana (eso lo hace is_flat_day)
        # Pero la ventana horaria sigue siendo válida
        df = _utc_ts("2024-01-13 08:00")  # sábado 08:00 UTC = 03:00 EST
        # Debe estar dentro de la ventana (la exclusión de mercado cierra viene de is_flat_day)
        assert london_killzone(df).iloc[0]


# ── NY AM Open: 09:30–11:00 America/New_York ─────────────────────────────────
# En EST (UTC-5): 14:30–16:00 UTC
# En EDT (UTC-4): 13:30–15:00 UTC

class TestNewYorkAMOpen:
    def test_inside_winter_est(self):
        # 2024-01-15 15:00 UTC = 10:00 EST → dentro de NY AM
        df = _utc_ts("2024-01-15 15:00")
        assert newyork_am_open(df).iloc[0]

    def test_outside_winter_before(self):
        # 2024-01-15 14:29 UTC = 09:29 EST → fuera de NY AM
        df = _utc_ts("2024-01-15 14:29")
        assert not newyork_am_open(df).iloc[0]

    def test_outside_winter_after(self):
        # 2024-01-15 16:01 UTC = 11:01 EST → fuera de NY AM
        df = _utc_ts("2024-01-15 16:01")
        assert not newyork_am_open(df).iloc[0]

    def test_inside_summer_edt(self):
        # 2024-06-15 14:00 UTC = 10:00 EDT → dentro de NY AM (13:30–15:00 UTC en verano)
        df = _utc_ts("2024-06-15 14:00")
        assert newyork_am_open(df).iloc[0]

    def test_boundary_start_inclusive(self):
        # 09:30 EST = 14:30 UTC (enero)
        df = _utc_ts("2024-01-15 14:30")
        assert newyork_am_open(df).iloc[0]

    def test_boundary_end_exclusive(self):
        # 11:00 EST = 16:00 UTC (enero)
        df = _utc_ts("2024-01-15 16:00")
        assert not newyork_am_open(df).iloc[0]

    def test_returns_series(self):
        df = _utc_range("2024-01-15 13:00", 20)
        assert isinstance(newyork_am_open(df), pd.Series)

    def test_same_length(self):
        df = _utc_range("2024-01-15 13:00", 48)
        assert len(newyork_am_open(df)) == len(df)


# ── NY AM Forex Alt: 07:00–10:00 America/New_York ────────────────────────────

class TestNewYorkAMForexAlt:
    def test_inside_winter(self):
        # 07:30 EST = 12:30 UTC (enero)
        df = _utc_ts("2024-01-15 12:30")
        assert newyork_am_forex_alt(df).iloc[0]

    def test_outside_before(self):
        # 06:59 EST = 11:59 UTC (enero)
        df = _utc_ts("2024-01-15 11:59")
        assert not newyork_am_forex_alt(df).iloc[0]

    def test_outside_after(self):
        # 10:01 EST = 15:01 UTC (enero)
        df = _utc_ts("2024-01-15 15:01")
        assert not newyork_am_forex_alt(df).iloc[0]


# ── DST correctness: semanas de cambio de horario distintas entre EE.UU. y RU ─

class TestDSTCorrectness:
    """
    EE.UU. DST 2024: entra el 10 mar (clocks forward), sale el 3 nov.
    RU no ajusta DST (siempre BST o GMT, varía; Europa cambia el 31 mar / 27 oct).
    La zona America/New_York con zoneinfo usa las reglas históricas correctas.
    """

    def test_us_spring_forward_2024(self):
        # 2024-03-10 spring forward: clocks EDT. LK es 02:00-05:00 EDT.
        # 08:30 UTC = 04:30 EDT → DENTRO de LK
        df_in = _utc_ts("2024-03-10 08:30")
        assert london_killzone(df_in).iloc[0]
        # 09:30 UTC = 05:30 EDT → FUERA de LK (después de las 05:00)
        df_out = _utc_ts("2024-03-10 09:30")
        assert not london_killzone(df_out).iloc[0]

    def test_us_summer_lk_offset(self):
        # Verano: LK 02:00-05:00 EDT = 06:00-09:00 UTC
        df_in = _utc_ts("2024-07-15 07:00")   # 03:00 EDT → dentro
        df_out = _utc_ts("2024-07-15 09:01")  # 05:01 EDT → fuera
        assert london_killzone(df_in).iloc[0]
        assert not london_killzone(df_out).iloc[0]

    def test_us_winter_lk_offset(self):
        # Invierno: LK 02:00-05:00 EST = 07:00-10:00 UTC
        df_in = _utc_ts("2024-01-15 08:00")   # 03:00 EST → dentro
        df_out = _utc_ts("2024-01-15 10:01")  # 05:01 EST → fuera
        assert london_killzone(df_in).iloc[0]
        assert not london_killzone(df_out).iloc[0]

    def test_winter_summer_ny_am_offset(self):
        # NY AM: invierno 14:30-16:00 UTC, verano 13:30-15:00 UTC
        df_winter = _utc_ts("2024-01-15 14:45")  # 09:45 EST → dentro
        df_summer = _utc_ts("2024-06-15 13:45")  # 09:45 EDT → dentro
        df_wrong = _utc_ts("2024-06-15 15:01")   # 11:01 EDT → FUERA de NY AM (end=11:00 EDT = 15:00 UTC)
        assert newyork_am_open(df_winter).iloc[0]
        assert newyork_am_open(df_summer).iloc[0]
        assert not newyork_am_open(df_wrong).iloc[0]


# ── any_session ────────────────────────────────────────────────────────────────

class TestAnySession:
    def test_true_when_in_lk(self):
        df = _utc_ts("2024-01-15 08:00")  # dentro LK (EST)
        assert any_session(df).iloc[0]

    def test_true_when_in_ny_am(self):
        df = _utc_ts("2024-01-15 15:00")  # dentro NY AM (EST)
        assert any_session(df).iloc[0]

    def test_false_outside_all(self):
        # 2024-01-15 12:00 UTC = 07:00 EST → fuera de LK (10:00 UTC) y NY AM (14:30 UTC)
        df = _utc_ts("2024-01-15 12:00")
        assert not any_session(df).iloc[0]

    def test_name(self):
        df = _utc_range("2024-01-15 06:00", 10)
        assert any_session(df).name == "any_session"


# ── local_time_info ────────────────────────────────────────────────────────────

class TestLocalTimeInfo:
    def test_returns_dataframe(self):
        df = _utc_range("2024-01-15 07:00", 5)
        result = local_time_info(df)
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns(self):
        df = _utc_range("2024-01-15 07:00", 5)
        result = local_time_info(df)
        for col in ["time_utc", "time_london", "time_newyork", "hour_utc", "hour_newyork"]:
            assert col in result.columns

    def test_known_conversion_winter(self):
        # 2024-01-15 14:00 UTC = 09:00 EST = 14:00 GMT
        df = _utc_ts("2024-01-15 14:00")
        result = local_time_info(df)
        assert result["time_utc"].iloc[0] == "14:00"
        assert result["time_london"].iloc[0] == "14:00"  # GMT en enero
        assert result["time_newyork"].iloc[0] == "09:00"  # EST = UTC-5

    def test_known_conversion_summer(self):
        # 2024-06-15 13:00 UTC = 09:00 EDT = 14:00 BST
        df = _utc_ts("2024-06-15 13:00")
        result = local_time_info(df)
        assert result["time_utc"].iloc[0] == "13:00"
        assert result["time_london"].iloc[0] == "14:00"  # BST = UTC+1
        assert result["time_newyork"].iloc[0] == "09:00"  # EDT = UTC-4

    def test_same_index_as_input(self):
        df = _utc_range("2024-01-15 07:00", 10)
        result = local_time_info(df)
        pd.testing.assert_index_equal(result.index, df.index)


# ── add_session_features ──────────────────────────────────────────────────────

class TestAddSessionFeatures:
    def test_returns_dataframe(self):
        df = _utc_range("2024-01-15 06:00", 20)
        result = add_session_features(df)
        assert isinstance(result, pd.DataFrame)

    def test_original_columns_preserved(self):
        df = _utc_range("2024-01-15 06:00", 20)
        result = add_session_features(df)
        for col in df.columns:
            assert col in result.columns

    def test_expected_new_columns(self):
        df = _utc_range("2024-01-15 06:00", 20)
        result = add_session_features(df)
        for col in [
            "london_killzone", "newyork_am_open", "newyork_am_forex_alt",
            "any_session", "time_utc", "time_london", "time_newyork",
            "hour_utc", "hour_newyork",
        ]:
            assert col in result.columns, f"Columna '{col}' no encontrada"

    def test_same_length(self):
        df = _utc_range("2024-01-15 06:00", 48)
        result = add_session_features(df)
        assert len(result) == len(df)

    def test_does_not_modify_original(self):
        df = _utc_range("2024-01-15 06:00", 10)
        original_cols = set(df.columns)
        _ = add_session_features(df)
        assert set(df.columns) == original_cols

    def test_boolean_columns_are_bool(self):
        df = _utc_range("2024-01-15 06:00", 20)
        result = add_session_features(df)
        for col in ["london_killzone", "newyork_am_open", "newyork_am_forex_alt", "any_session"]:
            assert result[col].dtype in [bool, "bool"], f"{col} no es bool"


# ── session_bar_counts ─────────────────────────────────────────────────────────

class TestSessionBarCounts:
    def test_returns_dataframe(self):
        df = _utc_range("2024-01-15 06:00", 200)
        result = session_bar_counts(df)
        assert isinstance(result, pd.DataFrame)

    def test_has_three_rows(self):
        df = _utc_range("2024-01-15 06:00", 200)
        result = session_bar_counts(df)
        assert len(result) == 3

    def test_pct_between_0_and_100(self):
        df = _utc_range("2024-01-15 06:00", 200)
        result = session_bar_counts(df)
        assert (result["pct_of_total"] >= 0).all()
        assert (result["pct_of_total"] <= 100).all()

    def test_bars_non_negative(self):
        df = _utc_range("2024-01-15 06:00", 200)
        result = session_bar_counts(df)
        assert (result["bars_in_window"] >= 0).all()


# ── Error handling ─────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_raises_on_non_datetime_index(self):
        df = pd.DataFrame({"close": [1.0, 2.0]}, index=[0, 1])
        with pytest.raises(TypeError):
            london_killzone(df)

    def test_handles_tz_aware_utc_index(self):
        # Índice con tz-aware UTC no debe lanzar error
        idx = pd.date_range("2024-01-15 07:00", periods=5, freq="15min", tz="UTC")
        df = pd.DataFrame({"close": 1.08}, index=idx)
        result = london_killzone(df)
        assert isinstance(result, pd.Series)
        assert len(result) == 5


# ── Integración: datos M1 reales ──────────────────────────────────────────────

class TestRealDataM1:
    @pytest.fixture(scope="class")
    def m1_week(self):
        import pathlib
        parquet = pathlib.Path("data/processed/eurusd_m1_bid.parquet")
        if not parquet.exists():
            pytest.skip("Dataset M1 no disponible")
        df = pd.read_parquet(parquet)
        # El parquet tiene 'datetime' como columna con tz-aware UTC
        if "datetime" in df.columns:
            df = df.set_index("datetime")
        return df.iloc[:10_080].copy()  # ~1 semana M1

    def test_add_features_no_errors(self, m1_week):
        result = add_session_features(m1_week)
        assert len(result) == len(m1_week)

    def test_boolean_columns_real_data(self, m1_week):
        result = add_session_features(m1_week)
        for col in ["london_killzone", "newyork_am_open", "any_session"]:
            assert result[col].dtype in [bool, "bool", object]

    def test_some_bars_in_each_session(self, m1_week):
        result = add_session_features(m1_week)
        # Al menos algunas barras deben estar en cada ventana (1 semana tiene 5 días)
        assert result["london_killzone"].sum() > 0
        assert result["newyork_am_open"].sum() > 0

    def test_sessions_mutually_exclusive(self, m1_week):
        # LK y NY AM no se solapan (LK: 02-05 NY, NY AM: 09:30-11:00 NY)
        result = add_session_features(m1_week)
        overlap = result["london_killzone"] & result["newyork_am_open"]
        assert overlap.sum() == 0, "LK y NY AM se solapan — error de configuración"

    def test_session_bar_counts_real(self, m1_week):
        counts = session_bar_counts(m1_week)
        assert counts["bars_in_window"].sum() > 0
