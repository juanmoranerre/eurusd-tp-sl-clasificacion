# Diccionario de datos V1

**Versión del dataset:** V1 (2026-11-02)
**Archivo principal:** `eurusd_operaciones.csv`
**Archivos asociados:** `eurusd_operaciones_excluidas.csv`, `results/eurusd_metadata.csv`

---

## eurusd_operaciones.csv — Dataset principal (17 columnas)

Este archivo es el input del notebook de clasificación. No contiene información posterior a la entrada del trade (sin leakage).

| Columna | Tipo | Rango/Valores | Descripción |
|---|---|---|---|
| `fecha` | string (timestamp) | 2020-2026 | Timestamp de la barra M15 de confirmación (UTC, tz-naive) |
| `direccion` | str categórico | compra / venta | Dirección del setup (del POI: BULLISH→compra, BEARISH→venta) |
| `sesion` | str categórico | london_killzone / newyork_am_open | Ventana operativa activa en la barra de confirmación |
| `cambio_estructura` | str categórico | bos_bull / bos_bear / choch_bull / choch_bear | Último evento de estructura M15 antes de la barra de confirmación |
| `h1_alignment` | str categórico | aligned / counter / neutral / unavailable | Relación entre sesgo H1 y dirección del setup |
| `atr` | float | > 0 | ATR(14) en precio EUR/USD en la barra de confirmación |
| `volatilidad` | float | ≥ 0 | Desviación estándar de log-retornos M15, ventana 20 barras |
| `volumen_rel` | float | > 0 | Tick count normalizado por media 20 barras |
| `distancia_estructura` | float | < 0 | Distancia desde el precio de confirmación hasta el nivel estructural de referencia (pips, siempre negativo) |
| `fib_retracement` | float | [0.50, 1.00] | Nivel de retroceso Fibonacci en la barra de confirmación |
| `fib_in_pref_zone` | int | 0 / 1 | 1 si fib_retracement ∈ [0.60, 0.70] |
| `poi_type` | int | 0 / 1 | Tipo de POI: 0=FVG, 1=Order Block |
| `poi_state_at_entry` | int | 0 / 1 | Estado del POI en la barra de confirmación: 0=FRESH, 1=TOUCHED |
| `poi_size_pips` | float | > 0 | Tamaño de la zona POI en pips (abs(proximal − distal) / PIP) |
| `body_range_ratio` | float | [0, 1] | Cuerpo / rango de la vela de confirmación |
| `displacement_score` | float | [0, 1] | Score del impulso previo al POI (multidimensional) |
| `resultado` | int | 0 / 1 | **TARGET**: 1 si net_pips > 0, 0 si net_pips ≤ 0 |

### Notas sobre columnas específicas

**`fecha`:** Timestamp del open de la barra de confirmación M15. La entrada efectiva ocurre en la siguiente barra M15 (fecha + 15 min). No es un predictor del modelo; se usa para análisis temporal.

**`direccion`:** La dirección viene del POI, no del sesgo H1. Con HTF_FILTER=False, hay setups "counter" (contra el sesgo H1). La dirección es información pre-entrada disponible.

**`cambio_estructura`:** Registra el último evento estructural M15 observado antes del bar de confirmación. No necesariamente alineado con la dirección del setup (p. ej., puede haber un bos_bull en una operación de venta si ese fue el último evento antes de la formación del setup bajista).

**`h1_alignment`:** Requiere one-hot encoding antes del split X/y en el notebook. Las 4 categorías son mutuamente excluyentes y exhaustivas para el período 2020-2026.

**`distancia_estructura`:**
- Para BUY: `(close_confirmación − pivot_high_st) / PIP` — siempre negativo porque el precio de confirmación está por debajo del swing high de referencia
- Para SELL: `(pivot_low_st − close_confirmación) / PIP` — siempre negativo porque el precio está por encima del swing low de referencia
- El valor absoluto = profundidad del retroceso. Un valor más negativo = retroceso más profundo = mayor zona de descuento/premium.

**`volumen_rel`:** No es volumen centralizado de mercado (el forex es OTC). Representa actividad relativa del flujo de cotizaciones Dukascopy. Útil como proxy de volatilidad de alta frecuencia.

