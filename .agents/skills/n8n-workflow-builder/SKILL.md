---
name: n8n-workflow-builder
description: >
  Guía al agente en el diseño, creación y configuración de workflows de n8n.
  Se activa cuando se solicita crear workflows, nodos, triggers, webhooks,
  subworkflows, expresiones de n8n, automatizaciones o integraciones con APIs
  externas. Exige comprender el objetivo antes de construir, consultar el MCP
  para verificar propiedades reales de nodos, y entregar workflows inicialmente
  desactivados con manejo de errores y pruebas sintéticas.
triggers:
  - crear workflow
  - crear nodo
  - conectar nodos
  - diseñar subworkflow
  - usar expresiones de n8n
  - configurar trigger
  - configurar webhook
  - crear automatización
  - integrar API externa
  - nuevo flujo
  - construir workflow
---

# Skill: n8n Workflow Builder

## Propósito

Garantizar que cada workflow creado sea correcto, seguro, mantenible y
verificable antes de ser activado en producción.

## Procedimiento Obligatorio

Sigue estos pasos **en orden**. No avances al siguiente sin completar el
anterior.

### Paso 1 — Comprender el objetivo

- Solicita o confirma:
  - ¿Cuál es el proceso de negocio que se automatiza?
  - ¿Cuáles son los eventos disparadores?
  - ¿Cuáles son los sistemas involucrados?
  - ¿Cuáles son los datos de entrada y salida esperados?
  - ¿Existen restricciones de seguridad, privacidad o rendimiento?
- No comiences a diseñar hasta tener claridad sobre el objetivo.

### Paso 2 — Diseñar el flujo antes de crearlo

- Describe el flujo en formato de lista ordenada de nodos y conexiones.
- Identifica:
  - Nodo disparador (trigger).
  - Nodos de transformación.
  - Nodos de integración (HTTP Request, credenciales externas).
  - Nodos de decisión (IF, Switch).
  - Nodos de salida (respuesta, almacenamiento, notificación).
  - Subworkflows reutilizables.
  - Nodos de manejo de errores (Error Trigger, nodo de fallback).
- Presenta el diseño al usuario antes de proceder.

### Paso 3 — Consultar el MCP para definiciones reales de nodos

- Antes de configurar cualquier nodo, consulta el MCP `n8n-laboratorio`
  para obtener la definición real del tipo de nodo.
- **Prohibido inventar nombres de propiedades, parámetros o valores de enum.**
- Si el MCP no está disponible, indica claramente qué propiedades no pudieron
  verificarse y solicita validación manual.

### Paso 4 — Crear el workflow

- Crea el workflow con estado **INACTIVE** (desactivado).
- Configura los nodos usando únicamente propiedades verificadas en el Paso 3.
- Nombra los nodos de forma descriptiva (no `Node 1`, `HTTP Request 3`).
- Asigna una descripción al workflow que explique su propósito.
- Agrega una etiqueta con la fecha de creación y el ambiente (dev / staging /
  prod).

### Paso 5 — Separar funciones reutilizables en subworkflows

- Si existe lógica que se repite en más de un workflow, extráela como
  subworkflow independiente.
- Documenta el contrato de entrada/salida del subworkflow.

### Paso 6 — Configurar manejo de errores

- Agrega un **Error Trigger** al workflow o usa el modo de manejo de errores
  del nodo.
- Define qué ocurre cuando falla un nodo: reintentar, notificar, registrar en
  log o abortar.
- Configura reintentos (`maxTries`, `waitBetweenTries`) cuando el nodo invoque
  APIs externas propensas a fallos transitorios.

### Paso 7 — Configurar credenciales

- **Nunca escribas secretos, tokens, contraseñas o API keys dentro del
  workflow.**
- Referencia siempre una credencial existente en n8n por su nombre.
- Si la credencial aún no existe, indica el tipo y el nombre esperado.

### Paso 8 — Validar el workflow

- Después de crear el workflow, consulta el MCP para leer su definición y
  verificar que los nodos y conexiones estén configurados correctamente.
- Verifica que no existan nodos huérfanos (sin conexión).

### Paso 9 — Probar con datos sintéticos

- Diseña un conjunto de datos de prueba que representen casos normales,
  casos borde y casos de error.
- Documenta los datos sintéticos utilizados.
- **Nunca uses datos reales de pacientes, credenciales reales ni producción.**
- Solicita al usuario la ejecución de prueba y analiza el resultado.

### Paso 10 — Informar

Al finalizar, entrega un informe con:

```markdown
## Informe de Workflow Creado

**Nombre del workflow:** [nombre]
**ID en n8n:** [id]
**Estado:** INACTIVE
**Trigger:** [tipo de trigger]

### Nodos creados
| Nodo | Tipo | Función |
|------|------|---------|
| ... | ... | ... |

### Credenciales requeridas
| Nombre esperado | Tipo | Estado |
|-----------------|------|--------|
| ... | ... | Pendiente / Configurada |

### Datos sintéticos utilizados
[descripción]

### Riesgos identificados
- [riesgo 1]
- [riesgo 2]

### Próximos pasos para activación
1. Configurar credenciales pendientes.
2. Ejecutar prueba completa con datos sintéticos.
3. Obtener aprobación del responsable.
4. Activar el workflow.
```

## Restricciones

- ❌ No actives workflows durante la creación.
- ❌ No uses datos reales de pacientes, empleados o producción para pruebas.
- ❌ No escribas secretos, tokens o contraseñas dentro del workflow.
- ❌ No inventes propiedades de nodos sin verificarlas en el MCP.
- ❌ No uses nodos `Code` cuando exista un nodo nativo equivalente.
- ❌ No omitas el manejo de errores.
- ❌ No crees workflows sin descripción y etiquetas.

## Criterios de Validación

Un workflow está listo para revisión de activación cuando:

- [ ] El workflow está INACTIVE.
- [ ] Todos los nodos tienen nombre descriptivo.
- [ ] No existen propiedades inventadas (verificadas en MCP).
- [ ] Existe manejo de errores configurado.
- [ ] No contiene secretos escritos directamente.
- [ ] Fue probado con datos sintéticos.
- [ ] El informe de workflow fue entregado al usuario.
- [ ] Las credenciales pendientes están documentadas.
