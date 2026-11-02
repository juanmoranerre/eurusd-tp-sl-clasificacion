# Notas de integración — CSV + Notebook Proyecto_02

**Última actualización:** 2026-11-02 (V1 cerrado definitivamente — C1 BID-BID + C2 unicidad POI)
**Dataset:** `eurusd_operaciones.csv` (raíz del proyecto)
**Notebook:** `notebooks/Proyecto_02.ipynb` (rama `feature/notebook`)

---

## Cómo funciona el flujo

1. Ejecutar `python scripts/generate_dataset.py` desde la raíz del proyecto.
   Produce tres archivos:
   - `eurusd_operaciones.csv` — dataset principal para el notebook
   - `eurusd_operaciones_excluidas.csv` — setups excluidos (AMBIGUOUS y similares)
   - `results/eurusd_metadata.csv` — metadatos completos para análisis

2. Copiar (o enlazar) `eurusd_operaciones.csv` al directorio de trabajo del notebook.

3. Abrir y ejecutar el notebook.

---

## Preprocesamiento que hace el notebook

```python
df = pd.read_csv("eurusd_operaciones.csv")

# resultado ya es 0/1 entero — el replace es un no-op pero es inofensivo
# df['resultado'] = df['resultado'].replace({"TP": 1, "SL": 0})  # ya no necesario

# Dirección como numérico
df['direccion'] = df['direccion'].replace({"compra": 1, "venta": 0})

# One-hot encoding (sesion, cambio_estructura, h1_alignment)
df = pd.get_dummies(df, columns=['sesion', 'cambio_estructura', 'h1_alignment'])

# Eliminar fecha antes del split X/y
df = df.drop(columns=['fecha'])

# Conversión numérica completa
df = df.astype(float)

y = df['resultado']
X = df.drop(columns=['resultado'])
```

**Importante:** `h1_alignment` es una variable categórica con 4 posibles valores
("aligned", "counter", "neutral", "unavailable"). Debe incluirse en el `get_dummies`
junto con `sesion` y `cambio_estructura`. Mezclarla directamente como string sin
codificar produciría un error o resultados incorrectos.

---

## Columnas del CSV y su rol en el notebook

| Columna | Tipo en CSV | Rol en notebook | Notas |
|---------|-------------|-----------------|-------|
| `fecha` | string timestamp | Se elimina antes del split X/y | No es predictor |
| `direccion` | str "compra"/"venta" | Predictor numérico (1/0 tras replace) | |
| `sesion` | str categórico | Predictor → one-hot | 2 categorías |
| `cambio_estructura` | str categórico | Predictor → one-hot | Último evento M15; no necesariamente alineado con la operación |
| `h1_alignment` | str categórico | Predictor → one-hot | 4 categorías: aligned/counter/neutral/unavailable |
| `atr` | float | Predictor numérico | ATR14 en precio (no en pips) |
| `volatilidad` | float | Predictor numérico | Std de log-retornos, ventana 20 barras |
| `volumen_rel` | float | Predictor numérico | Tick count Dukascopy / media 20 barras (no volumen centralizado) |
| `distancia_estructura` | float | Predictor numérico | Siempre negativo (ver nota abajo) |
| `fib_retracement` | float | Predictor numérico | [0.50, 1.00] — zona de descuento |
| `fib_in_pref_zone` | int (0/1) | Predictor numérico | 1 si fib ∈ [0.60, 0.70] |
| `poi_type` | int (0/1) | Predictor numérico | 0=FVG, 1=OB |
| `poi_state_at_entry` | int (0/1) | Predictor numérico | 0=fresh, 1=touched |
| `poi_size_pips` | float | Predictor numérico | Tamaño de la zona POI en pips |
| `body_range_ratio` | float | Predictor numérico | Cuerpo de la vela de confirmación [0, 1] |
| `displacement_score` | float | Predictor numérico | Score del impulso [0, 1] |
| `resultado` | int (0 o 1) | **TARGET** | 1 si net_pips > 0, 0 si net_pips ≤ 0 |

**Total: 17 columnas** (1 metadato, 15 predictores, 1 target)

### Notas sobre columnas específicas

**`resultado`:** Es directamente 0/1 entero. Representa rentabilidad neta, no
necesariamente que el trade haya alcanzado el TP formal. Un TIME_EXIT que cierra
en positivo también da resultado=1. El motivo de salida real está en metadata.

**`cambio_estructura`:** Registra el último evento de estructura M15 observado antes
de la barra de confirmación. Puede ser "bos_bull" incluso en una operación de VENTA
si el último evento estructural fue alcista. No es un indicador alineado con la
dirección del setup; es contexto de la estructura reciente.

