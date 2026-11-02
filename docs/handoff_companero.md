# Handoff para el compañero — Dataset V1 listo

**Para:** Compañero que trabaja en el notebook Proyecto_02
**De:** Motor Sistema A (desarrollo)
**Fecha:** 2026-11-02
**Estado:** Dataset V1 cerrado definitivamente

---

## TL;DR

El archivo `eurusd_operaciones.csv` está en la raíz del proyecto. Tiene 2,642 filas, 17 columnas, 0 NaN. El target es `resultado` (int 0/1). Lee `docs/data_dictionary_v1.md` para los detalles de cada columna.

---

## Qué hay en el repositorio para ti

```
eurusd_operaciones.csv              ← dataset principal para el notebook
eurusd_operaciones_excluidas.csv    ← excluidos (no para entrenamiento)
results/eurusd_metadata.csv         ← metadatos por trade (no para entrenamiento)
docs/data_dictionary_v1.md          ← descripción de cada columna
docs/strategy_v1_explained.md       ← qué genera cada setup (para contexto)
docs/notebook_integration_notes.md  ← cómo usar el CSV en el notebook
docs/presentation_v1_brief.md       ← resumen ejecutivo para presentar
```

---

## Preprocesamiento necesario en el notebook

```python
import pandas as pd

df = pd.read_csv("eurusd_operaciones.csv")

# 1. Dirección como numérico
df['direccion'] = df['direccion'].replace({"compra": 1, "venta": 0})

# 2. One-hot de variables categóricas ANTES del split
df = pd.get_dummies(df, columns=['sesion', 'cambio_estructura', 'h1_alignment'])

# 3. Eliminar fecha (identificador temporal, no predictor)
df = df.drop(columns=['fecha'])

# 4. Split X / y
y = df['resultado']
X = df.drop(columns=['resultado'])
```

**Importante:** `h1_alignment` tiene 4 valores posibles: `aligned`, `counter`, `neutral`, `unavailable`. Con el período 2020-2026 solo aparecen `aligned` y `counter` (no hay H1 ranging ni datos faltantes). Si cambias el período, podrían aparecer las otras categorías.

---

## El target

`resultado = 1` si la operación cerró con beneficio neto (después de spread + comisión + slippage).
`resultado = 0` si cerró en pérdida o en breakeven.

**No es** "¿llegó al TP?". Un trade que expira en positivo también da 1. Un breakeven da 0 (gross=0 pero costes=0.7 pips → pérdida neta).

**Distribución:** 969/2642 = 36.7% positivos. Desequilibrio moderado. Considera `class_weight='balanced'` en los modelos.

---

## Columnas categóricas y sus valores en V1

| Columna | Valores observados en V1 |
|---|---|
| `sesion` | `london_killzone` (1574), `newyork_am_open` (1068) |
| `cambio_estructura` | `bos_bull`, `bos_bear`, `choch_bull`, `choch_bear` |
| `h1_alignment` | `aligned` (1196), `counter` (1446) |
| `direccion` | `compra` (1310), `venta` (1332) |

---

## Lo que no debes tocar

`results/eurusd_metadata.csv` contiene información posterior a la entrada del trade (precios de salida, P&L, motivo de salida). **No incluyas estas columnas en X**. Incluirlas sería data leakage.

Las columnas del metadata que no deben ir a X:
`entry_bid`, `sl_price`, `tp_price`, `risk_pips`, `exit_reason`, `entry_time`, `exit_time`, `exit_bid`, `gross_pips`, `net_pips`, `net_usd`, `poi_id`

---

## División temporal para validación correcta

El notebook actual usa KFold(10) que mezcla años. Para una evaluación académicamente más rigurosa:

```python
from sklearn.model_selection import train_test_split

df_temporal = pd.read_csv("eurusd_operaciones.csv")
train = df_temporal[pd.to_datetime(df_temporal["fecha"]).dt.year <= 2024]
test  = df_temporal[pd.to_datetime(df_temporal["fecha"]).dt.year >= 2025]
```

Esto da ~2,269 train / 373 test. Ver `docs/roadmap_v2.md` para el plan de walk-forward.

---

## Supuestos de costes — cuidado al interpretar

Los 0.7 pips de coste total son una **hipótesis de simulación**, no costes históricos observados:
- Spread 0.2 pips: valor típico EUR/USD en horario de alta liquidez. En apertura de sesión o eventos macro puede ser 1-3 pips.
- Comisión 5 USD/lote: especificación FTMO pública. Varía por broker y tipo de cuenta.
- Slippage 0.0: optimista. En condiciones reales habría slippage positivo en entradas.

Si el modelo tiene buen rendimiento con 0.7 pips, hay que verificar con escenarios pesimistas antes de sacar conclusiones sobre rentabilidad real.

---

## Si algo no funciona

1. `python -m pytest tests/ -v` — 381 tests deben pasar antes de cualquier cambio
2. `python scripts/generate_dataset.py` — regenera el CSV desde cero (~10 min)
3. Ver `docs/reproducibility_v1.md` — checks de validación del dataset
4. Preguntar al desarrollador del motor (este repositorio)
