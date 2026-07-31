#!/bin/bash
# =============================================================================
# LabResultados — Server Backup Script
# Respalda: PostgreSQL + PDFs clinicos + n8n (workflows y credenciales)
# Retiene los ultimos 7 dias de backups por categoria.
# Ejecutar manualmente o via cron (ver install_cron.sh).
# =============================================================================

set -euo pipefail

# --- Configuracion -----------------------------------------------------------
PROJECT_DIR="$HOME/LabResultados"
BACKUP_DIR="$HOME/backups/labresultados"
RETAIN_DAYS=7
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
LOG_FILE="$BACKUP_DIR/backup.log"

DB_CONTAINER="labresultados-db-1"

# --- Funcion de logging ------------------------------------------------------
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

# --- Crear directorios -------------------------------------------------------
mkdir -p "$BACKUP_DIR/db" "$BACKUP_DIR/pdfs" "$BACKUP_DIR/n8n"

log "=========================================="
log "Iniciando backup de LabResultados"
log "=========================================="

# --- Leer credenciales del .env ----------------------------------------------
if [ ! -f "$PROJECT_DIR/.env" ]; then
    log "ERROR: No se encontro $PROJECT_DIR/.env"
    exit 1
fi

POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"'"'"'')
POSTGRES_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"'"'"'')
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '"'"'"'')

if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_PASSWORD" ] || [ -z "$POSTGRES_DB" ]; then
    log "ERROR: No se pudieron leer las credenciales de PostgreSQL desde .env"
    exit 1
fi

# --- 1. PostgreSQL dump ------------------------------------------------------
DB_FILE="$BACKUP_DIR/db/labresultados_$TIMESTAMP.sql.gz"
log "Respaldando PostgreSQL -> $(basename "$DB_FILE")"

if ! docker ps --filter "name=$DB_CONTAINER" --filter "status=running" -q | grep -q .; then
    log "ERROR: Contenedor '$DB_CONTAINER' no esta corriendo. Backup abortado."
    exit 1
fi

docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CONTAINER" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-password \
    | gzip > "$DB_FILE"

DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
log "PostgreSQL OK -- Tamano: $DB_SIZE"

# --- 2. PDFs clinicos (volumen pdf_storage_local) ----------------------------
PDF_FILE="$BACKUP_DIR/pdfs/pdfs_$TIMESTAMP.tar.gz"
log "Respaldando PDFs -> $(basename "$PDF_FILE")"

docker run --rm \
    -v pdf_storage_local:/data:ro \
    -v "$BACKUP_DIR/pdfs:/backup" \
    alpine sh -c "tar czf /backup/pdfs_${TIMESTAMP}.tar.gz -C /data . 2>/dev/null; echo ok"

PDF_SIZE=$(du -h "$PDF_FILE" | cut -f1)
log "PDFs OK -- Tamano: $PDF_SIZE"

# --- 3. n8n (workflows + credenciales, volumen n8n_data_local) ---------------
N8N_FILE="$BACKUP_DIR/n8n/n8n_$TIMESTAMP.tar.gz"
log "Respaldando n8n -> $(basename "$N8N_FILE")"

docker run --rm \
    -v n8n_data_local:/data:ro \
    -v "$BACKUP_DIR/n8n:/backup" \
    alpine sh -c "tar czf /backup/n8n_${TIMESTAMP}.tar.gz -C /data . 2>/dev/null; echo ok"

N8N_SIZE=$(du -h "$N8N_FILE" | cut -f1)
log "n8n OK -- Tamano: $N8N_SIZE"

# --- 4. Purgar backups viejos ------------------------------------------------
log "Purgando backups con mas de $RETAIN_DAYS dias..."

PRUNED=0
for dir in db pdfs n8n; do
    while IFS= read -r -d '' f; do
        rm -f "$f"
        log "  Eliminado: $(basename "$f")"
        PRUNED=$((PRUNED + 1))
    done < <(find "$BACKUP_DIR/$dir" -type f -mtime "+$RETAIN_DAYS" -print0 2>/dev/null)
done

[ "$PRUNED" -eq 0 ] && log "Sin backups viejos que eliminar." || log "Eliminados: $PRUNED archivo(s)."

# --- Resumen -----------------------------------------------------------------
DB_COUNT=$(find "$BACKUP_DIR/db"   -name "*.sql.gz"  2>/dev/null | wc -l | tr -d ' ')
PDF_COUNT=$(find "$BACKUP_DIR/pdfs" -name "*.tar.gz" 2>/dev/null | wc -l | tr -d ' ')
N8N_COUNT=$(find "$BACKUP_DIR/n8n"  -name "*.tar.gz" 2>/dev/null | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

log "=========================================="
log "Backup completado exitosamente"
log "  DB: $DB_COUNT | PDFs: $PDF_COUNT | n8n: $N8N_COUNT archivo(s)"
log "  Espacio total en $BACKUP_DIR: $TOTAL_SIZE"
log "=========================================="
