"""
auxiliary.py — Features técnicas auxiliares sin dependencia de decisiones del trader

Incluye indicadores clásicos calculados sin lookahead sobre cualquier DataFrame OHLCV:
  ATR   — Average True Range (volatilidad de rango real)
  EMA   — Exponential Moving Average del precio de cierre
  RSI   — Relative Strength Index (impulso relativo)
  Returns — Retornos simples y logarítmicos de close
  Rolling volatility — Desviación estándar de log-retornos en ventana deslizante
  Candle features — Tamaño del cuerpo y mechas (no requieren parámetros de estrategia)

Convención:
  - Todas las funciones reciben un DataFrame con columnas: open, high, low, close (y opcionalmente volume).
  - El índice debe ser datetime ordenado cronológicamente.
  - Los valores NaN al inicio de la ventana son normales y esperados.
  - Nunca se usa información futura (sin lookahead).
"""

import numpy as np
import pandas as pd


# ── ATR ───────────────────────────────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range sobre un DataFrame OHLCV.

    El True Range de cada barra se define como:
        TR = max(H-L, |H-Cprev|, |L-Cprev|)
    El ATR es la media exponencial del TR con período ``period``.

    Returns una Series con el mismo índice que ``df``.
    Las primeras ``period`` filas pueden ser NaN.
    """
    if period < 1:
        raise ValueError(f"period debe ser >= 1, se recibió {period}")
    _check_ohlc_columns(df)

    h = df["high"]
    l = df["low"]
    c_prev = df["close"].shift(1)

    tr = pd.concat(
        [h - l, (h - c_prev).abs(), (l - c_prev).abs()],
        axis=1,
    ).max(axis=1)

    # Wilder's smoothing = EWM con alpha=1/period, ajust=False
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range crudo (sin suavizado). Útil para inspección."""
    _check_ohlc_columns(df)
    h, l = df["high"], df["low"]
    c_prev = df["close"].shift(1)
    return pd.concat(
        [h - l, (h - c_prev).abs(), (l - c_prev).abs()], axis=1
    ).max(axis=1)


# ── EMA ───────────────────────────────────────────────────────────────────────

def ema(df: pd.DataFrame, period: int, source: str = "close") -> pd.Series:
    """
    Exponential Moving Average de la columna ``source``.

    Usa span=``period`` (factor de decay = 2/(period+1)), ajust=False.
    Los primeros ``period`` valores pueden ser NaN (min_periods=period).
    """
    if period < 1:
        raise ValueError(f"period debe ser >= 1, se recibió {period}")
    if source not in df.columns:
        raise ValueError(f"columna '{source}' no encontrada en el DataFrame")

    return df[source].ewm(span=period, adjust=False, min_periods=period).mean()


# ── RSI ───────────────────────────────────────────────────────────────────────

def rsi(df: pd.DataFrame, period: int = 14, source: str = "close") -> pd.Series:
    """
    Relative Strength Index (RSI) de Wilder.

    RSI = 100 - 100 / (1 + RS)
    donde RS = EWM(ganancias, alpha=1/period) / EWM(pérdidas, alpha=1/period)

    Retorna valores en [0, 100]. Las primeras ``period`` filas son NaN.
    Cuando avg_loss=0 y avg_gain>0, retorna 100. Cuando ambos=0, retorna NaN.
    """
    if period < 1:
        raise ValueError(f"period debe ser >= 1, se recibió {period}")
    if source not in df.columns:
        raise ValueError(f"columna '{source}' no encontrada en el DataFrame")

    delta = df[source].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    # Evitar división por cero: cuando avg_loss==0 y avg_gain>0 → RSI=100
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100.0 - 100.0 / (1.0 + rs)
    # Cuando avg_gain == avg_loss == 0: result ya es NaN (por replace arriba).
    # Cuando avg_gain > 0 y avg_loss == 0: rs=NaN → RSI debería ser 100.
    mask_zero_loss = (avg_loss == 0) & (avg_gain > 0)
    result[mask_zero_loss] = 100.0
    return result


# ── Retornos ─────────────────────────────────────────────────────────────────

def log_returns(df: pd.DataFrame, source: str = "close") -> pd.Series:
    """Log-retornos de la columna ``source``: ln(P_t / P_{t-1})."""
    if source not in df.columns:
        raise ValueError(f"columna '{source}' no encontrada en el DataFrame")
    return np.log(df[source] / df[source].shift(1))


def simple_returns(df: pd.DataFrame, source: str = "close") -> pd.Series:
    """Retornos simples: (P_t - P_{t-1}) / P_{t-1}."""
    if source not in df.columns:
        raise ValueError(f"columna '{source}' no encontrada en el DataFrame")
    return df[source].pct_change()


# ── Volatilidad rodante ───────────────────────────────────────────────────────

