# Notas de integración — CSV + Notebook Proyecto_02

**Fecha:** 2026-11-02
**Dataset:** `eurusd_operaciones.csv` (raíz del proyecto)
**Notebook:** `notebooks/Proyecto_02.ipynb` (rama `feature/notebook`)

---

## Cómo funciona el flujo

1. Ejecutar `python scripts/generate_dataset.py` desde la raíz del proyecto.
   Esto produce `eurusd_operaciones.csv` en la raíz.

2. Copiar (o enlazar) el CSV a la carpeta donde se ejecuta el notebook,
   si el notebook se ejecuta desde `notebooks/`.

3. Abrir y ejecutar el notebook.

---

## Preprocesamiento que hace el notebook

```python
df = pd.read_csv("eurusd_operaciones.csv")

# Target binario
df['resultado'] = df['resultado'].replace({"TP": 1, "SL": 0})

# Dirección como numérico
df['direccion'] = df['direccion'].replace({"compra": 1, "venta": 0})

# One-hot encoding
df = pd.get_dummies(df, columns=['sesion', 'cambio_estructura'])

# Antes del split X/y, eliminar fecha (string)
df = df.drop(columns=['fecha'])   # puede estar implícito o explícito en el notebook

# Conversión numérica completa
df = df.astype(float)

y = df['resultado']
X = df.drop(columns=['resultado'])
```

---

## Columnas del CSV y su rol en el notebook

| Columna | Tipo en CSV | Rol en notebook | Notas |
|---------|-------------|-----------------|-------|
| `fecha` | string timestamp | Se elimina antes del X/y split | No es predictor |
| `direccion` | "compra"/"venta" | Predictor numérico (1/0 tras replace) | |
| `sesion` | string categorical | One-hot → sesion_london_killzone, sesion_newyork_am_open | |
| `cambio_estructura` | string categorical | One-hot → cambio_estructura_bos_bull, cambio_estructura_bos_bear | |
| `atr` | float | Predictor numérico | ATR14 en precio |
| `volatilidad` | float | Predictor numérico | Desviación estándar de log-retornos (20 barras) |
| `volumen_rel` | float | Predictor numérico | Tick count / media 20 barras |
| `distancia_estructura` | float | Predictor numérico | Pips desde el close al último swing |
| `fib_retracement` | float | Predictor numérico | [0.50, 1.00] — zona de descuento |
| `fib_in_entry_zone` | int (0/1) | Predictor numérico | True si fib_retracement ≥ 0.50 |
| `fib_in_pref_zone` | int (0/1) | Predictor numérico | True si 0.60 ≤ fib_retracement ≤ 0.70 |
| `poi_type` | int (0=FVG, 1=OB) | Predictor numérico | |
| `poi_state_at_entry` | int (0=fresh, 1=touched) | Predictor numérico | |
| `poi_size_pips` | float | Predictor numérico | Tamaño de la zona POI en pips |
| `body_range_ratio` | float | Predictor numérico | Cuerpo de la vela de confirmación [0,1] |
| `displacement_score` | float | Predictor numérico | Score del impulso de la vela de confirmación [0,1] |
| `resultado` | "TP"/"SL" | Target binario (1/0 tras replace) | **VARIABLE OBJETIVO** |

---

## Estado del CSV (generado 2026-11-02)

```
Período           : 2020-01-01 → 2026-10-16
Total setups      : 814
Resultado TP (1)  : 294  (36.1%)
Resultado SL (0)  : 520  (63.9%)
Excluidos AMBIG.  : 1
NaN en features   : 0
```

### Distribución temporal

| Año  | SL  | TP  | Total |
|------|-----|-----|-------|
| 2020 | 73  | 53  | 126   |
| 2021 | 72  | 48  | 120   |
| 2022 | 83  | 45  | 128   |
| 2023 | 84  | 44  | 128   |
| 2024 | 71  | 41  | 112   |
| 2025 | 68  | 41  | 109   |
| 2026 | 69  | 22  | 91    |

---

## Advertencias importantes

### 1. Data leakage — columnas excluidas del CSV

Las siguientes columnas se guardan en `results/eurusd_metadata.csv` pero NO en el CSV principal:

- `entry_bid`, `sl_price`, `tp_price` — precios post-entrada
- `risk_pips`, `exit_bid`, `gross_pips`, `net_pips`, `net_usd` — P&L de la simulación
- `exit_reason` — razón de salida (TP/SL/TIME_EXIT/BE/AMBIGUOUS)
- `bar_index`, `entry_bar_index` — índices internos
- `h1_bias` — sesgo H1 redundante con `direccion`

Incluir cualquiera de estas columnas en el CSV de entrenamiento constituiría **data leakage** (información del futuro).

### 2. Parámetros provisionales V1

El dataset fue generado con las siguientes decisiones provisionales **pendientes de confirmación del trader**:

| Parámetro | Valor provisional | Variable |
|-----------|-------------------|----------|
| Cuerpo mínimo de vela de confirmación | 20% (body/range) | `CONF_MIN_BODY_RATIO` en setup_detector.py |
| Buffer SL más allá del distal POI | 0.5 pips | `SL_BUFFER_PIPS` en setup_detector.py |
| Filtro de alineación H1 | Obligatorio | `HTF_FILTER = True` en setup_detector.py |
| Riesgo mínimo aceptable | 5 pips | `MIN_RISK_PIPS` en setup_detector.py |

Si el trader confirma valores diferentes, hay que regenerar el dataset con `generate_dataset.py`.

### 3. Split temporal para evaluación académica

El KFold(10) del notebook mezcla datos de todos los años. Para una evaluación temporalmente correcta (no implementada en el notebook actual), usar:
- Train: 2020-2024 (610 setups)
- Test:  2025-2026 (204 setups)

Ver `docs/roadmap_v2.md` (V2-011) para el plan de validación walk-forward.

### 4. Número de setups y potencia estadística

Con 814 setups:
- KFold(10) → ~82 setups por pliegue
- Clase minoritaria (~36% TP): ~30 positivos por pliegue
- Suficiente para Logistic Regression y SVM RBF; MLP puede requerir más muestras

Si el trader relaja los filtros (HTF_FILTER=False, fib_min=0.4, etc.), el número puede aumentar considerablemente.

---

## Cómo regenerar el dataset

```bash
# Con los parámetros actuales
python scripts/generate_dataset.py

# Con fecha alternativa
python scripts/generate_dataset.py --start 2020-01-01 --end 2024-12-31

# Modo silencioso
python scripts/generate_dataset.py --quiet
```

El script tarda ~10 minutos para el período completo (la detección de setups es el paso lento;
la simulación M1 toma ~1 minuto adicional).
