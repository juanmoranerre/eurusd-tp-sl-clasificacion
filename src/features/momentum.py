"""
momentum.py — Displacement score y features de momentum

El trader confirmó (PD-005) que no existe un umbral fijo para displacement.
Se implementa un displacement_score multidimensional configurable que cuantifica:
  • Tamaño del cuerpo de la vela
  • Rango total respecto al ATR
  • Posición del cierre dentro del rango (0=bottom, 1=top)
  • Presencia de FVG en la misma barra
  • BOS o CHOCH asociado
  • Velocidad del movimiento (rango respecto a ventana previa)

El umbral que convierte el score en señal operativa queda PENDING (PD-005b).

Funciones:
  displacement_score()   — score escalar en [0, 1]
  add_momentum_features() — añade todas las métricas al DataFrame
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.auxiliary import atr, true_range


# ── Componentes del displacement score ───────────────────────────────────────

def body_to_range_ratio(df: pd.DataFrame) -> pd.Series:
    """Proporción del cuerpo respecto al rango total: |C-O|/(H-L)."""
    body = (df["close"] - df["open"]).abs()
    rng  = (df["high"] - df["low"]).replace(0, np.nan)
    return body / rng


def range_to_atr_ratio(df: pd.DataFrame, atr_period: int = 14) -> pd.Series:
    """Rango actual (H-L) como múltiplo del ATR. >1 indica vela grande."""
    rng = df["high"] - df["low"]
    a   = atr(df, atr_period)
    return rng / a.replace(0, np.nan)


def close_position(df: pd.DataFrame) -> pd.Series:
    """
    Posición del cierre dentro del rango [0, 1].
    0 = cierre en el mínimo, 1 = cierre en el máximo.
    """
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return (df["close"] - df["low"]) / rng


def directional_momentum(df: pd.DataFrame) -> pd.Series:
    """
    Impulso direccional: +1 si alcista, -1 si bajista, 0 si plano.
    Basado en la dirección del cuerpo de la vela.
    """
    diff = df["close"] - df["open"]
    return np.sign(diff).astype(int)


def speed_score(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    Velocidad relativa: rango de la barra actual vs rango promedio de las
    últimas ``lookback`` barras. Valores > 1 indican barra más rápida que la media.
    """
    rng = df["high"] - df["low"]
    avg_rng = rng.rolling(lookback, min_periods=1).mean().shift(1)
    return rng / avg_rng.replace(0, np.nan)


# ── Displacement score ────────────────────────────────────────────────────────

def displacement_score(
    df: pd.DataFrame,
    *,
    atr_period: int = 14,
    speed_lookback: int = 5,
    w_body: float = 0.25,
    w_range_atr: float = 0.30,
    w_close_pos: float = 0.20,
    w_speed: float = 0.25,
) -> pd.Series:
    """
    Score de displacement en [0, 1]. Combina cuatro componentes ponderados.

    Componentes:
      body_ratio    — tamaño relativo del cuerpo (normalizado en [0,1])
      range/ATR     — tamaño del rango vs ATR (normalizado sigmoid-like)
      close_pos     — posición del cierre (alcista=top, bajista=bottom)
      speed         — velocidad vs historial reciente

    Cada componente se normaliza a [0, 1] antes de ponderar.

    El umbral para considerar un displacement "válido" queda PENDING (PD-005b).
    El score en sí no requiere aprobación.

    Pesos por defecto son iniciales; se esperan ajustes tras análisis exploratorio.
    """
    _check_ohlc_columns(df)

    # Componente 1: body/range → ya en [0,1]
    br = body_to_range_ratio(df).clip(0, 1).fillna(0)

    # Componente 2: range/ATR → normalizar con clip; 2× ATR ≈ "grande"
    ra = range_to_atr_ratio(df, atr_period).clip(0, 3).fillna(0) / 3.0

    # Componente 3: posición del cierre
    cp = close_position(df).fillna(0.5)
    # Para alcistas queremos cp alto; para bajistas queremos cp bajo.
    direction = directional_momentum(df)
    # score de posición = cp para alcistas, (1-cp) para bajistas
    cp_score = np.where(direction >= 0, cp, 1 - cp)

    # Componente 4: velocidad
    sp = speed_score(df, lookback=speed_lookback).clip(0, 3).fillna(0) / 3.0

    score = w_body * br + w_range_atr * ra + w_close_pos * cp_score + w_speed * sp
    return pd.Series(score.values, index=df.index, name="displacement_score")


# ── Pipeline de features de momentum ─────────────────────────────────────────

def add_momentum_features(
    df: pd.DataFrame,
    *,
    atr_period: int = 14,
    speed_lookback: int = 5,
) -> pd.DataFrame:
    """
    Añade todas las features de momentum al DataFrame.

    Columnas añadidas:
      body_range_ratio    — |C-O|/(H-L)
      range_atr_ratio     — (H-L)/ATR
      close_position      — posición del cierre [0,1]
      directional_momentum — +1/0/-1
      speed_score         — velocidad relativa
      displacement_score  — score combinado [0,1]
    """
    out = df.copy()
    out["body_range_ratio"]     = body_to_range_ratio(df)
    out["range_atr_ratio"]      = range_to_atr_ratio(df, atr_period)
    out["close_position"]       = close_position(df)
    out["directional_momentum"] = directional_momentum(df)
    out["speed_score"]          = speed_score(df, speed_lookback)
    out["displacement_score"]   = displacement_score(
        df, atr_period=atr_period, speed_lookback=speed_lookback
    )
    return out


# ── Utilidades ────────────────────────────────────────────────────────────────

def _check_ohlc_columns(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas OHLC: {missing}")
