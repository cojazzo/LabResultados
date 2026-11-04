#!/usr/bin/env bash
# Importa un workflow exportado (.n8n.json) a n8n por su API pública. El workflow queda INACTIVO.
# La API key se pide por teclado (sin mostrarse); no se guarda en ningún archivo ni se imprime.
#   bash docs/n8n/importar_workflow.sh docs/n8n/LabResultados_forms_a_perfil.n8n.json
set -euo pipefail

ARCHIVO="${1:?Uso: importar_workflow.sh <archivo.n8n.json>}"
N8N_URL="${N8N_URL:-http://192.168.1.204:5678}"

read -r -s -p "API key de n8n: " N8N_KEY
echo

# La API solo acepta name, nodes, connections y settings (sin 'active', 'pinData', etc.)
CUERPO="$(python - "$ARCHIVO" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(json.dumps({k: d[k] for k in ("name", "nodes", "connections", "settings") if k in d}, ensure_ascii=False))
PY
)"

RESP="$(printf '%s' "$CUERPO" | curl -s -w '\n%{http_code}' -X POST "$N8N_URL/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_KEY" -H "Content-Type: application/json; charset=utf-8" --data-binary @-)"
unset N8N_KEY
CODIGO="$(printf '%s' "$RESP" | tail -n1)"
SALIDA="$(printf '%s' "$RESP" | sed '$d')"

if [ "$CODIGO" = "200" ]; then
  printf '%s' "$SALIDA" | python -c "import json,sys; d=json.load(sys.stdin); print('Creado: id', d['id'], '| activo:', d.get('active'), '|', d['name'])"
else
  echo "Fallo HTTP $CODIGO"
  printf '%s' "$SALIDA" | head -c 600
  echo
  exit 1
fi
