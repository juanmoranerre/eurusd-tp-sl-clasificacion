# Roadmap Versión 2 — Funcionalidades pospuestas

**Última actualización:** 2026-11-02 (cierre V1)
**Propósito:** Documentar todo lo que NO se implementa en la Versión 1 (primer entregable académico) pero que forma parte de la estrategia completa o puede mejorarla en el futuro.

**Estado V1:** Dataset cerrado definitivamente con 2,642 setups. Las correcciones C1 (BID-BID) y C2 (unicidad POI por episodio) fueron incorporadas antes del cierre.

Nada aquí se descarta. Cada entrada tiene: qué es, por qué se pospone, qué hace falta para implementarlo y qué módulos actuales se verían afectados.

---

## V2-001: Salidas parciales por Take Profit

**Qué es:**
Cierre del X% de la posición al alcanzar TP1 (2R), cierre del resto al alcanzar TP2 (3R). Permite asegurar una parte del beneficio antes de buscar un objetivo extendido.

**Por qué no en V1:**
Los porcentajes de cierre por TP (TP1_POSITION_PCT, TP2_POSITION_PCT) están PENDING (PD-017b). El backtester de V1 usa una sola salida final al TP objetivo.

**Qué falta:**
- Aprobación de PD-017b: qué fracción se cierra en TP1 vs TP2 (e.g., 50%/50%, 70%/30%).
- Decisión sobre si el TP2 solo se activa cuando hay liquidez objetivo visible.

**Módulos afectados:**
- `src/backtesting/trade_simulator.py` — añadir lógica de salida parcial con P&L pro-rata.
- `config/strategy_config.py` — activar `TP1_POSITION_PCT` y `TP2_POSITION_PCT`.
- `scripts/generate_dataset.py` — registrar `exit_reason_tp1`, `exit_reason_tp2`, `partial_pnl`.

**Notas:**
El dataset V1 incluye `rr_objetivo` para facilitar la integración futura. La columna `tp_price` en V1 corresponde siempre a 2R.

---

## V2-002: Break Even tipo B (tras consolidación)

**Qué es:**
Mover el SL a entrada después de identificar una consolidación post-entrada. Más conservador que el tipo A (que mueve a BE solo al alcanzar +1R).

**Por qué no en V1:**
La definición matemática de "consolidación" no está aprobada (PD-018b). V1 implementa solo el tipo A (SL a BE al +1R).

**Qué falta:**
- Aprobación de PD-018b: número de velas / criterio de rango que define consolidación (e.g., 3+ velas M15 con rango < 50% del ATR).

**Módulos afectados:**
- `src/backtesting/trade_simulator.py` — añadir detección de consolidación y lógica BE tipo B.
- `config/strategy_config.py` — activar `BE_MODE_B` con parámetros de consolidación.

---

## V2-003: Umbral del displacement_score para filtrar impulsos

**Qué es:**
Un valor mínimo del `displacement_score` para considerar que un BOS/CHOCH va acompañado de un movimiento genuinamente impulsivo y, por tanto, que el POI resultante es "de calidad".

**Por qué no en V1:**
El umbral no está aprobado (PD-005b). En V1 se aceptan todos los BOS y se registra el `displacement_score` como feature continua. Sin umbral filtrado.

**Qué falta:**
- Análisis de la distribución histórica del score (a presentar al trader).
- Aprobación del umbral mínimo.

**Módulos afectados:**
- `src/strategy/setup_detector.py` — añadir condición `displacement_score >= threshold`.
- `config/strategy_config.py` — activar `DISPLACEMENT_THRESHOLD`.

**Nota de V1:**
El `displacement_score` de la barra de BOS se registra en el dataset. Permitirá al trader analizar la distribución y definir el umbral.

---

## V2-004: Order Block — grupo de velas contrarias

**Qué es:**
Cuando varias velas contrarias consecutivas preceden al impulso, todas ellas forman el "bloque" (OB extendido). El proximal y el distal se toman del bloque completo, no de la última vela únicamente.

**Por qué no en V1:**
El número máximo de velas del bloque no está definido (PD-005c). V1 usa siempre la última vela contraria como OB.

**Qué falta:**
- Aprobación de PD-005c: ¿cuántas velas contrarias consecutivas se agrupan? (e.g., 2, 3, hasta N).

