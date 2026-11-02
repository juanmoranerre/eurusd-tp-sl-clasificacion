# Decisiones pendientes de aprobación del trader

**Última actualización:** 2026-11-01
**Estado:** Las decisiones PD-001 a PD-021 han sido respondidas. Las siguientes sub-decisiones siguen pendientes.

---

## PENDIENTES TRAS LAS RESPUESTAS DE 2026-11-01

### PD-005b: Umbral del displacement_score
**Qué falta:** El valor numérico sobre el displacement_score que activa una señal válida.
**Bloqueado:** El trader pidió ver alternativas antes de fijar el umbral.
**Acción:** Implementar displacement_score; presentar distribución histórica al trader.

### PD-017b: Porcentajes de cierre parcial por TP
**Qué falta:** Qué fracción de la posición se cierra en TP1 vs TP2.
**Bloqueado:** El trader confirmó que existen múltiples TPs pero dejó los % pendientes.
**Acción:** Implementar backtester con % configurables en None; no simular hasta confirmar.

### PD-018b: Definición matemática de "consolidación" para BE tipo B
**Qué falta:** Cuántas velas / qué patrón constituye una "consolidación" a efectos de mover el SL.
**Bloqueado:** El trader confirmó el concepto pero dejó la definición matemática pendiente.
**Acción:** Implementar BE tipo A; dejar BE tipo B como stub hasta confirmación.

### PD-021b: Comisión FTMO — round-turn vs por lado
**Qué falta:** Confirmar si los 5 USD/lote se aplican por lado o round-turn.
**Bloqueado:** El trader pidió testar ambas interpretaciones.
**Acción:** Implementar como parámetro configurable; NO usar un valor único.

### PD-021c: Swap overnight
**Qué falta:** Valor de swap por lote/día para EUR/USD long y short.
**Bloqueado:** Poco relevante para operativa <90 min, pero registrar si aparece.
**Acción:** Mantener como None hasta que sea necesario.

### PD-005c: Número mínimo de velas contrarias para OB como grupo
**Qué falta:** ¿Cuántas velas consecutivas contrarias se agrupan como bloque?
**Bloqueado:** El trader indicó que el mínimo es la última vela contraria, pero el agrupamiento queda abierto.
**Acción:** Implementar con identificación de la última vela + lógica de agrupamiento opcional.

---

*Las decisiones PD-001 a PD-021 originales han sido respondidas. Ver docs/decisions_log.md (DEC-006 a DEC-015).*
