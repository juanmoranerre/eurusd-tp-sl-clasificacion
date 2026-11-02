# Log de decisiones técnicas

**Formato:** `[FECHA] — ID — Decisión tomada → Consecuencias`

---

## 2026-11-01

### DEC-001 — Corrección del orden de campos BI5
**Decisión:** El formato Dukascopy BI5 almacena los campos en el orden `(ts, open, close, low, high, volume)`, no `(ts, open, high, low, close, volume)`.  
**Evidencia:**
- Con el orden incorrecto (o,h,l,c): 1,330 de 1,440 registros del 2019-01-03 tenían `close > high`.
- Con el orden correcto (o,c,l,h): 0 violaciones OHLC en 3,510,720 registros activos del dataset completo.
- El test anterior (`test_bid_data_can_have_close_above_high`) fue modificado para aceptar este comportamiento erróneo.
**Acción:** Corregido `_RECORD_DTYPE` en `src/data/parser_bi5.py`. Backup del parquet incorrecto como `eurusd_m1_bid_BACKUP_wrong_ohlc.parquet`. Parquet regenerado con datos correctos.  
**Consecuencias:** Todos los valores de `KNOWN_HIGH` y `KNOWN_CLOSE` en tests y scripts actualizados. 68 tests pasan con los invariantes OHLC completos.

### DEC-002 — Timestamp BI5 en segundos (no milisegundos)
**Decisión:** El campo `ts` del BI5 de Dukascopy M1 contiene **segundos** desde medianoche UTC (0, 60, 120, ..., 86340), no milisegundos.  
**Evidencia:** Los timestamps 0, 60, 120, ... corresponden a 00:00, 00:01, 00:02, ... y el último es 86340 = 23×3600+59×60.  
**Consecuencias:** La reconstrucción de datetime usa `pd.to_timedelta(arr["ts_s"], unit="s")`. Confirmado en test `test_second_record_is_60s_later`.

### DEC-003 — División temporal del proyecto
**Decisión:** División temporal aprobada en el master prompt (sección 12):
- 2019: calentamiento (warmup)
- 2020–2024: entrenamiento
- 2025: validación y optimización  
- 2026: test final (hasta 2026-10-16)
**Consecuencias:** Ninguna división aleatoria. Walk-forward validation dentro del período de entrenamiento.

### DEC-004 — Alineación temporal de temporalidades superiores
**Decisión:** Todas las temporalidades superiores (M15, H1, H4, D1, W1, MN) se alinean a medianoche UTC con `label='left'` (etiqueta = inicio del período).  
**Razonamiento:** La etiqueta de inicio del período garantiza que no se usa información futura: el dato de la barra solo está disponible cuando cierra, es decir, al inicio del período siguiente.  
**Consecuencias:** W1 usa `1W` (pandas: semana ending Sunday, label=Monday), MN usa `1ME` (month-end).

### DEC-005 — Métrica de referencia principal del modelo
**Decisión:** Macro F1 como métrica de referencia principal para la evaluación de modelos de clasificación.  
**Razonamiento:** Equilibra el rendimiento entre clases desequilibradas (BUY, SELL, NO_TRADE) sin penalizar desproporcionalmente la clase mayoritaria.  
**Consecuencias:** Optuna optimizará sobre Macro F1 durante el tuning. AUC-ROC OvR y PR-AUC como métricas secundarias.

---

*Las decisiones pendientes de aprobación del trader están en `docs/pending_decisions.md`.*