**`resultado`:** El target NO es "¿llegó al TP?". Es rentabilidad neta post-costes. Un TIME_EXIT con precio favorable da resultado=1. Un BE da resultado=0 (gross=0, net=-0.7 pips).

---

## results/eurusd_metadata.csv — Metadatos (17 columnas)

Contiene información post-entrada. **NO usar para entrenamiento** (leakage).

| Columna | Tipo | Descripción |
|---|---|---|
| `fecha` | string | Mismo timestamp que en CSV principal |
| `entry_time` | string (timestamp) | Apertura de la primera barra M1 del trade (= fecha + 15 min) |
| `exit_time` | string (timestamp) | Timestamp de salida del trade |
| `entry_bid` | float | Precio BID de entrada (open M1 tras confirmación) |
| `sl_price` | float | Precio de Stop Loss en BID terms |
| `tp_price` | float | Precio de Take Profit en BID terms |
| `risk_pips` | float | Distancia entry → SL en pips (≥ 5.0) |
| `exit_reason` | str | TP / SL / BE / TIME_EXIT / AMBIGUOUS |
| `exit_bid` | float | Precio BID de salida |
| `gross_pips` | float | P&L bruto BID-a-BID en pips |
| `net_pips` | float | P&L neto (gross − total_cost_pips = gross − 0.7) |
| `net_usd` | float | P&L neto en USD (1 lote estándar) |
| `h1_bias` | str | Sesgo H1 raw (bullish / bearish / ranging / NaN) |
| `bar_index` | int | Índice de la barra de confirmación en m15_feat |
| `entry_bar_index` | int | Índice de la barra de entrada (bar_index + 1) |
| `poi_id` | int | Identificador único del POI que generó el setup |
| `resultado` | int | 0 / 1 (igual que en CSV principal) |

---

## eurusd_operaciones_excluidas.csv — Setups excluidos (101 filas)

| Columna | Descripción |
|---|---|
| `fecha` | Timestamp de la barra de confirmación |
| `entry_bid` | Precio de entrada |
| `sl_price` / `tp_price` | Niveles operativos |
| `risk_pips` | Riesgo calculado |
| `motivo_exclusion` | **C2_POI_REUSE** o **AMBIGUOUS** |
| `exit_reason` | = motivo_exclusion para C2; AMBIGUOUS para AMBIGUOUS |
| `exit_bid`, `gross_pips`, `net_pips` | Solo presentes para AMBIGUOUS (NaN para C2) |
| `h1_bias`, `h1_alignment` | Contexto H1 en el momento del setup |
| `direccion`, `sesion` | Dirección y sesión del setup |
| `poi_id` | Identificador del POI (presente para C2_POI_REUSE) |

### Motivos de exclusión

**C2_POI_REUSE (96):** El setup cumplió TODAS las condiciones de detección, pero el POI ya había generado un setup en el episodio actual de contacto. El detector continuó buscando otros POIs en la misma barra M15.

**AMBIGUOUS (5):** El trade activó TP y SL en la misma barra M1. Por convención conservadora, se descarta del dataset principal (resultado=0 no sería representativo porque el resultado real dependería del order routing).

---

## Columnas excluidas del CSV por data leakage

Las siguientes columnas están en metadata pero NO en el CSV principal. Incluirlas en el modelo constituiría leakage post-entrada:

| Columna excluida | Razón |
|---|---|
| `entry_time`, `exit_time` | Ocurren después de la señal |
| `entry_bid`, `sl_price`, `tp_price` | Precios post-entrada |
| `exit_bid`, `gross_pips`, `net_pips`, `net_usd` | Resultado del trade |
| `exit_reason` | Causa de salida (TP/SL/BE/TIME_EXIT) |
| `risk_pips` | Depende de entry_bid y sl_price |
| `bar_index`, `entry_bar_index` | Índices internos de simulación |
| `h1_bias` | Redundante con h1_alignment; formato raw |
| `poi_id` | Identificador de trazabilidad |
| `fib_in_entry_zone` | Siempre 1 (varianza cero; es condición de filtro) |
