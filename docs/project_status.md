# Estado del proyecto — EUR/USD Trading Intelligence System

**Última actualización:** 2026-11-02
**Rama activa:** `development`
**Último commit:** `9ee49e3` — feat(fase2): feature engineering completa

---

## Resumen ejecutivo

| Fase | Descripción | Estado |
|------|-------------|--------|
| FASE 0 | Auditoría y correcciones | ✅ COMPLETADA |
| FASE 1 | Data Engineering | ✅ COMPLETADA |
| FASE 2 | Strategy Spec + Feature Engineering | ✅ COMPLETADA |
| FASE 3 | Motor determinista Sistema A + Backtester | ⬜ PENDIENTE |
| FASE 4 | Etiquetado + Modelo B (filtro setups) | ⬜ PENDIENTE |
| FASE 5 | Modelo C (clasificador M15) | ⬜ PENDIENTE |
| FASE 6 | Comparación A / B / C | ⬜ PENDIENTE |
| FASE 7 | Entrega final | ⬜ PENDIENTE |

---

## FASE 0 — Completada ✅

### Bug crítico resuelto
- Parser BI5 tenía campos `high` y `close` intercambiados.
  - Orden incorrecto (o,h,l,c): 2,488,544 violaciones OHLC (71% del dataset).
  - Orden correcto (o,c,l,h): 0 violaciones en 3,510,720 registros activos.
- Backup: `data/processed/eurusd_m1_bid_BACKUP_wrong_ohlc.parquet`
- Parquet correcto: `data/processed/eurusd_m1_bid.parquet`

### Infraestructura
- `config/settings.py` — configuración global y divisiones temporales
- `config/data_config.py` — rutas de archivos
- `config/strategy_config.py` — parámetros de estrategia (CONFIRMED + PENDING)
- `config/model_config.py` — configuración de modelos ML
- Git: rama `development`, remote `origin` configurado

---

## FASE 1 — Completada ✅

### Dataset M1
- **4,098,240 registros** (2,846 días × 1,440 min/día)
- Período: 2019-01-01 → 2026-10-16
- 0 errores de carga, 0 archivos corruptos

### Multi-temporalidades

| TF  | Barras | Activas | Planas | Archivo |
|-----|--------|---------|--------|---------|
| M15 | 273,216 | 234,048 | 39,168 | eurusd_m15_bid.parquet |
| H1  | 68,304  | 58,512  | 9,792  | eurusd_h1_bid.parquet |
| H4  | 17,076  | 14,628  | 2,448  | eurusd_h4_bid.parquet |
| D1  | 2,846   | 2,438   | 408    | eurusd_d1_bid.parquet |
| W1  | 407     | 407     | 0      | eurusd_w1_bid.parquet |
| MN  | 94      | 94      | 0      | eurusd_mn_bid.parquet |

0 violaciones OHLC en todas las temporalidades.

---

## FASE 2 — Completada ✅

### Decisiones del trader (2026-11-01)
Todas las PD-001 a PD-021 respondidas. Registradas en `docs/decisions_log.md` (DEC-006 a DEC-015) y `docs/strategy_specification.md`.

Sub-decisiones que quedan pendientes:

| ID | Descripción | Bloqueante para |
|----|-------------|-----------------|
| PD-005b | Umbral numérico del displacement_score | Señales de backtest |
| PD-005c | Tamaño máximo del grupo de velas OB | POI — OB bloques |
| PD-017b | % de cierre parcial en TP1 / TP2 | Backtester |
| PD-018b | Definición matemática de "consolidación" (BE tipo B) | Backtester |
| PD-021b | Comisión FTMO — round-turn vs por-lado | Costes |
| PD-021c | Swap overnight EUR/USD | Costes (baja prioridad) |

### Módulos de features implementados

| Módulo | Archivo | Descripción |
|--------|---------|-------------|
| Auxiliares | `src/features/auxiliary.py` | ATR, EMA, RSI, returns, candle features |
| Sesiones | `src/features/sessions.py` | Filtros London KZ / NY AM con DST |
| Estructura | `src/features/structure.py` | Swings STH→LTH, BOS, CHOCH |
| POI | `src/features/poi.py` | FVG, Order Blocks, tracking de estados |
| Liquidez | `src/features/liquidity.py` | PDH/PDL, PWH/PWL, EQH/EQL, sweeps |
| Fibonacci | `src/features/fibonacci.py` | FibSet, niveles, zonas de entrada |
| Momentum | `src/features/momentum.py` | displacement_score [0,1] |

