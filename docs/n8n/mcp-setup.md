# Configuración del Servidor MCP de n8n

Guía para habilitar y configurar el servidor MCP de n8n para que Antigravity
pueda comunicarse con la instancia de n8n de **LabResultados**.

---

## Requisitos previos de n8n

| Requisito | Detalle |
|-----------|---------|
| Versión de n8n | **1.x** o superior (con soporte de API REST) |
| API de n8n habilitada | Requerida para que el MCP pueda operar |
| Acceso a `http://localhost:5678` | Instancia local (o URL pública vía Cloudflare Tunnel) |
| API Key de n8n | Generada desde el panel de n8n |

> **Nota:** En este proyecto, n8n corre como servicio Docker en el puerto
> `5678`. Su URL pública está expuesta mediante Cloudflare Tunnel configurada
> en `N8N_PUBLIC_URL`.

---

## ¿Qué es el MCP de n8n?

El **Model Context Protocol (MCP)** permite a Antigravity comunicarse con n8n
de forma programática: listar workflows, consultar definiciones de nodos,
crear workflows, verificar ejecuciones, etc.

El servidor MCP de n8n expone la API REST de n8n como un conjunto de
herramientas que Antigravity puede invocar de forma estructurada.

---

## Paso 1 — Habilitar la API de n8n

1. Accede a n8n en `http://localhost:5678`.
2. Ve a **Settings → API**.
3. Activa la API REST de n8n.
4. Copia la **API Key** generada.

> ⚠️ Guarda la API Key de forma segura. No la escribas en ningún archivo
> versionado.

---

## Paso 2 — Obtener la URL base de n8n

La URL base de n8n para el MCP depende de tu entorno:

| Entorno | URL |
|---------|-----|
| Local (Docker) | `http://localhost:5678` |
| Producción (Cloudflare Tunnel) | El valor de `N8N_PUBLIC_URL` en tu `.env` |

La URL del endpoint MCP de n8n sigue este patrón:

```
{URL_BASE}/mcp
```

Ejemplo local: `http://localhost:5678/mcp`

> Verifica que este endpoint responda correctamente antes de configurar
> Antigravity.

---

## Paso 3 — Configurar Antigravity

### Formato de configuración

Antigravity almacena la configuración MCP en:

```
C:\Users\Emerson.Collazo\.gemini\config\mcp_config.json
```

La configuración del servidor `n8n-laboratorio` sigue este esquema:

```json
{
  "mcpServers": {
    "n8n-laboratorio": {
      "type": "http",
      "url": "INSERTAR_URL_DEL_MCP_AQUI",
      "headers": {
        "Authorization": "Bearer INSERTAR_TOKEN_AQUI"
      }
    }
  }
}
```

> ⚠️ **IMPORTANTE:** Antigravity no soporta variables de entorno dentro del
> archivo `mcp_config.json` en esta versión. Los valores deben configurarse
> manualmente.

### Instrucciones de configuración manual

1. Abre el archivo `mcp_config.json`:
   ```
   C:\Users\Emerson.Collazo\.gemini\config\mcp_config.json
   ```

2. Agrega la entrada `n8n-laboratorio` dentro del objeto `mcpServers`,
   conservando las entradas existentes (por ejemplo, `github-mcp-server`).

3. Reemplaza los marcadores:
   - `INSERTAR_URL_DEL_MCP_AQUI` → URL del endpoint MCP de n8n
     (ejemplo: `http://localhost:5678/mcp`)
   - `INSERTAR_TOKEN_AQUI` → API Key copiada del panel de n8n en el Paso 1

4. Guarda el archivo.

5. Reinicia Antigravity para que detecte el nuevo servidor MCP.

### Ejemplo de configuración completa (con marcadores, no valores reales)

```json
{
  "mcpServers": {
    "github-mcp-server": {
      "...": "configuración existente — no modificar"
    },
    "n8n-laboratorio": {
      "type": "http",
      "url": "INSERTAR_URL_DEL_MCP_AQUI",
      "headers": {
        "Authorization": "Bearer INSERTAR_TOKEN_AQUI"
      }
    }
  }
}
```

---

## Paso 4 — Variables de entorno de referencia

El archivo `.env.n8n-mcp.example` en la raíz del proyecto documenta las
variables relacionadas con el MCP:

```bash
# .env.n8n-mcp.example
N8N_MCP_URL=
N8N_MCP_TOKEN=
```

Puedes usar estas variables para guardar la URL y el token de forma segura en
tu entorno, aunque actualmente Antigravity requiere que los valores se
ingresen manualmente en `mcp_config.json`.

---

## Protección del token

### Dónde guardar el token de forma segura

- Gestor de contraseñas (recomendado): Bitwarden, 1Password, etc.
- Variable de entorno del sistema operativo (fuera del repositorio).
- **Nunca:** en archivos `.env` versionados, en el código, ni en commits.

### Verificar que el token no está en el repositorio

```bash
# Desde la raíz del proyecto
git log --all --full-history -- "**/*.env" "**/*token*" "**/*secret*"
git grep -r "n8n_api" --
```

---

## Cómo rotar el token

1. Accede a n8n → **Settings → API**.
2. Revoca la API Key actual.
3. Genera una nueva API Key.
4. Actualiza el valor en `mcp_config.json` manualmente.
5. Reinicia Antigravity.
6. Verifica la conexión (ver `mcp-verification.md`).

---

## Cómo desactivar el acceso del MCP

1. Accede a n8n → **Settings → API**.
2. Desactiva la API REST o revoca la API Key.
3. El servidor MCP `n8n-laboratorio` dejará de responder inmediatamente.
4. Opcionalmente, elimina la entrada `n8n-laboratorio` de `mcp_config.json`
   y reinicia Antigravity.

---

## Archivos sensibles excluidos de Git

El archivo `.gitignore` del proyecto ya excluye:

```
.env
.env.local
.env.*.local
```

El archivo `mcp_config.json` de Antigravity está en:
```
C:\Users\Emerson.Collazo\.gemini\config\mcp_config.json
```
Este archivo está fuera del repositorio del proyecto y **no se versiona**.

> ⚠️ **Nunca copies `mcp_config.json` al repositorio del proyecto.**

---

## Resumen de archivos relacionados con el MCP

| Archivo | Ubicación | Contiene secretos | Versionado |
|---------|-----------|-------------------|-----------|
| `mcp_config.json` | `C:\Users\...\config\` | **Sí** (token en texto plano) | **No** — fuera del repo |
| `.env.n8n-mcp.example` | Raíz del proyecto | **No** (solo marcadores) | **Sí** — referencia segura |
| `.env` | Raíz del proyecto | **Sí** (si se configura) | **No** — excluido en `.gitignore` |
