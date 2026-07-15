# Skills de n8n para LaboratorioExt

Documentación de las Skills disponibles para trabajar con n8n en el proyecto
**LabResultados**.

---

## Resumen de Skills

| Skill | Directorio | Activa cuando... |
|-------|-----------|-----------------|
| [`n8n-workflow-builder`](#n8n-workflow-builder) | `.agents/skills/n8n-workflow-builder/` | Se necesita crear o modificar workflows |
| [`n8n-workflow-review`](#n8n-workflow-review) | `.agents/skills/n8n-workflow-review/` | Se necesita revisar o auditar un workflow |
| [`n8n-webhook-security`](#n8n-webhook-security) | `.agents/skills/n8n-webhook-security/` | Se trabaja con webhooks o endpoints públicos |
| [`laboratory-automation`](#laboratory-automation) | `.agents/skills/laboratory-automation/` | La automatización involucra datos clínicos |

---

## n8n-workflow-builder

**Propósito:** Guiar la creación de workflows de forma correcta, segura y
verificable.

### Cuándo se activa

Se activa cuando el prompt incluye alguno de estos términos o conceptos:
- "crear workflow", "nuevo workflow", "nuevo flujo"
- "crear nodo", "agregar nodo", "conectar nodos"
- "diseñar subworkflow", "subworkflow reutilizable"
- "usar expresiones de n8n", "expresión de n8n"
- "configurar trigger", "trigger de n8n"
- "configurar webhook" (junto con creación)
- "crear automatización", "nueva automatización"
- "integrar API", "conectar API externa"

### Qué hace

1. Exige entender el objetivo antes de diseñar.
2. Presenta el diseño del flujo al usuario antes de crearlo.
3. Consulta el MCP `n8n-laboratorio` para verificar propiedades reales de nodos.
4. Crea el workflow en estado INACTIVE.
5. Configura manejo de errores y reintentos.
6. Prohíbe secretos escritos directamente.
7. Prueba con datos sintéticos.
8. Entrega un informe con nodos creados, credenciales pendientes y riesgos.

### Cómo invocarla desde un prompt

```
Crea un workflow en n8n que reciba una notificación cuando un lote de
resultados sea procesado y envíe un email al médico solicitante.
```

```
Diseña un subworkflow reutilizable para validar que un eventId no ha
sido procesado previamente.
```

---

## n8n-workflow-review

**Propósito:** Auditar workflows existentes, clasificar hallazgos por severidad
y proponer correcciones con aprobación previa.

### Cuándo se activa

Se activa cuando el prompt incluye:
- "revisar workflow", "auditar workflow", "analizar workflow"
- "corregir automatización", "depurar flujo"
- "encontrar errores", "diagnosticar problema"
- "mejorar workflow", "optimizar flujo"
- "revisar rendimiento", "revisar seguridad de workflow"

### Qué hace

1. Obtiene el workflow del MCP o solicita el JSON al usuario.
2. Analiza conectividad, expresiones, credenciales, manejo de errores,
   seguridad y rendimiento.
3. Clasifica hallazgos: Crítico / Alto / Moderado / Bajo.
4. **Presenta el informe ANTES de modificar nada.**
5. Solo aplica correcciones con aprobación explícita del usuario.
6. Entrega un informe de cierre con todas las correcciones aplicadas.

### Cómo invocarla desde un prompt

```
Revisa el workflow "Notificación de Resultados" e identifica si tiene
problemas de seguridad o manejo de errores.
```

```
Audita todos los workflows activos y clasifica los hallazgos por severidad.
```

---

## n8n-webhook-security

**Propósito:** Garantizar que todos los webhooks cumplan con los controles de
seguridad necesarios antes de exponerse públicamente.

### Cuándo se activa

Se activa cuando el prompt incluye:
- "Webhook Trigger", "webhook de n8n"
- "configurar webhook seguro", "autenticación de webhook"
- "firma HMAC", "verificar firma"
- "token de acceso", "header de autorización"
- "endpoint público", "exponer webhook"
- "recibir eventos externos", "protección anti-replay"
- "validar payload"

### Qué hace

Verifica y configura 15 controles de seguridad:

1. HTTPS obligatorio.
2. Autenticación (Bearer, HMAC, Basic, mTLS).
3. Validación estricta del payload.
4. Verificación de firma HMAC.
5. Validación de timestamp.
6. Protección anti-replay.
7. `eventId` único.
8. Idempotencia persistente.
9. Límite de tamaño del payload.
10. Timeout.
11. Rate limiting.
12. Sanitización de logs.
13. Respuestas HTTP explícitas.
14. Rechazo de campos inesperados.
15. Credenciales administradas desde n8n.

### Cómo invocarla desde un prompt

```
Configura un webhook seguro para recibir eventos de LabResultados cuando
un resultado esté listo para el paciente.
```

```
Audita la seguridad del webhook "Recepción de Órdenes" y genera un
checklist de cumplimiento.
```

---

## laboratory-automation

**Propósito:** Garantizar que las automatizaciones de laboratorio clínico
respeten la privacidad del paciente, los límites de responsabilidad clínica y
los requisitos de trazabilidad.

### Cuándo se activa

Se activa cuando el prompt menciona:
- "paciente", "orden", "muestra", "resultado", "reporte", "alerta"
- "inventario de laboratorio", "tiempo de respuesta"
- "notificación de laboratorio", "resultado crítico"
- "automatización clínica", "flujo de laboratorio"
- Cualquier combinación de n8n con datos de salud

### Qué hace

1. Clasifica el tipo y nivel de riesgo de la automatización.
2. Aplica los 11 principios no negociables (ver `SKILL.md`).
3. Exige que n8n actúe solo como capa de integración.
4. Verifica que la lógica clínica permanezca en LabResultados.
5. Aplica el principio de mínima información en notificaciones.
6. Exige `eventId` e idempotencia.
7. Configura auditoría y manejo de errores.
8. Valida con un checklist completo antes de recomendar activación.

### Cómo invocarla desde un prompt

```
Diseña una automatización para notificar al paciente por WhatsApp cuando
sus resultados estén listos, sin incluir los valores numéricos.
```

```
Crea un flujo para alertar al médico cuando LabResultados marque un
resultado como crítico.
```

---

## Cómo actualizar una Skill

1. Abre el archivo `SKILL.md` de la Skill correspondiente.
2. Modifica el contenido respetando el formato YAML del encabezado.
3. Actualiza la sección correspondiente en este documento.
4. Verifica que el YAML del encabezado siga siendo válido.

> **Formato mínimo requerido del encabezado YAML:**
> ```yaml
> ---
> name: nombre-de-la-skill
> description: >
>   Descripción clara de cuándo se activa y qué hace.
> triggers:
>   - término de activación 1
>   - término de activación 2
> ---
> ```

---

## Cómo verificar que Antigravity detecta las Skills

1. Abre Antigravity en este proyecto (`LaboratorioExt`).
2. Escribe un prompt que incluya uno de los términos de activación de la Skill.
3. Antigravity debe cargar automáticamente el `SKILL.md` correspondiente
   y seguir el procedimiento definido en él.
4. Si la Skill no se activa, verifica:
   - Que el archivo esté en `.agents/skills/<nombre-skill>/SKILL.md`.
   - Que el encabezado YAML sea válido (sin caracteres especiales sin escapar).
   - Que los términos del prompt coincidan con los `triggers` del YAML.

---

## Estructura de Archivos

```
.agents/
└── skills/
    ├── n8n-workflow-builder/
    │   └── SKILL.md
    ├── n8n-workflow-review/
    │   └── SKILL.md
    ├── n8n-webhook-security/
    │   └── SKILL.md
    └── laboratory-automation/
        └── SKILL.md
```
