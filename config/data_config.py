"""
data_config.py — Configuración de datos y rutas de archivos procesados

Define los nombres de archivo Parquet para cada temporalidad.
"""

from pathlib import Path

from config.settings import DATA_PROCESSED_DIR, INSTRUMENT, PRICE_TYPE

PRICE_TYPE_LOWER = PRICE_TYPE.lower()

# ── Archivos Parquet ──────────────────────────────────────────────────────────

M1_PARQUET   = DATA_PROCESSED_DIR / f"{INSTRUMENT.lower()}_m1_{PRICE_TYPE_LOWER}.parquet"
M15_PARQUET  = DATA_PROCESSED_DIR / f"{INSTRUMENT.lower()}_m15_{PRICE_TYPE_LOWER}.parquet"
H1_PARQUET   = DATA_PROCESSED_DIR / f"{INSTRUMENT.lower()}_h1_{PRICE_TYPE_LOWER}.parquet"
H4_PARQUET   = DATA_PROCESSED_DIR / f"{INSTRUMENT.lower()}_h4_{PRICE_TYPE_LOWER}.parquet"
D1_PARQUET   = DATA_PROCESSED_DIR / f"{INSTRUMENT.lower()}_d1_{PRICE_TYPE_LOWER}.parquet"
W1_PARQUET   = DATA_PROCESSED_DIR / f"{INSTRUMENT.lower()}_w1_{PRICE_TYPE_LOWER}.parquet"
MN_PARQUET   = DATA_PROCESSED_DIR / f"{INSTRUMENT.lower()}_mn_{PRICE_TYPE_LOWER}.parquet"

PARQUET_FILES = {
    "m1":  M1_PARQUET,
    "m15": M15_PARQUET,
    "h1":  H1_PARQUET,
    "h4":  H4_PARQUET,
    "d1":  D1_PARQUET,
    "w1":  W1_PARQUET,
    "mn":  MN_PARQUET,
}

# ── Columnas esperadas por temporalidad ───────────────────────────────────────

BASE_OHLCV_COLS    = ["datetime", "open", "high", "low", "close", "volume"]
M1_COLS            = BASE_OHLCV_COLS + ["is_flat_day"]
HIGHER_TF_COLS     = BASE_OHLCV_COLS + ["is_flat_period"]
