"""
strategy_config.py — Parámetros de la estrategia de trading EUR/USD

Clasificación de cada parámetro:
  [CONFIRMED]      — aprobado explícitamente por el trader (2026-11-01)
  [CONVENTIONAL]   — convención SMC/ICT de referencia aceptada como punto de partida
  [PENDING]        — requiere aprobación adicional antes de usar en backtest/etiquetado

Los parámetros PENDING deben mantenerse como None o como dict de escenarios.
Consultar docs/decisions_log.md (DEC-006 en adelante) y docs/pending_decisions.md.
"""

# ── Temporalidades del análisis ────────────────────────────────────────────────

ANALYSIS_TIMEFRAMES = ["mn", "w1", "h4", "h1", "m15", "m1"]  # [CONFIRMED]
ENTRY_TIMEFRAME     = "m15"  # [CONFIRMED] temporalidad de observación y decisión
EXECUTION_TIMEFRAME = "m1"   # [CONFIRMED] reconstrucción de movimientos y SL/TP

# ── BLOQUE 1 — Sesiones operativas ────────────────────────────────────────────

# Zonas horarias IANA (con DST histórico correcto)       [CONFIRMED]
LONDON_TIMEZONE  = "Europe/London"
NEWYORK_TIMEZONE = "America/New_York"

# Ventana 1: London Open / London Killzone               [CONFIRMED PD-001]
# 02:00–05:00 America/New_York (ICT/SMC convention)
LONDON_KILLZONE = {
    "tz":    "America/New_York",
    "start": "02:00",
    "end":   "05:00",
    "label": "london_killzone",
}

# Ventana 2: New York AM Open (principal)                [CONFIRMED PD-001]
# 09:30–11:00 America/New_York
NEWYORK_AM_OPEN = {
    "tz":    "America/New_York",
    "start": "09:30",
    "end":   "11:00",
    "label": "newyork_am_open",
}

# Ventana alternativa: Forex NY AM (para comparación)    [CONFIRMED PD-001]
# 07:00–10:00 America/New_York (algunas metodologías ICT/SMC)
NEWYORK_AM_FOREX_ALT = {
    "tz":    "America/New_York",
    "start": "07:00",
    "end":   "10:00",
    "label": "newyork_am_forex_alt",
}

# Lista ordenada de ventanas operativas activas          [CONFIRMED PD-001]
SESSION_WINDOWS = [LONDON_KILLZONE, NEWYORK_AM_OPEN]
SESSION_WINDOWS_ALL = [LONDON_KILLZONE, NEWYORK_AM_OPEN, NEWYORK_AM_FOREX_ALT]

# ── BLOQUE 2 — Estructura de mercado ──────────────────────────────────────────

# Pivotes de 3 velas (STH/STL)                          [CONFIRMED PD-002]
# Un swing queda confirmado cuando CIERRA la vela posterior (no-lookahead).
SWING_PIVOT_BARS = 1   # velas a cada lado del extremo (3-vela pivot: 1+1+1)

# Jerarquía de swings ICT                               [CONVENTIONAL PD-002]
# STH/STL → ITH/ITL → LTH/LTL
# Un swing intermedio se construye a partir de swings de corto plazo.
# Un swing de largo plazo se construye a partir de swings intermedios.
SWING_HIERARCHY = ["short_term", "intermediate_term", "long_term"]

# BOS: rotura confirmada por CIERRE de vela             [CONFIRMED PD-003]
# Mecha que supera un swing = sweep candidate, NO BOS.
BOS_CLOSE_CONFIRMATION = True

# CHOCH: primer cierre confirmado en dirección contraria [CONVENTIONAL PD-004]
# al swing protegido de la estructura predominante.
# Internal CHOCH ≠ External CHOCH (implementar distinción).
CHOCH_TYPES = ["internal", "external"]

# ── BLOQUE 3 — Displacement / Momentum ────────────────────────────────────────

# displacement_score configurable (no hay umbral fijo aprobado) [PENDING PD-005]
# Se implementa como score multidimensional. El umbral requiere aprobación.
DISPLACEMENT_ATR_PERIOD = 14       # período ATR de referencia para normalización
DISPLACEMENT_THRESHOLD  = None     # [PENDING] umbral sobre score que activa señal

