# Especificación de la estrategia EUR/USD

**Estado:** Borrador inicial — elementos CONFIRMADOS marcados, resto PENDIENTE  
**Última actualización:** 2026-11-01  
**Referencia:** Master prompt secciones 2.1–2.11, videos 1 y 2

---

## 1. Visión general

La estrategia es una metodología de Smart Money Concepts (SMC) aplicada a EUR/USD que identifica oportunidades en base a:

1. Contexto direccional multitemporal
2. Movimientos impulsivos (displacement)
3. Puntos de interés (POI)
4. Liquidez previa
5. Confirmación estructural (BOS/CHOCH)
6. Ejecución en ventanas de sesión

---

## 2. Temporalidades [CONFIRMED]

| TF     | Rol                                    |
|--------|----------------------------------------|
| MN     | Contexto macro                         |
| W1     | Estructura y dirección de mercado      |
| H4     | Contexto intermedio                    |
| H1     | Confirmación y análisis estructural    |
| M15    | Temporalidad principal de observación  |
| M1     | Reconstrucción post-entrada y SL/TP    |

La información de cada vela HTF solo está disponible cuando esa vela ha **cerrado completamente**.

---

## 3. Sesiones operativas [CONFIRMED: zonas horarias] [PENDING: horas exactas]

- **Apertura de Londres** — zona `Europe/London` (DST automático) — horas exactas PENDIENTE (PD-001)
- **Apertura de Nueva York** — zona `America/New_York` (DST automático) — horas exactas PENDIENTE (PD-001)

---

## 4. Análisis de contexto y direccionalidad [PARTIAL]

### Elementos a identificar [CONFIRMED: concepto]
- Dirección predominante en W1 y H4
- Secuencia de máximos y mínimos relevantes (Higher Highs / Higher Lows o Lower Highs / Lower Lows)
- Rangos y consolidaciones
- Rupturas estructurales

### Definición matemática de swing high/low [PENDING: PD-002]
El lookback para identificar máximos y mínimos relevantes debe confirmarse.

---

## 5. Momentum y displacement [PARTIAL]

### Elementos a estudiar [CONFIRMED: concepto]
- Intensidad del movimiento (magnitud vs. rango reciente)
- Dirección del desplazamiento
- Velas que componen el impulso
- Últimas velas contrarias antes del impulso
- Velocidad del desplazamiento
- Rupturas estructurales asociadas

### Umbral matemático de displacement [PENDING: PD-005]
El criterio cuantitativo para identificar un movimiento como "impulsivo" debe confirmarse.

### Velas contrarias mínimas [PENDING: PD-006]
El número mínimo de velas contrarias antes del impulso debe confirmarse.

---

## 6. Punto de Interés (POI) [PARTIAL]

### Definición conceptual [CONFIRMED: referencia video 2]
Zona del precio donde se originó un movimiento impulsivo y hacia donde el precio podría regresar para reaccionar.

### Tipo de estructura (FVG vs. Order Block) [PENDING: PD-007]
La diferencia entre imbalance, FVG y Order Block en la operativa del trader debe formalizarse.

### Temporalidad de identificación [PENDING: PD-008]
La TF de identificación inicial del POI debe confirmarse.

### Refinamiento del POI [PENDING: PD-009]
El método de refinamiento (TF de refinamiento + criterio de delimitación) debe confirmarse.

### Invalidación del POI [PENDING: PD-010]
El criterio de invalidación del POI debe confirmarse.

---

## 7. Liquidez previa [PARTIAL]

### Elementos a identificar [CONFIRMED: referencia video 2]
- Máximos y mínimos relevantes anteriores
- Buy-side liquidity (por encima de máximos)
- Sell-side liquidity (por debajo de mínimos)
- Sweeps (barridos de liquidez)
- Recuperación tras el sweep

### Definición de liquidez relevante [PENDING: PD-011]
Qué estructuras se consideran "liquidez" en la metodología del trader.

### Condición de sweep confirmado [PENDING: PD-012]
Qué constituye un sweep válido (vs. simple toque).

---

## 8. Confirmación [PARTIAL]

### Conceptos [CONFIRMED: referencia video 2]
El video 2 muestra anotaciones de BOS y CHOCH como elementos de confirmación estructural tras la llegada al POI.

### BOS (Break of Structure) [PENDING: PD-003]
La condición exacta para que una ruptura sea BOS debe confirmarse.

### CHOCH (Change of Character) [PENDING: PD-004]
La distinción entre CHOCH y BOS en la metodología del trader debe formalizarse.

---

## 9. Fibonacci [PARTIAL]

### Referencia [CONFIRMED: video 1]
El video 1 muestra una herramienta de retroceso Fibonacci con múltiples niveles y más de un TP.

### Niveles [CONFIRMED]
```
0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0
```

### Anclaje [PENDING: PD-013]
El punto exacto de anclaje del Fibonacci (swing origen y swing final) debe confirmarse.

### Zona de entrada [PENDING: PD-014]
Los niveles Fibonacci que definen la zona de entrada válida deben confirmarse.

---

## 10. Ejecución [PENDING]

- Precio de entrada [PENDING: PD-015]
- Stop Loss [PENDING: PD-016]
- Take Profit(s) múltiples [PENDING: PD-017]
- Regla de gestión / mover SL [PENDING: PD-018]

---

## 11. Secuencia operativa conceptual [CONFIRMED: estructura]

```
1. Analizar contexto HTF (W1, H4)
2. Determinar dirección predominante
3. Evaluar momentum y displacement
4. Identificar un punto de interés (POI)
5. Refinar el POI en TF inferior
6. Verificar liquidez previa (sweep confirmado o por confirmar)
7. Esperar que el precio regrese a la zona
8. Esperar confirmación (BOS / CHOCH)
9. Evaluar Fibonacci cuando corresponda
10. Ejecutar en M15
11. Gestionar SL y múltiples TP
```

Esta secuencia representa la estructura conceptual. Las reglas matemáticas exactas de cada paso están PENDIENTES de aprobación.

---

## 12. Lo que NO está confirmado

Los siguientes parámetros NO deben usarse en producción hasta aprobación explícita:
- Lookback de swings
- Umbral de displacement
- Tipo de POI (FVG / OB)
- TF de identificación y refinamiento del POI
- Tipo de liquidez y condición de sweep
- Tipo de confirmación exigida
- Anclaje y zona de entrada Fibonacci
- Precio de entrada, SL, TP1 y TP2
- Horas exactas de sesiones
- Costes y spread

Ver `docs/pending_decisions.md` para el listado completo con alternativas y recomendaciones.
