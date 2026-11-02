# Decisiones pendientes de aprobación del trader

**Última actualización:** 2026-11-01  
**Estado:** Este documento agrupa todas las preguntas que requieren la aprobación del trader antes de ser incorporadas como reglas matemáticas definitivas.

---

## BLOQUE 1 — Sesiones operativas (Sección 2.10)

### PD-001: Horas exactas de las sesiones
**Qué falta:** Los límites horarios exactos de las ventanas operativas.  
**Por qué importa:** El universo de decisiones M15 del Sistema C (Modelo C) y las features de sesión dependen directamente de estos horarios.

**Opciones:**
- A. **Londres:** 07:00–10:00 London time | **Nueva York:** 13:30–16:30 New York time (ventanas de máxima liquidez)
- B. **Londres:** 07:00–12:00 London time | **Nueva York:** 13:00–17:00 New York time (ventanas más amplias)
- C. Definición personalizada del trader

**Recomendación:** Opción A (ventanas cortas de alta liquidez) como punto de partida.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 2 — Estructura de mercado y máximos/mínimos (Sección 2.2)

### PD-002: Definición de swing high / swing low
**Qué falta:** El lookback exacto para identificar máximos y mínimos relevantes.  
**Por qué importa:** Determina qué estructuras se consideran "relevantes" para el análisis HTF.

**Opciones:**
- A. N velas a cada lado (parámetro configurable, ej. N=5 en M15)
- B. Fractal Williams (2 velas a cada lado)
- C. Pivot clásico (1 barra anterior y posterior)
- D. Lookback variable por temporalidad

**Recomendación:** Opción A con N ajustable. Proponer N=5 para H1, N=3 para M15 como valores iniciales.  
**Pendiente de:** Confirmación del trader.

### PD-003: Definición de BOS (Break of Structure)
**Qué falta:** Condiciones exactas para que una ruptura sea BOS.  
**Por qué importa:** Determina el cambio de sesgo/dirección en el análisis estructural.

**Opciones:**
- A. Cierre de vela por encima/debajo del swing previo
- B. Precio que toca el nivel del swing previo (sin necesidad de cierre)
- C. Cierre confirmado + retest del nivel roto

**Recomendación:** Opción A (cierre de vela) por mayor robustez estadística.  
**Pendiente de:** Confirmación del trader.

### PD-004: Definición de CHOCH (Change of Character)
**Qué falta:** Distinguir CHOCH de BOS en la metodología del trader.  
**Por qué importa:** La diferencia entre CHOCH y BOS afecta las señales de entrada.

**Opciones:**
- A. CHOCH = primera rotura contraria a la tendencia dominante (inicio de cambio)
- B. CHOCH = BOS confirmado + segundo BOS en la nueva dirección
- C. CHOCH = solo ruptura de MSB (Market Structure Break) en TF superior

**Recomendación:** Opción A como definición inicial.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 3 — Momentum y Displacement (Sección 2.3)

### PD-005: Umbral de displacement / movimiento impulsivo
**Qué falta:** El criterio matemático para distinguir un movimiento impulsivo de uno normal.  
**Por qué importa:** Define qué movimientos son candidatos a originar un POI válido.

**Opciones:**
- A. Desplazamiento > N × ATR(14) en la TF de análisis
- B. Amplitud de la vela > percentil 90 de los últimos M velas
- C. Combinación de amplitud + número de velas consecutivas en la misma dirección
- D. Umbral fijo en pips

**Recomendación:** Opción A con N=1.5 y ATR(14) en M15 como punto de partida.  
**Pendiente de:** Confirmación del trader.

### PD-006: Número mínimo de velas contrarias antes del impulso
**Qué falta:** Cuántas velas contrarias son necesarias para considerar que hubo una acumulación antes del impulso.  
**Por qué importa:** Parte del análisis del origen del movimiento (sección 2.3).

**Opciones:**
- A. Mínimo 2 velas contrarias en la TF de análisis
- B. Mínimo 3 velas contrarias
- C. Sin restricción numérica, solo estructura visual

**Recomendación:** Opción A como mínimo.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 4 — Punto de Interés (POI) (Sección 2.4 y 2.5)

### PD-007: Definición de POI — ¿FVG, Order Block o zona libre?
**Qué falta:** Qué estructuras constituyen un POI válido en la metodología del trader.  
**Por qué importa:** El POI es el elemento central de la estrategia y su definición incorrecta invalida todos los setups.