**Módulos afectados:**
- `src/features/poi.py` — extender `detect_order_blocks` para identificar bloques.
- `src/strategy/setup_detector.py` — ajustar proximal/distal al bloque.

---

## V2-005: Confirmación intrabar con datos M1

**Qué es:**
En lugar de esperar el cierre de la vela M15 para confirmar la entrada, usar el acumulado de M1 dentro de la vela M15 para decidir la entrada durante la vela (intrabar entry).

**Por qué no en V1:**
Requiere una lógica diferente de simulación (entrar dentro de la barra M15, no al inicio de la siguiente). Aumenta la complejidad del backtester y puede introducir ambigüedades sobre qué precio M1 se usa como entrada.

**Qué falta:**
- Decisión del trader sobre qué criterio M1 confirma la entrada intrabar.
- Verificación de que no produce lookahead dentro de la barra M15.

**Módulos afectados:**
- `config/strategy_config.py` — `ENTRY_MODE = "intrabar"` ya está preparado.
- `src/backtesting/trade_simulator.py` — añadir modo intrabar.

---

## V2-006: Clasificador Sistema C (BUY / SELL / NO_TRADE)

**Qué es:**
Un clasificador sobre TODAS las barras M15 en ventanas operativas, no solo sobre los setups identificados por la estrategia. Las etiquetas son BUY / SELL / NO_TRADE. El modelo puede descubrir patrones que Sistema A no identifica.

**Por qué no en V1:**
El entregable académico requiere un dataset de setups con variable binaria (TP/SL). El Sistema C requiere etiquetar el universo completo de barras M15, lo que es un problema diferente (labeling de ventanas, no de setups).

**Qué falta:**
- Criterio de etiquetado forward-looking para BUY/SELL/NO_TRADE sobre barras M15.
- Definición de horizonte y condiciones de retorno para cada etiqueta.

**Módulos afectados:**
- `src/models/labeler.py` — crear etiquetador para Sistema C.
- Nuevo script `scripts/generate_dataset_c.py`.

---

## V2-007: Costes — comisión round-turn vs por lado

**Qué es:**
Confirmación definitiva de si los 5 USD/lote de FTMO son round-turn (una vez por operación completa) o por lado (5 USD entrada + 5 USD salida = 10 USD round-turn).

**Por qué no en V1:**
Pendiente de verificación con documentación oficial FTMO (PD-021b). El dataset V1 registra los costes con ambas interpretaciones y declara explícitamente cuál usó.

**Qué falta:**
- Verificación en documentación FTMO del EUR/USD Challenge.

**Módulos afectados:**
- `src/backtesting/cost_model.py` — ambos modos ya están parametrizados.
- `config/strategy_config.py` — `COMMISSION_ROUND_TURN` / `COMMISSION_PER_SIDE`.

---

## V2-008: Swap overnight

**Qué es:**
Coste adicional por mantener una posición abierta después de las 22:00 UTC (rollover diario).

**Por qué no en V1:**
Las operaciones de la estrategia duran <90 minutos; el swap es improbable. Los valores de swap también están pendientes (PD-021c).

**Qué falta:**
- Valores de swap por lote/día para EUR/USD long y short.

**Módulos afectados:**
- `src/backtesting/cost_model.py` — añadir lógica de swap cuando la posición cruce el rollover.
- `config/strategy_config.py` — activar `OVERNIGHT_SWAP_EURUSD_LONG_DAILY` y `SHORT`.

---

## V2-009: Refinamiento multi-TF del POI (H4 → H1 → M30 → M15)

**Qué es:**
El workflow completo de identificación de POIs en H4/H1 y luego refinamiento en M30/M15 para obtener entradas más precisas y zonas con mejor relación riesgo-beneficio.

**Por qué no en V1:**
V1 detecta los POIs en M15 (temporalidad de ejecución) usando H1 para contexto de sesgo. El refinamiento cross-TF requiere alinear correctamente los timestamps entre temporalidades y rastrear el estado del POI a través de varias TFs, lo que añade complejidad significativa.

**Qué falta:**
- Decisión sobre qué TF es el "fuente" para cada tipo de POI.
- Lógica de refinamiento: cómo ajustar el proximal/distal de un POI H1 usando M30.
- Tests de no-lookahead cross-TF.

