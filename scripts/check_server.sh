#!/bin/bash
# =============================================================================
# LabResultados — Diagnostico de Estado del Servidor
# Ejecutar en el servidor:  bash scripts/check_server.sh
# =============================================================================

set -uo pipefail

PROJECT_DIR="$HOME/LabResultados"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}V $*${NC}"; }
fail() { echo -e "  ${RED}X $*${NC}"; }
warn() { echo -e "  ${YELLOW}! $*${NC}"; }
info() { echo -e "  ${CYAN}> $*${NC}"; }
header() { echo ""; echo -e "${CYAN}============================================${NC}"; echo -e "${CYAN}  $*${NC}"; echo -e "${CYAN}============================================${NC}"; }

# ===========================================================================
header "1. CONTENEDORES DOCKER"
# ===========================================================================
cd "$PROJECT_DIR"

for c in laboratorioext-backend-1 laboratorioext-frontend-1 laboratorioext-db-1; do
  STATUS=$(docker inspect --format '{{.State.Status}}' "$c" 2>/dev/null || echo "no_encontrado")
  HEALTH=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}' "$c" 2>/dev/null || echo "?")
  [ "$STATUS" = "running" ] && ok "$c — corriendo [$HEALTH]" || fail "$c — $STATUS"
done

N8N=$(docker inspect --format '{{.State.Status}}' "laboratorioext-n8n-1" 2>/dev/null || echo "no_encontrado")
[ "$N8N" = "running" ] && ok "n8n — corriendo" || warn "n8n — $N8N"

TUNNEL=$(docker inspect --format '{{.State.Status}}' "laboratorioext-tunnel-1" 2>/dev/null || echo "no_encontrado")
[ "$TUNNEL" = "running" ] && ok "cloudflare-tunnel — corriendo" || warn "cloudflare-tunnel — $TUNNEL"

# ===========================================================================
header "2. BACKEND FASTAPI (localhost:$BACKEND_PORT)"
# ===========================================================================

HC=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${BACKEND_PORT}/health" 2>/dev/null || echo "000")
[ "$HC" = "200" ] && ok "/health — HTTP $HC" || fail "/health — HTTP $HC (backend no responde)"

LOGIN=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:${BACKEND_PORT}/api/auth/login" \
  -d "username=admin&password=TEST_INVALIDO" 2>/dev/null || echo "000")
if   [ "$LOGIN" = "401" ]; then ok "/api/auth/login — HTTP 401 (endpoint activo, credencial de prueba rechazada)"
elif [ "$LOGIN" = "000" ]; then fail "/api/auth/login — sin respuesta (timeout)"
else warn "/api/auth/login — HTTP $LOGIN"; fi

DOCS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${BACKEND_PORT}/docs" 2>/dev/null || echo "000")
[ "$DOCS" = "200" ] && ok "/docs — HTTP $DOCS" || fail "/docs — HTTP $DOCS"

# ===========================================================================
header "3. FRONTEND / NGINX (localhost:$FRONTEND_PORT)"
# ===========================================================================

FRONT=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${FRONTEND_PORT}/" 2>/dev/null || echo "000")
[ "$FRONT" = "200" ] && ok "/ — HTTP $FRONT" || fail "/ — HTTP $FRONT"

PROXY=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:${FRONTEND_PORT}/api/auth/login" \
  -d "username=admin&password=TEST_INVALIDO" 2>/dev/null || echo "000")
if   [ "$PROXY" = "401" ]; then ok "Proxy /api/auth/login — 401 (Nginx ? Backend OK)"
elif [ "$PROXY" = "502" ]; then
  fail "Proxy /api/auth/login — 502 BAD GATEWAY (Nginx no alcanza el backend)"
  warn "  Solucion: sudo docker compose restart frontend"
elif [ "$PROXY" = "000" ]; then fail "Proxy /api/auth/login — sin respuesta"
else warn "Proxy /api/auth/login — HTTP $PROXY"; fi

# ===========================================================================
header "4. BASE DE DATOS POSTGRESQL"
# ===========================================================================

DB_HEALTH=$(docker inspect --format '{{.State.Health.Status}}' "laboratorioext-db-1" 2>/dev/null || echo "desconocido")
[ "$DB_HEALTH" = "healthy" ] && ok "DB — healthy" || fail "DB — $DB_HEALTH"

TABLE_COUNT=$(docker exec laboratorioext-db-1 \
  psql -U lab_user -d lab_resultados -t -c \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d ' \n' || echo "error")
[[ "$TABLE_COUNT" =~ ^[0-9]+$ ]] && [ "$TABLE_COUNT" -gt 0 ] \
  && ok "Tablas en BD: $TABLE_COUNT" \
  || fail "Error al contar tablas: $TABLE_COUNT"

ADMIN=$(docker exec laboratorioext-db-1 \
  psql -U lab_user -d lab_resultados -t -c \
  "SELECT is_active FROM usuarios WHERE username='admin' LIMIT 1;" \
  2>/dev/null | tr -d ' \n' || echo "")
if   [ "$ADMIN" = "t" ]; then ok "Usuario 'admin' — activo"
elif [ "$ADMIN" = "f" ]; then fail "Usuario 'admin' — INACTIVO"
else fail "Usuario 'admin' — NO EXISTE en la BD"; fi

ALEMBIC_CUR=$(docker exec laboratorioext-backend-1 alembic current 2>/dev/null \
  | grep -v "^INFO" | tr -d ' \n' || echo "error")
ALEMBIC_HEAD=$(docker exec laboratorioext-backend-1 alembic heads 2>/dev/null \
  | grep -v "^INFO" | tr -d ' \n' || echo "error")
info "Alembic actual: ${ALEMBIC_CUR}"
info "Alembic head:   ${ALEMBIC_HEAD}"
[ "$ALEMBIC_CUR" != "$ALEMBIC_HEAD" ] && [ -n "$ALEMBIC_HEAD" ] \
  && warn "Migraciones pendientes: sudo docker exec laboratorioext-backend-1 alembic upgrade head"

# ===========================================================================
header "5. LOGS DE ERRORES RECIENTES"
# ===========================================================================
echo ""
info "Backend (ultimos errores):"
docker logs laboratorioext-backend-1 2>&1 | grep -i "error\|exception\|traceback" | tail -5 || echo "  (sin errores)"

echo ""
info "Nginx (ultimos errores):"
docker logs laboratorioext-frontend-1 2>&1 | grep -i "error\|emerg\|crit\|502" | tail -5 || echo "  (sin errores)"

# ===========================================================================
header "6. PUERTOS EN ESCUCHA"
# ===========================================================================
for PORT in $BACKEND_PORT $FRONTEND_PORT 5432 5433 5678; do
  ( ss -tlnp 2>/dev/null | grep -q ":${PORT} " \
    || netstat -tlnp 2>/dev/null | grep -q ":${PORT} " ) \
    && ok "Puerto $PORT — ESCUCHANDO" \
    || warn "Puerto $PORT — no detectado"
done

# ===========================================================================
header "7. DISCO Y VOLUMENES"
# ===========================================================================
df -h "$HOME" | awk 'NR==2{printf "  Disco: %s usado / %s total (%s libre)\n", $3, $2, $4}'
echo ""
info "Docker disk usage:"
docker system df 2>/dev/null | tail -n +2 | sed 's/^/  /'

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Diagnostico completado: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
