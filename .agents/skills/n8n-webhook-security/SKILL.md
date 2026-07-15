---
name: n8n-webhook-security
description: >
  Guía al agente en la configuración segura de webhooks en n8n. Se activa
  cuando se trabaja con Webhook Trigger, APIs entrantes, autenticación,
  firmas HMAC, tokens de acceso, encabezados de autorización, endpoints
  públicos o recepción de eventos externos. Exige HTTPS, autenticación,
  validación de payload, protección anti-replay e idempotencia.
triggers:
  - Webhook Trigger
  - configurar webhook
  - recibir eventos
  - API entrante
  - autenticación de webhook
  - firma HMAC
  - token de acceso
  - encabezado de autorización
  - endpoint público
  - protección anti-replay
  - validar payload
---

# Skill: n8n Webhook Security

## Propósito

Garantizar que todos los webhooks configurados en n8n cumplan con los
controles de seguridad necesarios antes de ser expuestos públicamente.

## Lista de Requisitos de Seguridad

Antes de considerar un webhook listo para producción, verifica y configura
**todos** los puntos siguientes:

### 1. HTTPS obligatorio

- El webhook debe estar expuesto exclusivamente bajo HTTPS.
- Nunca expongas webhooks en HTTP en producción.
- Verifica que la URL pública configurada en `WEBHOOK_URL` (variable de entorno
  de n8n) use `https://`.

### 2. Autenticación del webhook

Elige **al menos uno** de los siguientes mecanismos:

| Mecanismo | Cuándo usarlo |
|-----------|--------------|
| Header Secret (Bearer token o header personalizado) | Sistemas internos y simples. |
| Firma HMAC | Proveedores externos (GitHub, Stripe, Twilio, etc.). |
| Basic Auth | Solo si el cliente no soporta headers personalizados. |
| mTLS | Requisitos de alta seguridad. |

- Configura el mecanismo elegido **desde n8n** (Webhook node → Authentication).
- No escribas el secreto directamente en el nodo; usa una credencial de n8n.

### 3. Validación estricta del payload

- Verifica que los campos requeridos estén presentes.
- Verifica los tipos de dato esperados.
- Rechaza payloads con campos inesperados (strict mode) cuando el origen es
  un sistema controlado por ti.
- Limita el tamaño máximo del payload (configura `N8N_PAYLOAD_SIZE_MAX` en el
  servidor o valida en el primer nodo del workflow).

### 4. Verificación de firma HMAC

Aplica cuando el proveedor externo soporte firmas (GitHub, Stripe, etc.):

```
Pasos:
1. Obtén el cuerpo RAW del request (antes de parsear JSON).
2. Calcula HMAC-SHA256 usando el secreto compartido.
3. Compara con el header de firma enviado por el proveedor.
4. Usa comparación de tiempo constante para evitar timing attacks.
5. Rechaza si la firma no coincide (HTTP 401).
```

- Implementa la verificación en un nodo `Code` o usando el nodo nativo de
  n8n para el proveedor específico (si está disponible).
- Documenta en el workflow qué header contiene la firma y el algoritmo usado.

### 5. Validación de marca de tiempo

- Si el proveedor envía un timestamp en el payload o en un header, valídalo.
- Rechaza eventos con más de **5 minutos** de antigüedad (ajustar según caso).
- Esto protege contra ataques de replay con requests capturados.

```
if (Math.abs(Date.now() - timestamp * 1000) > 300000) {
  // Rechazar: timestamp fuera de ventana permitida
}
```

### 6. Protección contra replay attacks

- Combina la validación de timestamp con un identificador único de evento.
- Nunca proceses el mismo `eventId` dos veces (ver punto 7).

### 7. Uso de `eventId` único

- Extrae el `eventId` del payload (o genera uno basado en el contenido del
  evento).
- Antes de procesar, verifica si el `eventId` ya fue procesado.
- Registra el `eventId` y el resultado en la base de datos o en un store de
  idempotencia.
- Si el `eventId` ya existe, devuelve HTTP 200 sin reprocesar.

### 8. Idempotencia persistente

- Las acciones desencadenadas por el webhook deben ser idempotentes.
- Si el mismo evento llega dos veces, el sistema debe comportarse como si
  hubiera llegado una sola vez.
- Documenta qué campo se usa como clave de idempotencia.

### 9. Límite de tamaño del payload

