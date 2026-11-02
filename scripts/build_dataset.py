"""
build_dataset.py — Construcción del dataset EUR/USD M1

Flujo:
  1. Prueba de un día conocido (2019-01-03) → comparación con valores del audit
  2. Si pasa → carga completa de todos los años
  3. Guardar a data/processed/eurusd_m1_bid.parquet
  4. Imprimir resumen

No modifica los archivos raw originales.
"""

import datetime
import sys
from pathlib import Path

import pandas as pd

# Añadir raíz del proyecto al path (evita necesidad de pip install -e .)
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loader import load_range, save_parquet
from src.data.parser_bi5 import parse_file

DATA_DIR    = PROJECT_ROOT / "data" / "raw" / "m1"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "eurusd_m1_bid.parquet"

# ── Valores de referencia corregidos (2026-11-01) ────────────────────────────
# Orden real Dukascopy BI5: (ts, open, CLOSE, low, HIGH, vol).
# HIGH y CLOSE estaban intercambiados antes de la corrección.
AUDIT_DATE   = datetime.date(2019, 1, 3)
AUDIT_OPEN   = 1.13122  # unchanged
AUDIT_HIGH   = 1.13175  # corrected (era 1.13173)
AUDIT_LOW    = 1.13099  # unchanged
AUDIT_CLOSE  = 1.13173  # corrected (era 1.13175)
AUDIT_VOLUME = 346.92
PRICE_TOL    = 1e-5
VOL_TOL      = 0.1


def _header(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def validate_single_day() -> bool:
    """
    Cargar 2019-01-03 y comparar con los valores validados manualmente.
    Retorna True si todos los checks pasan.
    """
    _header("PASO 1 — Validación día conocido: 2019-01-03")

    path = DATA_DIR / "2019" / "00" / "03" / "BID_candles_min_1.bi5"
    if not path.exists():
        print(f"  ERROR: archivo no encontrado: {path}")
        return False

    try:
        df = parse_file(path, AUDIT_DATE)
    except Exception as exc:
        print(f"  ERROR al parsear: {exc}")
        return False

    checks = {
        "Registros = 1440":         len(df) == 1440,
        "Primer timestamp = 00:00": df["datetime"].iloc[0] == pd.Timestamp("2019-01-03 00:00:00", tz="UTC"),
        "Último timestamp = 23:59": df["datetime"].iloc[-1] == pd.Timestamp("2019-01-03 23:59:00", tz="UTC"),
        f"Open ≈ {AUDIT_OPEN}":     abs(df["open"].iloc[0]   - AUDIT_OPEN)   < PRICE_TOL,
        f"High ≈ {AUDIT_HIGH}":     abs(df["high"].iloc[0]   - AUDIT_HIGH)   < PRICE_TOL,
        f"Low ≈ {AUDIT_LOW}":       abs(df["low"].iloc[0]    - AUDIT_LOW)    < PRICE_TOL,
        f"Close ≈ {AUDIT_CLOSE}":   abs(df["close"].iloc[0]  - AUDIT_CLOSE)  < PRICE_TOL,
        f"Volume ≈ {AUDIT_VOLUME}": abs(df["volume"].iloc[0] - AUDIT_VOLUME) < VOL_TOL,
        "H >= L en todos":          (df["high"] >= df["low"]).all(),
        "Datetime UTC":             str(df["datetime"].dt.tz) == "UTC",
        "Mes=1 (no 0-indexed)":     df["datetime"].iloc[0].month == 1,
    }

    all_ok = True
    for label, result in checks.items():
        status = "✓" if result else "✗"
        print(f"  {status}  {label}")
        if not result:
            all_ok = False

    if all_ok:
        print()
        print("  → Todos los checks pasaron. Procediendo con carga completa.")
    else:
        print()
        print("  → FALLÓ la validación. Abortando carga completa.")

    return all_ok


def run_full_pipeline() -> None:
    """Cargar todos los archivos y guardar a Parquet."""
    _header("PASO 2 — Carga completa del dataset")

    print(f"  Fuente  : {DATA_DIR}")
    print(f"  Destino : {OUTPUT_PATH}")
    print()
    print("  Cargando archivos... (esto puede tardar 30-60 segundos)")

    df, stats = load_range(DATA_DIR)

    _header("PASO 3 — Guardar a Parquet")
    save_parquet(df, OUTPUT_PATH)
    size_mb = OUTPUT_PATH.stat().st_size / 1_048_576
    print(f"  Archivo guardado: {OUTPUT_PATH}")
    print(f"  Tamaño en disco : {size_mb:.1f} MB")

    _header("RESUMEN DEL DATASET")
    print(f"  Archivos procesados : {stats['loaded']:>7,}")
    print(f"  Errores             : {stats['errors']:>7,}")
    print(f"  Días activos        : {stats['active_days']:>7,}")
    print(f"  Días planos         : {stats['flat_days']:>7,}")
    print(f"  Total registros     : {stats['total_records']:>7,}")
    print(f"  Primer datetime     : {stats['date_start']}")
    print(f"  Último datetime     : {stats['date_end']}")

    if stats["error_files"]:
        print()
        print("  Archivos con error:")
        for ef in stats["error_files"]:
            print(f"    • {ef['path']}: {ef['error']}")

    _header("VERIFICACIÓN DEL PARQUET")
    df_check = pd.read_parquet(OUTPUT_PATH)
    print(f"  Registros leídos    : {len(df_check):>7,}")
    print(f"  Columnas            : {list(df_check.columns)}")
    print(f"  Dtype datetime      : {df_check['datetime'].dtype}")
    print(f"  is_flat_day=True    : {df_check['is_flat_day'].sum():>7,}")
    print(f"  is_flat_day=False   : {(~df_check['is_flat_day']).sum():>7,}")
    print()
    print("  Muestra (primeras 3 filas activas):")
    active = df_check[~df_check["is_flat_day"]].head(3)
    print(active[["datetime", "open", "high", "low", "close", "volume"]].to_string(index=False))
    print()
    print("  ✓ Dataset listo para Etapa 2 (feature engineering).")


def main() -> None:
    _header("EUR/USD M1 — BUILD DATASET  (Etapa 0 + 1)")

    if not validate_single_day():
        sys.exit(1)

    run_full_pipeline()


if __name__ == "__main__":
    main()
