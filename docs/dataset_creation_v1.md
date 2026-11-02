# Dataset Creation V1 — Proceso y decisiones

**Versión:** V1 (cierre definitivo)
**Fecha:** 2026-11-02
**Período:** 2020-01-01 → 2026-10-16
**Resultado:** 2,642 setups válidos

---

## 1. Fuentes de datos

| Temporalidad | Filas | Archivo |
|---|---|---|
| M1 (bid) | 3,572,761 | `data/processed/eurusd_m1_bid.parquet` |
| M15 | 273,121 | `data/processed/eurusd_m15_bid.parquet` |
| H1 | 68,253 | `data/processed/eurusd_h1_bid.parquet` |

**Origen:** Dukascopy BI5 (BID only). Bug crítico corregido en FASE 0: el parser asignaba HIGH y CLOSE intercambiados. El parquet incorrecto está respaldado como `eurusd_m1_bid_BACKUP_wrong_ohlc.parquet`.

**Warmup:** Los datos de detección empiezan 3 meses antes de 2020-01-01 (2019-10-01) para que las features (ATR14, estructura M15, POIs creados antes del período) estén disponibles el primer día de operación.

---

## 2. Pipeline de generación

```
M15 + H1 → build_m15_features() → m15_feat (con estructura, POIs, sesiones, ATR, etc.)
                                 ↓
                         detect_setups()
                                 ↓
                    setups_df (2,647 candidatos)
                    c2_excluded_df (96 filtrados C2)
                                 ↓
                        _simulate_all() sobre M1
                                 ↓
                     _build_outputs()
                    /          |           \
          CSV (2,642)    meta (2,642)   excluidos (101)
```

Script: `python scripts/generate_dataset.py`
Tiempo de ejecución: ~570s (detección M15 dominante ~553s)

---

## 3. Parámetros vigentes V1

| Parámetro | Valor | Decisión | Estado |
|---|---|---|---|
| CONF_MIN_BODY_RATIO | 0.0 | P-A (2026-11-02) | Definitivo V1 |
| HTF_FILTER | False | P-B (2026-11-02) | Definitivo V1 |
| SL_BUFFER_PIPS | 0.5 | P-C (2026-11-02) | Provisional |
| MIN_RISK_PIPS | 5.0 | DEC-013 | Definitivo V1 |
| fib_min_retracement | 0.50 | DEC-012 | Definitivo V1 |
| horizonte | 90 min | PD-019 | Definitivo V1 |
| TP | 2R | PD-017 | Definitivo V1 |
| BE trigger | +1R | PD-018 (tipo A) | Definitivo V1 |

---

## 4. Correcciones incorporadas en V1

### C1 — Convención BID-BID (doble conteo del spread)

**Problema:** Para trades BUY, `trade_simulator.py` computaba `gross_pips` usando `entry_ask = entry_bid + spread` como precio de entrada, y luego `net_pips = gross_pips − total_cost_pips`. Como `total_cost_pips` ya incluye el spread (0.2 pips), se descontaba el spread dos veces en los trades BUY.

**Efecto antes de corrección:** net_pips de BUY era 0.2 pips más pesimista de lo correcto. 5 TIME_EXIT pasaron de resultado=0 a resultado=1 tras la corrección.

**Corrección:** Todo el P&L se calcula BID-a-BID (`gross_pips = (exit_bid − entry_bid) / PIP` para BUY). El coste total se descuenta una sola vez via `total_cost_pips = spread + slippage×2 + commission = 0.7 pips`.

**Limitación:** Los datos Dukascopy son BID-only. En una cuenta real, la entrada BUY se ejecuta a ASK (BID + spread) y las activaciones de SL/TP también dependen del spread. Esta diferencia (≤ 0.2 pips) es inferior a la incertidumbre del propio supuesto de spread.

### C2 — Una oportunidad por POI por episodio continuo

**Problema:** Un POI en estado TOUCHED podía generar un setup en cada barra M15 consecutiva mientras el precio permanecía en contacto con la zona, generando múltiples entradas idénticas desde el mismo POI en el mismo retroceso.

**Regla:** Un POI solo puede generar un setup por episodio continuo de contacto. Un nuevo episodio comienza cuando el precio sale completamente de la zona durante ≥1 barra M15:
- POI alcista: `bar_low > max(proximal, distal)` → precio sobre la zona → nuevo episodio
- POI bajista: `bar_high < min(proximal, distal)` → precio bajo la zona → nuevo episodio

**Efecto:** 96 setups filtrados por C2. Cuando C2 bloquea un POI, el detector continúa al siguiente POI activo en la misma barra. 58 setups netos eliminados del dataset final (38 barras encontraron un POI alternativo válido).

**Implementación:** Campos `poi_id`, `episode_count`, `last_setup_episode` añadidos al dataclass `POI`. Tracking en `detect_setups` y `_pois_from_features` de `setup_detector.py`.

---

## 5. Distribución del dataset resultante

| Métrica | Valor |
|---|---|
| Setups válidos | 2,642 |
| resultado = 1 (net > 0) | 969 (36.7%) |
| resultado = 0 (net ≤ 0) | 1,673 (63.3%) |
| Excluidos C2_POI_REUSE | 96 |
| Excluidos AMBIGUOUS | 5 |

| Motivo de salida | Count | resultado=1 |
|---|---|---|
| SL | 1,021 | 0 (0%) |
| TIME_EXIT | 944 | 622 (65.9%) |
| BE | 330 | 0 (0%) |
| TP | 347 | 347 (100%) |

| Año | Setups | resultado=1 |
|---|---|---|
| 2020 | 410 | 145 (35.4%) |
| 2021 | 398 | 158 (39.7%) |
| 2022 | 408 | 144 (35.3%) |
| 2023 | 394 | 136 (34.5%) |
| 2024 | 372 | 145 (39.0%) |
| 2025 | 373 | 147 (39.4%) |
| 2026 | 287 | 94 (32.8%) |

---

## 6. Archivos generados

| Archivo | Filas | Columnas | Descripción |
|---|---|---|---|
| `eurusd_operaciones.csv` | 2,642 | 17 | Dataset principal (sin leakage post-entrada) |
| `eurusd_operaciones_excluidas.csv` | 101 | 16 | Setups excluidos (96 C2 + 5 AMBIGUOUS) |
| `results/eurusd_metadata.csv` | 2,642 | 17 | Metadatos completos por trade (incluyendo poi_id) |

---

## 7. Propiedades estadísticas conocidas

**Horizontes solapados:** El auditor detectó 471 pares de setups con horizontes temporales que se superponen (simultáneos dentro de la ventana de 90 min). Esto es una propiedad del dataset, no un error. Los setups en el mismo período pueden competir por liquidez en un entorno real. No se eliminaron porque el modelo aprende sobre distribuciones, no sobre secuencias de ejecución.

**Sesgos del período:** 2022 y 2023 muestran win rate ligeramente más bajo (35%). Posible relación con la volatilidad del ciclo de subidas de tipos del BCE/Fed. No hay evidencia suficiente para separar este efecto del ruido estadístico con 400 setups/año.

**Desequilibrio de clases:** 63.3% / 36.7%. Moderado. En el notebook, considerar `class_weight='balanced'` o métricas que no asuman equiprobabilidad.
