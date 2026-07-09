#!/usr/bin/env bash
# ============================================================
# Alta de un cliente nuevo (modelo silo: 1 carpeta + 1 BD física + 1 servicio).
# Se corre en el servidor DESPUÉS de que el proveedor creó la BD en RDS.
#
# Uso:
#   ./scripts/onboard_tenant.sh <cliente> <carpeta_destino>
#   ej: ./scripts/onboard_tenant.sh nuevocliente /opt/nuevocliente_listas
#
# Qué hace:
#   1. Clona el repo canónico en la carpeta destino.
#   2. Crea el venv e instala dependencias.
#   3. Copia .env.example → .env  (queda por editar a mano con las credenciales).
#   4. Deja indicados los pasos manuales que faltan (editar .env, migrar, systemd).
# NO toca la BD ni crea el servicio systemd automáticamente (eso se revisa a mano).
# ============================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Santiago-caicedo/listas_comertex.git}"
CLIENTE="${1:?Falta el nombre del cliente}"
DEST="${2:?Falta la carpeta destino (ej: /opt/${CLIENTE}_listas)}"

[ -e "$DEST" ] && { echo "ERROR: $DEST ya existe"; exit 1; }

echo ">> Clonando repo canónico en $DEST"
git clone "$REPO_URL" "$DEST"
cd "$DEST"

echo ">> Creando venv e instalando dependencias"
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

echo ">> Preparando .env"
cp .env.example .env
SECRET="$(./venv/bin/python scripts/gen_secret_key.py)"
# Rellena el SECRET_KEY automáticamente; el resto queda por editar.
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" .env

cat <<EOF

============================================================
 Cliente '${CLIENTE}' preparado en ${DEST}
============================================================
FALTA (hacer a mano):
  1. Editar ${DEST}/.env  →  DB_NAME/DB_USER/DB_PASSWORD (los del proveedor),
     ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, MI_DOMINIO, S3_CLIENT_PREFIX=${CLIENTE},
     EMAIL_*, DEBUG=False
  2. Migrar:            ${DEST}/venv/bin/python manage.py migrate
  3. Superusuario:      ${DEST}/venv/bin/python manage.py createsuperuser
  4. Estáticos a S3:    ${DEST}/venv/bin/python manage.py collectstatic --noinput
  5. Crear el servicio systemd (gunicorn-${CLIENTE}) y Nginx del dominio.
  6. Agregar la fila del cliente a deploy/tenants.tsv
============================================================
EOF
