# VADOM Listas — Núcleo unificado (multi-tenant *silo*)

Repositorio **canónico y único** del sistema de consultas de Listas Restrictivas LAFT
de VADOM Consulting. Un solo código para **todos los clientes**.

## Modelo de arquitectura: *silo* (aislamiento físico)

Cada cliente (tenant) es una instancia aislada:

```
UN repo (este)  ──►  N despliegues, cada uno con:
                       • su propia carpeta        (/opt/<cliente>_listas)
                       • su propia BASE DE DATOS   (física, separada, en RDS)  ← requisito innegociable
                       • su propio .env            (dominio, BD, prefijo S3, secretos)
                       • su propio servicio        (gunicorn-<cliente>)
                       • su carpeta S3             (vadomdata/<prefijo>/…)
```

**Por qué silo y no schema/tabla compartida:** los datos LAFT exigen aislamiento físico
(regulatorio y contractual). El código es idéntico entre clientes; **solo cambia el `.env`**.
`settings.py` lee TODO lo específico del cliente desde el `.env` (nada hardcodeado).

## Estructura

```
gestor_listas/    Proyecto Django (settings lee todo del .env)
consultas/ usuarios/ empresas/ cargas_masivas/ core_admin/   Apps
static/           Estáticos fuente (logo, plantilla cargas masivas)
templates/        Páginas de error globales
docs/             Documentación (API, S3, lógica de negocio, WEBSERVICE_LAFT)
deploy/           tenants.example.tsv, plantilla systemd
scripts/          Operación (ver abajo)
.env.example      Plantilla de configuración por cliente
```

## Scripts de operación

| Script | Qué hace |
|---|---|
| `scripts/gen_secret_key.py` | Genera una `SECRET_KEY` de Django |
| `scripts/deploy_all.sh` | **Actualiza TODOS los tenants** de una vez (pull+pip+migrate+collectstatic+restart) |
| `scripts/onboard_tenant.sh <cli> <carpeta>` | Da de alta un cliente nuevo (clona, venv, .env) |

```bash
# Actualizar todos los despliegues tras un cambio (en el servidor):
./scripts/deploy_all.sh
# Solo algunos:            ./scripts/deploy_all.sh comertex redp
# Ver sin ejecutar:        DRY_RUN=1 ./scripts/deploy_all.sh
```

## Registro de tenants

`deploy/tenants.tsv` (copiar de `tenants.example.tsv`, **gitignored**) es el mapa de todos
los despliegues: cliente, carpeta, dominio, prefijo S3, servicio systemd. Lo consume
`deploy_all.sh`. NO contiene secretos (esos viven solo en cada `.env`).

## Alta de un cliente nuevo

1. Pedir al proveedor de despliegues la **BD** (enviar el nombre) → recibir credenciales.
2. En el servidor: `./scripts/onboard_tenant.sh <cliente> /opt/<cliente>_listas`
3. Editar el `.env` con las credenciales + dominio + `S3_CLIENT_PREFIX` + email.
4. `migrate` → `createsuperuser` → `collectstatic`.
5. Crear `gunicorn-<cliente>.service` (ver `deploy/gunicorn.service.template`) + Nginx.
6. Agregar la fila a `deploy/tenants.tsv`.

## Features configurables por cliente (`.env`)

| Variable | Efecto |
|---|---|
| `NOTIFICAR_HALLAZGOS` | Email a superiores cuando una búsqueda tiene hallazgos (default True) |
| `DEBUG` | False = estáticos en S3 (producción); True = local (desarrollo) |
| `S3_CLIENT_PREFIX` | Carpeta del cliente en el bucket S3 |

## Gotchas de despliegue

- **`dubious ownership`** → `sudo chown -R ubuntu:ubuntu /opt/<cliente>_listas`
- **`DisallowedHost`** → falta `ALLOWED_HOSTS` (host, sin `https://`) en el `.env`.
- **Estáticos rotos con `DEBUG=False`** → falta `S3_CLIENT_PREFIX` o `collectstatic`.
- AWS auth = IAM Role del EC2 (NO llaves en el `.env`).
