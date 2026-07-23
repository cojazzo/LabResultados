import json
import os

input_file = "docs/n8n/LabResultados_envio_puente.n8n.json"
output_file = "docs/n8n/LabResultados_envio_EWS.n8n.json"

with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Update name
data["name"] = "LabResultados - Envío de resultados vía EWS"

# Filter out old nodes we don't need
nodes_to_keep = [
    "Nota: configuración requerida",
    "Nota: endpoints supuestos",
    "Webhook: enviar resultados",
    "Validar payload",
    "Backend: preparar envíos",
    "Construir tarea de envío",
    "Leer PDF del servidor",
    "Resumen",
    "Responder al frontend"
]

new_nodes = [n for n in data["nodes"] if n["name"] in nodes_to_keep]

# Update the Sticky Notes
for n in new_nodes:
    if n["name"] == "Nota: configuración requerida":
        n["parameters"]["content"] = "## Antes de activar\n1. Crear credencial **Header Auth** para la API del backend y asignarla a los nodos HTTP Request de preparar y confirmar.\n2. Crear credencial **Header Auth** para la API EWS (`X-API-Key`) y asignarla al nodo HTTP Request EWS.\n3. Asegurarse que el contenedor n8n tiene acceso a `/data/pdfs`.\n4. El flujo se entrega INACTIVO."
    if n["name"] == "Nota: endpoints supuestos":
        n["parameters"]["content"] = "## Endpoints del backend (AJUSTAR a tu FastAPI)\n**POST /api/envios/preparar**\n**POST /api/envios/confirmar**\n\nEl webhook responde rápido al frontend, y en paralelo procesa los correos."

# Add new EWS nodes
new_nodes.extend([
    {
      "id": "code-base64",
      "name": "Preparar Base64 y JSON",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1040, 150],
      "parameters": {
        "mode": "runOnceForEachItem",
        "jsCode": "const json = $json;\nconst binaryData = $binary.data.data;\n\nreturn {\n  json: {\n    ...json,\n    pdf_base64: binaryData\n  }\n};"
      }
    },
    {
      "id": "http-ews",
      "name": "Enviar Email via EWS",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1260, 150],
      "parameters": {
        "method": "POST",
        "url": "http://127.0.0.1:8765/send-email",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ to: $json.para, subject: $json.asunto, body: $json.cuerpo_html, is_html: true, attachments: [{ filename: $json.pdf_filename, content_base64: $json.pdf_base64 }] }) }}",
        "options": {}
      }
    },
    {
      "id": "http-confirmar",
      "name": "Backend: confirmar éxito",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1480, 150],
      "parameters": {
        "method": "POST",
        "url": "http://backend:8000/api/envios/confirmar",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ id: $('Construir tarea de envío').item.json.id, estado: 'enviado', destinatario: $('Construir tarea de envío').item.json.para, fecha: new Date().toISOString() }) }}",
        "options": {}
      }
    }
])

data["nodes"] = new_nodes

# Rebuild connections
# The webhook needs to respond quickly. So we split after 'Backend: preparar envíos'
data["connections"] = {
    "Webhook: enviar resultados": {
      "main": [
        [
          {
            "node": "Validar payload",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Validar payload": {
      "main": [
        [
          {
            "node": "Backend: preparar envíos",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Backend: preparar envíos": {
      "main": [
        [
          {
            "node": "Construir tarea de envío",
            "type": "main",
            "index": 0
          },
          {
            "node": "Resumen",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Resumen": {
      "main": [
        [
          {
            "node": "Responder al frontend",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Construir tarea de envío": {
      "main": [
        [
          {
            "node": "Leer PDF del servidor",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Leer PDF del servidor": {
      "main": [
        [
          {
            "node": "Preparar Base64 y JSON",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Preparar Base64 y JSON": {
      "main": [
        [
          {
            "node": "Enviar Email via EWS",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Enviar Email via EWS": {
      "main": [
        [
          {
            "node": "Backend: confirmar éxito",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    
print("Workflow adapted!")
