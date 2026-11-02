# EUR/USD Trading Intelligence System — Instrucciones para Claude Code

## Descripción del proyecto

Sistema cuantitativo de investigación sobre EUR/USD que convierte una metodología discrecional de trading (SMC) en tres sistemas comparables:
- **Sistema A:** Baseline determinista (estrategia original formalizada)
- **Sistema B:** Filtro ML sobre los setups del Sistema A
- **Sistema C:** Clasificador predictivo M15 independiente (BUY/SELL/NO_TRADE)

## Reglas de trabajo

### Git
- **Nunca trabajar en `main`** — usar `development` o ramas `feature/*`
- Commits solo cuando un bloque funcional está validado (tests pasando)
- No hacer push de archivos de datos (BI5, Parquet) — están en `.gitignore`
- Mensajes de commit descriptivos en inglés o español

### Código
- Tests en `tests/` con pytest — ejecutar antes de cualquier commit
- Imports absolutos: `from src.data.parser_bi5 import ...`
- Type hints en todas las funciones públicas
- Sin comentarios de "qué hace" — solo "por qué" cuando sea no obvio
- Sin docstrings de múltiples párrafos — una línea si es necesario

### Datos
- Raw: `data/raw/m1/` — NUNCA modificar
- Processed: `data/processed/` — regenerables desde raw
- El parquet M1 correcto: `eurusd_m1_bid.parquet`
- El backup incorrecto (bug OHLC): `eurusd_m1_bid_BACKUP_wrong_ohlc.parquet`

### Decisiones de trading
- **Nunca inventar parámetros de estrategia** — consultar al trader
- Las decisiones pendientes están en `docs/pending_decisions.md`
- Las decisiones aprobadas están en `docs/decisions_log.md`
- Los parámetros PENDING en `config/strategy_config.py` son `None` hasta aprobación

## Estructura del proyecto

```
config/           # configuración centralizada (settings, data, strategy, model)
src/
  data/           # parser_bi5.py, loader.py, resampler.py
  features/       # feature engineering (pendiente)
  strategy/       # motor determinista Sistema A (pendiente)
  backtesting/    # backtester (pendiente)
  models/         # labeler, trainer, predictor (pendiente)
  evaluation/     # walk-forward, métricas (pendiente)
  visualization/  # gráficas (pendiente)
tests/            # todos los tests (pytest)
scripts/          # build_dataset.py, build_multitf.py
docs/             # documentación completa
data/
  raw/m1/         # archivos BI5 originales (no modificar)
  processed/      # parquets M1 + M15/H1/H4/D1/W1/MN
results/          # figuras, métricas, reportes generados
```

## Bug crítico resuelto (2026-11-01)

El formato Dukascopy BI5 almacena `(ts, open, **close**, low, **high**, vol)`,  
**NO** `(ts, open, high, low, close, vol)`.  
El parser antiguo tenía HIGH y CLOSE intercambiados → 2.5M violaciones OHLC.  
El parser corregido produce 0 violaciones en 3.5M registros activos.

## Cómo ejecutar

```bash
# Validar y regenerar dataset M1
python scripts/build_dataset.py

# Construir todas las temporalidades
python scripts/build_multitf.py

# Ejecutar todos los tests
python -m pytest tests/ -v

# Tests rápidos (sin dataset completo)
python -m pytest tests/ -v -k "not FullDataset"
```

## Estado actual (2026-11-01)

- FASE 0 (auditoría): ✅ completada
- FASE 1 (data engineering): ✅ completada
- FASE 2 (features): en progreso — esperando decisiones del trader (PD-001 a PD-021)
- FASE 3–7: pendientes