**`volumen_rel`:** Tick count de Dukascopy normalizado por la media de las últimas 20
barras. No representa volumen real de mercado centralizado (el forex es OTC). Debe
interpretarse como actividad relativa del flujo de precios en la ventana temporal.

**`distancia_estructura`:** Siempre negativa.
  - Para BUY: (close_confirmación - pivot_high_st) / PIP < 0
    (close está por debajo del swing high de referencia)
  - Para SELL: (pivot_low_st - close_confirmación) / PIP < 0
    (close está por encima del swing low de referencia)
  El valor absoluto representa la profundidad del retroceso desde el nivel estructural.
  El signo es consistente en ambas direcciones (siempre negativo) y no codifica
  información direccional adicional: la dirección se conoce por la columna `direccion`.

**`h1_alignment`:** La categoría "neutral" indica H1 en rango ("ranging"), sin sesgo
claro. La categoría "unavailable" indica ausencia de datos H1 para la barra. Ninguna
de estas debe confundirse con "counter". El modelo debe poder distinguirlas tras el
one-hot.

---

## Estado del CSV actual (V1 cerrado — 2026-11-02)

| Métrica | Valor |
|---|---|
| Setups válidos | 2,642 |
| resultado = 1 | 969 (36.7%) |
| resultado = 0 | 1,673 (63.3%) |
| London Killzone | 1,574 |
| NY AM Open | 1,068 |
| h1_alignment aligned | 1,196 |
| h1_alignment counter | 1,446 |

Regenerar con `python scripts/generate_dataset.py` si es necesario (~570s).
Los parámetros activos son P-A (sin filtro de cuerpo), P-B (sin filtro H1), P-C (SL buffer 0.5 pips), C1 (BID-BID) y C2 (unicidad POI por episodio).

---

## Advertencias importantes

### 1. Data leakage — columnas excluidas del CSV

Las siguientes columnas se guardan en `results/eurusd_metadata.csv` pero NO en el CSV principal:

- `entry_bid`, `sl_price`, `tp_price` — precios post-entrada
- `entry_time`, `exit_time`, `exit_bid` — tiempos y precios de la simulación
- `risk_pips`, `gross_pips`, `net_pips`, `net_usd` — P&L de la simulación
- `exit_reason` — causa real de salida (TP/SL/BE/TIME_EXIT/AMBIGUOUS)
- `bar_index`, `entry_bar_index` — índices internos
- `h1_bias` — sesgo H1 raw (redundante con h1_alignment)
- `fib_in_entry_zone` — siempre 1 (varianza cero)

Incluir cualquiera de estas columnas en el CSV de entrenamiento constituiría **data leakage**.

### 2. Supuestos de simulación — no son costes históricos observados

| Parámetro | Valor V1 | Estado |
|-----------|----------|--------|
| Spread | 0.2 pips | Hipótesis de referencia |
| Slippage | 0.0 pips | Optimista |
| Comisión | 5 USD/lote round-turn | Provisional (PD-021b PENDING) |
| Coste total | ~0.7 pips | Deducido en net_pips |
| Horizonte | 90 minutos reales | Tiempo transcurrido, no 90 barras M1 |
| Buffer SL | 0.5 pips | Provisional P-C |

### 3. Split temporal para evaluación académica

El KFold(10) del notebook mezcla datos de todos los años. Para una evaluación
temporalmente correcta (no implementada en el notebook actual):
- Train: 2020-2024
- Test: 2025-2026

Ver `docs/roadmap_v2.md` (V2-011) para el plan de validación walk-forward.

### 4. h1_alignment: cuatro categorías

Con HTF_FILTER=False (P-B, 2026-11-02), el dataset incluye setups de todas las
categorías de alineación. El notebook debe codificar `h1_alignment` con `get_dummies`
antes del split para que los modelos puedan aprender la influencia de cada categoría.

---

## Archivos generados

| Archivo | Contenido | Para qué |
|---------|-----------|---------|
| `eurusd_operaciones.csv` | Dataset principal, 17 columnas, sin leakage | Notebook, modelos ML |
| `eurusd_operaciones_excluidas.csv` | Setups excluidos (AMBIGUOUS) | Auditoría, debugging |
| `results/eurusd_metadata.csv` | Metadatos completos por trade | Análisis, trazabilidad |

---

## Cómo regenerar el dataset

```bash
# Con los parámetros actuales (P-A, P-B, P-C)
python scripts/generate_dataset.py

# Con período alternativo
python scripts/generate_dataset.py --start 2020-01-01 --end 2024-12-31

# Modo silencioso
python scripts/generate_dataset.py --quiet
```

El script tarda ~10-12 minutos para el período completo (la detección de setups
es el paso lento; la simulación M1 toma ~1 minuto adicional).
