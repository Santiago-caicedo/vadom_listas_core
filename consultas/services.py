# archivo: consultas/services.py

import logging
import re
import time
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# El servidor del proveedor corre sobre ASP.NET, que rechaza ciertos caracteres
# en la RUTA de la URL con "A potentially dangerous Request.Path value was
# detected from the client". No sirve codificarlos: los bloquea igual.
# Verificado el 11-ago-2026: & < > * : ? % devuelven HTTP 400 y \ devuelve 404.
# Sin esto, una empresa como "INDUSTRIAS S&S JEANS S.A.S" nunca se puede
# consultar y el analista ve un falso "servicio no disponible".
_CARACTERES_PROHIBIDOS = re.compile(r'[&<>*:?%\\]+')


def _preparar_nombre(nombres):
    """
    Deja el nombre en una forma que el webservice del proveedor acepte.

    Los caracteres que su servidor rechaza se reemplazan por espacios. Como el
    proveedor hace coincidencia aproximada por nombre, la búsqueda se conserva:
    "INDUSTRIAS S&S JEANS" se consulta como "INDUSTRIAS S S JEANS".
    """
    original = (nombres or '').strip()
    limpio = _CARACTERES_PROHIBIDOS.sub(' ', original)
    limpio = re.sub(r'\s+', ' ', limpio).strip().upper()
    if limpio != original.upper():
        logger.info("Nombre saneado para el webservice: %r -> %r", original, limpio)
    return quote(limpio, safe='')


def _sanear(valor):
    """
    Limpia recursivamente lo que devuelve el webservice del proveedor.

    PostgreSQL NO admite el carácter NUL (0x00) dentro de columnas de texto:
    si llega uno, el INSERT falla con "A string literal cannot contain NUL
    (0x00) characters" y se cae la consulta completa con un error 500.
    El proveedor ha enviado datos con ese carácter (incidente del 10-ago-2026),
    así que se limpia aquí, en la frontera, antes de que llegue a los modelos.
    """
    if isinstance(valor, str):
        return valor.replace('\x00', '')
    if isinstance(valor, dict):
        return {k: _sanear(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sanear(v) for v in valor]
    return valor


def _realizar_peticion(url):
    """
    Consulta el webservice de listas.

    Devuelve la lista de resultados, o None si el servicio no está disponible
    o respondió algo que no se puede interpretar. Devolver None es importante:
    la vista lo traduce en "servicio no disponible" y NO guarda la búsqueda,
    para no mostrarle al analista un falso "sin hallazgos".

    Reintenta SOLO ante timeout o error de conexión (el proveedor lento o
    arrancando en frío): ahí un segundo intento suele responder. Un error de
    aplicación del proveedor (HTTP != 200, MensajeError, cuerpo no-JSON) no se
    reintenta: volver a preguntar solo gasta cupo y da lo mismo.
    """
    timeout = getattr(settings, 'API_TIMEOUT', 55)
    intentos = max(1, getattr(settings, 'API_REINTENTOS', 1))

    for intento in range(1, intentos + 1):
        try:
            response = requests.get(url, timeout=timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if intento < intentos:
                logger.warning("El API de listas no respondió en %ss (intento %d/%d), reintentando: %s",
                               timeout, intento, intentos, e)
                time.sleep(1)
                continue
            logger.error("Error de conexión con el API de listas tras %d intentos: %s", intentos, e)
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Error de conexión con el API de listas: %s", e)
            return None
        except Exception:
            logger.exception("Fallo inesperado consultando el API de listas")
            return None

        return _interpretar_respuesta(response)

    return None


def _interpretar_respuesta(response):
    """Traduce la respuesta HTTP del proveedor a lista de resultados o None."""
    try:
        if response.status_code != 200:
            logger.error("El API de listas respondió %s: %s",
                         response.status_code, response.text[:300])
            return None

        # Responde 200 pero el cuerpo no es JSON (mantenimiento, proxy, HTML)
        try:
            data = response.json()
        except ValueError:
            logger.error("El API de listas respondió 200 pero no es JSON válido: %s",
                         response.text[:300])
            return None

        # El JSON parseó, pero puede no ser un objeto (null, lista, número...)
        # cuando el servicio está a medio romper.
        if not isinstance(data, dict):
            logger.error("El API de listas devolvió un JSON inesperado (%s): %s",
                         type(data).__name__, str(data)[:300])
            return None

        # El API puede responder 200 con un error de aplicación en 'MensajeError'
        if data.get('MensajeError'):
            logger.error("Error del API de listas (MensajeError): %s", data['MensajeError'])
            return None

        resultados = data.get('Resultados', [])
        if not isinstance(resultados, list):
            logger.error("El API de listas devolvió 'Resultados' que no es una lista (%s)",
                         type(resultados).__name__)
            return None

        return _sanear(resultados)

    except Exception:
        # Red de seguridad: ante CUALQUIER otra cosa inesperada preferimos
        # decir "servicio no disponible" antes que tumbar la consulta.
        logger.exception("Fallo inesperado interpretando la respuesta del API de listas")
        return None


def consultar_api_por_id(identificacion):
    """Se conecta al Web Service para consultar una identificación exacta."""
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsExactaID/{token}/{quote(str(identificacion).strip(), safe='')}"
    return _realizar_peticion(url)


def consultar_api_por_nombre(nombres):
    """Se conecta al Web Service para consultar por nombre."""
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsNombre/{token}/{_preparar_nombre(nombres)}"
    return _realizar_peticion(url)


def consultar_api_por_id_y_nombre(identificacion, nombres):
    """Se conecta al Web Service para consultar por ID y nombre."""
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = (f"{base_url}PepsIDNombre/{token}"
           f"/{quote(str(identificacion).strip(), safe='')}"
           f"/{_preparar_nombre(nombres)}")
    return _realizar_peticion(url)