**Opciones:**
- A. FVG (Fair Value Gap): imbalance de 3 velas (gap entre extremos de velas 1 y 3)
- B. Order Block: última vela contraria antes del impulso
- C. Ambos (jerarquía a definir)
- D. Zona compuesta (primera vela del impulso como referencia)

**Recomendación:** Presentar análisis con ambos (A y B) y compararlos con el video.  
**Pendiente de:** Confirmación del trader tras análisis conjunto.

### PD-008: Temporalidad de identificación del POI
**Qué falta:** ¿En qué TF se identifica el POI inicial?  
**Por qué importa:** El video muestra NAS100 pero no especifica la TF exacta.

**Opciones:**
- A. H1 como TF de identificación, M15 de refinamiento
- B. H4 como TF de identificación, H1 de refinamiento
- C. Depende del contexto macro (HTF determina la TF de análisis)

**Recomendación:** Opción A como punto de partida.  
**Pendiente de:** Confirmación del trader.

### PD-009: Criterio de refinamiento del POI
**Qué falta:** Cómo se reduce la zona inicial a una zona refinada.  
**Por qué importa:** La precisión de la entrada depende del refinamiento.

**Opciones:**
- A. Bajar una TF (H1 → M15) y buscar el FVG / Order Block en esa TF dentro de la zona original
- B. Usar el 50% interior de la zona original
- C. Usar los extremos de la vela o conjunto de velas que originan el POI en TF inferior

**Recomendación:** Opción A.  
**Pendiente de:** Confirmación del trader.

### PD-010: Criterio de invalidación del POI
**Qué falta:** Qué hace que una zona deje de ser válida.  
**Por qué importa:** Evita operar sobre zonas ya mitigadas o invalidadas.

**Opciones:**
- A. Precio cierra por encima del límite superior (para POI alcista) / por debajo del inferior (para POI bajista)
- B. Precio penetra N pips más allá del extremo de la zona
- C. Se produce un número de toques > N (zona "desgastada")

**Recomendación:** Opción A como condición necesaria, Opción C como condición adicional.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 5 — Liquidez (Sección 2.6)

### PD-011: Definición de liquidez relevante
**Qué falta:** Qué estructuras se consideran "liquidez" en la metodología del trader.  
**Por qué importa:** La liquidez previa es una condición del setup.

**Opciones:**
- A. Solo máximos/mínimos anteriores obvios (highs y lows de sesión)
- B. Iguales o dobles toques de un nivel (equal highs / equal lows)
- C. Ambos tipos

**Recomendación:** Opción C con análisis estadístico de cuál predice mejor.  
**Pendiente de:** Confirmación del trader.

### PD-012: Condición de sweep confirmado
**Qué falta:** Qué constituye una captura de liquidez confirmada (vs. simple toque).  
**Por qué importa:** El sweep es condición previa al setup en la metodología.

**Opciones:**
- A. Precio toca el nivel de liquidez + vela cierra de vuelta al lado contrario (wick sweep)
- B. Precio supera el nivel por ≥ N pips + retorna en la misma barra
- C. Cierre por encima + cierre posterior de vuelta

**Recomendación:** Opción A como criterio principal.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 6 — Fibonacci (Sección 2.9)

### PD-013: Punto de anclaje del Fibonacci
**Qué falta:** Desde dónde a dónde se traza la herramienta Fibonacci.  
**Por qué importa:** Los niveles de entrada dependen del anclaje correcto.

**Opciones:**
- A. Desde el swing low del movimiento impulsivo hasta el swing high (en tendencia alcista) — o viceversa
- B. Desde el origen del POI (última vela contraria) hasta el extreme del impulso
- C. Desde el inicio del movimiento de retroceso hasta el extreme

**Recomendación:** Opción A como interpretación estándar de SMC.  
**Pendiente de:** Confirmación del trader con referencia al video 1.

### PD-014: Zona de entrada Fibonacci
**Qué falta:** Qué niveles Fibonacci definen la zona de entrada válida.  
**Por qué importa:** Determina cuándo se considera que el precio ha llegado a la zona.

**Opciones:**
- A. 0.5 – 0.618 (zona OTE clásica)
- B. 0.618 – 0.786 (zona profunda)
- C. 0.382 – 0.5 (zona superficial)
- D. Zona personalizada del trader

**Recomendación:** Opción A como punto de partida.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 7 — Ejecución y gestión (Secciones 8 y 9)