def rolling_volatility(
    df: pd.DataFrame, period: int = 20, source: str = "close", annualize: bool = False
) -> pd.Series:
    """
    Desviación estándar de log-retornos en ventana rodante de ``period`` barras.

    Si ``annualize=True``, multiplica por sqrt(bars_per_year).
    ``bars_per_year`` se deduce automáticamente de la frecuencia del índice,
    o se deja sin anualizar si no se puede detectar.
    """
    if period < 2:
        raise ValueError(f"period debe ser >= 2, se recibió {period}")

    lr = log_returns(df, source)
    vol = lr.rolling(window=period, min_periods=period).std()

    if annualize:
        bars_per_year = _infer_bars_per_year(df)
        if bars_per_year is not None:
            vol = vol * np.sqrt(bars_per_year)

    return vol


def _infer_bars_per_year(df: pd.DataFrame) -> float | None:
    """Infiere barras por año a partir de la frecuencia del índice datetime."""
    if not isinstance(df.index, pd.DatetimeIndex) or len(df) < 2:
        return None
    inferred = pd.infer_freq(df.index[:50])
    if inferred is None:
        return None
    mapping = {
        "T": 525_600, "min": 525_600,
        "15T": 35_040, "15min": 35_040,
        "H": 8_760, "h": 8_760,
        "4H": 2_190, "4h": 2_190,
        "D": 252, "B": 252,
        "W": 52, "W-SUN": 52, "W-MON": 52,
        "MS": 12, "ME": 12, "M": 12,
    }
    return mapping.get(inferred)


# ── Candle features ───────────────────────────────────────────────────────────

def candle_body(df: pd.DataFrame) -> pd.Series:
    """Tamaño del cuerpo de la vela: |close - open|."""
    _check_ohlc_columns(df)
    return (df["close"] - df["open"]).abs()


def candle_range(df: pd.DataFrame) -> pd.Series:
    """Rango total de la vela: high - low."""
    _check_ohlc_columns(df)
    return df["high"] - df["low"]


def upper_wick(df: pd.DataFrame) -> pd.Series:
    """Mecha superior: high - max(open, close)."""
    _check_ohlc_columns(df)
    return df["high"] - df[["open", "close"]].max(axis=1)


def lower_wick(df: pd.DataFrame) -> pd.Series:
    """Mecha inferior: min(open, close) - low."""
    _check_ohlc_columns(df)
    return df[["open", "close"]].min(axis=1) - df["low"]


def body_ratio(df: pd.DataFrame) -> pd.Series:
    """
    Proporción del cuerpo sobre el rango total: |close-open| / (high-low).

    Devuelve NaN cuando high == low (barra plana).
    """
    _check_ohlc_columns(df)
    total = candle_range(df)
    return candle_body(df) / total.replace(0, np.nan)


def candle_direction(df: pd.DataFrame) -> pd.Series:
    """
    Dirección de la vela:
      +1 → alcista (close > open)
       0 → doji  (close == open)
      -1 → bajista (close < open)
    """
    _check_ohlc_columns(df)
    diff = df["close"] - df["open"]
    return np.sign(diff).astype(int)


# ── Función de utilidad: añadir todas las features auxiliares ─────────────────

def add_auxiliary_features(
    df: pd.DataFrame,
    *,
    atr_period: int = 14,
    ema_periods: list[int] | None = None,
    rsi_period: int = 14,
    vol_period: int = 20,
) -> pd.DataFrame:
    """
    Añade todas las features auxiliares al DataFrame y devuelve una copia enriquecida.

    Columnas nuevas añadidas:
      atr_{atr_period}              — ATR de Wilder
      ema_{p} (por cada período)    — EMA del cierre
      rsi_{rsi_period}              — RSI de Wilder
      log_ret                       — Log-retorno del cierre
      simple_ret                    — Retorno simple del cierre
      vol_{vol_period}              — Volatilidad rodante (std de log-ret)
      body                          — |close - open|
      rng                           — high - low
      upper_wick                    — high - max(open,close)
      lower_wick                    — min(open,close) - low
      body_ratio                    — body / rng
      direction                     — +1/0/-1
    """
    if ema_periods is None:
        ema_periods = [20, 50, 200]

    out = df.copy()

    out[f"atr_{atr_period}"]  = atr(df, atr_period)
    for p in ema_periods:
        out[f"ema_{p}"]       = ema(df, p)
    out[f"rsi_{rsi_period}"]  = rsi(df, rsi_period)
    out["log_ret"]            = log_returns(df)
    out["simple_ret"]         = simple_returns(df)
    out[f"vol_{vol_period}"]  = rolling_volatility(df, vol_period)
    out["body"]               = candle_body(df)
    out["rng"]                = candle_range(df)
    out["upper_wick"]         = upper_wick(df)
    out["lower_wick"]         = lower_wick(df)
    out["body_ratio"]         = body_ratio(df)
    out["direction"]          = candle_direction(df)

    return out


# ── Validación de columnas ────────────────────────────────────────────────────

def _check_ohlc_columns(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas OHLC: {missing}")
