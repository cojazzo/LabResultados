#!/bin/bash
# =============================================================================
# LabResultados — Sincronizar servidor con el repo (sin conflictos)
# Ejecutar en el servidor: bash scripts/sync_server.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="$HOME/LabResultados"
cd "$PROJECT_DIR"

echo "[1/4] Guardando cambios locales con stash..."
git stash

echo "[2/4] Descargando cambios del repo..."
git pull

echo "[3/4] Descartando stash (cambios locales ya incorporados al repo)..."
git stash drop 2>/dev/null && echo "  Stash descartado." || echo "  Sin stash que descartar."

echo "[4/4] Creando docker-compose.override.yml (configuracion local del servidor)..."
cat > "$PROJECT_DIR/docker-compose.override.yml" << 'EOF'
# Configuracion local del servidor — NO versionar (.gitignore)
services:
  ews:
    env_file:
      - ./backend/email_service/.env
    environment: []
EOF
echo "  docker-compose.override.yml creado."

echo ""
echo "============================================"
echo "Sincronizacion completada."
echo ""
echo "Siguiente paso:"
echo "  sudo docker compose up -d"
echo "  sudo docker compose ps"
echo "============================================"
