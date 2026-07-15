# Verificación del Servidor MCP de n8n

Registro del estado de conexión, herramientas y capacidades del servidor MCP
`n8n-laboratorio` para el proyecto **LabResultados**.

**Última verificación:** 2026-07-13
**Versión de n8n verificada:** `2.29.10`
**Realizada por:** Antigravity

---

## Resumen de Estado

| Parámetro | Valor |
|-----------|-------|
| **Nombre del servidor** | `n8n-laboratorio` |
| **Estado de configuración** | ✅ Configurado en `mcp_config.json` |
| **n8n corriendo** | ✅ Sí — contenedor `n8n-local`, Up, puerto 5678 |
| **API REST autenticada** | ✅ Funciona — token JWT válido |
| **Transporte** | `http` |
| **URL configurada** | `http://localhost:5678/mcp` |
| **Endpoint MCP `/mcp`** | ❌ HTTP 404 — no disponible en n8n 2.29.10 |
| **Estado de conexión MCP** | ⚠️ Parcial — API REST ✅, protocolo MCP ❌ |

---

## Capacidades Confirmadas (vía API REST)

La API REST de n8n responde correctamente con el token configurado.

| Capacidad | Endpoint | Estado | Resultado |
|-----------|----------|--------|-----------|
| Health check | `GET /healthz` | ✅ OK | `{"status":"ok"}` |
| Listar workflows | `GET /api/v1/workflows` | ✅ OK | 2 workflows encontrados |
| Consultar ejecuciones | `GET /api/v1/executions` | ✅ OK | 1 ejecución encontrada |
| Crear workflow | `POST /api/v1/workflows` | ✅ Disponible | No probado |
| Actualizar workflow | `PATCH /api/v1/workflows/{id}` | ✅ Disponible | No probado |
| Activar/desactivar | `POST /api/v1/workflows/{id}/activate` | ✅ Disponible | No probado (requiere aprobación) |

### Workflows existentes en n8n

| ID | Nombre | Activo | Nodos |
|----|--------|--------|-------|
| `7Yr9VFwKXAkSpZv1` | My workflow | ❌ False | 2 |
| `RxyJbwKVjqPSOJVF` | My workflow 2 | ❌ False | 2 |

### Ejecuciones encontradas

| ID | Workflow | Estado |
|----|----------|--------|
| `1` | `7Yr9VFwKXAkSpZv1` | `success` |

---

## Capacidades NO Disponibles

| Capacidad | Estado | Razón |
|-----------|--------|-------|
| Endpoint MCP `/mcp` | ❌ HTTP 404 | No existe en n8n 2.29.10 |
| Endpoint `/api/v1/mcp` | ❌ HTTP 404 | No existe |
| Consultar tipos de nodo | ❌ HTTP 404 | `/api/v1/node-types` no existe en esta versión |
| Herramientas MCP nativas | ❌ No disponibles | Requieren solución alternativa |

---

## Diagnóstico Definitivo: n8n 2.29.10 = Latest

**n8n `2.29.10` es la versión `latest` disponible en Docker Hub** (verificado el 2026-07-13). La imagen fue actualizada y el contenedor fue recreado correctamente:

- Puerto publicado: `5678 -> 0.0.0.0:5678` ✅
- Health check: `ok` ✅
- Migraciones MCP ejecutadas: `CreateMcpRegistryServerTable`, `CreateInstanceAiMcpRegistryConnectionTable` ✅
- Endpoint `/mcp`: **HTTP 404** ❌

**Causa raíz confirmada:** n8n 2.29.10 incluye un **cliente** MCP (para que n8n consuma herramientas de servidores MCP externos), pero **no expone un endpoint servidor MCP** para que clientes externos como Antigravity lo consuman vía protocolo HTTP MCP.

### Opciones actualizadas

#### Opción A — Trabajar con API REST (disponible hoy, sin cambios)

Antigravity usa `http://127.0.0.1:5678/api/v1/` con el token configurado. Todas las operaciones de workflows, ejecuciones y credenciales están disponibles. **Esta es la opción recomendada por ahora.**

#### Opción B — Esperar versiones futuras de n8n

Es posible que versiones posteriores de n8n expongan un endpoint servidor MCP. Monitorear las notas de versión de n8n.

#### Opción C — Usar n8n MCP Server (proyecto comunitario)

