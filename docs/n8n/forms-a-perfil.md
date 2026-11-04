# Alta automática de perfiles desde Google Forms

Workflow: `LabResultados_forms_a_perfil.n8n.json` (importar en n8n; se entrega **INACTIVO**).
Backend: `POST /api/integraciones/forms/respuestas`.

## Qué hace

1. Cuando alguien responde el Google Forms, el **Google Sheets Trigger** detecta la fila nueva en la hoja de respuestas.
2. **Preparar respuesta** arma `{ id_respuesta, campos }` con las columnas tal cual vienen en la hoja.
3. **Agrupar respuestas** junta las filas del mismo ciclo de lectura en una sola llamada.
4. **Backend: alta de perfiles** envía el lote a LabResultados con la clave de sistema (Header Auth).
5. Si hubo errores o perfiles por revisar, avisa al equipo técnico **solo con conteos** (sin datos personales).
   Un `Error Trigger` cubre las fallas del propio workflow.

n8n **no** decide nada clínico ni de identidad: solo reenvía. Las reglas viven en el backend.

## Cómo se une con la tira y el Vitros

El backend (`app/services/identidad.py`) decide a qué perfil pertenece cada respuesta:

| Situación | Resultado |
|---|---|
| La CURP ya existe | Se actualiza ese perfil. Si hay un perfil de laboratorio sin CURP (SYN-…, NTS-…, número de petición) con **exactamente el mismo nombre**, se **fusiona** en él (sus resultados pasan al perfil con CURP). |
| La CURP no existe y hay **un único** perfil de laboratorio sin CURP con el mismo nombre | Ese perfil **adopta** la CURP y conserva todos sus resultados. |
| Varios candidatos, nombre solo parecido, o sexo/fecha de nacimiento que contradicen | **No une nada**; crea el perfil y lo reporta en `revisar` (cuenta en `por_revisar`). Una persona decide. |
| Sin CURP en el formulario | Reutiliza el perfil de laboratorio con el mismo nombre, o crea uno nuevo (SYN-…). |

Reglas que no se tocan: los alumnos del padrón de tamiz-escolar (con folio) conservan su nombre, nacimiento y sexo
(los manda tamiz); del formulario solo se suman contacto y datos clínicos. Reenviar la misma respuesta no duplica nada
(idempotente por `id_respuesta`, que se guarda en `questionnaire_source_id`).

Después de crear el perfil con CURP, la tira (ID = CURP) y el Vitros (NTS = CURP) caen en el mismo perfil.

## Antes de activar

| Credencial (nombre sugerido) | Tipo | Estado |
|---|---|---|
| Google Sheets (cuenta que ve la hoja del Forms) | OAuth2 de Google | Pendiente |
| `LabResultados API (clave de sistema)` | Header Auth: header `Authorization`, valor = `SYSTEM_API_KEY` del `.env` del backend (sin `Bearer`) | Pendiente |

Además: elegir documento y hoja en el trigger (hoy son marcadores `REEMPLAZAR_…`) y configurar el canal del aviso al
equipo técnico (los dos nodos `Notificar … (configurar canal)` son marcadores sin acción).

## Datos sintéticos para probar

Usar únicamente filas ficticias en una hoja de prueba (nunca la hoja real):

| Caso | Fila de prueba | Esperado |
|---|---|---|
| Normal | CURP `TEST010101HASAAA01`, Luna Sofía Pérez Cárdenas ficticia | `accion: creado` |
| Reenvío | La misma fila otra vez | `accion: sin_cambios` |
| Perfil de laboratorio previo | Cargar antes un resultado sin CURP con el mismo nombre y luego la fila | `accion: adoptado` (el perfil conserva su resultado) |
| Ambiguo | Dos perfiles de laboratorio con el mismo nombre | `accion: creado` con `revisar` de 2 elementos y aviso al equipo |
| Error | Fila sin CURP ni nombre | `erroneos: 1` y aviso al equipo |

Las pruebas automáticas del backend con estos mismos casos están en `backend/tests/test_forms_alta_automatica.py`.

## Verificación contra el MCP

Los nodos se verificaron con `get_node` y el workflow con `validate_workflow` (11 nodos, 9 conexiones, 0 errores,
0 advertencias). Se creó en la instancia (2026-11-04) con id `TWkwc4acAPwdvau6`, **inactivo**, y se validó de nuevo
con `n8n_validate_workflow` (mismo resultado). En sus Settings se fijó `errorWorkflow` = él mismo, porque un
`Error Trigger` dentro del mismo workflow solo se dispara así. Si se importa el JSON en otra instancia, hay que
repetir ese ajuste (Settings → Error Workflow).

Propiedad no verificada: el intervalo de sondeo del Google Sheets Trigger (`pollTimes`) no aparece en el esquema del MCP;
el workflow no lo define y usa el valor por defecto del trigger. Revisar en la interfaz de n8n.

## Riesgos y decisiones

- **Datos personales y de salud**: el workflow desactiva el guardado de ejecuciones (éxito y error) para no dejar
  copias en n8n. La trazabilidad queda en LabResultados (Lotes y `questionnaire_source_id`).
- **Fusión automática**: solo con nombre completo exacto. Dos personas distintas con el mismo nombre completo y sin
  CURP en laboratorio se tratan como ambiguas si hay más de un candidato; con un solo candidato se asume la misma persona.
- **Historial**: el trigger solo ve filas nuevas. Las respuestas anteriores se siguen importando con el Excel
  (que ahora usa la misma lógica de identidad).
- **Encabezados del Forms**: el backend reconoce las columnas por su nombre (igual que el Excel). Si se cambian las
  preguntas del Forms, hay que revisar el mapeo.
- **Endpoint antiguo** `POST /api/automation/questionnaires`: no exige autenticación. Conviene protegerlo o retirarlo.
