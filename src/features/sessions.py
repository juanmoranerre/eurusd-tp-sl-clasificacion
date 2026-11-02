"""
sessions.py — Filtros de sesiones operativas para EUR/USD

Ventanas confirmadas por el trader (2026-11-01, PD-001):
  London Killzone : 02:00–05:00 America/New_York
  NY AM Open      : 09:30–11:00 America/New_York
  NY AM Forex Alt : 07:00–10:00 America/New_York  (para comparación)

Uso de zonas horarias IANA (America/New_York, Europe/London) para conversiones
históricas correctas incluyendo semanas en las que EE.UU. y RU cambian de horario
en fechas diferentes.

Convención de salida:
  Cada función devuelve una columna booleana: True = dentro de la ventana.
  add_session_features() añade todas las columnas al DataFrame de entrada.
"""

from __future__ import annotations

import zoneinfo
from datetime import time

import numpy as np
import pandas as pd

from config.strategy_config import (
    LONDON_KILLZONE,
    NEWYORK_AM_FOREX_ALT,
    NEWYORK_AM_OPEN,
    SESSION_WINDOWS_ALL,
)

# ── Tipos auxiliares ──────────────────────────────────────────────────────────

SessionWindow = dict  # {tz: str, start: str, end: str, label: str}


# ── Core: detección de si un timestamp UTC está en una ventana horaria ─────────

def _parse_time(t: str) -> time:
    h, m = map(int, t.split(":"))
    return time(h, m)


def _in_window_vectorized(
    utc_index: pd.DatetimeIndex,
    tz_name: str,
    start_str: str,
    end_str: str,
) -> np.ndarray:
    """
    Devuelve array booleano: True si el timestamp UTC está dentro de [start, end)
    en la zona horaria ``tz_name``.

    Maneja correctamente los cambios de horario (DST) históricos.
    La ventana es cerrada-izquierda, abierta-derecha: [start, end).
    """
    tz = zoneinfo.ZoneInfo(tz_name)
    start = _parse_time(start_str)
    end = _parse_time(end_str)

    # Convertir el índice UTC a la zona objetivo
    local_index = utc_index.tz_localize("UTC").tz_convert(tz_name)
    local_times = local_index.time  # array de datetime.time

    # Comparación elemento a elemento
    return np.array([(start <= t < end) for t in local_times], dtype=bool)


def in_session(df: pd.DataFrame, window: SessionWindow) -> pd.Series:
    """
    Devuelve Serie booleana: True si la barra está dentro de la ventana ``window``.

    ``df`` debe tener un DatetimeIndex en UTC (tz-naive o tz-aware UTC).
    """
    _check_datetime_index(df)
    idx = _to_utc_datetimeindex(df.index)
    mask = _in_window_vectorized(idx, window["tz"], window["start"], window["end"])
    return pd.Series(mask, index=df.index, name=window["label"])


# ── Features de sesión ────────────────────────────────────────────────────────

def london_killzone(df: pd.DataFrame) -> pd.Series:
    """02:00–05:00 America/New_York — London Killzone (ICT/SMC)."""
    return in_session(df, LONDON_KILLZONE)


def newyork_am_open(df: pd.DataFrame) -> pd.Series:
    """09:30–11:00 America/New_York — NY AM Open (apertura NYSE)."""
    return in_session(df, NEWYORK_AM_OPEN)


def newyork_am_forex_alt(df: pd.DataFrame) -> pd.Series:
    """07:00–10:00 America/New_York — NY AM Forex Alt (para comparación)."""
    return in_session(df, NEWYORK_AM_FOREX_ALT)


def any_session(df: pd.DataFrame) -> pd.Series:
    """True si la barra está en CUALQUIERA de las ventanas operativas principales."""
    lk = london_killzone(df)
    ny = newyork_am_open(df)
    return (lk | ny).rename("any_session")


def local_time_info(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade columnas con la hora local en London y New York para cada barra.

    Columnas:
      time_utc       — hora UTC (HH:MM)
      time_london    — hora Europe/London local
      time_newyork   — hora America/New_York local
      hour_utc       — entero 0-23
      hour_newyork   — entero 0-23
    """
    _check_datetime_index(df)
    idx = _to_utc_datetimeindex(df.index)

    idx_utc = idx.tz_localize("UTC") if idx.tzinfo is None else idx
    idx_london = idx_utc.tz_convert("Europe/London")
    idx_ny = idx_utc.tz_convert("America/New_York")

    out = pd.DataFrame(index=df.index)
    out["time_utc"]     = [t.strftime("%H:%M") for t in idx_utc]
    out["time_london"]  = [t.strftime("%H:%M") for t in idx_london]
    out["time_newyork"] = [t.strftime("%H:%M") for t in idx_ny]
    out["hour_utc"]     = idx_utc.hour
    out["hour_newyork"] = idx_ny.hour

    return out


def add_session_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade todas las features de sesión al DataFrame y devuelve una copia.

    Columnas nuevas:
      london_killzone    — bool
      newyork_am_open    — bool
      newyork_am_forex_alt — bool
      any_session        — bool (LK | NY_AM)
      time_utc           — str HH:MM
      time_london        — str HH:MM
      time_newyork       — str HH:MM
      hour_utc           — int
      hour_newyork       — int
    """
    out = df.copy()
    out["london_killzone"]       = london_killzone(df).values
    out["newyork_am_open"]       = newyork_am_open(df).values
    out["newyork_am_forex_alt"]  = newyork_am_forex_alt(df).values
    out["any_session"]           = any_session(df).values

    time_info = local_time_info(df)
    for col in time_info.columns:
        out[col] = time_info[col].values

    return out


# ── Estadísticas de distribución de barras por sesión ─────────────────────────

def session_bar_counts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cuenta barras por ventana operativa. Útil para auditoría del dataset.

    Devuelve DataFrame con columnas: window, bars_in_window, pct_of_total.
    """
    total = len(df)
    rows = []
    for window in SESSION_WINDOWS_ALL:
        mask = in_session(df, window)
        count = int(mask.sum())
        rows.append({
            "window": window["label"],
            "bars_in_window": count,
            "pct_of_total": round(count / total * 100, 2) if total > 0 else 0.0,
        })
    return pd.DataFrame(rows)


# ── Utilidades internas ────────────────────────────────────────────────────────

def _check_datetime_index(df: pd.DataFrame) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            f"El índice debe ser DatetimeIndex, se recibió {type(df.index).__name__}"
        )


def _to_utc_datetimeindex(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Normaliza el índice: si tiene timezone, convierte a UTC; si no, asume UTC."""
    if idx.tzinfo is not None:
        return idx.tz_convert("UTC").tz_localize(None)
    return idx
