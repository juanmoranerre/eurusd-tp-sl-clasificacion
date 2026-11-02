# Especificación de la estrategia EUR/USD

**Estado:** Completamente actualizado con decisiones del trader (PD-001 a PD-021)
**Última actualización:** 2026-11-02
**Referencia cruzada:** `docs/decisions_log.md` (DEC-006 a DEC-015)

---

## Estado de decisiones

| Bloque | PDs | Estado | DEC |
|--------|-----|--------|-----|
| Sesiones operativas | PD-001 | ✅ CONFIRMADO | DEC-006 |
| Swings y jerarquía | PD-002 | ✅ CONFIRMADO | DEC-007 |
| BOS | PD-003 | ✅ CONFIRMADO | DEC-007 |
| CHOCH | PD-004 | ✅ CONFIRMADO | DEC-007 |
| Displacement score | PD-005 | ⚠️ PARCIAL — score implementado, umbral PENDING (PD-005b) | DEC-008 |
| Order Blocks — grupo | PD-006 | ⚠️ PARCIAL — última vela implementada, tamaño grupo PENDING (PD-005c) | DEC-009 |
| Tipos de POI | PD-007 | ✅ CONFIRMADO | DEC-010 |
| TF de identificación POI | PD-008 | ✅ CONFIRMADO | DEC-010 |
| TF de refinamiento POI | PD-009 | ✅ CONFIRMADO | DEC-010 |
| Estados de POI | PD-010 | ✅ CONFIRMADO | DEC-010 |
| Liquidez — niveles | PD-011 | ✅ CONFIRMADO | DEC-011 |
| Liquidez — sweep | PD-012 | ✅ CONFIRMADO | DEC-011 |
| Fibonacci — anclaje | PD-013 | ✅ CONFIRMADO | DEC-012 |
| Fibonacci — zona de entrada | PD-014 | ✅ CONFIRMADO | DEC-012 |
| Entrada conservadora | PD-015 | ✅ CONFIRMADO | DEC-013 |
| Stop Loss | PD-016 | ✅ CONFIRMADO | DEC-013 |
| Take Profit | PD-017 | ⚠️ PARCIAL — R confirmados, % cierre PENDING (PD-017b) | DEC-013 |
| Breakeven | PD-018 | ⚠️ PARCIAL — tipo A confirmado, consolidación tipo B PENDING (PD-018b) | DEC-013 |
| Etiquetado Sistema B | PD-019 | ✅ CONFIRMADO | DEC-014 |
| Etiquetado Sistema C | PD-020 | ✅ CONFIRMADO | DEC-014 |
| Costes | PD-021 | ⚠️ PARCIAL — spread/slippage confirmados, round-turn vs por-lado PENDING (PD-021b) | DEC-015 |

---

## 1. Temporalidades

| TF  | Rol                                     |
|-----|-----------------------------------------|
| MN  | Contexto macro                          |
| W1  | Estructura y dirección de mercado       |
| H4  | Contexto intermedio                     |
| H1  | Confirmación y análisis estructural     |
| M15 | TF principal de observación y ejecución |
| M1  | Reconstrucción post-entrada y SL/TP     |

**Invariante no-lookahead:** la información de una vela HTF solo está disponible cuando esa vela ha **cerrado completamente**. Todas las features respetan esto.

---

## 2. Sesiones operativas [CONFIRMADO — DEC-006]

| Sesión | Horario (local NY) | IANA TZ | Uso |
|--------|--------------------|---------|-----|
| London Killzone | 02:00 – 05:00 | America/New_York | Principal |
| NY AM Open | 09:30 – 11:00 | America/New_York | Principal |
| NY AM Forex Alt | 07:00 – 10:00 | America/New_York | Alternativa |

- Se usa `zoneinfo.ZoneInfo("America/New_York")` para conversiones DST-correctas (historical).
- Se registra la hora en UTC **y** en hora local de NY en cada barra.
- `SESSION_WINDOWS = [LONDON_KILLZONE, NEWYORK_AM_OPEN]` (las dos principales).

---

## 3. Estructura de mercado [CONFIRMADO — DEC-007]

### 3.1 Swings

- **Tipo:** pivote de 3 velas (1 vela a cada lado).
- **Confirmación:** el swing se confirma cuando **cierra** la vela posterior (n=1 por defecto). No se usa el extremo en el momento en que ocurre.
- **Jerarquía:**
  - Nivel 1: STH / STL (short-term high/low)
  - Nivel 2: ITH / ITL — el máximo STH entre dos STL consecutivos; el mínimo STL entre dos STH consecutivos.
  - Nivel 3: LTH / LTL — aplicando la misma lógica sobre el nivel ITH/ITL.

### 3.2 BOS (Break of Structure)

