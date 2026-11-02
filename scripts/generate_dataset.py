"""
generate_dataset.py — Generador del dataset eurusd_operaciones.csv

Ejecuta el pipeline completo Sistema A V1:
  1. Carga los datos históricos (M1, M15, H1)
  2. Detecta setups sobre M15 (2020-01-01 → 2026-10-16)
  3. Simula cada trade sobre M1
  4. Calcula resultado binario y features pre-entrada
  5. Exporta eurusd_operaciones.csv compatible con notebooks/Proyecto_02.ipynb

Uso:
  python scripts/generate_dataset.py
  python scripts/generate_dataset.py --start 2020-01-01 --end 2024-12-31
  python scripts/generate_dataset.py --out results/eurusd_op_test.csv

Columnas de salida (requeridas por el notebook):
  fecha, direccion, sesion, cambio_estructura,
  atr, volatilidad, volumen_rel, distancia_estructura, resultado

Columnas adicionales (predictores automáticos en el notebook):
  fib_retracement, fib_in_entry_zone, fib_in_pref_zone,
  poi_type, poi_state_at_entry, poi_size_pips,
  body_range_ratio, displacement_score

Columnas de metadatos (NO en el CSV final — evitan data leakage):
  entry_bid, sl_price, tp_price, risk_pips, exit_reason,
  bar_index, entry_bar_index, h1_bias
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Asegurar que el proyecto está en el path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.data_config import H1_PARQUET, M1_PARQUET, M15_PARQUET
from src.backtesting.cost_model import CostModel, DEFAULT_COST_MODEL
from src.backtesting.trade_simulator import get_m1_slice, simulate_trade
from src.strategy.setup_detector import detect_setups

# ── Columnas que van al CSV (sin metadata post-entrada) ───────────────────────
CSV_COLUMNS = [
    # Requeridas por el notebook
    "fecha",
    "direccion",
    "sesion",
    "cambio_estructura",
    "atr",
    "volatilidad",
    "volumen_rel",
    "distancia_estructura",
    # Features adicionales (predictores automáticos)
    "fib_retracement",
    "fib_in_entry_zone",
    "fib_in_pref_zone",
    "poi_type",
    "poi_state_at_entry",
    "poi_size_pips",
    "body_range_ratio",
    "displacement_score",
    # Target binario
    "resultado",
]

# Columnas de metadatos guardadas en archivo separado (para análisis, no para modelos)
META_COLUMNS = [
    "fecha",
    "entry_bid",
    "sl_price",
    "tp_price",
    "risk_pips",
    "exit_reason",
    "h1_bias",
    "bar_index",
    "entry_bar_index",
    "resultado",
]


def _normalize_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte la columna 'datetime' a UTC tz-naive para consistencia."""
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
    """Carga M1, M15, H1 filtrando por período con margen suficiente."""
    t0 = time.perf_counter()

    # Cargamos con un margen de 3 meses antes del start para dar tiempo
    # a que los indicadores (ATR, swings, H1 structure) se estabilicen
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

    # M1 solo desde el start exacto (necesitamos M1 solo para simular trades)
    # La simulación empieza cuando hay setups, y esos setups son desde `start`
    # Cargamos con margen de 2 horas para cubrir el primer trade
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
        print(f"[sim] Simulando {n} setups sobre M1...")

    for idx, row in setups_df.iterrows():
        entry_time = pd.Timestamp(row["fecha"]) + pd.Timedelta(minutes=15)
        # entry_time es el open de la barra M15 siguiente
        # Usamos la columna entry_bid que ya tiene el open de la barra i+1
        entry_bid  = row["entry_bid"]
        sl_price   = row["sl_price"]
        tp_price   = row["tp_price"]
        direction  = "buy" if row["direccion"] == "compra" else "sell"

        m1_slice = get_m1_slice(m1, entry_time, max_bars=90)

        if len(m1_slice) == 0:
            # No hay datos M1 para este setup → TIME_EXIT
            results.append({
                "resultado":    0,
                "exit_reason":  "TIME_EXIT",
                "exit_bid":     entry_bid,
                "gross_pips":   0.0,
                "net_pips":     -DEFAULT_COST_MODEL.central.total_cost_pips(1.0),
                "net_usd":      -DEFAULT_COST_MODEL.central.total_cost_usd(1.0),
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
            "exit_bid":    trade.exit_bid,
            "gross_pips":  trade.gross_pips,
            "net_pips":    trade.net_pips,
            "net_usd":     trade.net_usd,
        })

        if verbose and (idx + 1) % 200 == 0:
            done = idx + 1
            pct = 100 * done / n
            wins = sum(r["resultado"] for r in results)
            print(f"[sim] {done}/{n} ({pct:.1f}%)  win_rate={wins/done:.1%}")

    results_df = pd.DataFrame(results)
    # Eliminar columna resultado placeholder (None) del setups antes de concatenar
    setups_clean = setups_df.drop(columns=["resultado", "exit_reason"], errors="ignore").reset_index(drop=True)
    return pd.concat([setups_clean, results_df], axis=1)


