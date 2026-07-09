#!/usr/bin/env bash
# ============================================================
# Despliegue masivo: actualiza TODOS los tenants de una sola vez.
# Recorre deploy/tenants.tsv y en cada carpeta hace:
#   git pull  →  pip install  →  migrate  →  collectstatic  →  restart gunicorn
#
# Uso (en el servidor):
#   ./scripts/deploy_all.sh                # todos
#   ./scripts/deploy_all.sh comertex redp  # solo esos clientes
#   DRY_RUN=1 ./scripts/deploy_all.sh      # muestra qué haría, sin ejecutar
#
# Requiere: deploy/tenants.tsv (ver deploy/tenants.example.tsv)
#           cada carpeta con su venv en <carpeta>/venv y su .env propio.
# ============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TENANTS_FILE="${TENANTS_FILE:-$SCRIPT_DIR/deploy/tenants.tsv}"
FILTER=("$@")
FAILED=()

log()  { printf '\033[1;36m[%s]\033[0m %s\n' "$1" "$2"; }
run()  { if [ "${DRY_RUN:-0}" = "1" ]; then echo "   DRY: $*"; else eval "$*"; fi; }

if [ ! -f "$TENANTS_FILE" ]; then
    echo "ERROR: no existe $TENANTS_FILE (copia deploy/tenants.example.tsv → deploy/tenants.tsv)"
    exit 1
fi

quiere() {  # ¿este cliente está en el filtro? (vacío = todos)
    [ ${#FILTER[@]} -eq 0 ] && return 0
    for f in "${FILTER[@]}"; do [ "$f" = "$1" ] && return 0; done
    return 1
}

while IFS=$'\t' read -r cliente carpeta dominio s3 servicio notas; do
    case "$cliente" in ''|\#*) continue ;; esac      # saltar comentarios/vacíos
    quiere "$cliente" || continue

    echo "============================================================"
    log "$cliente" "$carpeta  ($dominio)"

    if [ ! -d "$carpeta/.git" ]; then
        log "$cliente" "SKIP: no es repo git en $carpeta"; FAILED+=("$cliente:no-repo"); continue
    fi
    PY="$carpeta/venv/bin/python"
    PIP="$carpeta/venv/bin/pip"
    [ -x "$PY" ] || { log "$cliente" "SKIP: sin venv en $carpeta/venv"; FAILED+=("$cliente:no-venv"); continue; }

    ( set -e
      cd "$carpeta"
      log "$cliente" "git pull";        run "git pull --ff-only"
      log "$cliente" "pip install";      run "$PIP install -q -r requirements.txt"
      log "$cliente" "migrate";          run "$PY manage.py migrate --noinput"
      log "$cliente" "collectstatic";    run "$PY manage.py collectstatic --noinput"
      log "$cliente" "restart $servicio";run "sudo systemctl restart $servicio"
    ) || { log "$cliente" "FALLÓ ❌"; FAILED+=("$cliente"); }
done < "$TENANTS_FILE"

echo "============================================================"
if [ ${#FAILED[@]} -eq 0 ]; then
    log "OK" "Todos los tenants actualizados."
else
    log "REVISAR" "Fallaron: ${FAILED[*]}"; exit 1
fi
