# Diccionario de datos — EUR/USD Trading Intelligence System

**Fuente:** Dukascopy Historical Data (BID, M1)  
**Instrumento:** EUR/USD  
**Período:** 2019-01-01 → 2026-10-16  
**Última actualización:** 2026-11-01

---

## 1. Datos raw (BI5)

### Formato del archivo BI5

| Campo    | Tipo binario | Posición | Descripción                                    |
|----------|-------------|----------|------------------------------------------------|
| ts       | uint32 BE   | 0        | Segundos desde medianoche UTC (0, 60, ..., 86340) |
| open     | uint32 BE   | 1        | Precio open × 100,000 (e.g., 113175 = 1.13175) |
| close    | uint32 BE   | 2        | **Precio close** × 100,000 (**no high** — ver nota) |
| low      | uint32 BE   | 3        | Precio low × 100,000                           |
| high     | uint32 BE   | 4        | **Precio high** × 100,000 (**no close** — ver nota) |
| volume   | float32 BE  | 5        | Volumen en lotes (tick volume BID)             |

> **NOTA CRÍTICA:** El orden binario de Dukascopy BI5 NO es OHLC canónico.  
> El campo en posición 2 es `close` y el campo en posición 4 es `high`.  
> Con el orden incorrecto (o,h,l,c) se producen ~2.5M violaciones OHLC en el dataset completo.  
> Con el orden correcto (o,c,l,h) se producen 0 violaciones.

### Estructura de directorios

```
data/raw/m1/{año}/{mes_0idx:02d}/{día:02d}/BID_candles_min_1.bi5
```

- Mes 0-indexado: `00` = enero, ..., `11` = diciembre
- Ejemplo: `data/raw/m1/2019/00/03/BID_candles_min_1.bi5` = 3 enero 2019
- Siempre 1440 registros por archivo (1 por minuto, 24 horas completas)
- Días no operativos (fines de semana, festivos): registros con OHLC idéntico

---

## 2. Dataset M1 procesado

**Archivo:** `data/processed/eurusd_m1_bid.parquet`  
**Registros:** 4,098,240 (2,846 días × 1,440 minutos)  
**Tamaño:** ~52.6 MB

| Columna      | Tipo              | Descripción                                                    |
|--------------|-------------------|----------------------------------------------------------------|
| datetime     | datetime64[ms, UTC] | Timestamp UTC del inicio del minuto                          |
| open         | float64           | Precio de apertura (BID)                                      |
| high         | float64           | Precio máximo del minuto (BID)                                |
| low          | float64           | Precio mínimo del minuto (BID)                                |
| close        | float64           | Precio de cierre (BID)                                        |
| volume       | float64           | Volumen de ticks BID (no es volumen real negociado)           |
| is_flat_day  | bool              | True si el día completo es no operativo (OHLC idéntico)       |

### Invariantes garantizados (registros activos, is_flat_day=False)
- `high >= open`
- `high >= close`
- `high >= low`
- `low <= open`
- `low <= close`
- `0.8 < precio < 2.0` (rango histórico EUR/USD)
- `volume >= 0`

---

## 3. Datasets multi-temporalidad

Construidos mediante resample OHLCV desde M1. Alineados a medianoche UTC.

| Archivo                         | TF   | Registros  | Barras activas | Tamaño  |
|---------------------------------|------|-----------|----------------|---------|
| eurusd_m15_bid.parquet          | M15  | 273,216   | 234,048        | ~5.4 MB |
| eurusd_h1_bid.parquet           | H1   | 68,304    | 58,512         | ~1.8 MB |
| eurusd_h4_bid.parquet           | H4   | 17,076    | 14,628         | ~0.6 MB |
| eurusd_d1_bid.parquet           | D1   | 2,846     | 2,438          | ~0.1 MB |
| eurusd_w1_bid.parquet           | W1   | 407       | 407            | ~0.0 MB |
| eurusd_mn_bid.parquet           | MN   | 94        | 94             | ~0.0 MB |

### Columnas de temporalidades superiores

| Columna          | Tipo              | Descripción                                              |
|------------------|-------------------|----------------------------------------------------------|
| datetime         | datetime64[ms, UTC] | Inicio del período (label='left')                      |
| open             | float64           | Open del primer M1 del período                          |
| high             | float64           | Máximo de todos los highs M1 del período                |
| low              | float64           | Mínimo de todos los lows M1 del período                 |
| close            | float64           | Close del último M1 del período                         |
| volume           | float64           | Suma de todos los volúmenes M1 del período              |
| is_flat_period   | bool              | True si TODOS los M1 del período tienen is_flat_day=True |

---

## 4. Divisiones temporales

| Período     | Rango                     | Uso                            |
|-------------|---------------------------|--------------------------------|
| Warmup      | 2019-01-01 – 2019-12-31   | Calentamiento, no se modela    |
| Train       | 2020-01-01 – 2024-12-31   | Entrenamiento de modelos       |
| Validation  | 2025-01-01 – 2025-12-31   | Selección y tuning de modelos  |
| Test        | 2026-01-01 – 2026-10-16   | Evaluación final (hold-out)    |

---

## 5. Notas sobre volumen

El volumen en datos BID de Dukascopy representa **tick volume** (número de actualizaciones de precio), NO volumen real negociado. EUR/USD es OTC y no tiene un mercado centralizado con volumen verificable. El volumen debe interpretarse como una proxy de actividad/liquidez relativa.

---

## 6. Notas sobre spread y costes

Los datos son exclusivamente **BID**. No existe spread ASK histórico verificable en este dataset. Para el backtest, los supuestos de spread y slippage se modelarán como escenarios de sensibilidad (ver `docs/pending_decisions.md`, PD-021).