### PD-015: Precio de entrada exacto
**Qué falta:** ¿La entrada es al cierre de la vela de confirmación, al inicio de la siguiente, o en el POI?  
**Por qué importa:** El precio de entrada afecta directamente el cálculo de R y el resultado real.

**Opciones:**
- A. Open de la vela siguiente al cierre de la vela de confirmación
- B. Close de la vela de confirmación
- C. Al llegar al POI (límite order)
- D. Al cierre de una vela de confirmación en M1

**Recomendación:** Opción A (open siguiente vela M15) para evitar lookahead.  
**Pendiente de:** Confirmación del trader.

### PD-016: Stop Loss
**Qué falta:** Ubicación exacta del SL.  
**Por qué importa:** El SL define el riesgo real y la ratio R de cada operación.

**Opciones:**
- A. Por debajo del mínimo del POI refinado (para BUY) / por encima del máximo (para SELL)
- B. Por debajo/encima del swing previo más cercano
- C. N pips más allá del extremo del POI

**Recomendación:** Opción A con N pips de margen a confirmar.  
**Pendiente de:** Confirmación del trader.

### PD-017: Take Profit(s) múltiples
**Qué falta:** Número de TPs, niveles y distribución de posición.  
**Por qué importa:** El video muestra explícitamente más de un TP.

**Opciones:**
- A. TP1 = máximo/mínimo previo (primer objetivo de liquidez), TP2 = extensión 1.618 Fibonacci
- B. TP1 = nivel Fibonacci 1.0, TP2 = nivel 1.618
- C. TP1 y TP2 a confirmar con el video

**Recomendación:** Opción A como estructura inicial.  
**Distribución de posición:** 50%/50% o 60%/40% — pendiente de confirmación.  
**Pendiente de:** Confirmación del trader.

### PD-018: Regla de mover Stop Loss
**Qué falta:** ¿Cuándo y adónde se mueve el SL?  
**Por qué importa:** El breakeven afecta al resultado de operaciones que llegan a TP1.

**Opciones:**
- A. Mover a breakeven al alcanzar TP1 (y cerrar el 50%)
- B. Mover a breakeven inmediatamente al entrar (si el precio se aleja N pips)
- C. Solo mover tras confirmación adicional de estructura

**Recomendación:** Opción A.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 8 — Etiquetado ML (Secciones 9 y 10)

### PD-019: Horizonte y parámetros de etiquetado Sistema B (filtro setups)
**Qué falta:** Cómo se clasifica GOOD_SETUP vs BAD_SETUP.  
**Por qué importa:** Sin etiquetas aprobadas no se puede entrenar el Sistema B.

**Propuesta:**
- Resultado se determina por M1 posterior a la entrada
- GOOD_SETUP: TP1 alcanzado antes que SL
- BAD_SETUP: SL alcanzado antes que TP1
- AMBIGUOUS: ni TP ni SL alcanzados en el horizonte definido

**Parámetros a confirmar:** TP pips, SL pips, horizonte en barras M1.  
**Pendiente de:** Confirmación del trader.

### PD-020: Etiquetado Sistema C (BUY / SELL / NO_TRADE)
**Qué falta:** Cómo se asignan las etiquetas en momentos de decisión M15.  
**Por qué importa:** Sin etiquetas aprobadas no se puede entrenar el Sistema C.

**Propuesta (Triple Barrier Method):**
- Desde cada M15 de decisión, observar el precio durante H barras M15
- BUY si el precio sube N pips antes de caer M pips
- SELL si el precio baja M pips antes de subir N pips
- NO_TRADE si no se alcanza ningún umbral en el horizonte

**Parámetros a confirmar:** N pips, M pips, H barras, relación TP/SL.  
**Pendiente de:** Confirmación del trader.

---

## BLOQUE 9 — Costes y ejecución (Sección 13)

### PD-021: Supuestos de spread, slippage y comisiones
**Qué falta:** Valores de coste para el backtest.  
**Por qué importa:** Sin costes, el backtest no es realista. Los datos son solo BID.

**Opciones:**
- A. Spread histórico promedio EUR/USD: 0.5 pips (favorable)
- B. Spread conservador: 1.0–1.5 pips
- C. Sin costes (backtest bruto) + análisis de sensibilidad con 0.5, 1.0, 2.0 pips

**Recomendación:** Opción C — reportar resultados brutos + sensibilidad explícita.  
**Pendiente de:** Confirmación del trader.

---

*Cada bloque debe resolverse antes de implementar los módulos que dependen de él.*  
*Las respuestas se registrarán en `docs/decisions_log.md` con fecha y consecuencias.*
