#!/bin/bash
# =============================================================================
# LabResultados — Server Restore Script
# Uso:
#   ./server_restore.sh                        <- restaura el backup mas reciente
#   ./server_restore.sh -d 2026-07-31_02-00    <- restaura un timestamp especifico
#
# ADVERTENCIA: Reemplaza TODOS los datos actuales con el backup seleccionado.
# =============================================================================

set -euo pipefail

PROJECT_DIR="$HOME/LabResultados"
BACKUP_DIR="$HOME/backups/labresultados"
DB_CONTAINER="labresultados-db-1"

# --- Funcion de logging ------------------------------------------------------
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# --- Parsear argumentos ------------------------------------------------------
TARGET_TS=""
while getopts "d:" opt; do
    case $opt in
        d) TARGET_TS="$OPTARG" ;;
        *) echo "Uso: $0 [-d TIMESTAMP]"; exit 1 ;;
    esac
done

# --- Leer credenciales -------------------------------------------------------
if [ ! -f "$PROJECT_DIR/.env" ]; then
    log "ERROR: No se encontro $PROJECT_DIR/.env"
    exit 1
fi

POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"'"'"'')
POSTGRES_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"'"'"'')
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"'"'"'')

# --- Resolver archivos a restaurar -------------------------------------------
if [ -z "$TARGET_TS" ]; then
    DB_FILE=$(find "$BACKUP_DIR/db"   -name "*.sql.gz"  | sort -r | head -1)
    PDF_FILE=$(find "$BACKUP_DIR/pdfs" -name "*.tar.gz" | sort -r | head -1)
    N8N_FILE=$(find "$BACKUP_DIR/n8n"  -name "*.tar.gz" | sort -r | head -1)
    log "Sin timestamp especificado. Usando el backup mas reciente."
else
    DB_FILE="$BACKUP_DIR/db/labresultados_$TARGET_TS.sql.gz"
    PDF_FILE="$BACKUP_DIR/pdfs/pdfs_$TARGET_TS.tar.gz"
    N8N_FILE="$BACKUP_DIR/n8n/n8n_$TARGET_TS.tar.gz"
fi

# --- Verificar que existan ---------------------------------------------------
MISSING=0
[ ! -f "$DB_FILE"  ] && log "AVISO: No se encontro dump de DB: $DB_FILE"   && MISSING=$((MISSING+1))
[ ! -f "$PDF_FILE" ] && log "AVISO: No se encontro backup de PDFs: $PDF_FILE" && MISSING=$((MISSING+1))
[ ! -f "$N8N_FILE" ] && log "AVISO: No se encontro backup de n8n: $N8N_FILE"  && MISSING=$((MISSING+1))

[ "$MISSING" -eq 3 ] && log "ERROR: No hay archivos de backup para restaurar." && exit 1

# --- Confirmacion de seguridad -----------------------------------------------
echo ""
echo "  ==========================================================="
echo "  ADVERTENCIA: Esta operacion reemplaza TODOS los datos"
echo "  actuales de LabResultados con el backup seleccionado."
echo "  ==========================================================="
echo ""
[ -f "$DB_FILE"  ] && echo "  DB   : $(basename "$DB_FILE")"
[ -f "$PDF_FILE" ] && echo "  PDFs : $(basename "$PDF_FILE")"
[ -f "$N8N_FILE" ] && echo "  n8n  : $(basename "$N8N_FILE")"
echo ""
read -r -p "  Escribe 'restaurar' para continuar, cualquier otra cosa cancela: " CONFIRM
if [ "$CONFIRM" != "restaurar" ]; then
    log "Restauracion cancelada por el usuario."
    exit 0
fi

# --- Detener servicios que usan los datos ------------------------------------
log "Deteniendo backend y n8n..."
cd "$PROJECT_DIR"
sudo docker compose stop backend n8n 2>/dev/null || true

# --- 1. Restaurar PostgreSQL -------------------------------------------------
if [ -f "$DB_FILE" ]; then
    log "Restaurando PostgreSQL desde $(basename "$DB_FILE")..."

    docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CONTAINER" \
        psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB;" 2>&1
    docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CONTAINER" \
        psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $POSTGRES_DB;" 2>&1

    gunzip -c "$DB_FILE" | docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CONTAINER" \
        psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q

    log "PostgreSQL restaurado."
fi

# --- 2. Restaurar PDFs -------------------------------------------------------
if [ -f "$PDF_FILE" ]; then
    log "Restaurando PDFs desde $(basename "$PDF_FILE")..."

    docker run --rm \
        -v pdf_storage_local:/data \
        -v "$BACKUP_DIR/pdfs:/backup:ro" \
        alpine sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null; tar xzf /backup/$(basename "$PDF_FILE") -C /data"

    log "PDFs restaurados."
fi

# --- 3. Restaurar n8n --------------------------------------------------------
if [ -f "$N8N_FILE" ]; then
    log "Restaurando n8n desde $(basename "$N8N_FILE")..."

    docker run --rm \
        -v n8n_data_local:/data \
        -v "$BACKUP_DIR/n8n:/backup:ro" \
        alpine sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null; tar xzf /backup/$(basename "$N8N_FILE") -C /data"

    log "n8n restaurado."
fi

# --- Reiniciar servicios -----------------------------------------------------
log "Reiniciando servicios..."
cd "$PROJECT_DIR"
sudo docker compose start backend n8n 2>/dev/null || true

log "=========================================="
log "Restauracion completada."
log "Verifica con: sudo docker compose ps"
log "=========================================="