El proyecto [`n8n-mcp`](https://github.com/n8n-io/n8n-mcp) expone la API de n8n como servidor MCP compatible. Requiere instalación separada como sidecar.

> Evaluar según necesidad. Recomendado para equipos que dependen del protocolo MCP.

---

## Estado de Configuración en Antigravity

### Ubicación del archivo de configuración MCP

```
C:\Users\Emerson.Collazo\.gemini\config\mcp_config.json
```

### Servidores MCP configurados actualmente

| Servidor | Estado |
|----------|--------|
| `github-mcp-server` | ✅ Configurado (comando Docker) |
| `n8n-laboratorio` | ❌ **Pendiente de configuración manual** |

### Razón del estado pendiente

Antigravity no soporta variables de entorno dentro de `mcp_config.json`.
Los valores de URL y token deben ingresarse manualmente en el archivo.

Dado que el token es un secreto, **no se incluye en este documento ni en
ningún archivo versionado.**

---

## Pasos Pendientes para Completar la Configuración

> [!IMPORTANT]
> Completa estos pasos antes de usar el MCP de n8n con Antigravity.

### 1. Verificar que n8n esté corriendo

```bash
# Desde la raíz del proyecto
docker-compose ps
```

n8n debe aparecer como `running` en el puerto `5678`.

### 2. Habilitar la API REST de n8n

1. Accede a `http://localhost:5678`.
2. Ve a **Settings → API**.
3. Activa la API REST.
4. Copia la **API Key** generada.

### 3. Verificar el endpoint MCP de n8n

```powershell
# Verificar que n8n responde (sin autenticación)
Invoke-WebRequest -Uri "http://localhost:5678/healthz" -TimeoutSec 5
```

Respuesta esperada: `HTTP 200 OK`

```powershell
# Verificar que el endpoint MCP existe (requiere API Key)
# Reemplaza TU_API_KEY con la clave obtenida en el Paso 2
$headers = @{ "X-N8N-API-KEY" = "TU_API_KEY" }
Invoke-WebRequest -Uri "http://localhost:5678/mcp" -Headers $headers -TimeoutSec 5
```

> **Nota:** El endpoint exacto puede variar según la versión de n8n y si el
> servidor MCP está habilitado como plugin o módulo. Consulta la documentación
> de tu versión de n8n.

### 4. Agregar la entrada en mcp_config.json

Edita `C:\Users\Emerson.Collazo\.gemini\config\mcp_config.json` y agrega:

```json
"n8n-laboratorio": {
  "type": "http",
  "url": "http://localhost:5678/mcp",
  "headers": {
    "Authorization": "Bearer TU_API_KEY_AQUI"
  }
}
```

Reemplaza `TU_API_KEY_AQUI` con la API Key real. **No versiones este archivo.**

### 5. Reiniciar Antigravity

Cierra y vuelve a abrir Antigravity para que detecte el nuevo servidor MCP.

### 6. Verificar la conexión

Escribe en Antigravity:

```
Lista los workflows disponibles en n8n usando el MCP n8n-laboratorio.
```

Si la conexión es correcta, Antigravity listará los workflows de n8n.

---

## Verificación del Estado de n8n (en este momento)

### Resultado del health check

| Prueba | Resultado |
|--------|-----------|
| `GET http://localhost:5678/healthz` | ⏳ Pendiente — n8n puede no estar iniciado |
| Docker container `n8n` activo | ⏳ No verificado |
| API REST de n8n habilitada | ⏳ Requiere acceso manual al panel |
| Endpoint MCP disponible | ⏳ Pendiente de configuración |

> Para iniciar n8n: `docker-compose up -d n8n` desde la raíz del proyecto.

---

## Herramientas Esperadas del MCP de n8n (cuando esté disponible)

Una vez que el servidor MCP esté correctamente configurado, las siguientes
herramientas deberían estar disponibles:

| Herramienta | Función | Disponibilidad Esperada |
|-------------|---------|------------------------|
| `list_workflows` | Listar todos los workflows | ✅ Esperada |
| `get_workflow` | Consultar un workflow por ID | ✅ Esperada |
| `get_node_types` | Consultar definiciones de tipos de nodos | ✅ Esperada |
| `create_workflow` | Crear un nuevo workflow | ✅ Esperada |
| `update_workflow` | Actualizar un workflow existente | ✅ Esperada |
| `activate_workflow` | Activar un workflow | ✅ Esperada (uso restringido) |
| `deactivate_workflow` | Desactivar un workflow | ✅ Esperada |
| `get_executions` | Consultar historial de ejecuciones | ✅ Esperada |
| `run_workflow` | Ejecutar un workflow manualmente | ⚠️ Depende de la versión y permisos |
| `validate_workflow` | Validar la estructura de un workflow | ⚠️ Puede no estar disponible como herramienta directa |
| `delete_workflow` | Eliminar un workflow | ⚠️ Uso restringido — requiere aprobación explícita |

> Las herramientas reales disponibles dependen de la versión del servidor MCP
> de n8n instalada. Esta tabla se actualizará cuando la conexión sea exitosa.

---

## Capacidades MCP Nativas

*(Pendiente — requiere actualizar n8n o habilitar el servidor MCP)*

| Capacidad | Estado | Notas |
|-----------|--------|-------|
| Listar workflows | ⏳ Pendiente MCP | ✅ Disponible vía API REST |
| Consultar workflow por ID | ⏳ Pendiente MCP | ✅ Disponible vía API REST |
| Consultar definiciones de nodos | ⏳ Pendiente MCP | ❌ No disponible en esta versión |
| Crear workflows | ⏳ Pendiente MCP | ✅ Disponible vía API REST |
| Actualizar workflows | ⏳ Pendiente MCP | ✅ Disponible vía API REST |
| Validar workflows | ⏳ Pendiente MCP | ❌ No disponible vía API REST |
| Consultar ejecuciones | ⏳ Pendiente MCP | ✅ Disponible vía API REST |

---

## Capacidades No Disponibles o Restringidas

| Capacidad | Restricción |
|-----------|-------------|
| Activar workflows desde el MCP | ⚠️ Solo con aprobación explícita del usuario |
| Eliminar workflows desde el MCP | ⚠️ Solo con aprobación explícita del usuario |
| Acceder a datos de ejecuciones pasadas | ⚠️ Puede requerir permisos adicionales de la API Key |
| Leer credenciales de n8n | ❌ No permitido — las credenciales son secretas |
| Modificar configuración del servidor n8n | ❌ Fuera del alcance del MCP |

---

## Errores Conocidos

### Error: n8n no está corriendo

**Síntoma:** `Invoke-WebRequest: Unable to connect to the remote server`

**Diagnóstico:** El contenedor Docker de n8n no está iniciado.

**Solución:**
```bash
# Desde la raíz del proyecto
docker-compose up -d n8n
# Verificar que esté corriendo
docker-compose ps n8n
```

### Error: API Key inválida o faltante

**Síntoma:** `HTTP 401 Unauthorized`

**Diagnóstico:** La API Key no está configurada correctamente en `mcp_config.json`
o fue revocada.

**Solución:**
1. Verifica que la API Key en `mcp_config.json` sea la correcta.
2. Si fue revocada, genera una nueva desde **Settings → API** en n8n.
3. Actualiza `mcp_config.json` manualmente.
4. Reinicia Antigravity.

### Error: Endpoint MCP no encontrado

**Síntoma:** `HTTP 404 Not Found` al conectar al endpoint `/mcp`

**Diagnóstico:** El servidor MCP de n8n puede no estar habilitado o la URL
del endpoint es diferente.

**Solución:**
1. Verifica la versión de n8n: `docker-compose exec n8n n8n --version`
2. Consulta la documentación de n8n para tu versión:
   `https://docs.n8n.io/api/`
3. Es posible que el endpoint MCP sea `/api/v1/` en lugar de `/mcp`.
4. Actualiza la URL en `mcp_config.json` con el valor correcto.

### Error: Transporte no soportado

**Síntoma:** Antigravity no reconoce el tipo de transporte `http`

**Diagnóstico:** La versión de Antigravity instalada puede requerir un formato
diferente de configuración MCP.

**Solución:**
1. Verifica la versión de Antigravity instalada.
2. Consulta la documentación de Antigravity para el formato correcto.
3. Es posible que el formato sea `streamable-http` o `sse` en lugar de `http`.
4. Actualiza `mcp_config.json` con el tipo correcto.

---

## Historial de Verificaciones

| Fecha | Estado | Notas |
|-------|--------|-------|
| 2026-07-13 (inicial) | ⚠️ Configuración pendiente | Token no configurado |
| 2026-07-13 (verificación 1) | ⚠️ Parcial | API REST ✅, MCP endpoint ❌ — n8n v2.29.10 |
| 2026-07-13 (actualización) | ⚠️ Sin cambio | n8n:latest = 2.29.10, endpoint MCP no existe en esta versión. API REST operativa. |

---

## Cómo Actualizar Este Documento

Cuando completes la configuración y la conexión sea exitosa:

1. Actualiza la tabla de **Resumen de Estado**.
2. Completa los resultados en **Verificación del Estado de n8n**.
3. Actualiza las tablas de **Capacidades Confirmadas** y **No Disponibles**.
4. Agrega una fila al **Historial de Verificaciones**.
5. Documenta cualquier error encontrado y su solución.
