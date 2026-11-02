"""
generate_dataset.py — Generador del dataset eurusd_operaciones.csv

Ejecuta el pipeline completo Sistema A V1:
  1. Carga los datos históricos (M1, M15, H1)
  2. Detecta setups sobre M15 (2020-01-01 → 2026-10-16)
  3. Simula cada trade sobre M1 con horizonte de 90 minutos
  4. Calcula resultado binario (0/1) y features pre-entrada
  5. Exporta:
       eurusd_operaciones.csv          — dataset principal (sin leakage)
       eurusd_operaciones_excluidas.csv — setups excluidos (AMBIGUOUS)
       results/eurusd_metadata.csv     — metadatos de cada trade (trazabilidad)

Columnas del CSV principal (17 columnas):
  Metadato temporal  : fecha
  Predictores string : direccion, sesion, cambio_estructura, h1_alignment
  Predictores float  : atr, volatilidad, volumen_rel, distancia_estructura,
                       fib_retracement, fib_in_pref_zone, poi_size_pips,
                       body_range_ratio, displacement_score
  Predictores int    : poi_type, poi_state_at_entry
  Target (int 0/1)   : resultado

Nota sobre resultado:
  resultado = 1 si net_pips > 0  (rentabilidad neta positiva tras todos los costes)
  resultado = 0 si net_pips <= 0
  Esto NO significa necesariamente que el trade haya alcanzado el TP.
  exit_reason en metadata (TP/SL/BE/TIME_EXIT/AMBIGUOUS) registra la causa real.

Columnas excluidas del CSV por leakage post-entrada:
  entry_bid, sl_price, tp_price, risk_pips, exit_reason,
  entry_time, exit_time, exit_bid, gross_pips, net_pips, net_usd,
  bar_index, entry_bar_index, h1_bias, fib_in_entry_zone (varianza cero)

Supuestos de simulación (escenario central):
  spread   : 0.2 pips  (hipótesis, no spread histórico observado)
  slippage : 0.0 pips
  comisión : 5 USD/lote round-turn ≈ 0.5 pips (PD-021b PENDING)
  coste total : 0.7 pips por operación
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.data_config import H1_PARQUET, M1_PARQUET, M15_PARQUET
from src.backtesting.cost_model import CostModel, DEFAULT_COST_MODEL
from src.backtesting.trade_simulator import get_m1_slice, simulate_trade
from src.strategy.setup_detector import detect_setups

# ── Columnas del CSV principal (sin leakage post-entrada) ─────────────────────
CSV_COLUMNS = [
    "fecha",
    "direccion",
    "sesion",
    "cambio_estructura",
    "h1_alignment",
    "atr",
    "volatilidad",
    "volumen_rel",
    "distancia_estructura",
    "fib_retracement",
    "fib_in_pref_zone",
    "poi_type",
    "poi_state_at_entry",
    "poi_size_pips",
    "body_range_ratio",
    "displacement_score",
    "resultado",
]

# Columnas de metadatos (trazabilidad; no para modelos)
META_COLUMNS = [
    "fecha",
    "entry_time",
    "exit_time",
    "entry_bid",
    "sl_price",
    "tp_price",
    "risk_pips",
    "exit_reason",
    "exit_bid",
    "gross_pips",
    "net_pips",
    "net_usd",
    "h1_bias",
    "bar_index",
    "entry_bar_index",
    "poi_id",
    "resultado",
]

# Columnas del archivo de excluidos (AMBIGUOUS + otros excluidos futuros)
EXCLUIDOS_COLUMNS = [
    "fecha",
    "entry_time",
    "exit_time",
    "entry_bid",
    "sl_price",
    "tp_price",
    "risk_pips",
    "exit_reason",
    "motivo_exclusion",
    "exit_bid",
    "gross_pips",
    "net_pips",
    "h1_bias",
    "h1_alignment",
    "direccion",
    "sesion",
]


def _normalize_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte la columna 'datetime' a UTC tz-naive."""
    col = df["datetime"]
    if hasattr(col.dt, "tz") and col.dt.tz is not None:
        df = df.copy()
        df["datetime"] = col.dt.tz_convert("UTC").dt.tz_localize(None)
    return df


