# archivo: consultas/services_judicial.py
"""
Servicio de consulta de PROCESOS JUDICIALES en la Rama Judicial (CPNU).

Fuente: API de la Consulta de Procesos Nacional Unificada.
  https://consultaprocesos.ramajudicial.gov.co:448/api/v2
(El puerto es el 448; el 443 sirve la SPA del portal, no la API.)

Notas:
- Búsqueda SOLO por nombre/razón social (la API no permite por cédula ni devuelve
  documento). Los resultados pueden incluir homónimos → uso informativo, requiere
  verificación humana.
- El portal de la Rama es intermitente (a veces responde 503). Por eso se usan
  reintentos con backoff y, si aun así falla, se devuelve None (fail-safe): la
  búsqueda LAFT principal NO debe caerse por esto.
- Esta consulta ocurre DENTRO de la petición del analista, así que los valores por
  defecto de timeout y reintentos están calculados para que el peor caso (la Rama
  caída) no deje la página colgada: 2 intentos x 15s + 1.5s de espera ~= 32s.
  Se pueden ajustar por cliente desde el .env.
"""

import time
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Configurable por settings/.env; con defaults sensatos.
CPNU_BASE = getattr(
    settings, "CPNU_BASE_URL",
    "https://consultaprocesos.ramajudicial.gov.co:448/api/v2",
)
CPNU_TIMEOUT = getattr(settings, "CPNU_TIMEOUT", 15)
CPNU_REINTENTOS = getattr(settings, "CPNU_REINTENTOS", 2)
# Máximo de páginas a traer (20 procesos c/u). Evita traer cientos para nombres comunes.
CPNU_MAX_PAGINAS = getattr(settings, "CPNU_MAX_PAGINAS", 5)  # 5 x 20 = 100 procesos máx

# Headers de navegador (el portal rechaza peticiones sin ellos).
CPNU_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CO,es;q=0.9",
    "Origin": "https://consultaprocesos.ramajudicial.gov.co",
    "Referer": "https://consultaprocesos.ramajudicial.gov.co/procesos/nombrerazonsocial",
}


def _get_con_reintentos(path, params=None):
    """
    GET a la CPNU con reintentos y backoff.
    Devuelve el JSON (dict) si hay 200, o None tras agotar los intentos.
    """
    for intento in range(1, CPNU_REINTENTOS + 1):
        try:
            resp = requests.get(
                f"{CPNU_BASE}{path}",
                params=params,
                headers=CPNU_HEADERS,
                timeout=CPNU_TIMEOUT,
            )
            ctype = resp.headers.get("Content-Type", "").lower()
            if resp.status_code == 200 and "json" in ctype:
                try:
                    data = resp.json()
                except ValueError:
                    logger.error("CPNU %s -> 200 con Content-Type JSON pero cuerpo invalido", path)
                    return None
                # Un JSON que no es objeto (null, lista suelta) no lo sabemos interpretar.
                if not isinstance(data, dict):
                    logger.error("CPNU %s -> JSON inesperado (%s)", path, type(data).__name__)
                    return None
                return data
            # 503 (Rama caída) u otro código → reintentar
            logger.warning("CPNU %s -> HTTP %s (intento %d/%d)",
                           path, resp.status_code, intento, CPNU_REINTENTOS)
        except requests.exceptions.RequestException as e:
            logger.warning("CPNU %s -> error de conexion: %s (intento %d/%d)",
                           path, e, intento, CPNU_REINTENTOS)

        if intento < CPNU_REINTENTOS:
            time.sleep(1.5 * intento)  # backoff creciente: 1.5s, 3s, ...

    logger.error("CPNU %s -> fallo tras %d intentos", path, CPNU_REINTENTOS)
    return None


def consultar_procesos_judiciales(nombre, tipo_persona="nat", solo_activos=False):
    """
    Busca procesos judiciales por nombre o razón social.

    Args:
        nombre: nombre completo o razón social (mín. 3 caracteres).
        tipo_persona: 'nat' (natural) | 'jur' (jurídica).
        solo_activos: True = solo procesos activos; False = incluye históricos.

    Returns:
        Una tupla (procesos, total_reportado):
        - procesos: list[dict] con los procesos de TODAS las páginas recorridas
          (hasta CPNU_MAX_PAGINAS). Puede estar vacía si no hay resultados.
          Es None si la consulta falló (Rama caída/error) en la primera página.
          El llamador debe distinguir [] (sin procesos) de None (no se pudo consultar).
        - total_reportado: cuántos procesos dice la Rama que existen en total.
          Sirve para avisar cuando el tope de páginas trunca la lista; es 0 si no
          se pudo consultar y nunca es menor que los procesos efectivamente traídos.
    """
    if not nombre or len(nombre.strip()) < 3:
        return None, 0

    todos = []
    total_reportado = 0
    pagina = 1
    while pagina <= CPNU_MAX_PAGINAS:
        data = _get_con_reintentos(
            "/Procesos/Consulta/NombreRazonSocial",
            params={
                "nombre": nombre.strip(),
                "tipoPersona": tipo_persona,
                "SoloActivos": "true" if solo_activos else "false",
                "codificacionDespacho": "",
                "pagina": pagina,
            },
        )
        if data is None:
            # Falla en la 1ª página → no se pudo consultar (None).
            # Falla en una página posterior → devolvemos lo que ya tengamos.
            if pagina == 1:
                return None, 0
            break

        procesos = data.get("procesos")
        if isinstance(procesos, list):
            todos.extend(procesos)

        paginacion = data.get("paginacion") or {}
        # La Rama reporta el total real de procesos del nombre; puede ser mayor
        # que lo que traemos si hay más páginas que CPNU_MAX_PAGINAS.
        if pagina == 1:
            try:
                total_reportado = int(paginacion.get("cantidadRegistros") or 0)
            except (TypeError, ValueError):
                total_reportado = 0

        total_paginas = paginacion.get("cantidadPaginas") or 1
        if pagina >= total_paginas:
            break
        pagina += 1

    # Si la Rama no reportó el total, al menos sabemos lo que trajimos.
    return todos, max(total_reportado, len(todos))


# Palabras clave por tipo de despacho → categoría. El orden importa (más específico primero).
_CATEGORIAS = [
    ("Penal", ("PENAL",)),
    ("Disciplinario", ("DISCIPLINA", "DISCIPLINARIA")),
    ("Administrativo", ("ADMINISTRATIVO", "CONSEJO DE ESTADO", "CONTENCIOSO")),
    ("Laboral", ("LABORAL",)),
    ("Familia", ("FAMILIA",)),
    ("Civil", ("CIVIL",)),
]


def clasificar_proceso(despacho):
    """
    Clasifica un proceso por el 'despacho' (lo que trae la búsqueda por nombre).
    'Penal' es el de mayor relevancia para LAFT. Devuelve una etiqueta de categoría.
    """
    d = (despacho or "").upper()
    for categoria, claves in _CATEGORIAS:
        if any(k in d for k in claves):
            return categoria
    return "Otro"


def consultar_detalle_proceso(id_proceso):
    """Detalle de un proceso (ponente, clase, ubicación…). None si falla."""
    return _get_con_reintentos(f"/Proceso/Detalle/{id_proceso}")


def consultar_actuaciones_proceso(id_proceso, pagina=1):
    """Actuaciones (movimientos) de un proceso. None si falla."""
    return _get_con_reintentos(
        f"/Proceso/Actuaciones/{id_proceso}", params={"pagina": pagina}
    )