**Módulos afectados:**
- `src/features/poi.py` — añadir campo `source_tf` y `refined_at_tf`.
- `src/strategy/setup_detector.py` — lógica de refinamiento cross-TF.

---

## V2-010: Gestión dinámica de posición basada en momentum post-entrada

**Qué es:**
Detectar debilitamiento del momentum después de la entrada (velas progresivamente más pequeñas, menor desplazamiento, consolidación visible) y considerar salida anticipada antes del TP o del tiempo límite.

**Por qué no en V1:**
Las variables de momentum post-entrada serían posteriores a la entrada → lookahead como predictores. V1 no implementa salidas dinámicas.

**Qué falta:**
- Definición de cuándo el momentum se considera "débil" (e.g., N velas con body/range < umbral).
- Acuerdo sobre si estas salidas cuentan como "resultado" separado o se mezclan con TP/SL/TIME_EXIT.

**Módulos afectados:**
- `src/backtesting/trade_simulator.py` — añadir lógica de salida por debilitamiento.
- Dataset V2 — nueva columna `exit_reason = MOMENTUM_EXIT`.

---

## V2-011: Walk-forward validation cronológica completa

**Qué es:**
Evaluación rigurosa con separación estricta de tiempo: entrenamiento en 2020-2024, validación en 2025, test final en 2026. Con re-entrenamiento por año o por período.

**Por qué no en V1:**
El notebook académico usa KFold con 10 pliegues. V1 incluye la columna `fecha` y el año para facilitar esta separación en el notebook, pero no implementa la evaluación temporal de forma sistemática.

**Qué falta:**
- Wrapper de evaluación cronológica compatible con scikit-learn.
- Documentación de limitaciones del KFold temporal.

**Módulos afectados:**
- `src/evaluation/` — crear `walk_forward.py`.

---

## V2-012: Análisis de sensibilidad de costes

**Qué es:**
Ejecutar el backtest con los 3 escenarios de spread × 3 de slippage × 2 de comisión = 18 combinaciones y reportar cómo varía la tasa de éxito y el ROC-AUC de los modelos.

**Por qué no en V1:**
V1 genera el dataset con el escenario central (spread 0.2 pips, slippage 0.0, comisión round-turn). El análisis de sensibilidad es un refinamiento posterior.

**Qué falta:**
- Dataset generado con otros escenarios de costes.
- Análisis comparativo.

**Módulos afectados:**
- `scripts/generate_dataset.py` — parametrizar escenarios de costes.
- `src/evaluation/` — análisis de sensibilidad.

---

## V2-013: Análisis de sensibilidad al buffer SL

**Qué es:**
Comparación sistemática del impacto de distintos valores del buffer más allá del distal del POI sobre la distribución de resultados, el número de setups y la tasa de rentabilidad.

**Escenarios propuestos:**
| Buffer | Alias | Efecto esperado |
|--------|-------|-----------------|
| 0.2 pips | ajustado | Más setups activados; mayor riesgo de stop-hunting |
| 0.5 pips | central (V1) | Equilibrio provisional |
| 1.0 pips | holgado | Menos falsos activados; mayor riesgo en cada operación |

**Por qué no en V1:**
El parámetro está fijado en 0.5 pips de forma provisional (P-C, 2026-11-02). La sensibilidad requiere regenerar el dataset tres veces (una por escenario) y comparar métricas out-of-sample.

**Qué falta:**
- Decisión del trader sobre qué métrica guía la comparación (win_rate, R esperado, ROC-AUC del modelo).
- Definición de "mejor" buffer: ¿menor coste por SL, más muestras, mejor clasificación?

**Módulos afectados:**
- `scripts/generate_dataset.py` — ya acepta `--sl_buffer_pips` como parámetro de línea de comandos (V2).
- `src/strategy/setup_detector.py` — `SL_BUFFER_PIPS` es configurable vía `detect_setups(sl_buffer_pips=...)`.

---

## Resumen de dependencias por decisión pendiente

| Decisión | Bloquea |
|----------|---------|
| PD-005b (umbral displacement) | V2-003 |
| PD-005c (OB grupo velas) | V2-004 |
| PD-017b (% cierre TP) | V2-001 |
| PD-018b (consolidación BE B) | V2-002 |
| PD-021b (comisión round-turn/lado) | V2-007 |
| PD-021c (swap overnight) | V2-008 |
