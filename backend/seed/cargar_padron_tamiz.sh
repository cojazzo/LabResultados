#!/usr/bin/env bash
# Carga el padrón de tamiz-escolar en LabResultados.
# Se ejecuta desde tu PC (Git Bash), en la raíz del repo o en cualquier carpeta:
#   bash backend/seed/cargar_padron_tamiz.sh            # simulación (hace rollback, no guarda nada)
#   bash backend/seed/cargar_padron_tamiz.sh --real     # carga real
# Requisitos: el backend de LabResultados ya desplegado con la migración de folio_tamiz.
# Los datos de los alumnos se exportan y cargan DENTRO del servidor; no pasan por tu PC.
set -euo pipefail

SSH="ssh -i $HOME/.ssh/inaerserver_claude_key -o BatchMode=yes -o IdentitiesOnly=yes inaer@192.168.1.204"
SQL="$(dirname "$0")/export_padron_tamiz.sql"
ARGS="--dry-run"
[ "${1:-}" = "--real" ] && ARGS=""

echo "1/4 Exportando el padrón desde tamiz-escolar (solo lectura)..."
$SSH "umask 077; docker exec -i tamiz-escolar-db-1 psql -U tamiz -d tamiz -t -A > /tmp/padron_tamiz.jsonl && wc -l /tmp/padron_tamiz.jsonl" < "$SQL"

echo "2/4 Copiando al contenedor de LabResultados..."
$SSH "docker cp /tmp/padron_tamiz.jsonl labresultados-backend-1:/tmp/padron_tamiz.jsonl"

echo "3/4 Cargando ${ARGS:-(REAL)}..."
$SSH "docker exec labresultados-backend-1 python seed/sync_padron_tamiz.py /tmp/padron_tamiz.jsonl $ARGS"

echo "4/4 Borrando archivos temporales con datos de alumnos..."
$SSH "rm -f /tmp/padron_tamiz.jsonl; docker exec labresultados-backend-1 rm -f /tmp/padron_tamiz.jsonl"
echo "Listo."
