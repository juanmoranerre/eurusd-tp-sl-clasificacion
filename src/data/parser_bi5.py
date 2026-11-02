"""
parser_bi5.py — Dukascopy BI5 → pandas DataFrame

Formato verificado (auditoría 2026-11-01, corrección 2026-11-01):
  • Compresión  : LZMA clásico (magic bytes 5D 00 00 40)
  • Registros   : 1440 por archivo (uno por minuto, 24 h completas)
  • Tamaño      : 24 bytes/registro, big-endian
  • Orden real  : timestamp_s (uint32) | open (uint32) | CLOSE (uint32)
                  low (uint32) | HIGH (uint32) | volume (float32)
  • NOTA: Dukascopy BI5 NO almacena OHLC en orden canónico.
          El campo en posición 2 es CLOSE; el campo en posición 4 es HIGH.
          Verificado decodificando bytes crudos: con el orden correcto 0
          violaciones OHLC en >14.000 registros activos; con el orden
          incorrecto (o,h,l,c) se producen ~1.300 violaciones/día.
  • Precios     : valor entero ÷ 100 000  →  precio real EUR/USD
  • timestamp   : SEGUNDOS desde medianoche UTC del día del archivo
                  (valores: 0, 60, 120, ..., 86340  ≡  00:00 → 23:59)

Invariantes OHLC garantizados en datos activos:
  H >= max(O, C)  y  L <= min(O, C)  (verificado en todo el dataset).

Los días no operativos (fines de semana, festivos) están presentes como
archivos reales con 1440 registros de OHLC idéntico; no se eliminan aquí.
"""

import datetime
import lzma
import struct
from pathlib import Path

import numpy as np
import pandas as pd

# ── Constantes de formato ────────────────────────────────────────────────────

# Orden REAL de campos en el binario Dukascopy BI5 (verificado 2026-11-01):
# posición 2 = close, posición 4 = high  (NO es o,h,l,c sino o,c,l,h)
_RECORD_DTYPE = np.dtype([
    ("ts_s",   ">u4"),   # segundos desde medianoche (0, 60, 120, ..., 86340)
    ("open",   ">u4"),   # precio × 100 000
    ("close",  ">u4"),   # pos 2: CLOSE (no high — error histórico corregido)
    ("low",    ">u4"),   # pos 3: LOW
    ("high",   ">u4"),   # pos 4: HIGH (no close — error histórico corregido)
    ("volume", ">f4"),   # lotes
])

RECORD_SIZE: int = _RECORD_DTYPE.itemsize      # 24
RECORDS_PER_DAY: int = 1440
PRICE_FACTOR: float = 100_000.0

_EMPTY_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


# ── API pública ──────────────────────────────────────────────────────────────

def parse_file(path: Path, date: datetime.date) -> pd.DataFrame:
    """
    Parsear un archivo BI5 y devolver sus registros como DataFrame.

    Parameters
    ----------
    path : Path
        Ruta al archivo BID_candles_min_1.bi5.
    date : datetime.date
        Fecha del archivo (extraída del directorio, mes 0-indexado ya corregido).

    Returns
    -------
    pd.DataFrame
        Columnas: datetime (UTC, tz-aware), open, high, low, close, volume.
        Vacío si el archivo está vacío.

    Raises
    ------
    ValueError
        Si el archivo no puede descomprimirse (LZMA inválido).
    """
    path = Path(path)
    raw = path.read_bytes()

    if not raw:
        return pd.DataFrame(columns=_EMPTY_COLUMNS)

    try:
        decompressed = lzma.decompress(raw)
    except lzma.LZMAError as exc:
        raise ValueError(f"LZMA decompression failed for {path}: {exc}") from exc

    n = len(decompressed) // RECORD_SIZE
    if n == 0:
        return pd.DataFrame(columns=_EMPTY_COLUMNS)

    arr = np.frombuffer(decompressed[: n * RECORD_SIZE], dtype=_RECORD_DTYPE)

    # Reconstruir datetime UTC: fecha del directorio + offset en SEGUNDOS
    base_ts = pd.Timestamp(date, tz="UTC")
    offsets = pd.to_timedelta(arr["ts_s"].astype(np.int64), unit="s")
    datetimes = base_ts + offsets

    return pd.DataFrame({
        "datetime": datetimes,
        "open":     arr["open"].astype(np.float64)  / PRICE_FACTOR,
        "high":     arr["high"].astype(np.float64)  / PRICE_FACTOR,
        "low":      arr["low"].astype(np.float64)   / PRICE_FACTOR,
        "close":    arr["close"].astype(np.float64) / PRICE_FACTOR,
        "volume":   arr["volume"].astype(np.float64),
    })


def date_from_path(bi5_path: Path) -> datetime.date:
    """
    Inferir la fecha de un archivo BI5 a partir de su ruta de directorio.

    Estructura esperada: .../m1/{year}/{month_0idx:02d}/{day:02d}/BID_...bi5
    El mes del directorio es 0-indexado (00 = enero, 11 = diciembre).

    Raises
    ------
    ValueError
        Si la ruta no tiene la estructura esperada o la fecha es inválida.
    """
    parts = bi5_path.parts
    try:
        day_dir   = parts[-2]
        month_dir = parts[-3]
        year_dir  = parts[-4]
        year  = int(year_dir)
        month = int(month_dir) + 1   # 0-indexed → 1-indexed
        day   = int(day_dir)
        return datetime.date(year, month, day)
    except (IndexError, ValueError) as exc:
        raise ValueError(
            f"No se puede inferir la fecha de la ruta: {bi5_path}"
        ) from exc
