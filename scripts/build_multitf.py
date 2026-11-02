"""
build_multitf.py — Construir todas las temporalidades superiores desde M1

Flujo:
  1. Cargar eurusd_m1_bid.parquet
  2. Construir M15, H1, H4, D1, W1, MN
  3. Validar invariantes OHLC en cada temporalidad
  4. Guardar a data/processed/eurusd_{tf}_bid.parquet
  5. Imprimir resumen

No modifica los datos raw ni el Parquet M1.
"""

import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.data_config import PARQUET_FILES
from src.data.resampler import (
    SUPPORTED_TIMEFRAMES,
    build_all_timeframes,
    validate_ohlcv_invariants,
)
from src.data.loader import save_parquet

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

M1_PARQUET   = PARQUET_FILES["m1"]
OUTPUT_FILES = {tf: PARQUET_FILES[tf] for tf in SUPPORTED_TIMEFRAMES}


def _header(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main() -> None:
    _header("EUR/USD — BUILD MULTI-TIMEFRAME DATASET")

    # ── Cargar M1 ────────────────────────────────────────────────────────────
    _header("PASO 1 — Cargar M1")
    if not M1_PARQUET.exists():
        print(f"  ERROR: Parquet M1 no encontrado: {M1_PARQUET}")
        print("  Ejecuta primero: python scripts/build_dataset.py")
        sys.exit(1)

    df_m1 = pd.read_parquet(M1_PARQUET)
    print(f"  Registros M1  : {len(df_m1):>9,}")
    print(f"  Período       : {df_m1['datetime'].iloc[0]}  →  {df_m1['datetime'].iloc[-1]}")
    print(f"  Activos       : {(~df_m1['is_flat_day']).sum():>9,}")
    print(f"  Planos        : {df_m1['is_flat_day'].sum():>9,}")

    # ── Construir temporalidades ─────────────────────────────────────────────
    _header("PASO 2 — Construir temporalidades")

    all_tf = build_all_timeframes(df_m1)

    # ── Validar y guardar ────────────────────────────────────────────────────
    _header("PASO 3 — Validar y guardar")

    errors = []
    for tf_name, df_tf in all_tf.items():
        freq = SUPPORTED_TIMEFRAMES[tf_name]
        out  = OUTPUT_FILES[tf_name]

        validation = validate_ohlcv_invariants(df_tf, name=tf_name.upper())
        size_mb = 0.0

        if validation["ok"]:
            save_parquet(df_tf, out)
            size_mb = out.stat().st_size / 1_048_576
            status = "✓"
        else:
            status = "✗  VIOLACIONES OHLC"
            errors.append((tf_name, validation["violations"]))

        active = (~df_tf["is_flat_period"]).sum()
        flat   = df_tf["is_flat_period"].sum()

        print(
            f"  {status}  {tf_name.upper():>4}  ({freq:>5})  "
            f"{len(df_tf):>8,} barras  "
            f"activas={active:>7,}  planas={flat:>6,}  "
            f"{size_mb:.1f} MB"
        )

    # ── Resumen final ────────────────────────────────────────────────────────
    _header("RESUMEN")

    if errors:
        print("  ERRORES DETECTADOS:")
        for tf, violations in errors:
            print(f"    {tf}: {violations}")
        sys.exit(1)
    else:
        print("  Todas las temporalidades construidas y validadas correctamente.")
        print()
        print("  Archivos generados:")
        for tf_name, path in OUTPUT_FILES.items():
            if path.exists():
                size_mb = path.stat().st_size / 1_048_576
                print(f"    {path.name:<40}  {size_mb:5.1f} MB")


if __name__ == "__main__":
    main()
