#!/bin/bash
# =============================================================================
# LabResultados — Instalar cron job de backup diario
# Ejecutar UNA VEZ en el servidor Ubuntu.
# Registra: backup diario a las 2:00 AM
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/server_backup.sh"

# Verificar que el script de backup existe
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "ERROR: No se encontro $BACKUP_SCRIPT"
    exit 1
fi

# Dar permisos de ejecucion
chmod +x "$BACKUP_SCRIPT"
chmod +x "$SCRIPT_DIR/server_restore.sh" 2>/dev/null || true

echo "Script de backup: $BACKUP_SCRIPT"

# Construir la linea de cron
CRON_LINE="0 2 * * * $BACKUP_SCRIPT >> $HOME/backups/labresultados/cron.log 2>&1"

# Agregar al crontab sin duplicar
EXISTING=$(crontab -l 2>/dev/null || echo "")

if echo "$EXISTING" | grep -qF "$BACKUP_SCRIPT"; then
    echo "El cron job ya esta registrado:"
    echo "  $CRON_LINE"
else
    (echo "$EXISTING"; echo "$CRON_LINE") | crontab -
    echo ""
    echo "Cron job registrado exitosamente:"
    echo "  $CRON_LINE"
fi

echo ""
echo "Crontab actual:"
crontab -l

echo ""
echo "Para ejecutar el backup manualmente:"
echo "  $BACKUP_SCRIPT"
echo ""
echo "Para ver el log:"
echo "  tail -f $HOME/backups/labresultados/backup.log"