# Order Blocks: última vela contraria antes del impulso [CONFIRMED PD-006]
# Admite también grupo de velas contrarias consecutivas.
OB_LAST_CANDLE   = True   # usar última vela contraria (mínimo)
OB_ALLOW_GROUP   = True   # permitir identificar bloques de varias velas

# ── BLOQUE 4 — Point of Interest (POI) ────────────────────────────────────────

# Tipos de POI activos                                   [CONFIRMED PD-007]
POI_TYPES = ["fvg", "order_block"]

# FVG (Fair Value Gap / Imbalance)                      [CONFIRMED PD-007]
# Bullish FVG: high(candle_1) < low(candle_3)
# Bearish FVG: low(candle_1) > high(candle_3)

# Temporalidades de identificación y refinamiento       [CONFIRMED PD-008/009]
POI_IDENTIFICATION_TF = ["h4", "h1"]   # h4=contexto mayor, h1=principal
POI_REFINEMENT_TF     = ["h1", "m30"]  # refinamiento de la zona original
POI_EXECUTION_TF      = "m15"          # observación y confirmación de entrada

# Estados de un POI                                     [CONFIRMED PD-010]
POI_STATES = ["fresh", "touched", "partially_mitigated", "fully_mitigated", "invalidated"]

# Invalidación: cierre más allá del extremo distal      [CONVENTIONAL PD-010]
# Para OB: close beyond distal extreme.
# Para FVG: fill completo ≠ invalidación de OB asociado.
POI_INVALIDATION_RULE = "close_beyond_distal"

# ── BLOQUE 5 — Liquidez ────────────────────────────────────────────────────────

# Tipos de zonas de liquidez a rastrear                 [CONFIRMED PD-011]
LIQUIDITY_LEVELS = [
    "equal_highs",          # EQH — BSL
    "equal_lows",           # EQL — SSL
    "swing_high",           # BSL
    "swing_low",            # SSL
    "prev_day_high",        # PDH — BSL
    "prev_day_low",         # PDL — SSL
    "prev_week_high",       # PWH — BSL
    "prev_week_low",        # PWL — SSL
    "session_high",         # BSL (máximo de sesión actual)
    "session_low",          # SSL (mínimo de sesión actual)
]

# Detección de equal highs/lows                         [CONVENTIONAL PD-011]
EQUAL_HLS_TOLERANCE_PIPS = 0.5  # umbral provisional para "igual" — ajustar con datos

# Sweep candidate: mecha que supera el nivel            [CONFIRMED PD-012]
# Rejection confirmation: cierre de vuelta al lado contrario
SWEEP_WICK_ONLY   = True  # registrar breach con solo mecha (sin cierre de vuelta)
SWEEP_CLOSE_BACK  = True  # registrar también el cierre de vuelta como confirmación

# ── BLOQUE 6 — Fibonacci ──────────────────────────────────────────────────────

# Niveles activos en la configuración del trader        [CONFIRMED PD-013/014]
FIB_LEVELS = [0.0, 0.5, 0.6, 0.75, 0.9, 1.0]

# Anclaje: impulso alcista → 0%=máximo, 100%=mínimo    [CONFIRMED PD-013]
#          impulso bajista → 0%=mínimo, 100%=máximo
# Se preservan timestamps de anclaje para no-lookahead.

# Zona mínima de entrada                                [CONFIRMED PD-014]
FIB_ENTRY_MIN  = 0.50  # retroceso mínimo para considerar descuento válido
FIB_ENTRY_PREF_LOW  = 0.60  # zona preferida inferior
FIB_ENTRY_PREF_HIGH = 0.70  # zona preferida superior
# 75%-90%: zona de riesgo aumentado (retroceso excesivo)

# ── BLOQUE 7 — Ejecución y gestión de riesgo ──────────────────────────────────

# Modo de entrada                                       [CONFIRMED PD-015]
# Conservative: confirmación al cierre de vela M15, entrada en el siguiente precio.
# Intrabar: solo disponible con datos tick (NO disponibles en este dataset).
ENTRY_MODE = "conservative"  # "conservative" | "intrabar" (intrabar requiere tick data)

# Riesgo por operación                                  [CONFIRMED PD-016]
RISK_PER_TRADE_PCT = 0.01   # ~1% del capital por operación

# SL: más allá de la referencia técnica que invalida la idea [CONFIRMED PD-016]
# No ajustar el SL para obtener un tamaño de lote concreto.

