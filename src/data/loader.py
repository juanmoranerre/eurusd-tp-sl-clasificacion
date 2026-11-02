"""
loader.py — Carga multi-día de datos BI5 EUR/USD M1

Responsabilidades:
  1. Descubrir todos los archivos BI5 bajo data/raw/m1/
  2. Convertir la convención de directorio de Dukascopy (mes 0-indexado) a fechas reales
  3. Cargar y concatenar cronológicamente
  4. Añadir columna `is_flat_day` (True = día sin actividad: fin de semana o festivo)
  5. Guardar a Parquet sin tocar los archivos raw
"""

import datetime
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from src.data.parser_bi5 import date_from_path, parse_file

logger = logging.getLogger(__name__)

BI5_FILENAME = "BID_candles_min_1.bi5"


# ── Funciones públicas ────────────────────────────────────────────────────────

def discover_files(
    data_dir: Path,
    start: Optional[datetime.date] = None,
    end: Optional[datetime.date] = None,
) -> list[tuple[datetime.date, Path]]:
    """
    Descubrir y ordenar cronológicamente todos los archivos BI5.

    Parameters
    ----------
    data_dir : Path
        Raíz del dataset (e.g. data/raw/m1/).
    start, end : datetime.date | None
        Rango inclusivo para filtrar. None = sin límite.

    Returns
    -------
    list[(date, Path)]
        Lista ordenada por fecha.
    """
    entries: list[tuple[datetime.date, Path]] = []

    for year_dir in sorted(data_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue

            month_0idx = int(month_dir.name)
            if not 0 <= month_0idx <= 11:
                logger.warning("Directorio de mes inválido: %s", month_dir)
                continue

            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir() or not day_dir.name.isdigit():
                    continue

                bi5 = day_dir / BI5_FILENAME
                if not bi5.exists():
                    continue

                try:
                    date = date_from_path(bi5)
                except ValueError as exc:
                    logger.warning("Fecha inválida, ignorando %s: %s", bi5, exc)
                    continue

                if start and date < start:
                    continue
                if end and date > end:
                    continue

                entries.append((date, bi5))

    return sorted(entries, key=lambda x: x[0])


def is_flat_day(df: pd.DataFrame) -> bool:
    """
    Detectar si un día es no operativo (todos los registros con OHLC idéntico).

    Los archivos de fines de semana y festivos de Dukascopy tienen 1440 velas
    con open == high == low == close. El volumen puede ser no nulo en algunos.
    """
    return bool(
        (df["open"] == df["high"]).all()
        and (df["high"] == df["low"]).all()
        and (df["low"] == df["close"]).all()
    )


def load_range(
    data_dir: Path,
    start: Optional[datetime.date] = None,
    end: Optional[datetime.date] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Cargar y concatenar todos los días dentro del rango dado.

    Parameters
    ----------
    data_dir : Path
        Raíz del dataset (e.g. data/raw/m1/).
    start, end : datetime.date | None
        Filtro de fechas (inclusivo). None = sin límite.

    Returns
    -------
    (DataFrame, stats)
        DataFrame con columnas:
          datetime (UTC), open, high, low, close, volume, is_flat_day
        stats: diccionario con métricas de procesamiento.
    """
    files = discover_files(data_dir, start, end)

    stats: dict = {
        "total_files":   len(files),
        "loaded":        0,
        "flat_days":     0,
        "active_days":   0,
        "errors":        0,
        "error_files":   [],
        "date_start":    None,
        "date_end":      None,
        "total_records": 0,
    }

    frames: list[pd.DataFrame] = []

    for date, path in files:
        try:
            df = parse_file(path, date)
        except ValueError as exc:
            stats["errors"] += 1
            stats["error_files"].append({"path": str(path), "error": str(exc)})
            logger.error("Error al cargar %s: %s", path, exc)
            continue

        if df.empty:
            logger.warning("Archivo vacío ignorado: %s", path)
            continue

        flat = is_flat_day(df)
        df = df.copy()
        df["is_flat_day"] = flat

        if flat:
            stats["flat_days"] += 1
        else:
            stats["active_days"] += 1

        frames.append(df)
        stats["loaded"] += 1

    if not frames:
        return pd.DataFrame(), stats

    result = pd.concat(frames, ignore_index=True)
    result.sort_values("datetime", inplace=True)
    result.reset_index(drop=True, inplace=True)

    stats["total_records"] = len(result)
    stats["date_start"]    = result["datetime"].iloc[0].date()
    stats["date_end"]      = result["datetime"].iloc[-1].date()

    return result, stats


def save_parquet(df: pd.DataFrame, output_path: Path) -> None:
    """
    Guardar DataFrame a Parquet con motor pyarrow.

    El directorio de destino se crea si no existe.
    No modifica los archivos raw originales.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info("Parquet guardado: %s  (%d registros)", output_path, len(df))
