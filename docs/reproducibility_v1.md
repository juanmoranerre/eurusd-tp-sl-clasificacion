# Reproducibilidad V1 — Guía para regenerar el dataset

**Versión:** V1 (2026-11-02)
**Objetivo:** Instrucciones completas para reproducir `eurusd_operaciones.csv` desde cero

---

## Requisitos previos

### Datos históricos (no incluidos en el repositorio)

Los archivos de datos históricos están excluidos del repositorio (`.gitignore`).
Deben estar presentes en:

```
data/processed/
├── eurusd_m1_bid.parquet          # 4,098,240 filas M1 (2019-2026)
├── eurusd_m15_bid.parquet         # ~273,000 filas M15
├── eurusd_h1_bid.parquet          # ~68,000 filas H1
└── eurusd_m1_bid_BACKUP_wrong_ohlc.parquet   # backup del parser incorrecto (no usar)
```

Para regenerar los parquets desde los BI5 originales:
```bash
python scripts/build_dataset.py          # genera eurusd_m1_bid.parquet
python scripts/build_multitf.py          # genera M15, H1, H4, D1, W1, MN
```

Los BI5 originales están en `data/raw/m1/` (excluidos del repositorio).

### Entorno Python

```bash
conda env create -f environment.yml   # o pip install -r requirements.txt
conda activate <nombre_env>
```

Dependencias clave: `pandas>=2.0`, `numpy>=1.24`, `pyarrow`, `pytz`

---

## Ejecución estándar

```bash
# Desde la raíz del proyecto
python scripts/generate_dataset.py
```

Produce:
- `eurusd_operaciones.csv` — dataset principal
- `eurusd_operaciones_excluidas.csv` — excluidos
- `results/eurusd_metadata.csv` — metadatos

**Tiempo esperado:** ~570s en hardware de referencia (M1 Pro 16GB)
- Carga de datos: ~0.3s
- Detección de setups M15: ~553s (loop Python sobre 247k barras)
- Simulación M1: ~16s

### Opciones de línea de comandos

```bash
# Período alternativo
python scripts/generate_dataset.py --start 2020-01-01 --end 2024-12-31

# Archivos de salida personalizados
python scripts/generate_dataset.py \
    --out mi_dataset.csv \
    --excluidos mi_excluidos.csv \
    --meta results/mi_metadata.csv

# Modo silencioso (sin progreso)
python scripts/generate_dataset.py --quiet
```

---

## Verificación de resultados

Después de regenerar, los siguientes checks deben pasar:

```python
import pandas as pd
import numpy as np

csv = pd.read_csv("eurusd_operaciones.csv")
meta = pd.read_csv("results/eurusd_metadata.csv")
excl = pd.read_csv("eurusd_operaciones_excluidas.csv")

# Checks fundamentales
assert len(csv) == 2642, f"Expected 2642, got {len(csv)}"
assert len(meta) == 2642
assert len(excl) == 101
assert csv.isna().sum().sum() == 0, "NaN en CSV principal"
assert np.isinf(csv.select_dtypes(float)).sum().sum() == 0, "Inf en CSV principal"
assert set(csv["resultado"].unique()) == {0, 1}
assert (csv["distancia_estructura"] < 0).all(), "distancia_estructura debe ser siempre negativa"

# Check C1 (convención BID-BID): BE debe tener gross=0 y net=-0.7
be_rows = meta[meta["exit_reason"] == "BE"]
assert abs(be_rows["gross_pips"].mean()) < 1e-9, "BE gross debe ser ~0"
assert abs(be_rows["net_pips"].mean() - (-0.7)) < 1e-4, "BE net debe ser -0.7"

# Check horizonte temporal
elapsed = (pd.to_datetime(meta["exit_time"]) - pd.to_datetime(meta["entry_time"])).dt.total_seconds() / 60
assert (elapsed <= 90).all(), "Ningún trade debe superar 90 min"

# Check excluidos
assert set(excl["motivo_exclusion"].unique()) == {"AMBIGUOUS", "C2_POI_REUSE"}
assert (excl["motivo_exclusion"] == "AMBIGUOUS").sum() == 5
assert (excl["motivo_exclusion"] == "C2_POI_REUSE").sum() == 96

print("Todos los checks pasaron")
```

---

## Parámetros que afectan al resultado

Cambiar cualquiera de estos produce un dataset diferente:

| Parámetro | Ubicación | Valor V1 | Efecto |
|---|---|---|---|
| `CONF_MIN_BODY_RATIO` | `src/strategy/setup_detector.py` | 0.0 | Umbral de cuerpo mínimo |
| `HTF_FILTER` | `src/strategy/setup_detector.py` | False | Filtro de alineación H1 |
| `SL_BUFFER_PIPS` | `src/strategy/setup_detector.py` | 0.5 | Buffer del SL |
| `MIN_RISK_PIPS` | `src/strategy/setup_detector.py` | 5.0 | Riesgo mínimo aceptable |
| `fib_min_retracement` | `detect_setups()` parámetro | 0.50 | Nivel Fibonacci mínimo |
| `MAX_HORIZON_MINUTES` | `src/backtesting/trade_simulator.py` | 90 | Horizonte temporal |
| `BE_TRIGGER_R` | `src/backtesting/trade_simulator.py` | 1.0 | Multiplicador de R para BE |
| `spread` | `src/backtesting/cost_model.py` | 0.2 | Spread hipotético |
| `commission_usd` | `src/backtesting/cost_model.py` | 5.0 | Comisión por lote round-turn |
| `start_date` / `end_date` | CLI o `detect_setups()` | 2020-01-01 / 2026-10-16 | Período del dataset |

---

## Tests

Los 381 tests del suite cubren features, parser, estructura y momentum. No hay tests unitarios para el backtester o detector de setups (están planificados para V2).

```bash
python -m pytest tests/ -v
```

---

## Determinismo

El pipeline es determinista: dados los mismos datos de entrada y parámetros, produce el mismo dataset. No hay sampling aleatorio, no hay seeds que configurar.

El único elemento no determinista es el warmup de features (ATR, estructura) que depende del período de calentamiento (2019-10-01 → 2019-12-31). Si se cambia el `start_date` o se modifican los datos de warmup, el resultado puede variar ligeramente en los primeros setups de enero 2020.

---

## Control de versiones del dataset

El dataset **no** está incluido en el repositorio (`.gitignore`). Para rastrear qué dataset corresponde a qué commit de código:

```bash
# Registrar hash del CSV generado
sha256sum eurusd_operaciones.csv > results/eurusd_operaciones_v1.sha256
git log -1 --pretty=format:"%H %s" >> results/eurusd_operaciones_v1.sha256
```

El commit del cierre V1 lleva el tag `v1-dataset-close` en la rama `development`.