---

## Tests

| Archivo de test | Tests | Estado | Módulo |
|-----------------|-------|--------|--------|
| test_parser_bi5.py | 68 | ✅ 68/68 | src/data/parser_bi5.py |
| test_loader.py | 28 | ✅ 28/28 | src/data/loader.py |
| test_resampler.py | 43 | ✅ 43/43 | src/data/resampler.py |
| test_auxiliary.py | 81 | ✅ 81/81 | src/features/auxiliary.py |
| test_sessions.py | 52 | ✅ 52/52 | src/features/sessions.py |
| test_structure.py | 42 | ✅ 42/42 | src/features/structure.py |
| test_poi.py | 22 | ✅ 22/22 | src/features/poi.py |
| test_liquidity.py | 19 | ✅ 19/19 | src/features/liquidity.py |
| test_fibonacci.py | 22 | ✅ 22/22 | src/features/fibonacci.py |
| test_momentum.py | 30 | ✅ 30/30 | src/features/momentum.py |
| **TOTAL** | **407** | **✅ 407/407** | |

---

## Historial de commits (rama development)

| Commit | Descripción |
|--------|-------------|
| `9ee49e3` | feat(fase2): feature engineering completa — sessions, structure, POI, liquidity, fibonacci, momentum |
| `95235ec` | feat(features): auxiliary.py — ATR, EMA, RSI, retornos, volatilidad, candle features |
| `503a05b` | feat: FASE 0+1 — infraestructura completa, parser corregido, multi-TF |

---

## Estructura de archivos actual

```
proyecto final lae/
├── config/
│   ├── settings.py          ✅ divisiones temporales, ruta raíz
│   ├── data_config.py       ✅ rutas de parquets
│   ├── strategy_config.py   ✅ todos los parámetros FASE 2 (PENDING=None)
│   └── model_config.py      ✅ configuración ML
├── src/
│   ├── data/
│   │   ├── parser_bi5.py    ✅ bug OHLC corregido
│   │   ├── loader.py        ✅
│   │   └── resampler.py     ✅ M15/H1/H4/D1/W1/MN con label='left'
│   ├── features/
│   │   ├── auxiliary.py     ✅ ATR, EMA, RSI, candle
│   │   ├── sessions.py      ✅ London KZ / NY AM / Alt con DST
│   │   ├── structure.py     ✅ STH/ITH/LTH, BOS, CHOCH
│   │   ├── poi.py           ✅ FVG, OB, estados
│   │   ├── liquidity.py     ✅ PDH/PDL, EQH/EQL, sweeps
│   │   ├── fibonacci.py     ✅ FibSet, zonas
│   │   └── momentum.py      ✅ displacement_score
│   ├── strategy/            ⬜ Motor Sistema A (FASE 3)
│   ├── backtesting/         ⬜ Backtester + CostModel (FASE 3)
│   ├── models/              ⬜ Labeler + Trainer + Predictor (FASE 4/5)
│   ├── evaluation/          ⬜ Walk-forward, métricas (FASE 6)
│   └── visualization/       ⬜ Gráficas (FASE 7)
├── tests/
│   ├── test_parser_bi5.py   ✅ 68 tests
│   ├── test_loader.py       ✅ 28 tests
│   ├── test_resampler.py    ✅ 43 tests
│   ├── test_auxiliary.py    ✅ 81 tests
│   ├── test_sessions.py     ✅ 52 tests
│   ├── test_structure.py    ✅ 42 tests
│   ├── test_poi.py          ✅ 22 tests
│   ├── test_liquidity.py    ✅ 19 tests
│   ├── test_fibonacci.py    ✅ 22 tests
│   └── test_momentum.py     ✅ 30 tests
├── scripts/
│   ├── build_dataset.py     ✅
│   └── build_multitf.py     ✅
├── docs/
│   ├── strategy_specification.md  ✅ completo con todas las decisiones
│   ├── decisions_log.md           ✅ DEC-001 a DEC-015
│   ├── pending_decisions.md       ✅ 6 sub-decisiones pendientes
│   ├── project_status.md          ✅ este archivo
│   ├── architecture.md            ✅
│   └── data_dictionary.md         ✅
├── data/
│   ├── raw/m1/              ✅ 2,846 archivos BI5 (no modificar)
│   └── processed/           ✅ M1 + M15/H1/H4/D1/W1/MN parquets
└── results/                 ⬜ vacío hasta FASE 3+
```

