# EUR/USD Trading Intelligence System — Resumen V1

**Autor:** Proyecto Final LAE
**Fecha cierre V1:** 2026-11-02
**Estado:** Dataset listo para modelado ML

---

## ¿Qué hemos construido?

Un sistema que convierte una metodología discrecional de trading (SMC/ICT) en un dataset de clasificación binaria, listo para entrenar modelos de Machine Learning.

**Input:** 6 años de datos M1 EUR/USD (Dukascopy, 2020-2026)
**Output:** 2,642 operaciones con 15 predictores pre-entrada + resultado binario

---

## El dato clave

De 2,642 setups generados por la estrategia baseline (Sistema A):

| | Count | % |
|---|---|---|
| Resultado = 1 (rentable) | 969 | 36.7% |
| Resultado = 0 (no rentable) | 1,673 | 63.3% |

La estrategia baseline gana el 36.7% de las veces. El objetivo de los Sistemas B y C es determinar si un modelo ML puede seleccionar los setups con mayor probabilidad de éxito y mejorar esta tasa.

---

## Tres sistemas a comparar

```
Sistema A (baseline)  →  2,642 setups / 36.7% win rate
        ↓
Sistema B (ML filter) →  subset de A con mayor win rate
        ↓
Sistema C (classifier) →  predicción independiente BUY/SELL/NO_TRADE sobre todas las barras M15
```

El dataset V1 es el input del Sistema B. Los tres sistemas serán evaluados con walk-forward validation (train 2020-2024, test 2025-2026).

---

## Qué predice el modelo

**Target:** `resultado` = 1 si la operación cierra con beneficio neto tras costes, 0 si cierra en pérdida.

Costes incluidos (escenario central):
- Spread: 0.2 pips
- Slippage: 0.0 pips
- Comisión: 5 USD/lote round-turn ≈ 0.5 pips
- **Total: 0.7 pips por operación**

---

## Los 15 predictores del modelo

| Categoría | Variables |
|---|---|
| Dirección y contexto | `direccion`, `sesion`, `cambio_estructura`, `h1_alignment` |
| Volatilidad | `atr`, `volatilidad`, `volumen_rel` |
| Geometría | `distancia_estructura`, `fib_retracement`, `fib_in_pref_zone` |
| Características del POI | `poi_type`, `poi_state_at_entry`, `poi_size_pips` |
| Confirmación | `body_range_ratio`, `displacement_score` |

Todos son observables antes de la entrada (sin lookahead).

---

## Distribución por motivo de salida

| Salida | Count | % win |
|---|---|---|
| SL (stop loss) | 1,021 | 0% |
| TIME_EXIT (expiración) | 944 | 65.9% |
| BE (breakeven) | 330 | 0% |
| TP (take profit) | 347 | 100% |

Nota: BE cierra con resultado=0 porque el beneficio bruto es cero pero los costes (0.7 pips) producen pérdida neta.

---

## Integridad del dataset

- **0 NaN** en predictores | **0 Inf**
- **Sin lookahead** (verificado): contexto H1 usa merge_asof backward
- **Sin duplicados** temporales
- **2,533 POIs únicos** generaron los 2,642 setups
- **96 setups filtrados** por reutilización de POI en mismo episodio (C2)
- **5 AMBIGUOUS** preservados en archivo de excluidos

---

## Próximos pasos

1. **Notebook Proyecto_02** (inmediato): entrenar modelos sobre el dataset V1
   - Preprocesamiento: one-hot de `sesion`, `cambio_estructura`, `h1_alignment`
   - Modelos: Logistic Regression, Random Forest, XGBoost (mínimo)
   - Métrica principal: Macro F1

2. **Sistema B**: filtro ML sobre setups del Sistema A (dataset V1)

3. **Sistema C**: clasificador M15 independiente (universo = todas las barras en sesión)

4. **Walk-forward validation**: evaluación temporalmente correcta (train 2020-2024, test 2025-2026)
