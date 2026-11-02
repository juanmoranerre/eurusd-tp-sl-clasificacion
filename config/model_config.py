"""
model_config.py — Configuración de los modelos de Machine Learning

Contiene parámetros estructurales aprobados.
Los hiperparámetros se aprenden mediante Optuna (no se fijan aquí).
"""

from config.settings import RANDOM_SEED

# ── Algoritmos a comparar [CONFIRMED] ────────────────────────────────────────
# Sección 11 del master prompt: comparar LR, RF, XGBoost.
MODELS = ["logistic_regression", "random_forest", "xgboost"]
OPTIONAL_MODELS = ["lightgbm"]  # solo con justificación técnica

# ── Métricas de evaluación [CONFIRMED] ───────────────────────────────────────
PRIMARY_METRIC = "macro_f1"     # métrica de referencia principal
SECONDARY_METRICS = [
    "accuracy",
    "balanced_accuracy",
    "precision_per_class",
    "recall_per_class",
    "f1_per_class",
    "roc_auc_ovr",
    "pr_auc",
    "confusion_matrix",
    "calibration",
]

# ── División temporal [CONFIRMED] ─────────────────────────────────────────────
# Ver config/settings.py para las fechas exactas.
# No se realizan divisiones aleatorias.
TEMPORAL_SPLIT = {
    "warmup": ("2019-01-01", "2019-12-31"),
    "train":  ("2020-01-01", "2024-12-31"),
    "val":    ("2025-01-01", "2025-12-31"),
    "test":   ("2026-01-01", "2026-10-16"),
}

# ── Walk-forward validation [CONFIRMED] ───────────────────────────────────────
WALK_FORWARD_N_SPLITS  = 5
WALK_FORWARD_EMBARGO   = 5    # períodos de embargo entre train y val (en barras M15)

# ── Optuna [CONFIRMED] ────────────────────────────────────────────────────────
OPTUNA_N_TRIALS  = 100
OPTUNA_TIMEOUT   = 3600       # segundos máximos por estudio
OPTUNA_SEED      = RANDOM_SEED

# ── Reproducibilidad [CONFIRMED] ─────────────────────────────────────────────
SEED = RANDOM_SEED

# ── Parámetros de etiquetado [PENDING] ────────────────────────────────────────
# Deben aprobarse antes de generar etiquetas definitivas.
# Ver docs/pending_decisions.md
LABEL_HORIZON_BARS   = None   # [PENDING] horizonte en barras M15
LABEL_TP_PIPS        = None   # [PENDING] Take Profit en pips
LABEL_SL_PIPS        = None   # [PENDING] Stop Loss en pips
LABEL_COST_PIPS      = None   # [PENDING] coste asumido en pips

# Sistema B (filtro de setups)
SYSTEM_B_THRESHOLD   = 0.5    # umbral por defecto (configurable post-aprobación)

# Sistema C (clasificador predictivo)
# Clases: BUY, SELL, NO_TRADE
SYSTEM_C_CLASSES     = ["BUY", "SELL", "NO_TRADE"]