---

## V1 vs V2 — Alcance del entregable

### V1 — Entregable académico (objetivo actual)

Genera `eurusd_operaciones.csv` con una fila por setup detectado, listo para `notebooks/Proyecto_02.ipynb`.

**Columnas obligatorias del notebook:**
`fecha`, `direccion`, `sesion`, `cambio_estructura`, `atr`, `volatilidad`, `volumen_rel`, `distancia_estructura`, `resultado`

**Columnas adicionales de features pre-entrada** (se convierten en predictores automáticamente por el notebook).

**Restricciones V1:**
- Sin salidas parciales (sin TP1/TP2 con porcentajes)
- Sin BE tipo B (consolidación no definida)
- Sin umbral de displacement_score (PD-005b pendiente)
- Sin OB multi-candle (PD-005c pendiente)
- Entrada conservadora: cierre M15 → apertura siguiente vela
- TP = 2R fijo, BE tipo A (+1R), tiempo límite = 6 barras M15 (90 min)
- Costes: spread central 0.2 pips, slippage 0.0, comisión round-turn

**Decisiones provisionales pendientes de confirmación:**
- Confirmación de vela en POI: cierre en dirección de la operación
- Alineación HTF: solo operar cuando H1 structure_bias coincide con dirección
- Buffer SL más allá del distal: provisional 0.5 pips

### V2 — Sistema completo (roadmap)

Ver `docs/roadmap_v2.md` — 12 funcionalidades detalladas. Ninguna se descarta.

---

## Integración con el notebook académico

**Archivo:** `notebooks/Proyecto_02.ipynb` (rama `feature/notebook`)
**Lee:** `eurusd_operaciones.csv` desde el directorio de trabajo
**Proceso:**
1. `resultado` → replace `{"TP": 1, "SL": 0}` → target binario
2. `direccion` → replace `{"compra": 1, "venta": 0}`
3. `sesion` / `cambio_estructura` → pd.get_dummies (one-hot)
4. `fecha` → eliminar antes de X/y split
5. Todas las columnas restantes → features numéricas (pd.astype(float))
6. KFold(n_splits=10, shuffle=False)
7. Modelos: Logistic Regression, SVM RBF, MLP (GP Bayesian opt, 25 iter)
8. Métrica: ROC-AUC

**CRÍTICO:** ninguna columna post-entrada (pnl_pips, exit_time, exit_price, etc.) puede estar en el CSV principal — causaría data leakage.

---

## Próximos pasos

### FASE 3 — Motor Sistema A + Backtester

**Módulos a implementar:**
- `src/strategy/context.py` — sesgo HTF desde H1 structure_bias
- `src/strategy/setup_detector.py` — detección de setups M15 con POI + sesión + confirmación
- `src/backtesting/cost_model.py` — spread, slippage, comisión, escenarios
- `src/backtesting/trade_simulator.py` — simulación M1, TP/SL/BE/TIME_EXIT
- `src/features/feature_builder.py` — todas las features pre-entrada por setup
- `scripts/generate_dataset.py` — orquestación → `eurusd_operaciones.csv`

**Confirmaciones pendientes antes de implementar el setup_detector:**
1. ¿Cuerpo mínimo de la vela de confirmación en POI? (provisional: body/range ≥ 20%)
2. ¿Filtro H1 obligatorio o registrar como feature? (provisional: obligatorio)
3. ¿Buffer SL más allá del distal? (provisional: 0.5 pips)

### Restricciones permanentes

- Nunca trabajar directamente en `main`.
- No subir datos BI5/Parquet, credenciales, entornos virtuales ni modelos pesados.
- No declarar rentable una estrategia sin evidencia fuera de muestra.
- No inventar parámetros para llenar huecos PENDING.