def _build_csv(full_df: pd.DataFrame) -> pd.DataFrame:
    """Construye el DataFrame final para el CSV con las columnas en el orden correcto."""
    # Convertir resultado binario a "TP"/"SL" strings para el notebook
    # (el notebook hace replace({"TP": 1, "SL": 0}))
    full_df = full_df.copy()
    full_df["resultado_str"] = full_df["resultado"].map({1: "TP", 0: "SL"})

    # Usar resultado_str como la columna resultado del CSV
    full_df["resultado"] = full_df["resultado_str"]

    # Formato de fecha legible
    full_df["fecha"] = full_df["fecha"].astype(str)

    # Verificar columnas requeridas
    missing = [c for c in CSV_COLUMNS if c not in full_df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes en el dataset: {missing}")

    # Excluir setups AMBIGUOUS del dataset principal (son ruido para clasificación)
    n_before = len(full_df)
    full_df = full_df[full_df["exit_reason"] != "AMBIGUOUS"].copy()
    n_ambiguous = n_before - len(full_df)

    # Excluir filas con NaN en columnas críticas
    critical = ["atr", "volatilidad", "volumen_rel", "distancia_estructura", "fib_retracement"]
    full_df = full_df.dropna(subset=critical)

    return full_df[CSV_COLUMNS], full_df[META_COLUMNS], n_ambiguous


def main():
    parser = argparse.ArgumentParser(description="Genera eurusd_operaciones.csv")
    parser.add_argument("--start", default="2020-01-01", help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--end",   default="2026-10-16", help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument("--out",   default="eurusd_operaciones.csv", help="Archivo de salida")
    parser.add_argument("--meta",  default="results/eurusd_metadata.csv", help="Metadata de trades")
    parser.add_argument("--quiet", action="store_true", help="Silenciar log detallado")
    args = parser.parse_args()

    verbose = not args.quiet
    t_total = time.perf_counter()

    # ── 1. Cargar datos
    m1, m15, h1 = _load_data(args.start, args.end, verbose)

    # ── 2. Detectar setups
    if verbose:
        print(f"\n[detect] Detectando setups M15 ({args.start} → {args.end})...")
    t1 = time.perf_counter()

    setups_df = detect_setups(
        m15,
        h1,
        start_date=args.start,
        end_date=args.end,
    )

    if verbose:
        print(f"[detect] {len(setups_df):,} setups detectados en {time.perf_counter()-t1:.1f}s")

    if len(setups_df) == 0:
        print("[ERROR] No se detectaron setups. Verifica los datos y parámetros.")
        sys.exit(1)

    # ── 3. Simular trades
    full_df = _simulate_all(setups_df, m1, verbose)

    # ── 4. Construir CSV
    csv_df, meta_df, n_ambiguous = _build_csv(full_df)

    # ── 5. Guardar
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    csv_df.to_csv(out_path, index=False)

    meta_path = Path(args.meta)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_df.to_csv(meta_path, index=False)

    # ── 6. Reporte final
    elapsed = time.perf_counter() - t_total
    n_total = len(csv_df)
    n_tp    = (csv_df["resultado"] == "TP").sum()
    n_sl    = (csv_df["resultado"] == "SL").sum()

    print(f"\n{'='*60}")
    print(f"Dataset generado: {out_path}")
    print(f"{'='*60}")
    print(f"  Total setups válidos : {n_total:>6,}")
    print(f"  Resultado TP (1)     : {n_tp:>6,}  ({n_tp/n_total:.1%})")
    print(f"  Resultado SL (0)     : {n_sl:>6,}  ({n_sl/n_total:.1%})")
    print(f"  Excluidos AMBIGUOUS  : {n_ambiguous:>6,}")
    print(f"  Tiempo total         : {elapsed:.1f}s")
    print(f"  Metadata guardada en : {meta_path}")
    print(f"{'='*60}")
    print(f"\nColumnas del CSV ({len(csv_df.columns)}):")
    for col in csv_df.columns:
        print(f"  {col}")

    if n_total < 100:
        print(f"\n⚠  ADVERTENCIA: solo {n_total} setups. Considera ampliar el período o revisar filtros.")
    elif n_total < 300:
        print(f"\n⚠  ADVERTENCIA: {n_total} setups. El notebook recomienda ≥ 300 para modelos robustos.")
    else:
        print(f"\n✓ Dataset listo para el notebook ({n_total} setups).")

    print("\nDistribución por sesión:")
    print(csv_df["sesion"].value_counts().to_string())
    print("\nDistribución por cambio_estructura:")
    print(csv_df["cambio_estructura"].value_counts().to_string())

    # Distribución por año
    csv_df_with_year = csv_df.copy()
    csv_df_with_year["year"] = pd.to_datetime(csv_df["fecha"]).dt.year
    print("\nSetups por año:")
    print(csv_df_with_year.groupby("year")["resultado"].value_counts().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
