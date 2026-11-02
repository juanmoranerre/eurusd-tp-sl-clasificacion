"""
context.py — Contexto de alto nivel para cada barra M15

Responsabilidad principal:
  Dado el DataFrame M15 y el DataFrame H1 (ambos con 'datetime' como columna,
  no como índice), construye el contexto operativo visible en cada barra M15:

    h1_structure_bias   — "bullish" | "bearish" | "ranging" | None
    h1_last_bos_bull    — True si el último evento estructural H1 fue un BOS alcista
    h1_last_bos_bear    — idem bajista
    h1_displacement     — displacement_score de la barra de BOS en H1 (forward-filled)

Restricción de no-lookahead (CRÍTICA):
  La barra H1 con timestamp t cubre [t, t+1h).  Su close, BOS y bias solo se
  conocen a partir de t+1h.  Por eso la alineación usa merge_asof con
  h1_close_time = h1.datetime + 1h, y solo propaga a barras M15 con
  datetime >= h1_close_time.

  Ejemplo:
    H1 bar  14:00 UTC  → disponible para M15 a partir de 15:00 UTC
    M15 bar 14:00, 14:15, 14:30, 14:45  → ven el sesgo del H1 bar 13:00
    M15 bar 15:00  → primera que ve el sesgo del H1 bar 14:00
"""

from __future__ import annotations

import pandas as pd

from src.features.structure import add_market_structure


def build_h1_context(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    *,
    n: int = 1,
    level: str = "short_term",
) -> pd.DataFrame:
    """
    Añade columnas de contexto H1 al DataFrame M15.

    Parámetros
    ----------
    m15 : DataFrame con columna 'datetime' (UTC, no como índice) y OHLC.
    h1  : DataFrame con columna 'datetime' (UTC, no como índice) y OHLC.
    n   : velas a cada lado del pivot (default 1).
    level : nivel de swing para el que se detectan BOS/CHOCH.

    Devuelve
    --------
    Copia del DataFrame M15 con columnas adicionales:
      h1_structure_bias  — str o None
      h1_bos_bull        — bool (último BOS H1 alcista, forward-filled)
      h1_bos_bear        — bool (último BOS H1 bajista, forward-filled)
    """
    if "datetime" not in m15.columns:
        raise ValueError("m15 debe tener columna 'datetime'.")
    if "datetime" not in h1.columns:
        raise ValueError("h1 debe tener columna 'datetime'.")

    # 1. Calcular estructura en H1
    h1_struct = add_market_structure(h1.copy(), n=n, level=level)

    # 2. Preparar M15 ordenado (necesitamos su dtype de datetime para normalizar H1)
    m15_sorted = m15.sort_values("datetime").reset_index(drop=True)

    # 3. Añadir close_time: la barra H1 se conoce a partir de su cierre
    h1_struct = h1_struct.copy()
    h1_struct["_close_time"] = h1_struct["datetime"] + pd.Timedelta(hours=1)

    # Normalizar precisión de datetime para que merge_asof no falle (ms vs us)
    target_dtype = m15_sorted["datetime"].dtype
    h1_struct["_close_time"] = h1_struct["_close_time"].astype(target_dtype)

    # 4. Seleccionar columnas a propagar
    context_cols = ["_close_time", "structure_bias", "bos_bull", "bos_bear"]
    missing = [c for c in context_cols if c not in h1_struct.columns]
    if missing:
        raise ValueError(f"Columnas faltantes en h1 estructurado: {missing}")

    h1_ctx = h1_struct[context_cols].sort_values("_close_time").reset_index(drop=True)

    # 5. merge_asof: para cada barra M15, el último H1 cerrado ANTES de esa barra
    merged = pd.merge_asof(
        m15_sorted,
        h1_ctx.rename(columns={
            "structure_bias": "h1_structure_bias",
            "bos_bull":       "h1_bos_bull",
            "bos_bear":       "h1_bos_bear",
        }),
        left_on="datetime",
        right_on="_close_time",
        direction="backward",
    ).drop(columns=["_close_time"])

    # Restore original index order
    merged = merged.sort_values("datetime").reset_index(drop=True)
    return merged


def get_h1_bias_at(
    h1_context: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> str | None:
    """
    Devuelve el sesgo H1 disponible en el instante `timestamp`.

    Útil para consultas puntuales durante la generación de setups.
    """
    rows = h1_context[h1_context["datetime"] <= timestamp]
    if rows.empty or "h1_structure_bias" not in rows.columns:
        return None
    last = rows.iloc[-1]
    return last.get("h1_structure_bias", None)
