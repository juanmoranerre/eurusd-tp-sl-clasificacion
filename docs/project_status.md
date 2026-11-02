# Estado del proyecto — EUR/USD Trading Intelligence System

**Última actualización:** 2026-11-02 (CIERRE V1)
**Rama activa:** `development`
**Último commit:** cierre V1 (ver git log)

---

## Resumen ejecutivo

| Fase | Descripción | Estado |
|------|-------------|--------|
| FASE 0 | Auditoría y correcciones | ✅ COMPLETADA |
| FASE 1 | Data Engineering | ✅ COMPLETADA |
| FASE 2 | Strategy Spec + Feature Engineering | ✅ COMPLETADA |
| FASE 3 | Motor Sistema A + Backtester + Dataset | ✅ COMPLETADA (V1 cerrado) |
| FASE 4 | Etiquetado + Modelo B (filtro setups) | ⬜ PENDIENTE |
| FASE 5 | Modelo C (clasificador M15) | ⬜ PENDIENTE |
| FASE 6 | Comparación A / B / C | ⬜ PENDIENTE |
| FASE 7 | Entrega final | ⬜ PENDIENTE |

---

## FASE 3 — Dataset V1 cerrado definitivamente ✅

### Parámetros vigentes

| Parámetro | Valor | Decisión |
|---|---|---|
| CONF_MIN_BODY_RATIO | 0.0 | P-A (2026-11-02) |
| HTF_FILTER | False | P-B (2026-11-02) |
| SL_BUFFER_PIPS | 0.5 | P-C provisional |
| MIN_RISK_PIPS | 5.0 | DEC-013 |
| fib_min_retracement | 0.50 | DEC-012 |
| horizonte | 90 min | PD-019 |
| TP | 2R | PD-017 |
| BE | tipo A (+1R) | PD-018 |
| spread | 0.2 pips | DEC-015 escenario central |
| total_cost_pips | 0.7 pips | spread+commission |

### Correcciones incorporadas en V1

**C1 — Convención BID-BID:** Eliminado el doble conteo del spread para BUY. P&L calculado BID-a-BID, spread descontado una sola vez. 5 TIME_EXIT BUY corregidos (resultado=0 → resultado=1).

**C2 — Una oportunidad por POI por episodio:** Un POI solo puede generar un setup por episodio continuo de contacto. 96 setups filtrados (58 netos, 38 barras encontraron POI alternativo).

### Resultados del dataset

| Métrica | Valor |
|---|---|
| Setups válidos | **2,642** |
| resultado = 1 | 969 (36.7%) |
| resultado = 0 | 1,673 (63.3%) |
| Excluidos C2_POI_REUSE | 96 |
| Excluidos AMBIGUOUS | 5 |

| Motivo de salida | Count | resultado=1 |
|---|---|---|
| SL | 1,021 | 0% |
| TIME_EXIT | 944 | 65.9% |
| BE | 330 | 0% |
| TP | 347 | 100% |

### Archivos generados

| Archivo | Filas | Columnas |
|---|---|---|
| `eurusd_operaciones.csv` | 2,642 | 17 |
| `eurusd_operaciones_excluidas.csv` | 101 | 16 |
| `results/eurusd_metadata.csv` | 2,642 | 17 (incluye poi_id) |

---

## FASE 0 — Completada ✅

Bug crítico resuelto: parser BI5 tenía HIGH y CLOSE intercambiados.
- Orden incorrecto: 2,488,544 violaciones OHLC (71% del dataset)
- Orden correcto (o,c,l,h): 0 violaciones en 3,510,720 registros activos

Backup incorrecto: `data/processed/eurusd_m1_bid_BACKUP_wrong_ohlc.parquet`
Parquet correcto: `data/processed/eurusd_m1_bid.parquet`

---

## FASE 1 — Completada ✅

Dataset M1: **4,098,240 registros**, período 2019-01-01 → 2026-10-16, 0 errores.

| TF | Barras | Archivo |
|---|---|---|
| M15 | 273,216 | eurusd_m15_bid.parquet |
| H1 | 68,304 | eurusd_h1_bid.parquet |
| H4 | 17,076 | eurusd_h4_bid.parquet |
| D1 | 2,846 | eurusd_d1_bid.parquet |
| W1 | 407 | eurusd_w1_bid.parquet |
| MN | 94 | eurusd_mn_bid.parquet |

---

## FASE 2 — Completada ✅

Todas las PD-001 a PD-021 respondidas. Registradas en `docs/decisions_log.md` (DEC-006 a DEC-018).

Sub-decisiones pendientes para V2:

| ID | Descripción |
|----|-------------|
| PD-005b | Umbral numérico del displacement_score |
| PD-005c | Tamaño máximo del grupo de velas OB |
| PD-017b | % de cierre parcial en TP1 / TP2 |
| PD-018b | Definición matemática de consolidación (BE tipo B) |
| PD-021b | Comisión FTMO — round-turn vs por-lado |
| PD-021c | Swap overnight EUR/USD |

---

## Tests

**381/381 pasando** (verificado 2026-11-02 tras cierre V1).

| Archivo | Tests |
|---|---|
| test_parser_bi5.py | 40 |
| test_loader.py | 28 |
| test_resampler.py | 43 |
| test_auxiliary.py | 81 |
| test_sessions.py | 52 |
| test_structure.py | 42 |
| test_poi.py | 22 |
| test_liquidity.py | 21 |
| test_fibonacci.py | 22 |
| test_momentum.py | 30 |

---

## Documentación V1

| Documento | Estado |
|---|---|
| `docs/dataset_creation_v1.md` | ✅ nuevo |
| `docs/strategy_v1_explained.md` | ✅ nuevo |
| `docs/data_dictionary_v1.md` | ✅ nuevo |
| `docs/reproducibility_v1.md` | ✅ nuevo |
| `docs/presentation_v1_brief.md` | ✅ nuevo |
| `docs/handoff_companero.md` | ✅ nuevo |
| `docs/decisions_log.md` | ✅ actualizado (DEC-017, DEC-018) |
| `docs/notebook_integration_notes.md` | ✅ actualizado |
| `docs/roadmap_v2.md` | ✅ actualizado |
| `docs/project_status.md` | ✅ este archivo |

---

## Próximos pasos

### Inmediatos
1. Ejecutar `notebooks/Proyecto_02.ipynb` con el nuevo dataset V1
2. Validar resultados del notebook (Macro F1 > 0.5?)
3. Push a remote `development` cuando el trader revise

### FASE 4 — Sistema B (filtro ML)
- Input: `eurusd_operaciones.csv` (dataset V1)
- Objetivo: seleccionar setups con mayor probabilidad de éxito
- Walk-forward: train 2020-2024, test 2025-2026

### FASE 5 — Sistema C (clasificador M15)
- Input: todas las barras M15 en ventanas operativas
- Output: BUY / SELL / NO_TRADE por barra

### V2 del dataset
Ver `docs/roadmap_v2.md` para las 12+ mejoras planificadas.

---

## Restricciones permanentes

- Nunca trabajar directamente en `main`
- No subir datos BI5/Parquet, credenciales, entornos virtuales ni modelos pesados
- No declarar rentable una estrategia sin evidencia fuera de muestra
- No inventar parámetros para llenar huecos PENDING
