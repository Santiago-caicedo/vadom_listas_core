# archivo: consultas/services.py

import requests
from django.conf import settings

def _realizar_peticion(url):
    """Función auxiliar para realizar peticiones y manejar errores comunes."""
    try:
        # Hacemos la petición GET con un tiempo de espera de 20 segundos
        response = requests.get(url, timeout=20)

        # Si la petición fue exitosa (código 200 OK)
        if response.status_code == 200:
            data = response.json()
            # El manual indica que los datos vienen en la llave "Resultados"
            return data.get('Resultados', [])
        else:
            # Si el API responde con un error (404, 500, etc.)
            print(f"Error en la respuesta del API: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        # Si hay un error de conexión (no hay internet, el servidor está caído, etc.)
        print(f"Error de conexión con el API: {e}")
        return None

def consultar_api_por_id(identificacion):
    """Se conecta al Web Service para consultar una identificación exacta."""
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsExactaID/{token}/{identificacion}"
    return _realizar_peticion(url)

def consultar_api_por_nombre(nombres):
    """Se conecta al Web Service para consultar por nombre."""
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsNombre/{token}/{nombres.upper()}" # Nombres suelen ir en mayúscula
    return _realizar_peticion(url)

def consultar_api_por_id_y_nombre(identificacion, nombres):
    """Se conecta al Web Service para consultar por ID y nombre."""
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsIDNombre/{token}/{identificacion}/{nombres.upper()}"
    return _realizar_peticion(url)