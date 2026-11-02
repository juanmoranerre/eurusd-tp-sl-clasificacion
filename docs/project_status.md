# Estado del proyecto — EUR/USD Trading Intelligence System

**Última actualización:** 2026-11-01  
**Rama activa:** development

---

## Resumen ejecutivo

| Fase   | Descripción                      | Estado         |
|--------|----------------------------------|----------------|
| FASE 0 | Auditoría y correcciones         | ✅ COMPLETADA   |
| FASE 1 | Data Engineering                 | ✅ COMPLETADA   |
| FASE 2 | Strategy Spec + Feature Eng.     | 🔵 EN PROGRESO  |
| FASE 3 | Baseline determinista (Sistema A) | ⬜ PENDIENTE   |
| FASE 4 | Modelo B (filtro setups)         | ⬜ PENDIENTE    |
| FASE 5 | Modelo C (clasificador M15)      | ⬜ PENDIENTE    |
| FASE 6 | Comparación A/B/C                | ⬜ PENDIENTE    |
| FASE 7 | Entrega final                    | ⬜ PENDIENTE    |

---

## FASE 0 — Completada ✅

### Auditoría del parser BI5
- **BUG CRÍTICO ENCONTRADO Y CORREGIDO:** El parser original tenía intercambiados los campos `high` y `close` en el registro BI5.
  - Orden incorrecto (o,h,l,c): 2,488,544 violaciones OHLC en el dataset completo (71% de registros activos)
  - Orden correcto (o,c,l,h): 0 violaciones OHLC
- Backup del parquet incorrecto: `data/processed/eurusd_m1_bid_BACKUP_wrong_ohlc.parquet`
- Parquet correcto regenerado: `data/processed/eurusd_m1_bid.parquet`
- Tests modificados para reflejar los valores correctos (KNOWN_HIGH y KNOWN_CLOSE actualizados)
- Tests que "aceptaban" violaciones OHLC reemplazados por tests de invariantes correctos

### Infraestructura del proyecto
- Estructura de directorios creada (config/, src/features/, src/strategy/, etc.)
- `config/settings.py` — configuración global con divisiones temporales
- `config/data_config.py` — rutas de archivos de datos
- `config/strategy_config.py` — parámetros de estrategia (CONFIRMED + PENDING)
- `config/model_config.py` — configuración de modelos ML

### Git
- Repositorio inicializado en `main`
- Rama `development` creada
- Remote `origin` configurado: `https://github.com/juanmoranerre/eurusd-tp-sl-clasificacion.git`
- Primer commit publicado en `development`

---

## FASE 1 — Completada ✅

### Dataset M1
- **4,098,240 registros** (2,846 días × 1,440 minutos)
- Período: 2019-01-01 → 2026-10-16
- 0 errores de carga, 0 archivos corruptos
- Columnas: datetime (UTC), open, high, low, close, volume, is_flat_day

### Multi-temporalidades construidas
| TF   | Barras    | Activas   | Planas  | Archivo                     |
|------|-----------|-----------|---------|----------------------------|
| M15  | 273,216   | 234,048   | 39,168  | eurusd_m15_bid.parquet     |
| H1   | 68,304    | 58,512    | 9,792   | eurusd_h1_bid.parquet      |
| H4   | 17,076    | 14,628    | 2,448   | eurusd_h4_bid.parquet      |
| D1   | 2,846     | 2,438     | 408     | eurusd_d1_bid.parquet      |
| W1   | 407       | 407       | 0       | eurusd_w1_bid.parquet      |
| MN   | 94        | 94        | 0       | eurusd_mn_bid.parquet      |

- **0 violaciones OHLC en todas las temporalidades**
- Todos los tests pasan (111 tests en total)

---

## FASE 2 — En progreso 🔵

### Completado
- `docs/strategy_specification.md` — especificación inicial con elementos CONFIRMED/PENDING
- `docs/pending_decisions.md` — 21 decisiones pendientes de aprobación del trader (PD-001 a PD-021)

### Pendiente (requiere decisiones del trader)
- Definición matemática de swings (PD-002)
- Umbral de displacement (PD-005)
- Tipo de POI (FVG vs. Order Block, PD-007)
- TF de identificación y refinamiento del POI (PD-008, PD-009)
- Condiciones de liquidez y sweep (PD-011, PD-012)
- Definición de BOS/CHOCH (PD-003, PD-004)
- Anclaje Fibonacci y zona de entrada (PD-013, PD-014)
- Sesiones operativas: horas exactas (PD-001)
- Ejecución: entrada, SL, TP (PD-015, PD-016, PD-017, PD-018)
- Etiquetado ML (PD-019, PD-020)
- Costes y spread (PD-021)

---

## Tests ejecutados

| Módulo               | Tests | Estado    |
|----------------------|-------|-----------|
| test_parser_bi5.py   | 68    | ✅ 68/68  |
| test_loader.py       | 28    | ✅ 28/28  |
| test_resampler.py    | 43    | ✅ 43/43  |
| **TOTAL**            | **139** | **✅ 139/139** |

---

## Errores conocidos / Resueltos

| Error                          | Estado    | Referencia    |
|--------------------------------|-----------|---------------|
| Bug OHLC parser BI5            | ✅ Resuelto | DEC-001       |
| Tests adaptados para bug       | ✅ Corregidos | DEC-001     |

---

## Próximos pasos

1. **Inmediato:** El trader responde las decisiones agrupadas (PD-001 a PD-021)
2. **Tras PD-001:** Implementar filtros de sesión en features
3. **Tras PD-002 a PD-006:** Implementar estructura de mercado y swings
4. **Tras PD-007 a PD-010:** Implementar POI y refinamiento
5. **Tras PD-011 a PD-018:** Implementar motor determinista (Sistema A) y backtester
6. **Tras PD-019 a PD-020:** Generar etiquetas y entrenar Sistemas B y C

---

## Archivos del proyecto

```
proyecto final lae/
├── config/               ✅ settings.py, data_config.py, strategy_config.py, model_config.py
├── src/data/             ✅ parser_bi5.py, loader.py, resampler.py
├── src/features/         ⬜ pendiente
├── src/strategy/         ⬜ pendiente
├── src/backtesting/      ⬜ pendiente
├── src/models/           ⬜ pendiente
├── src/evaluation/       ⬜ pendiente
├── src/visualization/    ⬜ pendiente
├── tests/                ✅ test_parser_bi5.py, test_loader.py, test_resampler.py
├── scripts/              ✅ build_dataset.py, build_multitf.py
├── docs/                 ✅ todos los archivos de documentación
├── data/processed/       ✅ M1 + M15, H1, H4, D1, W1, MN parquets
└── data/raw/m1/          ✅ 2846 archivos BI5 (2019-2026)
```