# Take Profit targets                                   [CONFIRMED PD-017]
TP1_R = 2.0   # primer objetivo: 2R (normal)
TP2_R = 3.0   # segundo objetivo: 3R (cuando la estructura/liquidez lo justifica)

# Distribución de posición por TP                       [PENDING PD-017]
TP1_POSITION_PCT = None  # [PENDING] fracción de la posición que se cierra en TP1
TP2_POSITION_PCT = None  # [PENDING] fracción restante que se cierra en TP2

# Gestión de SL                                         [CONFIRMED PD-018]
# Tipo A: mover a breakeven al alcanzar +1R
# Tipo B: mover a breakeven tras consolidación + confirmación estructural
BE_TRIGGER_R = 1.0   # nivel de R para mover BE en tipo A
BE_MODE_A = "at_1R"               # mover al alcanzar +1R
BE_MODE_B = "after_consolidation" # [PENDING] definición exacta de consolidación

# ── BLOQUE 8 — Etiquetado ML ──────────────────────────────────────────────────

# Sistema B: GOOD_SETUP / BAD_SETUP                     [CONFIRMED PD-019]
LABEL_B_TARGET_R    = 2.0    # +2R = objetivo favorable
LABEL_B_STOP_R      = 1.0    # -1R = stop out
LABEL_B_HORIZON_BARS_M15 = 6   # horizonte máximo: 6 velas M15 (90 minutos)
LABEL_B_HORIZON_ALT_M15  = 4   # horizonte alternativo: 4 velas M15 (60 minutos)
# Casos UNRESOLVED: no alcanza ni TP ni SL en el horizonte → excluir del binario

# Reconstrucción de etiquetas con M1 (precisión intrabar)
LABEL_RECONSTRUCTION_TF = "m1"
# Si TP y SL aparecen en la misma vela M1 → marcar como AMBIGUOUS

# Sistema C: BUY / SELL / NO_TRADE                      [CONFIRMED PD-020]
# Universo: todas las barras M15 dentro de las ventanas operativas.
# No limitar al universo del Sistema A.
# El modelo debe poder encontrar patrones que el Sistema A no identifica.
LABEL_C_CLASSES = ["BUY", "SELL", "NO_TRADE"]

# ── BLOQUE 9 — Costes y ejecución (FTMO-like) ─────────────────────────────────

# Comisión                                              [CONFIRMED PD-021]
COMMISSION_USD_PER_LOT = 5.0      # 5 USD/lote (especificación FTMO pública)
# Testar ambas interpretaciones:
COMMISSION_ROUND_TURN = 5.0       # 5 USD lote round-turn
COMMISSION_PER_SIDE   = 5.0       # 5 USD lote por lado (entrada + salida = 10 USD)

# Escenarios de spread (pips)                           [CONFIRMED PD-021]
SPREAD_SCENARIOS_PIPS = [0.1, 0.2, 0.5]
SPREAD_CENTRAL_PIPS   = 0.2       # hipótesis central (NO es spread histórico real)

# Escenarios de slippage (pips)                         [CONFIRMED PD-021]
SLIPPAGE_SCENARIOS_PIPS = [0.0, 0.1, 0.2]
SLIPPAGE_CENTRAL_PIPS   = 0.0     # escenario base optimista

# Contract size FTMO EUR/USD                            [CONFIRMED PD-021]
CONTRACT_SIZE = 100_000   # 100,000 unidades base por lote estándar

# Dirección de ejecución (precio de entrada/salida)     [CONFIRMED PD-021]
# BUY: entrada a ASK (BID + spread), salida a BID.
# SELL: entrada a BID, salida a ASK (BID + spread).
# Con solo BID histórico: aproximar ASK = BID + spread_assumption.

# Swap overnight                                        [CONFIRMED PD-021]
# Duración media de operación ~1h-1.5h → swap overnight improbable.
# Registrar si alguna simulación mantiene posición hasta rollover.
OVERNIGHT_SWAP_EURUSD_LONG_DAILY  = None  # [PENDING] pip/lote cuando se obtenga
OVERNIGHT_SWAP_EURUSD_SHORT_DAILY = None  # [PENDING] pip/lote cuando se obtenga

# ── Máximo de posiciones simultáneas ──────────────────────────────────────────
MAX_CONCURRENT = None  # [PENDING] sin restricción definida por el trader todavía