- Configura un límite máximo de tamaño. Recomendado: **1 MB** para la mayoría
  de casos; ajustar según el caso de uso.
- Rechaza payloads que excedan el límite con HTTP 413.

### 10. Timeout

- Configura un timeout máximo de procesamiento.
- Si el procesamiento es largo (>30 s), considera responder de inmediato con
  HTTP 202 y procesar de forma asíncrona.

### 11. Rate limiting

- Cuando sea posible, configura rate limiting a nivel del proxy inverso
  (Nginx, Cloudflare, Traefik).
- Documenta el límite configurado y dónde está configurado.

### 12. Sanitización de logs

- **Nunca registres en logs:** nombres completos, CURP, diagnósticos,
  resultados clínicos, tokens, firmas ni contraseñas.
- Registra solo: `eventId`, timestamp, tipo de evento, resultado del
  procesamiento y código de error (si aplica).

### 13. Respuestas HTTP explícitas

| Situación | Código HTTP |
|-----------|------------|
| Procesado correctamente | 200 |
| Aceptado, procesando de forma asíncrona | 202 |
| Payload inválido o campos faltantes | 400 |
| Autenticación fallida | 401 |
| Firma inválida | 401 |
| Timestamp fuera de ventana | 401 |
| Evento duplicado (ya procesado) | 200 (idempotente) |
| Payload demasiado grande | 413 |
| Rate limit excedido | 429 |
| Error interno | 500 |

### 14. Rechazo de campos inesperados

- Cuando el origen es un sistema controlado, define un esquema estricto.
- Ignora o rechaza campos no esperados para prevenir ataques de parameter
  pollution.

### 15. Credenciales administradas desde n8n

- Todos los secretos (tokens, claves HMAC, contraseñas) deben estar almacenados
  como credenciales en n8n, no escritos directamente en los nodos.

## Procedimiento de Revisión de Seguridad de Webhook

Antes de exponer públicamente cualquier webhook, verifica este checklist:

```markdown
## Checklist de Seguridad de Webhook

- [ ] HTTPS configurado en WEBHOOK_URL
- [ ] Mecanismo de autenticación elegido y configurado
- [ ] Validación de payload implementada
- [ ] Verificación de firma HMAC (si el proveedor lo soporta)
- [ ] Validación de timestamp implementada
- [ ] Protección anti-replay implementada
- [ ] eventId único extraído y verificado
- [ ] Idempotencia documentada
- [ ] Límite de tamaño del payload configurado
- [ ] Timeout configurado o respuesta asíncrona
- [ ] Rate limiting configurado (nivel proxy/Cloudflare)
- [ ] Logs sanitizados (sin datos sensibles)
- [ ] Respuestas HTTP explícitas configuradas
- [ ] Campos inesperados rechazados (si aplica)
- [ ] Credenciales almacenadas en n8n (no escritas en el nodo)
```

## Restricciones

- ❌ No expongas webhooks en HTTP (solo HTTPS).
- ❌ No escribas tokens, secretos o claves HMAC dentro del workflow.
- ❌ No omitas la autenticación en endpoints públicos.
- ❌ No registres datos de pacientes, diagnósticos ni resultados en los logs
  del webhook.
- ❌ No actives el workflow del webhook sin haber completado el checklist de
  seguridad.

## Informe Esperado al Finalizar

```markdown
## Informe de Seguridad de Webhook

**Endpoint:** [URL sin el token]
**Workflow:** [nombre / ID]
**Fecha:** [fecha]

### Mecanismos de Seguridad Configurados
| Control | Estado | Notas |
|---------|--------|-------|
| HTTPS | ✅ / ❌ | ... |
| Autenticación | ✅ / ❌ | Tipo: ... |
| Firma HMAC | ✅ / ❌ / N/A | ... |
| Validación timestamp | ✅ / ❌ | Ventana: ... min |
| Protección anti-replay | ✅ / ❌ | Campo: eventId |
| Idempotencia | ✅ / ❌ | Store: ... |
| Límite de payload | ✅ / ❌ | Máximo: ... |
| Rate limiting | ✅ / ❌ | Nivel: ... |
| Logs sanitizados | ✅ / ❌ | ... |

### Controles Pendientes
- [control pendiente 1]: [pasos para implementarlo]

### Riesgos Residuales
- [riesgo 1]: [mitigación aplicada o pendiente]
```