- **Definición:** CIERRE de vela por encima del último STH/ITH/LTH (BOS alcista) o por debajo del último STL/ITL/LTL (BOS bajista).
- **Regla crítica:** una mecha que supera el nivel **NO** constituye BOS; es un sweep candidate (ver sección 6).
- **Implementación:** `bos_bull[i] = close[i] > last_swing_high[i-1]`; igual para bajista.

### 3.3 CHOCH (Change of Character)

- **Definición:** primer cierre confirmado en dirección contraria al swing **protegido** de la estructura predominante.
- **Distinción:**
  - **CHOCH interno:** se produce dentro del retroceso de la estructura principal; no confirma reversión definitiva.
  - **CHOCH externo:** se produce contra la estructura HTF; requiere displacement + BOS en la nueva dirección para considerarse reversión.
- **Regla:** un CHOCH en solitario no es suficiente para cambiar el sesgo operativo.
- `structure_bias` toma los valores: `"bullish"` / `"bearish"` / `"ranging"`.

---

## 4. Displacement [PARCIAL — DEC-008]

- **No existe un umbral fijo.** El displacement se cuantifica con un `displacement_score` en [0, 1].
- **Componentes del score (pesos iniciales, sujetos a ajuste):**
  | Componente | Descripción | Peso inicial |
  |------------|-------------|--------------|
  | body_range_ratio | \|C-O\| / (H-L) | 0.25 |
  | range_atr_ratio | (H-L) / ATR₁₄ | 0.30 |
  | close_position | posición del cierre en el rango | 0.20 |
  | speed_score | rango actual / rango medio reciente | 0.25 |
- **⚠️ PENDING PD-005b:** el umbral numérico que activa una señal válida. No usar en producción hasta aprobación.
- **⚠️ PENDING PD-005c:** número máximo de velas contrarias para agrupar como OB bloque.

---

## 5. Puntos de Interés (POI) [CONFIRMADO — DEC-009, DEC-010]

### 5.1 Tipos

Ambos activos e independientes:

**FVG (Fair Value Gap):**
- Alcista: `high(c1) < low(c3)` — gap entre barras c1 y c3, marcado en c3.
- Bajista: `low(c1) > high(c3)` — marcado en c3.
- `proximal` = extremo más cercano al precio actual; `distal` = extremo más alejado.

**Order Block:**
- Última vela contraria antes del impulso relevante que produce BOS/CHOCH.
- También se admite un grupo de velas contrarias consecutivas (tamaño: ⚠️ PENDING PD-005c).
- OB alcista: vela bajista antes de impulso alcista.
- OB bajista: vela alcista antes de impulso bajista.

### 5.2 Jerarquía de temporalidades

| Rol | Temporalidades |
|-----|----------------|
| Contexto | H4 |
| Identificación principal | H1 |
| Refinamiento | H1 / M30 |
| Ejecución | M15 |

No es obligatorio pasar por todos los niveles.

### 5.3 Estados del POI

```
fresh → touched → partially_mitigated → fully_mitigated → invalidated
```

Transiciones (para POI alcista con proximal=hi, distal=lo):
- `touched`: wick entra en la zona pero el cierre queda por encima del proximal.
- `partially_mitigated`: el cierre se produce dentro de la zona (distal < close < proximal).
- `fully_mitigated`: el wick alcanza el distal pero el close queda igual o por encima.
- `invalidated`: **cierre más allá del distal**. Para FVG: fill completo ≠ invalidación del OB asociado.

---

## 6. Liquidez [CONFIRMADO — DEC-011]

### 6.1 Niveles de liquidez

| Tipo | BSL (Buy-Side) | SSL (Sell-Side) |
|------|----------------|-----------------|
| Iguales | Equal Highs (EQH) | Equal Lows (EQL) |
| Swings | Swing Highs | Swing Lows |
| Prev Day | PDH (Prev Day High) | PDL (Prev Day Low) |
| Prev Week | PWH (Prev Week High) | PWL (Prev Week Low) |
| Sesión | Session High | Session Low |

Todos son **zonas inferidas de acción del precio**, no órdenes reales visibles en el libro.

### 6.2 Sweep — dos eventos separados

Los sweeps se registran como dos características independientes:

1. **sweep_candidate:** el wick supera el nivel (`high > BSL_level` para BSL; `low < SSL_level` para SSL).
2. **rejection_confirm:** el wick supera el nivel Y el cierre regresa al lado contrario (`high > level AND close < level` para BSL).

**Regla:** un `rejection_confirm` implica siempre un `sweep_candidate`, pero no al revés.

---

## 7. Fibonacci [CONFIRMADO — DEC-012]

### 7.1 Anclaje

- Último impulso relevante.
- **Alcista:** 0% = máximo del impulso (extremo), 100% = mínimo (origen).
- **Bajista:** 0% = mínimo del impulso (extremo), 100% = máximo (origen).

### 7.2 Niveles activos

`0%, 50%, 60%, 75%, 90%, 100%`

### 7.3 Zonas

