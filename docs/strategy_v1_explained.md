# Estrategia V1 — Descripción técnica del Sistema A

**Versión:** V1 (cierre definitivo 2026-11-02)
**Sistema:** A — Baseline determinista (formalización de la metodología SMC del trader)

---

## 1. Concepto de setup

Un setup del Sistema A se produce cuando confluyen:

1. **Ventana operativa**: barra M15 dentro de London Killzone (02:00–05:00 ET) o NY AM Open (09:30–11:00 ET)
2. **POI activo**: existe un FVG o Order Block en estado FRESH o TOUCHED (no PARTIALLY_MITIGATED, FULLY_MITIGATED ni INVALIDATED)
3. **Contacto con la zona**: la barra toca o entra en el POI
4. **Confirmación de dirección**: cierre de la vela de confirmación en la dirección del POI (close > open para BUY; close < open para SELL)
5. **Retroceso Fibonacci ≥ 50%**: el precio se ha retraído al menos el 50% del último impulso relevante hacia la zona de descuento/premium
6. **Riesgo mínimo**: distancia entry → SL ≥ 5.0 pips
7. **C2 — Unicidad por episodio**: el POI no ha generado ya un setup en el episodio actual de contacto

No hay filtro de alineación H1 (P-B). `h1_alignment` es un predictor, no un filtro.

---

## 2. Tipos de POI

### FVG (Fair Value Gap)
Desequilibrio de 3 velas confirmado al cierre de la tercera vela:
- **Alcista:** `high(c1) < low(c3)` → zona = [high(c1), low(c3)]
- **Bajista:** `low(c1) > high(c3)` → zona = [high(c3), low(c1)]

### Order Block
Última vela contraria antes de un impulso relevante:
- **Alcista:** última vela bajista antes de un desplazamiento alcista significativo
- **Bajista:** última vela alcista antes de un desplazamiento bajista significativo

El tamaño mínimo del impulso se determina por ATR(14) × 1.0.

---

## 3. Estados del POI

```
FRESH → TOUCHED → PARTIALLY_MITIGATED → FULLY_MITIGATED
      ↘ INVALIDATED (en cualquier estado)
```

- **FRESH**: zona no visitada
- **TOUCHED**: primer contacto; cierre vuelve fuera del proximal
- **PARTIALLY_MITIGATED**: cierre dentro de la zona (entre proximal y distal)
- **FULLY_MITIGATED**: wick alcanza o cruza el distal
- **INVALIDATED**: cierre más allá del distal (alcista: close < distal; bajista: close > distal)

Solo se aceptan setups desde FRESH o TOUCHED. PARTIALLY_MITIGATED queda excluido por considerar que la zona ha perdido integridad.

---

## 4. Gestión de la operación

### Entrada
Modo conservador (P-C): apertura de la barra M15 siguiente al bar de confirmación.
`entry_bid = open[i+1]`

### Stop Loss
Más allá del extremo distal del POI, con un buffer provisional de 0.5 pips:
- BUY: `sl_price = poi.distal − 0.5 × PIP`
- SELL: `sl_price = poi.distal + 0.5 × PIP`

### Take Profit
2R desde la entrada:
- BUY: `tp_price = entry_bid + 2 × (entry_bid − sl_price)`
- SELL: `tp_price = entry_bid − 2 × (sl_price − entry_bid)`

### Breakeven (BE tipo A)
Cuando el precio alcanza +1R desde la entrada, el SL se mueve a entry_bid:
- BUY BE level: `entry_bid + 1 × risk`
- SELL BE level: `entry_bid − 1 × risk`

### Horizonte temporal
90 minutos reales desde la apertura de la primera barra M1. Si no se activa TP ni SL en ese tiempo, TIME_EXIT al close de la última barra M1 disponible.

---

## 5. Convención de precios y costes (C1 — BID-BID)

Todos los precios (entry, SL, TP, exit) se expresan en BID terms. El P&L bruto se calcula BID-a-BID. El coste total se descuenta una sola vez:

```
gross_pips = (exit_bid − entry_bid) / PIP    [BUY]
gross_pips = (entry_bid − exit_bid) / PIP    [SELL]
net_pips   = gross_pips − total_cost_pips
```

Escenario central de costes:
- Spread: 0.2 pips (hipótesis, no histórico observado)
- Slippage: 0.0 pips (optimista)
- Comisión: 5 USD/lote round-turn ≈ 0.5 pips (provisional PD-021b)
- **total_cost_pips = 0.7 pips**

---

## 6. Resultado binario

```
resultado = 1   si net_pips > 0
resultado = 0   si net_pips ≤ 0
```

El resultado representa rentabilidad neta post-costes. Un BE cierra con resultado=0 (gross≈0, net=-0.7 pips).

---

## 7. Alineación H1 (h1_alignment)

El sesgo H1 se determina mediante estructura de mercado M1 resampled a H1, con merge_asof backward (sin lookahead). Categorías:

| Valor | Condición |
|---|---|
| `aligned` | Sesgo H1 coincide con dirección del setup |
| `counter` | Sesgo H1 contrario al setup |
| `neutral` | H1 en rango ("ranging") |
| `unavailable` | Sin datos H1 para la barra |

---

## 8. Variables del dataset por categoría

### Contexto de mercado
- `sesion`: ventana operativa (london_killzone / newyork_am_open)
- `cambio_estructura`: último evento M15 (bos_bull / bos_bear / choch_bull / choch_bear)
- `h1_alignment`: alineación con sesgo H1 (4 categorías)

### Volatilidad y volumen
- `atr`: ATR(14) en precio EUR/USD (no en pips)
- `volatilidad`: desviación estándar de log-retornos, ventana 20 barras M15
- `volumen_rel`: tick count Dukascopy / media 20 barras (no volumen centralizado)

### Geometría de la estructura
- `distancia_estructura`: profundidad del retroceso desde el nivel estructural (siempre < 0)
- `fib_retracement`: nivel Fibonacci del precio de confirmación [0.50, 1.00]
- `fib_in_pref_zone`: 1 si fib ∈ [0.60, 0.70]

### Características del POI
- `poi_type`: 0=FVG, 1=Order Block
- `poi_state_at_entry`: 0=FRESH, 1=TOUCHED
- `poi_size_pips`: tamaño de la zona en pips

### Vela de confirmación
- `body_range_ratio`: cuerpo / rango de la vela de confirmación [0, 1]
- `displacement_score`: score multidimensional del impulso previo [0, 1]
- `direccion`: compra / venta

### Target
- `resultado`: 1 si net_pips > 0, 0 si net_pips ≤ 0

---

## 9. Limitaciones V1

- **SL buffer 0.5 pips**: provisional. Análisis de sensibilidad pendiente (V2-016 en roadmap).
- **Modo de entrada conservador**: solo cierre M15 + apertura siguiente. El modo intrabar requeriría tick data no disponible.
- **BE tipo B**: solo se implementa tipo A (SL a entry tras +1R). El tipo B (tras consolidación) tiene definición pendiente.
- **Un solo TP**: no se implementan cierres parciales (TP1=2R, TP2=3R). Pendiente de aprobación del trader.
- **BID-only pricing**: los datos M1 de Dukascopy son BID. Las activaciones reales de TP/SL en cuentas con spread variable difieren ligeramente.
