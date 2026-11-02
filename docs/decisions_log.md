# Log de decisiones técnicas

**Formato:** `[FECHA] — ID — Decisión tomada → Consecuencias`

---

## 2026-11-01

### DEC-001 — Corrección del orden de campos BI5
**Decisión:** El formato Dukascopy BI5 almacena los campos en el orden `(ts, open, close, low, high, volume)`, no `(ts, open, high, low, close, volume)`.  
**Evidencia:**
- Con el orden incorrecto (o,h,l,c): 1,330 de 1,440 registros del 2019-01-03 tenían `close > high`.
- Con el orden correcto (o,c,l,h): 0 violaciones OHLC en 3,510,720 registros activos del dataset completo.
- El test anterior (`test_bid_data_can_have_close_above_high`) fue modificado para aceptar este comportamiento erróneo.
**Acción:** Corregido `_RECORD_DTYPE` en `src/data/parser_bi5.py`. Backup del parquet incorrecto como `eurusd_m1_bid_BACKUP_wrong_ohlc.parquet`. Parquet regenerado con datos correctos.  
**Consecuencias:** Todos los valores de `KNOWN_HIGH` y `KNOWN_CLOSE` en tests y scripts actualizados. 68 tests pasan con los invariantes OHLC completos.

### DEC-002 — Timestamp BI5 en segundos (no milisegundos)
**Decisión:** El campo `ts` del BI5 de Dukascopy M1 contiene **segundos** desde medianoche UTC (0, 60, 120, ..., 86340), no milisegundos.  
**Evidencia:** Los timestamps 0, 60, 120, ... corresponden a 00:00, 00:01, 00:02, ... y el último es 86340 = 23×3600+59×60.  
**Consecuencias:** La reconstrucción de datetime usa `pd.to_timedelta(arr["ts_s"], unit="s")`. Confirmado en test `test_second_record_is_60s_later`.

### DEC-003 — División temporal del proyecto
**Decisión:** División temporal aprobada en el master prompt (sección 12):
- 2019: calentamiento (warmup)
- 2020–2024: entrenamiento
- 2025: validación y optimización  
- 2026: test final (hasta 2026-10-16)
**Consecuencias:** Ninguna división aleatoria. Walk-forward validation dentro del período de entrenamiento.

### DEC-004 — Alineación temporal de temporalidades superiores
**Decisión:** Todas las temporalidades superiores (M15, H1, H4, D1, W1, MN) se alinean a medianoche UTC con `label='left'` (etiqueta = inicio del período).  
**Razonamiento:** La etiqueta de inicio del período garantiza que no se usa información futura: el dato de la barra solo está disponible cuando cierra, es decir, al inicio del período siguiente.  
**Consecuencias:** W1 usa `1W` (pandas: semana ending Sunday, label=Monday), MN usa `1ME` (month-end).

### DEC-005 — Métrica de referencia principal del modelo
**Decisión:** Macro F1 como métrica de referencia principal para la evaluación de modelos de clasificación.  
**Razonamiento:** Equilibra el rendimiento entre clases desequilibradas (BUY, SELL, NO_TRADE) sin penalizar desproporcionalmente la clase mayoritaria.  
**Consecuencias:** Optuna optimizará sobre Macro F1 durante el tuning. AUC-ROC OvR y PR-AUC como métricas secundarias.

---

*Las decisiones pendientes de aprobación del trader están en `docs/pending_decisions.md`.*

---

## DEC-006: Sesiones operativas (PD-001 resuelto — 2026-11-01)

**Decisión:** London Killzone = 02:00–05:00 America/New_York. NY AM Open = 09:30–11:00 America/New_York. Ventana alternativa Forex NY AM = 07:00–10:00 America/New_York.
**Zona horaria:** America/New_York (IANA) con conversión histórica correcta incluyendo DST. No usar UTC fijo.
**Consecuencia:** sessions.py usa pytz/zoneinfo para conversiones. Se registra hora UTC y hora local.

---

## DEC-007: Estructura de mercado (PD-002/003/004 resueltos — 2026-11-01)

**Swings (PD-002):** Pivote de 3 velas (1 vela a cada lado). Jerarquía STH/STL → ITH/ITL → LTH/LTL. Un swing se confirma cuando CIERRA la vela posterior (no lookahead).
**BOS (PD-003):** Confirmado por CIERRE de vela por encima (alcista) / debajo (bajista) del swing estructural relevante. Mecha que supera un nivel = sweep candidate, NO BOS.
**CHOCH (PD-004):** Primer cierre confirmado en dirección contraria al swing protegido de la estructura predominante. Distinguir: CHOCH interno (dentro del retroceso), CHOCH externo (contra estructura HTF). Un CHOCH no implica reversión definitiva sin displacement + BOS en nueva dirección.
**Consecuencia:** structure.py implementa jerarquía de swings, BOS y CHOCH con distinción interna/externa.

---

## DEC-008: Displacement (PD-005 parcialmente resuelto — 2026-11-01)

