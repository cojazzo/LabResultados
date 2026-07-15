---
name: laboratory-automation
description: >
  Guía al agente en el diseño de automatizaciones para contextos de laboratorio
  clínico. Se activa cuando una automatización involucre pacientes, órdenes,
  muestras, resultados, reportes, alertas, inventario, tiempos de respuesta
  o notificaciones del laboratorio. Establece límites claros entre la
  aplicación principal (fuente de verdad) y n8n (capa de integración).
  Prohíbe que n8n valide, corrija, autorice o elimine datos clínicos.
triggers:
  - paciente
  - orden de laboratorio
  - muestra
  - resultado clínico
  - reporte de laboratorio
  - alerta de laboratorio
  - inventario de laboratorio
  - tiempo de respuesta
  - notificación de laboratorio
  - automatización clínica
  - resultado crítico
  - flujo de laboratorio
---

# Skill: Laboratory Automation

## Propósito

Garantizar que las automatizaciones de laboratorio clínico cumplan con los
principios de seguridad, privacidad, trazabilidad y responsabilidad clínica
apropiados para el manejo de información de salud.

## Principios Fundamentales (No Negociables)

### 1. La aplicación principal es la fuente de verdad

- **LabResultados** (backend FastAPI + PostgreSQL) es la única fuente de
  verdad para datos clínicos.
- n8n no almacena ni modifica datos clínicos. Solo los lee, transforma y
  orquesta notificaciones o integraciones.
- Cualquier lectura de datos clínicos debe realizarse mediante la API de
  LabResultados con autenticación apropiada.

### 2. n8n es exclusivamente una capa de integración y orquestación

**n8n PUEDE:**
- Recibir eventos de LabResultados mediante webhooks o polling.
- Enrutar notificaciones (email, WhatsApp) con información mínima.
- Coordinar la ejecución de procesos entre sistemas externos.
- Registrar eventos en sistemas de auditoría.
- Ejecutar cuestionarios de recolección de información pre-analítica.

**n8n NO PUEDE:**
- Validar, autorizar, corregir ni eliminar resultados clínicos.
- Modificar órdenes, muestras o pacientes directamente en la base de datos.
- Tomar decisiones clínicas de ningún tipo.
- Actuar como sistema de registro médico (EHR/LIS).

### 3. Identificación de valores críticos: solo en la aplicación principal

- La clasificación de un resultado como "crítico" o "fuera de rango" debe
  realizarse en LabResultados mediante reglas explícitas definidas por
  profesionales de la salud.
- n8n recibe la señal de "resultado crítico" ya procesada. No la calcula.
- n8n no tiene acceso a los rangos de referencia ni a la lógica de
  interpretación clínica.

### 4. La IA no interpreta resultados ni emite diagnósticos

- Ningún componente de IA (incluido Antigravity) debe interpretar valores
  de laboratorio ni emitir diagnósticos.
- Los modelos de lenguaje pueden ayudar a diseñar workflows y redactar
  plantillas de notificación, pero **no** deben analizar datos clínicos
  individuales.

### 5. Principio de mínima información en notificaciones

- Las notificaciones deben contener únicamente la información necesaria
  para que el destinatario tome la acción requerida.
- Preferir enlace autenticado al sistema: `https://lab.tu-sistema.com/resultado/{token}`
- **Nunca incluir en notificaciones:**
  - Nombre completo del paciente (usar solo nombre parcial o referencia).
  - CURP, número de seguro o identificación oficial.
  - Diagnósticos.
  - Resultados numéricos completos.
  - Datos de terceros (médico tratante, familiar) no autorizados.

### 6. Todos los eventos deben incluir un `eventId`

- Cada evento emitido por LabResultados hacia n8n debe incluir un `eventId`
  único (UUID v4 preferible).
- n8n debe registrar el `eventId` y no reprocesar eventos ya procesados.

### 7. Todas las acciones deben ser idempotentes

- Si el mismo evento llega dos veces, la acción debe ejecutarse solo una vez.
- Documenta el campo de idempotencia para cada acción en el workflow.

### 8. Auditoría y manejo de errores obligatorios

- Todos los workflows clínicos deben:
  - Registrar en un log de auditoría: `eventId`, tipo de evento, resultado,
    timestamp, y si fue procesado o ignorado (duplicado).
  - Tener un nodo de manejo de errores configurado.
  - Notificar al equipo técnico cuando ocurra un error crítico.

### 9. Pruebas solo con información sintética

- Usa únicamente datos de pacientes ficticios para pruebas.
- No uses CURP, nombres, fechas de nacimiento, ni resultados de pacientes
  reales durante el desarrollo o pruebas.
- Documenta los datos sintéticos utilizados en el informe del workflow.

### 10. Aprobación humana antes de activar

- Todos los workflows de laboratorio clínico deben permanecer INACTIVE
  hasta recibir aprobación explícita del responsable del laboratorio.
- La aprobación debe quedar documentada (comentario en el workflow o
  registro externo).

### 11. Nunca almacenar credenciales en un workflow exportado

- Cuando se exporte un workflow como JSON, no debe contener ninguna
  credencial, token, contraseña o API key.
