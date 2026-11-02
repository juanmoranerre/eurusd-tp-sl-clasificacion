"""
resampler.py — Construcción de temporalidades superiores desde M1 EUR/USD

Convierte el dataset M1 a cualquier temporalidad superior mediante resample OHLCV.

Reglas:
  • El precio de apertura (open) es el primer precio del período.
  • El máximo (high) es el máximo de todos los highs del período.
  • El mínimo (low) es el mínimo de todos los lows del período.
  • El precio de cierre (close) es el último precio del período.
  • El volumen es la suma de todos los volúmenes del período.
  • is_flat_period: True si TODOS los minutos M1 del período son días planos.
  • Los períodos sin ningún minuto M1 se eliminan (no deben existir con datos completos).

Alineación temporal:
  • M15, H1, H4: alineados a medianoche UTC (0:00, 0:15, ...).
  • D1: un registro por día calendario (UTC).
  • W1: semanas de lunes a domingo (UTC).
  • MN: meses calendario (etiqueta = primer día del mes).

Restricción de lookahead:
  La etiqueta temporal de cada barra es el INICIO del período (label='left'),
  lo que garantiza que el dato solo está disponible cuando la barra cierra,
  es decir, al inicio del siguiente período.
"""

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Alias de frecuencias soportados ──────────────────────────────────────────

SUPPORTED_TIMEFRAMES: dict[str, str] = {
    "m15": "15min",
    "h1":  "1h",
    "h4":  "4h",
    "d1":  "1D",
    "w1":  "1W",
    "mn":  "1ME",
}

_OHLCV_AGG = {
    "open":   "first",
    "high":   "max",
    "low":    "min",
    "close":  "last",
    "volume": "sum",
}


# ── API pública ───────────────────────────────────────────────────────────────

def resample_ohlcv(
    m1_df: pd.DataFrame,
    freq: str,
    *,
    closed: Literal["left", "right"] = "left",
    label: Literal["left", "right"] = "left",
) -> pd.DataFrame:
    """
    Resamplear datos M1 a una temporalidad superior.

    Parameters
    ----------
    m1_df : pd.DataFrame
        DataFrame M1 con columnas: datetime (UTC tz-aware), open, high, low,
        close, volume, is_flat_day. La columna datetime puede ser índice o columna.
    freq : str
        Alias de frecuencia pandas (e.g. "15min", "1h", "4h", "1D", "1W", "1ME").
    closed : {"left", "right"}
        Lado de cierre del intervalo (default "left").
    label : {"left", "right"}
        Etiqueta del intervalo (default "left" = inicio del período).

    Returns
    -------
    pd.DataFrame
        Columnas: datetime (UTC), open, high, low, close, volume, is_flat_period.
        Ordenado cronológicamente. Sin períodos vacíos.

    Raises
    ------
    ValueError
        Si el DataFrame está vacío o le faltan columnas requeridas.
    """
    if m1_df is None or m1_df.empty:
        raise ValueError("m1_df está vacío. No se puede resamplear.")

    required = {"open", "high", "low", "close", "volume", "is_flat_day"}
    missing = required - set(m1_df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en m1_df: {missing}")

    df = m1_df.copy()
    if "datetime" in df.columns:
        df = df.set_index("datetime")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("El índice debe ser DatetimeIndex con tz UTC.")

    resampler = df.resample(freq, closed=closed, label=label)

    agg = resampler.agg(_OHLCV_AGG)
    is_flat = resampler["is_flat_day"].all().rename("is_flat_period")

    result = pd.concat([agg, is_flat], axis=1)

    # Eliminar períodos sin datos (open NaN = período sin ningún minuto M1)
    result = result.dropna(subset=["open"])

    # Asegurarse de que is_flat_period es bool
    result["is_flat_period"] = result["is_flat_period"].astype(bool)

    result.index.name = "datetime"
    result = result.reset_index()

    # Columnas en orden canónico
    result = result[["datetime", "open", "high", "low", "close", "volume", "is_flat_period"]]

    logger.debug(
        "Resampleado %d → %d registros (%s, closed=%s, label=%s)",
        len(m1_df), len(result), freq, closed, label,
    )

    return result


def build_timeframe(
    m1_df: pd.DataFrame,
    tf_name: str,
) -> pd.DataFrame:
    """
    Construir una temporalidad a partir de su nombre canónico.

    Parameters
    ----------
    m1_df : pd.DataFrame
        Dataset M1 completo (con is_flat_day).
    tf_name : str
        Nombre de temporalidad: "m15", "h1", "h4", "d1", "w1", "mn".

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas OHLCV + is_flat_period.

    Raises
    ------
    ValueError
        Si tf_name no está en SUPPORTED_TIMEFRAMES.
    """
    tf_name = tf_name.lower()
    if tf_name not in SUPPORTED_TIMEFRAMES:
        raise ValueError(
            f"Temporalidad no soportada: '{tf_name}'. "
            f"Opciones: {list(SUPPORTED_TIMEFRAMES)}"
        )

    freq = SUPPORTED_TIMEFRAMES[tf_name]
    logger.info("Construyendo temporalidad %s (freq=%s) desde M1 ...", tf_name, freq)
    df = resample_ohlcv(m1_df, freq)
    logger.info(
        "  %s: %d barras  (%s → %s)",
        tf_name, len(df),
        df["datetime"].iloc[0],
        df["datetime"].iloc[-1],
    )
    return df


def build_all_timeframes(
    m1_df: pd.DataFrame,
    timeframes: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Construir todas las temporalidades superiores a partir del DataFrame M1.

    Parameters
    ----------
    m1_df : pd.DataFrame
        Dataset M1 completo.
    timeframes : list[str] | None
        Subconjunto de temporalidades a construir. None = todas.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario {nombre_tf: DataFrame}.
    """
    if timeframes is None:
        timeframes = list(SUPPORTED_TIMEFRAMES.keys())

    result: dict[str, pd.DataFrame] = {}
    for tf in timeframes:
        result[tf] = build_timeframe(m1_df, tf)

    return result


def validate_ohlcv_invariants(df: pd.DataFrame, name: str = "") -> dict:
    """
    Verificar invariantes OHLC en un DataFrame de temporalidad superior.
    Solo evalúa registros activos (is_flat_period=False).

    Returns
    -------
    dict
        {"ok": bool, "violations": {rule: count}, "active_rows": int}
    """
    prefix = f"[{name}] " if name else ""
    active = df[~df["is_flat_period"]] if "is_flat_period" in df.columns else df

    violations = {
        "H < L":  int((active["high"] <  active["low"]).sum()),
        "H < O":  int((active["high"] <  active["open"]).sum()),
        "H < C":  int((active["high"] <  active["close"]).sum()),
        "L > O":  int((active["low"]  >  active["open"]).sum()),
        "L > C":  int((active["low"]  >  active["close"]).sum()),
    }

    total_violations = sum(violations.values())
    ok = (total_violations == 0)

    if not ok:
        for rule, count in violations.items():
            if count > 0:
                logger.warning("%s%s: %d violaciones OHLC", prefix, rule, count)
    else:
        logger.info("%sInvariantes OHLC correctos (%d registros activos)", prefix, len(active))

    return {"ok": ok, "violations": violations, "active_rows": len(active)}
