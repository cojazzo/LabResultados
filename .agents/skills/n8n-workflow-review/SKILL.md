---
name: n8n-workflow-review
description: >
  Guía al agente en la revisión, auditoría y diagnóstico de workflows de n8n
  existentes. Se activa cuando se solicita revisar, corregir, mejorar, auditar
  o encontrar errores en un workflow o automatización. Clasifica los hallazgos
  por severidad y no permite modificar el workflow hasta presentar el plan de
  corrección y obtener aprobación.
triggers:
  - revisar workflow
  - corregir automatización
  - encontrar errores en workflow
  - mejorar flujo
  - auditar nodos
  - revisar rendimiento
  - revisar seguridad
  - depurar workflow
  - analizar workflow
  - diagnosticar flujo
---

# Skill: n8n Workflow Review

## Propósito

Identificar, clasificar y documentar todos los problemas presentes en un
workflow de n8n antes de proponer correcciones. Garantiza que ninguna
modificación se realice sin que el usuario conozca y apruebe el plan.

## Procedimiento Obligatorio

Sigue estos pasos en orden estricto.

### Paso 1 — Obtener el workflow

- Solicita el ID o nombre del workflow a revisar.
- Consulta el MCP `n8n-laboratorio` para obtener la definición completa del
  workflow.
- Si el MCP no está disponible, solicita que el usuario exporte el workflow en
  formato JSON y lo comparta.

### Paso 2 — Análisis de conectividad y estructura

Verifica:

- [ ] Nodos desconectados (sin entrada o sin salida, excepto triggers y
      terminadores intencionales).
- [ ] Ramas sin salida definida.
- [ ] Posibles ciclos infinitos.
- [ ] Nodos duplicados con la misma función.
- [ ] Flujo principal sin nodo trigger definido.

### Paso 3 — Análisis de expresiones

Verifica:

- [ ] Expresiones que referencian propiedades inexistentes.
- [ ] Expresiones sin manejo de valores `null` o `undefined`.
- [ ] Expresiones que asumen una estructura de datos que puede variar.
- [ ] Uso de `$json` o `$item` de forma incorrecta.

### Paso 4 — Análisis de credenciales y secretos

Verifica:

- [ ] Credenciales faltantes en nodos que las requieren.
- [ ] Secretos, tokens, API keys o contraseñas escritos directamente en el
      workflow (en cualquier campo: URL, header, body, código).
- [ ] Uso de credenciales de ambiente incorrecto (dev/staging/prod mezclados).

### Paso 5 — Análisis de manejo de errores

Verifica:

- [ ] Ausencia de Error Trigger o nodo de fallback.
- [ ] Nodos que llaman APIs externas sin configuración de reintento.
- [ ] Reintentos mal configurados (maxTries=0, waitBetweenTries demasiado
      corto para rate-limiting).
- [ ] Ausencia de timeout en nodos HTTP Request.
- [ ] Sin manejo de respuestas 429 (rate limit) y 500 (error servidor).

### Paso 6 — Análisis de seguridad

Verifica:

- [ ] Exposición de datos sensibles en logs (nombres completos, CURP,
      diagnósticos, resultados clínicos).
- [ ] Webhooks sin autenticación.
- [ ] URLs sin HTTPS.
- [ ] Ausencia de validación de firma HMAC en webhooks externos.
- [ ] Ausencia de validación de timestamp (protección anti-replay).
- [ ] Ausencia de `eventId` único para idempotencia.
- [ ] Datos sensibles transmitidos por canales inseguros.

### Paso 7 — Análisis de rendimiento y calidad

Verifica:

- [ ] Uso innecesario de nodos `Code` cuando existe un nodo nativo equivalente.
- [ ] Consultas a APIs sin paginación donde debería haberla.
- [ ] Bucles que podrían generar consultas excesivas.
- [ ] Ausencia de idempotencia en acciones con efectos secundarios.
- [ ] Duplicación de acciones (misma operación ejecutada dos veces).
- [ ] Workflows activos sin evidencia de pruebas suficientes.

### Paso 8 — Clasificar hallazgos

Clasifica cada hallazgo en una de las siguientes categorías:

| Severidad  | Criterio                                                          |
|------------|-------------------------------------------------------------------|
| **Crítico**  | Falla de seguridad activa, exposición de datos sensibles, secreto escrito directamente, ciclo infinito. |
| **Alto**     | Ausencia de manejo de errores en flujo principal, credencial faltante, webhook sin autenticación. |
| **Moderado** | Reintento mal configurado, expresión frágil, ausencia de paginación, nodo desconectado no intencional. |
| **Bajo**     | Nodo sin nombre descriptivo, falta de etiquetas, código no documentado. |

### Paso 9 — Presentar hallazgos ANTES de modificar

**No modifiques el workflow en este paso.**

Entrega el siguiente informe al usuario:

```markdown
## Informe de Revisión de Workflow

**Workflow:** [nombre / ID]
**Fecha de revisión:** [fecha]
**Revisado por:** Antigravity (n8n-workflow-review)

### Resumen Ejecutivo

| Severidad | Cantidad |
|-----------|----------|
| Crítico   | X        |
| Alto      | X        |
| Moderado  | X        |
| Bajo      | X        |

### Hallazgos Detallados

#### 🔴 Críticos
1. **[Título del hallazgo]**
   - Nodo afectado: [nombre del nodo]
   - Descripción: [qué está mal y por qué es crítico]
   - Corrección propuesta: [cómo corregirlo]

#### 🟠 Altos
...

#### 🟡 Moderados
...

#### 🔵 Bajos
...

### Plan de Corrección Propuesto

1. [Acción 1 — Prioridad crítica]
2. [Acción 2 — Prioridad alta]
...

### Aprobación Requerida

¿Deseas que proceda con las correcciones según el plan anterior?
```

### Paso 10 — Aplicar correcciones (solo con aprobación)

- Una vez que el usuario apruebe el plan, aplica las correcciones en el
  orden de prioridad (críticos primero).
- Después de cada corrección, verifica mediante el MCP que el nodo quede
  correctamente configurado.
- Entrega un informe de cierre con todas las correcciones aplicadas.

## Restricciones

- ❌ No modifiques ningún nodo ni propiedad del workflow antes de presentar
  el informe de hallazgos y obtener aprobación explícita.
- ❌ No inventes propiedades de nodos al corregir; verifica en el MCP.
- ❌ No omitas ninguna categoría de análisis.
- ❌ No actives el workflow durante la revisión o corrección.
- ❌ No ignores hallazgos por considerarlos "menores" sin documentarlos.

## Criterios de Validación

La revisión está completa cuando:

- [ ] Se ejecutaron los 7 análisis (pasos 2 al 7).
- [ ] Todos los hallazgos están clasificados por severidad.
- [ ] El informe fue presentado al usuario antes de cualquier modificación.
- [ ] Las correcciones se aplicaron solo con aprobación explícita.
- [ ] Se verificó el workflow corregido mediante el MCP.
