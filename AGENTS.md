# AGENTS.md — LaboratorioExt

Instrucciones para el agente de desarrollo de **LabResultados** —
Sistema de Gestión de Resultados de Laboratorio Clínico.

---

## Descripción del Proyecto

**LabResultados** es un sistema integral para la gestión, carga masiva y
distribución de resultados de laboratorio clínico. Incluye:

- **Backend:** FastAPI + Python 3.12 + PostgreSQL 16 (fuente de verdad).
- **Frontend:** React + Vite (puerto 3000).
- **n8n:** Capa de integración y orquestación (puerto 5678).
- **Cloudflare Tunnel:** Exposición pública segura de webhooks.

---

## Skills Disponibles

Las Skills de este proyecto están ubicadas en `.agents/skills/` y se
cargan automáticamente por Antigravity. Léelas y aplícalas cuando
corresponda.

| Skill | Directorio | Cuándo usar |
|-------|-----------|-------------|
| `n8n-workflow-builder` | `.agents/skills/n8n-workflow-builder/` | Crear workflows, nodos, triggers, webhooks, automatizaciones |
| `n8n-workflow-review` | `.agents/skills/n8n-workflow-review/` | Revisar, corregir, auditar o mejorar workflows existentes |
| `n8n-webhook-security` | `.agents/skills/n8n-webhook-security/` | Configurar y auditar la seguridad de webhooks |
| `laboratory-automation` | `.agents/skills/laboratory-automation/` | Cualquier automatización que involucre datos de laboratorio clínico |

**Regla:** Lee el `SKILL.md` correspondiente **antes** de comenzar la tarea
relacionada.

---

## Reglas Generales de n8n

### Consultar el MCP antes de crear nodos

- Antes de configurar cualquier nodo de n8n, consulta el servidor MCP
  `n8n-laboratorio` para obtener la definición real del tipo de nodo.
- **Prohibido inventar propiedades, parámetros o valores de enum de nodos.**
- Si el MCP no está disponible, documenta qué propiedades no pudieron
  verificarse e indica al usuario que las valide manualmente.

### Crear workflows desactivados

- Todos los workflows nuevos deben crearse con estado **INACTIVE**.
- Ningún workflow debe activarse sin pruebas documentadas y aprobación
  humana explícita.

### No incluir secretos en código

- Ningún secreto, token, API key, contraseña o credencial debe escribirse
  directamente en un workflow, en un archivo de código o en un archivo
  versionado.
- Usa siempre credenciales administradas por n8n o variables de entorno.
- Los archivos con secretos reales (`.env`) deben estar excluidos de Git.

### Probar con datos sintéticos

- Toda prueba de workflows de laboratorio clínico debe realizarse
  exclusivamente con datos ficticios.
- No uses datos reales de pacientes, CURP, nombres o resultados en ningún
  entorno de prueba.

### Validar antes de recomendar activación

- Verifica que el workflow esté correctamente configurado (todos los nodos
  conectados, sin propiedades inventadas, con manejo de errores).
- Presenta un informe de validación antes de recomendar la activación.

### No usar n8n para modificar información clínica crítica

- n8n es una capa de integración y orquestación, no un sistema clínico.
- n8n no valida, autoriza, corrige ni elimina resultados clínicos.
- La clasificación de valores críticos, la interpretación de resultados y
  la autorización clínica ocurren exclusivamente en LabResultados
  (backend FastAPI + PostgreSQL).
- Los modelos de IA, incluido Antigravity, no interpretan resultados de
  laboratorio ni emiten diagnósticos.

---

## Reglas Generales del Proyecto

### Aplicación principal

- El backend FastAPI es la fuente de verdad para todos los datos clínicos.
- No modifiques la lógica clínica del backend sin revisión explícita del
  responsable del laboratorio.

### Credenciales y seguridad

- El archivo `.env` está excluido de Git (`/.env` en `.gitignore`).
- Usa `.env.example` como referencia sin valores reales.
- No compartas ni escribas tokens, contraseñas o claves en archivos
  versionados.

### Arquitectura

- El frontend se comunica con el backend exclusivamente a través de
  la API REST documentada en `/docs` y `/redoc`.
- n8n se comunica con el backend mediante la misma API REST, con
  autenticación apropiada.
- Las notificaciones externas (email, WhatsApp) pasan por n8n usando
  credenciales administradas, no por el backend directamente.

---

## Servidor MCP de n8n

- **Nombre del servidor:** `n8n-laboratorio`
- **Tipo de transporte:** HTTP remoto
- **Configuración:** Ver `docs/n8n/mcp-setup.md`
- **Estado de verificación:** Ver `docs/n8n/mcp-verification.md`

El token de acceso y la URL del MCP **no deben escribirse** en ningún
archivo versionado. Deben configurarse de forma segura según las
instrucciones en `docs/n8n/mcp-setup.md`.

---

## Documentación de n8n

| Documento | Ruta | Contenido |
|-----------|------|-----------|
| Skills | `docs/n8n/skills.md` | Descripción y uso de cada Skill |
| Configuración MCP | `docs/n8n/mcp-setup.md` | Cómo configurar el servidor MCP |
| Verificación MCP | `docs/n8n/mcp-verification.md` | Estado de conexión y herramientas disponibles |
