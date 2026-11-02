# Arquitectura del sistema — EUR/USD Trading Intelligence System

**Versión:** 0.1  
**Última actualización:** 2026-11-01

---

## Visión general

El sistema está compuesto por tres experimentos independientes y comparables:

```
                    ┌────────────────────────────────┐
                    │   DATA ENGINEERING LAYER       │
                    │   M1 BI5 → OHLCV multitf       │
                    └─────────────┬──────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │  SISTEMA A   │   │   SISTEMA B      │   │   SISTEMA C      │
    │  Baseline    │   │  Strategy Filter │   │  ML Classifier   │
    │  Determinista│   │  (ML Binary)     │   │  (ML Multiclass) │
    └──────┬───────┘   └───────┬──────────┘   └────────┬─────────┘
           │                   │                        │
           └───────────────────┴────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   EVALUATION LAYER          │
                    │   Backtesting + Métricas    │
                    └────────────────────────────┘
```

---

## Módulos del proyecto

### `src/data/`
| Módulo         | Responsabilidad                                               |
|----------------|---------------------------------------------------------------|
| `parser_bi5.py` | Parsear archivos Dukascopy BI5 → DataFrame M1              |
| `loader.py`    | Descubrir, cargar y concatenar archivos BI5 → dataset M1    |
| `resampler.py` | Construir temporalidades superiores desde M1 (M15 → MN)     |

### `src/features/` (FASE 2 — pendiente)
| Módulo             | Responsabilidad                                           |
|--------------------|-----------------------------------------------------------|
| `structure.py`     | Swings, BOS, CHOCH, dirección estructural                |
| `momentum.py`      | Displacement, velocidad, intensidad del impulso          |
| `poi.py`           | Identificación y refinamiento de POI                     |
| `liquidity.py`     | Máximos/mínimos relevantes, sweeps de liquidez           |
| `fibonacci.py`     | Niveles Fibonacci, zona de retroceso                     |
| `sessions.py`      | Features de sesión (Londres, Nueva York)                 |
| `auxiliary.py`     | ATR, EMA, RSI, retornos, volatilidad (variables auxiliares) |

### `src/strategy/` (FASE 3 — pendiente)
| Módulo             | Responsabilidad                                           |
|--------------------|-----------------------------------------------------------|
| `engine.py`        | Motor determinista de la estrategia (Sistema A)          |
| `signals.py`       | Identificación de setups BUY/SELL                        |
| `rules.py`         | Reglas formalizadas de la estrategia                     |

### `src/backtesting/` (FASE 3 — pendiente)
| Módulo             | Responsabilidad                                           |
|--------------------|-----------------------------------------------------------|
| `backtester.py`    | Simulación histórica con múltiples TP                    |
| `trade.py`         | Representación de una operación individual               |
| `metrics.py`       | Métricas de trading (win rate, expectancy, drawdown, etc.) |

### `src/models/` (FASE 4/5 — pendiente)
| Módulo             | Responsabilidad                                           |
|--------------------|-----------------------------------------------------------|
| `labeler.py`       | Etiquetado GOOD_SETUP/BAD_SETUP y BUY/SELL/NO_TRADE      |
| `features_ml.py`   | Pipeline de features para ML (sin lookahead)             |
| `trainer.py`       | Entrenamiento LR, RF, XGBoost con Optuna                 |
| `predictor.py`     | Inferencia sobre nuevos datos                            |
| `calibration.py`   | Calibración de probabilidades                            |

### `src/evaluation/` (FASE 6 — pendiente)
| Módulo             | Responsabilidad                                           |
|--------------------|-----------------------------------------------------------|
| `walk_forward.py`  | Validación walk-forward temporal                         |
| `classification.py` | Métricas de clasificación (F1, AUC, calibración)       |
| `trading_eval.py`  | Métricas de trading (profit factor, drawdown, etc.)      |
| `comparison.py`    | Comparación A vs B vs C                                  |

### `src/visualization/` (FASE 6/7 — pendiente)
| Módulo             | Responsabilidad                                           |
|--------------------|-----------------------------------------------------------|
| `charts.py`        | Gráficos de velas con anotaciones (POI, BOS, etc.)       |
| `equity.py`        | Equity curves y drawdown                                  |
| `ml_plots.py`      | Matriz de confusión, importancia, calibración            |

---

## Configuración centralizada (`config/`)

| Archivo              | Contenido                                             |
|----------------------|-------------------------------------------------------|
| `settings.py`        | Rutas, fechas, timeframes, semilla aleatoria          |
| `data_config.py`     | Nombres de archivos Parquet por temporalidad          |
| `strategy_config.py` | Parámetros de estrategia (CONFIRMED + PENDING)        |
| `model_config.py`    | Algoritmos, métricas, splits temporales, Optuna       |

---

## Principios de diseño

1. **Sin lookahead:** Toda feature se calcula usando solo información disponible hasta el momento de la decisión.
2. **Reproducibilidad:** Semilla fija (42), datos raw inmutables, parámetros en config/.
3. **Separación temporal:** No se realizan divisiones aleatorias. Train/Val/Test son bloques cronológicos.
4. **Modularidad:** Cada módulo tiene una única responsabilidad y sus propios tests.
5. **Transparencia:** Las decisiones pendientes están documentadas. Ninguna regla de trading se inventa sin aprobación.
6. **Comparabilidad:** Los tres sistemas (A/B/C) se evalúan con los mismos datos, período y métricas.