def _load_data(
    start: str,
    end: str,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carga M1, M15, H1 con margen de warm-up."""
    t0 = time.perf_counter()
    margin_start = pd.Timestamp(start) - pd.DateOffset(months=3)
    margin_start_str = margin_start.strftime("%Y-%m-%d")

    if verbose:
        print(f"[load] Cargando M15 desde {margin_start_str}...")
    m15_full = pd.read_parquet(M15_PARQUET)
    m15_full = _normalize_datetime(m15_full)
    m15 = m15_full[m15_full["datetime"] >= margin_start_str].copy()

    if verbose:
        print(f"[load] Cargando H1 desde {margin_start_str}...")
    h1_full = pd.read_parquet(H1_PARQUET)
    h1_full = _normalize_datetime(h1_full)
    h1 = h1_full[h1_full["datetime"] >= margin_start_str].copy()

    if verbose:
        print(f"[load] M15 = {len(m15):,} barras | H1 = {len(h1):,} barras")
        print(f"[load] Cargando M1 desde {start}...")

    m1_start = pd.Timestamp(start) - pd.DateOffset(hours=2)
    m1_full = pd.read_parquet(M1_PARQUET)
    m1_full = _normalize_datetime(m1_full)
    m1 = m1_full[
        (m1_full["datetime"] >= m1_start.strftime("%Y-%m-%d"))
        & (m1_full["datetime"] <= pd.Timestamp(end) + pd.DateOffset(hours=2))
    ].copy()

    if verbose:
        print(f"[load] M1 = {len(m1):,} barras")
        print(f"[load] Tiempo de carga: {time.perf_counter() - t0:.1f}s")

    return m1.reset_index(drop=True), m15.reset_index(drop=True), h1.reset_index(drop=True)


def _simulate_all(
    setups_df: pd.DataFrame,
    m1: pd.DataFrame,
    verbose: bool = True,
) -> pd.DataFrame:
    """Simula todos los trades y añade columnas de resultado."""
    results = []
    n = len(setups_df)

    if verbose:
        print(f"[sim] Simulando {n} setups sobre M1 (horizonte 90 min)...")

    for idx, row in setups_df.iterrows():
        # entry_time = apertura de la barra M15 i+1 (= fecha + 15 min)
        entry_time = pd.Timestamp(row["fecha"]) + pd.Timedelta(minutes=15)
        entry_bid  = row["entry_bid"]
        sl_price   = row["sl_price"]
        tp_price   = row["tp_price"]
        direction  = "buy" if row["direccion"] == "compra" else "sell"

        m1_slice = get_m1_slice(m1, entry_time)

        if len(m1_slice) == 0:
            # Sin datos M1: TIME_EXIT inmediato en entry_time
            sc = DEFAULT_COST_MODEL.central
            results.append({
                "resultado":    0,
                "exit_reason":  "TIME_EXIT",
                "entry_time":   entry_time,
                "exit_time":    entry_time,
                "exit_bid":     entry_bid,
                "gross_pips":   0.0,
                "net_pips":     -sc.total_cost_pips(1.0),
                "net_usd":      -sc.total_cost_usd(1.0),
            })
            continue

        trade = simulate_trade(
            direction=direction,
            entry_bid=entry_bid,
            sl_price=sl_price,
            tp_price=tp_price,
            m1_slice=m1_slice,
            cost_model=DEFAULT_COST_MODEL,
            scenario="central",
        )
        results.append({
            "resultado":   trade.resultado,
            "exit_reason": trade.exit_reason,
            "entry_time":  trade.entry_time,
            "exit_time":   trade.exit_time,
            "exit_bid":    trade.exit_bid,
            "gross_pips":  trade.gross_pips,
            "net_pips":    trade.net_pips,
            "net_usd":     trade.net_usd,
        })

        if verbose and (idx + 1) % 200 == 0:
            done = idx + 1
            pct  = 100 * done / n
            wins = sum(r["resultado"] for r in results)
            print(f"[sim] {done}/{n} ({pct:.1f}%)  win_rate={wins/done:.1%}")

    results_df = pd.DataFrame(results)
    # Eliminar placeholders None del setups antes de concat
    setups_clean = setups_df.drop(columns=["resultado", "exit_reason"], errors="ignore").reset_index(drop=True)
    return pd.concat([setups_clean, results_df], axis=1)


def _build_outputs(
    full_df: pd.DataFrame,
    c2_excluded_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int, int]:
    """
    Construye los tres DataFrames de salida:
      (csv_df, meta_df, excluidos_df, n_ambiguous, n_c2)

    csv_df       : dataset principal sin leakage
    meta_df      : metadatos completos de cada trade en csv_df
    excluidos_df : setups excluidos (AMBIGUOUS + C2_POI_REUSE)
    """
    full_df = full_df.copy()

    # Separar AMBIGUOUS antes de cualquier otra operación
    excluidos_mask = full_df["exit_reason"] == "AMBIGUOUS"
    excluidos_raw  = full_df[excluidos_mask].copy()
    main_df        = full_df[~excluidos_mask].copy()
    n_ambiguous    = len(excluidos_raw)

    # Excluir filas con NaN en columnas críticas del CSV
    critical = ["atr", "volatilidad", "volumen_rel", "distancia_estructura", "fib_retracement"]
    n_before = len(main_df)
    main_df = main_df.dropna(subset=critical)
    n_nan   = n_before - len(main_df)
    if n_nan > 0:
        print(f"[build] Descartadas {n_nan} filas con NaN en features críticas")

    # resultado ya es int (0/1) desde TradeResult; asegurar tipo
    main_df["resultado"] = main_df["resultado"].astype(int)

    # Formato de fecha
    main_df["fecha"] = main_df["fecha"].astype(str)

    # Verificar columnas requeridas
    missing = [c for c in CSV_COLUMNS if c not in main_df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes en el dataset: {missing}")

    # ── CSV principal
    csv_df = main_df[CSV_COLUMNS].copy()

    # ── Metadata (trazabilidad completa, incluyendo resultado y poi_id)
    meta_df = main_df[META_COLUMNS].copy()

    # ── Excluidos: AMBIGUOUS + C2_POI_REUSE
    excl_parts = []
    if n_ambiguous > 0:
        excluidos_raw = excluidos_raw.copy()
        excluidos_raw["motivo_exclusion"] = "AMBIGUOUS"
        excluidos_raw["fecha"] = excluidos_raw["fecha"].astype(str)
        excl_cols = [c for c in EXCLUIDOS_COLUMNS if c in excluidos_raw.columns]
        excl_parts.append(excluidos_raw[excl_cols].copy())

    n_c2 = 0
    if c2_excluded_df is not None and len(c2_excluded_df) > 0:
        n_c2 = len(c2_excluded_df)
        c2_df = c2_excluded_df.copy()
        c2_df["fecha"] = c2_df["fecha"].astype(str)
        excl_cols_c2 = [c for c in EXCLUIDOS_COLUMNS if c in c2_df.columns]
        excl_parts.append(c2_df[excl_cols_c2].copy())

    if excl_parts:
        excluidos_df = pd.concat(excl_parts, ignore_index=True)
    else:
        excluidos_df = pd.DataFrame(columns=EXCLUIDOS_COLUMNS)

    return csv_df, meta_df, excluidos_df, n_ambiguous, n_c2


def main():
    parser = argparse.ArgumentParser(description="Genera eurusd_operaciones.csv")
    parser.add_argument("--start",    default="2020-01-01",                   help="Fecha inicio")
    parser.add_argument("--end",      default="2026-10-16",                   help="Fecha fin")
    parser.add_argument("--out",      default="eurusd_operaciones.csv",        help="CSV principal")
    parser.add_argument("--excluidos",default="eurusd_operaciones_excluidas.csv", help="CSV de excluidos")
    parser.add_argument("--meta",     default="results/eurusd_metadata.csv",   help="Metadata")
    parser.add_argument("--quiet",    action="store_true")
    args = parser.parse_args()

    verbose   = not args.quiet
    t_total   = time.perf_counter()

    m1, m15, h1 = _load_data(args.start, args.end, verbose)

    if verbose:
        print(f"\n[detect] Detectando setups M15 ({args.start} → {args.end})...")
    t1 = time.perf_counter()

    setups_df, c2_excluded_df = detect_setups(m15, h1, start_date=args.start, end_date=args.end)

    if verbose:
        n_c2_detect = len(c2_excluded_df) if c2_excluded_df is not None else 0
        print(f"[detect] {len(setups_df):,} setups detectados en {time.perf_counter()-t1:.1f}s")
        print(f"[detect] {n_c2_detect:,} setups filtrados por C2 (POI reuse en mismo episodio)")

    if len(setups_df) == 0:
        print("[ERROR] No se detectaron setups. Verifica los datos y parámetros.")
        sys.exit(1)

    full_df = _simulate_all(setups_df, m1, verbose)

    csv_df, meta_df, excluidos_df, n_ambiguous, n_c2 = _build_outputs(full_df, c2_excluded_df)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    csv_df.to_csv(out_path, index=False)

    meta_path = Path(args.meta)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_df.to_csv(meta_path, index=False)

    excl_path = Path(args.excluidos)
    excl_path.parent.mkdir(parents=True, exist_ok=True)
    excluidos_df.to_csv(excl_path, index=False)

    # ── Reporte final
    elapsed  = time.perf_counter() - t_total
    n_total  = len(csv_df)
    n_tp     = (csv_df["resultado"] == 1).sum()
    n_sl     = (csv_df["resultado"] == 0).sum()

    print(f"\n{'='*60}")
    print(f"Dataset generado: {out_path}")
    print(f"{'='*60}")
    print(f"  Total setups válidos  : {n_total:>6,}")
    print(f"  resultado = 1 (net>0) : {n_tp:>6,}  ({n_tp/n_total:.1%})")
    print(f"  resultado = 0 (net<=0): {n_sl:>6,}  ({n_sl/n_total:.1%})")
    print(f"  Excluidos AMBIGUOUS   : {n_ambiguous:>6,}  → {args.excluidos}")
    print(f"  Excluidos C2_POI_REUSE: {n_c2:>6,}  → {args.excluidos}")
    print(f"  Tiempo total          : {elapsed:.1f}s")
    print(f"  Metadata guardada en  : {meta_path}")
    print(f"{'='*60}")

    print(f"\nColumnas del CSV ({len(csv_df.columns)}):")
    for col in csv_df.columns:
        print(f"  {col}")

    if n_total < 100:
        print(f"\n[ADVERTENCIA] Solo {n_total} setups. Revisa los datos y parámetros.")
    elif n_total < 300:
        print(f"\n[ADVERTENCIA] {n_total} setups. El notebook recomienda >= 300 para modelos robustos.")
    else:
        print(f"\n[OK] Dataset listo para el notebook ({n_total} setups).")

    # Distribuciones
    print("\nPor sesion:")
    print(csv_df["sesion"].value_counts().to_string())
    print("\nPor h1_alignment:")
    print(csv_df["h1_alignment"].value_counts().to_string())
    print("\nPor direccion:")
    print(csv_df["direccion"].value_counts().to_string())
    print("\nPor poi_type (0=FVG, 1=OB):")
    print(csv_df["poi_type"].value_counts().to_string())

    # Motivos de salida (desde metadata)
    print("\nMotivos de salida (exit_reason en metadata):")
    print(meta_df["exit_reason"].value_counts().to_string())
    print("\nExit reason x resultado:")
    print(meta_df.groupby(["exit_reason", "resultado"]).size().unstack(fill_value=0).to_string())

    # Por año
    csv_copy = csv_df.copy()
    csv_copy["year"] = pd.to_datetime(csv_df["fecha"]).dt.year
    print("\nSetups por año (resultado 0/1):")
    print(csv_copy.groupby("year")["resultado"].value_counts().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
