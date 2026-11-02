"""
strategy_config.py — Parámetros de la estrategia de trading

IMPORTANTE:
  Los valores marcados con # [PENDING] NO están confirmados por el trader.
  No se deben usar como parámetros definitivos hasta ser aprobados.
  Ver docs/pending_decisions.md para la lista completa de decisiones pendientes.

Los valores marcados con # [CONFIRMED] han sido aprobados explícitamente.
"""

# ── Temporalidades del análisis [CONFIRMED] ───────────────────────────────────
# Jerarquía de análisis multitemporal (sección 2.1 del master prompt)
ANALYSIS_TIMEFRAMES = ["mn", "w1", "h4", "h1", "m15", "m1"]
ENTRY_TIMEFRAME     = "m15"   # temporalidad principal de observación y decisión
EXECUTION_TIMEFRAME = "m1"    # reconstrucción de movimientos y evaluación SL/TP

# ── Sesiones operativas [PENDING] ────────────────────────────────────────────
# Las horas exactas y duraciones de las ventanas deben confirmarse.
# Se usan las zonas horarias correctas (con DST) según sección 2.10.
# PENDIENTE: horas de inicio/fin de cada sesión.
LONDON_TIMEZONE  = "Europe/London"    # [CONFIRMED] timezone
NEWYORK_TIMEZONE = "America/New_York" # [CONFIRMED] timezone

LONDON_OPEN_HOUR   = None  # [PENDING] hora local de apertura de Londres
LONDON_CLOSE_HOUR  = None  # [PENDING] hora local de cierre de la ventana
NEWYORK_OPEN_HOUR  = None  # [PENDING] hora local de apertura de Nueva York
NEWYORK_CLOSE_HOUR = None  # [PENDING] hora local de cierre de la ventana

# ── Gestión de posición [PENDING] ─────────────────────────────────────────────
# Estos parámetros deben aprobarse antes de generar etiquetas o backtest.
RISK_PER_TRADE_PCT = None   # [PENDING] % del capital en riesgo por operación
MAX_CONCURRENT     = None   # [PENDING] máximo de posiciones simultáneas

# ── Fibonacci [PENDING] ───────────────────────────────────────────────────────
# Niveles a representar (referencia: sección 2.9 del master prompt)
# El anclaje exacto, puntos de swing y zonas de entrada deben confirmarse.
FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0]  # [CONFIRMED] niveles estándar
FIB_ENTRY_ZONE_LOW  = None   # [PENDING] nivel inferior de la zona de entrada
FIB_ENTRY_ZONE_HIGH = None   # [PENDING] nivel superior de la zona de entrada

# ── Parámetros de estructura de mercado [PENDING] ─────────────────────────────
# Todos los umbrales de momentum, swing, BOS, CHOCH deben confirmarse.
SWING_LOOKBACK        = None  # [PENDING] velas de lookback para detectar swings
MOMENTUM_THRESHOLD    = None  # [PENDING] desplazamiento mínimo para considerar impulso
DISPLACEMENT_FACTOR   = None  # [PENDING] factor multiplicador de ATR para displacement
ATR_PERIOD            = None  # [PENDING] período ATR para normalización de volatilidad

# ── Parámetros de POI [PENDING] ──────────────────────────────────────────────
POI_MIN_CANDLES       = None  # [PENDING] mínimo de velas contrarias para formar POI
POI_MAX_TOUCHES       = None  # [PENDING] máximo de toques antes de invalidación
POI_INVALIDATION_PCT  = None  # [PENDING] % de penetración que invalida la zona

# ── Costes y ejecución [PENDING] ─────────────────────────────────────────────
# Los datos son BID. No existe spread histórico verificable.
# Los escenarios de coste deben aprobarse explícitamente.
SPREAD_ASSUMPTION_PIPS = None  # [PENDING] spread supuesto en pips
SLIPPAGE_PIPS          = None  # [PENDING] slippage supuesto en pips
COMMISSION_USD_LOT     = None  # [PENDING] comisión por lote estándar