| Zona | Rango | Estado |
|------|-------|--------|
| Fuera de zona | < 50% | No válida |
| Zona mínima de entrada | ≥ 50% | Válida |
| Zona preferida | 60% – 70% | Preferida |
| Zona de riesgo | 75% – 90% | Riesgo aumentado |
| Origen | 100% | Límite teórico |

---

## 8. Ejecución y gestión de riesgo [PARCIAL — DEC-013]

### 8.1 Entrada

- **Modo disponible:** conservador — esperar el cierre de la vela M15 y entrar al precio de apertura de la siguiente.
- **Modo intrabar:** requiere datos de tick (NO disponible con BI5 M1).

### 8.2 Stop Loss

- Colocado más allá de la referencia técnica que invalida la idea (más allá del POI o del swing estructural relevante).
- Riesgo: ~1% del capital de la cuenta.

### 8.3 Take Profit

- TP1 = 2R (normal).
- TP2 = 3R (cuando la estructura justifica el objetivo extendido).
- **⚠️ PENDING PD-017b:** porcentajes de cierre parcial en cada TP (qué fracción de la posición se cierra en TP1 vs TP2).

### 8.4 Breakeven

- **Tipo A:** mover SL a breakeven al alcanzar +1R. ✅ Implementable.
- **Tipo B:** mover SL a breakeven tras una consolidación post-entrada. **⚠️ PENDING PD-018b:** definición matemática de "consolidación" (número de velas / criterio de rango).

---

## 9. Costes de transacción [PARCIAL — DEC-015]

### 9.1 Comisión

- 5 USD/lote (especificación FTMO).
- **⚠️ PENDING PD-021b:** confirmar si aplica round-turn (operación completa) o por lado.
- Implementar como parámetro configurable `COMMISSION_ROUND_TURN` y `COMMISSION_PER_SIDE`.

### 9.2 Spread

| Escenario | Valor |
|-----------|-------|
| Optimista | 0.1 pips |
| Central (hipótesis de referencia) | 0.2 pips |
| Pesimista | 0.5 pips |

### 9.3 Slippage

| Escenario | Valor |
|-----------|-------|
| Base | 0.0 pips |
| Moderado | 0.1 pips |
| Alto | 0.2 pips |

### 9.4 Dirección de precios

- **BUY:** entrada a ASK (BID + spread), salida a BID.
- **SELL:** entrada a BID, salida a ASK (BID + spread).

### 9.5 Swap overnight

- Poco relevante para operativa < 90 min.
- **⚠️ PENDING PD-021c:** valores por lote/día para EUR/USD long y short.

---

## 10. Etiquetado para ML [CONFIRMADO — DEC-014]

### 10.1 Sistema B — filtro sobre setups Sistema A

| Etiqueta | Condición |
|----------|-----------|
| GOOD_SETUP | +2R antes que -1R dentro de 6 barras M15 (90 min) |
| BAD_SETUP | -1R antes que +2R dentro del mismo horizonte |
| UNRESOLVED | Ni TP ni SL alcanzados en el horizonte |
| AMBIGUOUS | TP y SL alcanzados en la misma barra M1 |

- Reconstrucción con datos M1 para precisión intrabar.
- Horizonte alternativo a explorar: 4 barras M15 (60 min).

### 10.2 Sistema C — clasificador M15 independiente

- **Universo:** todas las barras M15 en ventanas operativas (NO solo setups de Sistema A).
- **Etiquetas:** BUY / SELL / NO_TRADE.
- El modelo puede encontrar patrones que Sistema A no identifica.
- NO_TRADE no se asigna automáticamente; se infiere del contexto.

---

## 11. Reglas meta

1. **Reglas personales prevalecen** sobre convenciones educativas SMC cuando difieren.
2. Si una regla personal no está suficientemente especificada, **consultar antes de convertir a código**.
3. **No inventar parámetros** para que el código pueda ejecutarse.
4. **No declarar rentable** una estrategia sin evidencia fuera de muestra y supuestos de costes transparentes.
5. **No generar etiquetas finales** cuando dependan de parámetros PENDING no aprobados.
6. **No conectar brokers** ni ejecutar operaciones reales en ninguna fase.

---

## 12. Parámetros PENDING — no usar en producción

| Parámetro | Config | Decisión |
|-----------|--------|----------|
| `DISPLACEMENT_THRESHOLD` | `None` | PD-005b |
| `OB_GROUP_MAX_CANDLES` | `None` | PD-005c |
| `TP1_POSITION_PCT` | `None` | PD-017b |
| `TP2_POSITION_PCT` | `None` | PD-017b |
| `BE_CONSOLIDATION_DEF` | `None` | PD-018b |
| `COMMISSION_MODE` | configurable | PD-021b |
| `SWAP_LONG_USD` | `None` | PD-021c |
| `SWAP_SHORT_USD` | `None` | PD-021c |

Ver `docs/pending_decisions.md` para el detalle de cada pendiente.