- Las credenciales están almacenadas en el servidor de n8n, no en el
  workflow.

## Procedimiento para Automatizaciones de Laboratorio

### Paso 1 — Clasificar el tipo de automatización

| Tipo | Descripción | Nivel de riesgo |
|------|-------------|-----------------|
| Notificación de resultado listo | Aviso al paciente de que puede recoger/ver su resultado | Bajo |
| Alerta de resultado crítico | Notificación urgente al médico | **Alto** |
| Cuestionario pre-analítico | Recolección de información del paciente antes de la toma | Bajo |
| Integración con sistema externo | Envío de datos a otro sistema de salud | **Alto** |
| Recordatorio de cita / toma | Aviso programado al paciente | Bajo |
| Reporte de inventario | Alertas internas de stock de reactivos | Bajo |

### Paso 2 — Para automatizaciones de alto riesgo

Antes de diseñar el workflow:

1. Confirma con el responsable del laboratorio el alcance exacto.
2. Documenta qué datos fluirán y por qué son necesarios.
3. Obtén confirmación de que LabResultados es el origen del evento
   (no n8n generando o modificando datos).
4. Define el plan de notificación de errores (¿quién recibe la alerta si
   el workflow falla?).

### Paso 3 — Diseñar con el principio de mínima superficie de datos

- Mapea cada campo de datos que fluye en el workflow.
- Para cada campo, justifica por qué es necesario.
- Elimina cualquier campo que no sea estrictamente necesario para la
  acción que realiza n8n.

### Paso 4 — Configurar auditoría

Cada workflow clínico debe incluir un nodo de auditoría que registre:

```json
{
  "eventId": "uuid-del-evento",
  "workflowName": "nombre-del-workflow",
  "eventType": "resultado_listo | alerta_critica | ...",
  "processedAt": "ISO8601",
  "status": "processed | skipped_duplicate | error",
  "errorMessage": null
}
```

### Paso 5 — Validar antes de recomendar activación

Verifica el checklist completo antes de recomendar activar el workflow:

```markdown
## Checklist de Validación — Automatización Clínica

### Datos y Privacidad
- [ ] n8n solo recibe datos mínimos necesarios
- [ ] No fluyen CURP, nombres completos ni diagnósticos por canales inseguros
- [ ] Las notificaciones usan enlace autenticado, no datos clínicos directos
- [ ] Los logs no contienen información sensible del paciente

### Responsabilidad Clínica
- [ ] n8n no clasifica ni interpreta resultados
- [ ] La lógica de "resultado crítico" está en LabResultados, no en n8n
- [ ] No existe lógica de IA interpretando datos clínicos en el workflow

### Seguridad Técnica
- [ ] Todos los webhooks usan HTTPS
- [ ] Autenticación configurada en todos los webhooks
- [ ] Todas las credenciales están en n8n, no escritas en el workflow
- [ ] eventId implementado y verificado
- [ ] Idempotencia implementada para todas las acciones

### Calidad del Workflow
- [ ] Manejo de errores configurado
- [ ] Notificación de errores al equipo técnico
- [ ] Auditoría de eventos configurada
- [ ] Probado con datos sintéticos (sin datos reales)
- [ ] Workflow en estado INACTIVE

### Aprobación
- [ ] Responsable del laboratorio revisó el diseño
- [ ] Aprobación documentada
```

## Restricciones

- ❌ n8n no valida, autoriza, corrige ni elimina resultados clínicos.
- ❌ n8n no calcula ni clasifica valores críticos.
- ❌ Los modelos de IA no interpretan resultados de laboratorio.
- ❌ No se envían nombres completos, CURP, diagnósticos ni resultados
  por canales inseguros.
- ❌ No se usan datos reales de pacientes en pruebas.
- ❌ No se activa ningún workflow sin aprobación humana documentada.
- ❌ No se almacenan credenciales en workflows exportados.

## Informe Final Esperado

```markdown
## Informe de Automatización Clínica

**Nombre del workflow:** [nombre]
**Tipo de automatización:** [tipo]
**Nivel de riesgo:** [Bajo / Alto]
**Estado:** INACTIVE
**Fecha:** [fecha]

### Datos que fluyen en el workflow
| Campo | Origen | Destino | Justificación |
|-------|--------|---------|---------------|
| eventId | LabResultados | n8n | Idempotencia y auditoría |
| ... | ... | ... | ... |

### Datos excluidos explícitamente
- CURP: no necesario para la notificación
- Resultado numérico completo: se usa enlace autenticado
- ...

### Mecanismos de Seguridad
| Control | Estado |
|---------|--------|
| HTTPS | ✅ |
| Autenticación webhook | ✅ |
| eventId + idempotencia | ✅ |
| Auditoría | ✅ |
| Manejo de errores | ✅ |

### Datos Sintéticos Utilizados en Pruebas
[descripción de los datos ficticios]

### Estado del Checklist de Validación
[Checklist completo como se definió arriba]

### Aprobación Requerida
Este workflow permanece INACTIVE. Para activarlo, el responsable del
laboratorio debe aprobar explícitamente.
```