**Decisión:** No hay umbral fijo. Se implementa displacement_score multidimensional (cuerpo, rango/ATR, posición cierre, FVG asociado, BOS, velocidad). El umbral que activa señal queda PENDING.
**Consecuencia:** momentum.py calcula score; el trader debe aprobar el umbral antes de usar en backtest.

---

## DEC-009: Order Blocks (PD-006 resuelto — 2026-11-01)

**Decisión:** OB = última vela contraria antes del impulso relevante que produce BOS/CHOCH. También se admite grupo de velas contrarias consecutivas.
**Consecuencia:** poi.py identifica OB como última vela contraria + posible bloque.

---

## DEC-010: POI — tipos, temporalidades, estados (PD-007/008/009/010 resueltos — 2026-11-01)

**Tipos (PD-007):** Ambos activos: FVG (imbalance 3 velas) y Order Block. Son independientes.
  - FVG alcista: high(c1) < low(c3). FVG bajista: low(c1) > high(c3).
  - OB: última vela contraria (o grupo) antes de impulso relevante.
**Temporalidades (PD-008):** H4=contexto, H1=identificación principal, H1/M30=refinamiento, M15=ejecución.
**Refinamiento (PD-009):** H4→H1→M30→M15 (no obligatorio pasar por todos).
**Estados (PD-010):** fresh → touched → partially_mitigated → fully_mitigated → invalidated.
  - Invalidación OB: close beyond distal extreme. FVG fill completo ≠ invalidación de OB asociado.
**Consecuencia:** poi.py implementa ambos tipos con tracking de estados.

---

## DEC-011: Liquidez (PD-011/012 resueltos — 2026-11-01)

**Niveles (PD-011):** BSL (buy-side): equal highs, swing highs, prev day/week high, session high. SSL (sell-side): equal lows, swing lows, prev day/week low, session low. Son zonas inferidas de acción del precio, no órdenes reales.
**Sweep (PD-012):** Dos características separadas: (1) breach candidate = mecha que supera el nivel; (2) rejection confirmation = cierre de vuelta al lado contrario. Ambas se registran, no se fusionan.
**Consecuencia:** liquidity.py rastrea ambos eventos por separado.

---

## DEC-012: Fibonacci (PD-013/014 resueltos — 2026-11-01)

**Anclaje (PD-013):** Último impulso relevante. Alcista: 0%=máximo, 100%=mínimo. Bajista: 0%=mínimo, 100%=máximo.
**Niveles activos (PD-014):** 0%, 50%, 60%, 75%, 90%, 100%.
**Zona preferida:** 50%–70% (mínimo 50%, preferida 60%–70%). 75%–90% = zona de riesgo. 100% = origen del impulso.
**Consecuencia:** fibonacci.py calcula niveles con timestamps de anclaje preservados para no-lookahead.

---

## DEC-013: Ejecución y gestión de riesgo (PD-015/016/017/018 resueltos — 2026-11-01)

**Entrada (PD-015):** Modo conservador (disponible): cierre de vela M15 + entrada al precio siguiente. Modo intrabar: requiere tick data (NO disponible con BI5 M1).
**SL (PD-016):** Más allá de la referencia técnica que invalida la idea (POI/estructura). Riesgo: ~1% de la cuenta.
**TP (PD-017):** TP1=2R (normal), TP2=3R (si la estructura lo justifica). Porcentajes de cierre parcial: PENDING.
**BE (PD-018):** Tipo A = breakeven al +1R. Tipo B = breakeven tras consolidación (definición de consolidación: PENDING).
**Consecuencia:** backtester implementa ambos modos de BE. TP percentages configurables en None hasta aprobación.

---

## DEC-014: Etiquetado ML (PD-019/020 resueltos — 2026-11-01)

**Sistema B (PD-019):** GOOD_SETUP = +2R antes de -1R dentro de 6 velas M15 (90 min). BAD_SETUP = -1R antes de +2R. UNRESOLVED = ni TP ni SL en el horizonte (excluir del binario). Horizonte alternativo: 4 barras M15 (60 min). Reconstrucción con M1. Misma vela M1 con TP y SL → AMBIGUOUS.
**Sistema C (PD-020):** Universo = todas las barras M15 en ventanas operativas (NO solo setups de Sistema A). Etiquetas: BUY / SELL / NO_TRADE. El modelo puede encontrar patrones que el Sistema A no identifica.
**Consecuencia:** labeler.py generará etiquetas con estos parámetros. NO_TRADE no se asigna automáticamente.

---

## DEC-015: Costes (PD-021 resuelto — 2026-11-01)

**Comisión:** 5 USD/lote (especificación FTMO pública). Testar: round-turn vs por-lado.
**Spread:** Escenarios: 0.1, 0.2, 0.5 pips. Hipótesis central: 0.2 pips (NO spread histórico real).
**Slippage:** Escenarios: 0.0, 0.1, 0.2 pips. Base: 0.0 (optimista).
**Dirección BUY:** entrada a ASK (BID+spread), salida a BID. SELL: entrada a BID, salida a ASK.
**Swap:** improbable (<90 min/operación). Registrar si aparece.
**Consecuencia:** backtester implementa CostModel parametrizable con los escenarios definidos.
