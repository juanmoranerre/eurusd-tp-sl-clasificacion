"""
settings.py — Configuración global del proyecto EUR/USD Trading Intelligence System

Contiene únicamente valores decididos y aprobados.
Las decisiones pendientes de aprobación del trader están en docs/pending_decisions.md
y en config/strategy_config.py (sección PENDING).
"""

from pathlib import Path

# ── Rutas del proyecto ────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent

DATA_RAW_DIR       = PROJECT_ROOT / "data" / "raw" / "m1"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DATA_DATASETS_DIR  = PROJECT_ROOT / "data" / "datasets"
RESULTS_DIR        = PROJECT_ROOT / "results"
DOCS_DIR           = PROJECT_ROOT / "docs"

# ── Activo e instrumento ─────────────────────────────────────────────────────

INSTRUMENT = "EURUSD"
PRICE_TYPE = "BID"        # Dukascopy solo proporciona BID histórico
SOURCE     = "Dukascopy"

# ── Dataset temporal ─────────────────────────────────────────────────────────

DATA_START = "2019-01-01"
DATA_END   = "2026-10-16"

# División temporal aprobada (sección 12 del master prompt)
WARMUP_START = "2019-01-01"
WARMUP_END   = "2019-12-31"
TRAIN_START  = "2020-01-01"
TRAIN_END    = "2024-12-31"
VAL_START    = "2025-01-01"
VAL_END      = "2025-12-31"
TEST_START   = "2026-01-01"
TEST_END     = "2026-10-16"

# ── Temporalidades ────────────────────────────────────────────────────────────

# Temporalidad original (M1 = base)
TF_M1 = "m1"

# Temporalidades derivadas (construidas mediante resample)
TIMEFRAMES = {
    "m15": "15min",   # principal de observación
    "h1":  "1h",      # confirmación y análisis estructural
    "h4":  "4h",      # contexto intermedio
    "d1":  "1D",      # estructura diaria
    "w1":  "1W",      # estructura semanal
    "mn":  "1ME",     # contexto mensual
}

# ── Reproducibilidad ─────────────────────────────────────────────────────────

RANDOM_SEED = 42
