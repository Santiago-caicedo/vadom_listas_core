# Integración API ConsultaListasPeps

Documentación completa para integrar el servicio de consultas de Listas Restrictivas LAFT en cualquier proyecto.

---

## Descripción del Servicio

**Proveedor:** ConsultaListasPeps
**Propósito:** Verificar personas/empresas contra listas restrictivas nacionales e internacionales para cumplimiento LAFT (Lavado de Activos y Financiamiento del Terrorismo).

**URL Base del Servicio:**
```
https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/
```

---

## Configuración Requerida

### Variables de Entorno

```bash
# .env
API_TOKEN=tu-token-aqui
API_BASE_URL=https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/
```

### Configuración Django (settings.py)

```python
from decouple import config

API_TOKEN = config('API_TOKEN')
API_BASE_URL = config('API_BASE_URL')
```

### Dependencias

```bash
pip install requests python-decouple
```

---

## Estructura del Servicio (services.py)

Crea un archivo `services.py` en tu app para manejar las conexiones al API:

```python
# archivo: tu_app/services.py

import requests
from django.conf import settings


def _realizar_peticion(url):
    """
    Función auxiliar para realizar peticiones GET y manejar errores.
    Retorna lista de resultados o None si hay error.
    """
    try:
        response = requests.get(url, timeout=20)

        if response.status_code == 200:
            data = response.json()
            return data.get('Resultados', [])
        else:
            print(f"Error API: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
        return None


def consultar_api_por_id(identificacion):
    """
    Búsqueda EXACTA por número de identificación (cédula, NIT, etc.)
    Retorna solo coincidencias con ID exacto.
    """
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsExactaID/{token}/{identificacion}"
    return _realizar_peticion(url)


def consultar_api_por_nombre(nombres):
    """
    Búsqueda por nombre completo.
    Recomendado enviar en formato: PRIMER_APELLIDO SEGUNDO_APELLIDO PRIMER_NOMBRE SEGUNDO_NOMBRE
    Ejemplo: "SANTOS CALDERON JUAN MANUEL"
    """
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsNombre/{token}/{nombres.upper()}"
    return _realizar_peticion(url)


def consultar_api_por_id_y_nombre(identificacion, nombres):
    """
    Búsqueda combinada por ID y nombre.
    Útil cuando se tienen ambos datos para mayor precisión.
    """
    token = settings.API_TOKEN
    base_url = settings.API_BASE_URL
    url = f"{base_url}PepsIDNombre/{token}/{identificacion}/{nombres.upper()}"
    return _realizar_peticion(url)
```

---

## Endpoints Disponibles

### Implementados

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `consultar_api_por_id(id)` | `PepsExactaID/{token}/{id}` | Búsqueda exacta por documento |
| `consultar_api_por_nombre(nombre)` | `PepsNombre/{token}/{nombre}` | Búsqueda por nombre |
| `consultar_api_por_id_y_nombre(id, nombre)` | `PepsIDNombre/{token}/{id}/{nombre}` | Búsqueda combinada |

### Disponibles (no implementados)

| Endpoint | Descripción |
|----------|-------------|
| `PepsExactaIDSimple/{token}/{id}` | Respuesta reducida por ID exacto |
| `PepsID/{token}/{id}` | Búsqueda aproximada de ID (±1 dígito) |
| `PepsIDSimple/{token}/{id}` | Versión simple de PepsID |

---

## Estructura de Respuesta del API

### Respuesta Completa

```json
{
  "ExtraInfo": "",
  "MensajeError": "",
  "TotalResultados": 3,
  "Resultados": [
    {
      "Registro": 167217,
      "Codigo": "BLS1342216",
      "NombreCompleto": "LONDONO ECHEVERRY RODRIGO",
      "Primer_Nombre": "RODRIGO",
      "Segundo_Nombre": "",
      "Primer_Apellido": "LONDONO",
      "Segundo_Apellido": "ECHEVERRY",
      "Id": "79149126",
      "Tipo_Id": "CC",
      "Tipo_Lista": "BOLETIN FISCALIA",
      "Origen_Lista": "COLOMBIA",
      "Tipo_Persona": "INDIVIDUO",
      "Relacionado_Con": "Descripción del caso o motivo de inclusión...",
      "Rol_o_Descripcion1": "Información adicional del rol",
      "Rol_o_Descripcion2": "Información secundaria",
      "Aka": "ALIAS O NOMBRE ALTERNO",
      "Fuente": "HTTP://WWW.FISCALIA.GOV.CO",
      "Fecha_Update": "/Date(1500354000000-0500)/",
      "Estado": "INGRESA LISTA: 20160801",
      "LlaveImagen": "",
      "Boletin": true,
      "Restrictiva": false,
      "CoincidenciaID": 100,
      "CoincidenciaNombre": 85
    }
  ]
}
```

### Descripción de Campos

| Campo API | Tipo | Descripción |
|-----------|------|-------------|
| `NombreCompleto` | string | Nombre completo de la persona/entidad |
| `Id` | string | Número de identificación |
| `Tipo_Id` | string | Tipo de documento (CC, NIT, CE, etc.) |
| `Tipo_Lista` | string | Nombre de la lista donde aparece |
| `Origen_Lista` | string | País de origen de la lista |
| `Tipo_Persona` | string | INDIVIDUO o ENTIDAD |
| `Relacionado_Con` | string | Descripción del caso |
| `Aka` | string | Alias conocidos |
| `Fuente` | string | URL o fuente de información |
| `Fecha_Update` | string | Fecha de actualización (formato .NET) |
| `Estado` | string | Estado en la lista |
| `Boletin` | boolean | Si es de tipo boletín |
| `Restrictiva` | boolean | Si es lista restrictiva (alto riesgo) |
| `CoincidenciaID` | int | % de coincidencia con ID buscado (0-100) |
| `CoincidenciaNombre` | int | % de coincidencia con nombre buscado (0-100) |

---

## Modelo de Datos Sugerido

```python
# archivo: tu_app/models.py

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Busqueda(models.Model):
    """Registro de cada consulta realizada."""
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    termino_buscado = models.CharField(max_length=100)
    fecha_busqueda = models.DateTimeField(auto_now_add=True)
    encontro_resultados = models.BooleanField(default=False)
    genero_alerta = models.BooleanField(default=False)  # Si encontró lista restrictiva

    def __str__(self):
        return f"Búsqueda: {self.termino_buscado}"


class Resultado(models.Model):
    """Cada coincidencia encontrada en una búsqueda."""
    busqueda = models.ForeignKey(Busqueda, related_name='resultados', on_delete=models.CASCADE)

    # Campos del API
    nombre_completo = models.CharField(max_length=255, null=True, blank=True)
    identificacion = models.CharField(max_length=50, null=True, blank=True)
    tipo_lista = models.CharField(max_length=100, null=True, blank=True)
    origen_lista = models.CharField(max_length=100, null=True, blank=True)
    relacionado_con = models.TextField(null=True, blank=True)
    fuente = models.CharField(max_length=255, null=True, blank=True)
    es_restrictiva = models.BooleanField(default=False)
    es_boletin = models.BooleanField(default=False)
    alias = models.CharField(max_length=255, null=True, blank=True)
    coincidencia_nombre = models.IntegerField(default=0)
    coincidencia_id = models.IntegerField(default=0)
    tipo_persona = models.CharField(max_length=50, null=True, blank=True)
    fecha_update = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=100, null=True, blank=True)
    llaveimagen = models.CharField(max_length=255, null=True, blank=True)

    # Clasificación interna
    clasificacion = models.CharField(max_length=20, default='No Clasificado')

    def __str__(self):
        return f"{self.nombre_completo} ({self.identificacion})"
```

### Mapeo API → Modelo

| Campo API | Campo Modelo |
|-----------|--------------|
| `NombreCompleto` | `nombre_completo` |
| `Id` | `identificacion` |
| `Tipo_Lista` | `tipo_lista` |
| `Origen_Lista` | `origen_lista` |
| `Relacionado_Con` | `relacionado_con` |
| `Fuente` | `fuente` |
| `Restrictiva` | `es_restrictiva` |
| `Boletin` | `es_boletin` |
| `Aka` | `alias` |
| `CoincidenciaNombre` | `coincidencia_nombre` |
| `CoincidenciaID` | `coincidencia_id` |
| `Tipo_Persona` | `tipo_persona` |
| `Fecha_Update` | `fecha_update` |
| `Estado` | `estado` |
| `LlaveImagen` | `llaveimagen` |

---

## Sistema de Clasificación de Colores

### Función de Clasificación

```python
def get_classification(tipo_lista):
    """
    Clasifica el resultado según el tipo de lista.

    Retorna:
        - "Rojo": Listas de alto riesgo (restrictivas, boletines fiscalía, etc.)
        - "Amarillo": Filtraciones (Panama Papers, Paradise Papers, etc.)
        - "PEP's": Personas Políticamente Expuestas
        - "No Clasificado": Si no hay tipo_lista
    """
    if not tipo_lista:
        return 'No Clasificado'

    tipo_lista_upper = tipo_lista.upper()

    # 1. AMARILLO - Filtraciones específicas (riesgo medio)
    yellow_lists = [
        "PARADISE PAPERS",
        "PANAMA PAPERS",
        "BAHAMAS LEAKS",
        "BOLETIN PANAMA PAPERS",
        "OFFSHORE LEAKS"
    ]
    if tipo_lista_upper in yellow_lists:
        return "Amarillo"

    # 2. PEP's - Personas Políticamente Expuestas
    pep_keywords = [
        'PEP', 'GOBIERNO', 'CONSEJO', 'CORTE', 'EMBAJADAS',
        'MINISTERIO', 'PRESIDENCIA', 'SENADO', 'CAMARA',
        'ASAMBLEA', 'ALCALDIAS', 'CONCEJOS', 'NOTARIAS',
        'SIGEP', 'ELECTORAL', 'JUDICATURA', 'CANDIDATOS', 'PARTIDOS'
    ]
    if any(keyword in tipo_lista_upper for keyword in pep_keywords):
        return "PEP's"

    # 3. ROJO - Todo lo demás (alto riesgo)
    return "Rojo"
```

### Matriz de Clasificación

| Clasificación | Color | Criterio | Ejemplos |
|---------------|-------|----------|----------|
| **Rojo** | 🔴 | Todo lo que no sea amarillo o PEP | OFAC, ONU, INTERPOL, Fiscalía, FBI |
| **Amarillo** | 🟡 | Filtraciones de documentos | Panama Papers, Paradise Papers, Offshore Leaks |
| **PEP's** | 🟣 | Personas Políticamente Expuestas | Gobierno, Ministerios, Senado, Alcaldías |

### Colores CSS Sugeridos

```css
/* Clasificación Rojo - Alto Riesgo */
.clasificacion-rojo {
    background-color: #dc3545;
    border-left: 4px solid #dc3545;
}

/* Clasificación Amarillo - Riesgo Medio */
.clasificacion-amarillo {
    background-color: #ffc107;
    border-left: 4px solid #ffc107;
}

/* Clasificación PEP's - Políticamente Expuesto */
.clasificacion-peps {
    background-color: #6f42c1;
    border-left: 4px solid #6f42c1;
}
```

---

## Uso en Vistas

### Vista de Búsqueda Completa

```python
# archivo: tu_app/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services import (
    consultar_api_por_id,
    consultar_api_por_nombre,
    consultar_api_por_id_y_nombre
)
from .models import Busqueda, Resultado


def get_classification(tipo_lista):
    """Función de clasificación (ver sección anterior)"""
    # ... implementación completa arriba ...
    pass


@login_required
def pagina_busqueda(request):
    resultados_api = None
    alerta_generada = False
    busqueda_obj = None

    if request.method == 'POST':
        identificacion = request.POST.get('identificacion', '').strip()
        nombres = request.POST.get('nombres', '').strip()
        termino_buscado = ""

        # 1. DECIDIR QUÉ MÉTODO DEL API USAR
        if identificacion and nombres:
            termino_buscado = f"ID: {identificacion} y Nombre: {nombres}"
            resultados_api = consultar_api_por_id_y_nombre(identificacion, nombres)
        elif identificacion:
            termino_buscado = f"ID: {identificacion}"
            resultados_api = consultar_api_por_id(identificacion)
        elif nombres:
            termino_buscado = f"Nombre: {nombres}"
            resultados_api = consultar_api_por_nombre(nombres)

        # 2. GUARDAR EN BASE DE DATOS
        if termino_buscado:
            busqueda_obj = Busqueda.objects.create(
                usuario=request.user,
                termino_buscado=termino_buscado
            )

            if resultados_api is not None:
                busqueda_obj.encontro_resultados = bool(resultados_api)

                for item in resultados_api:
                    # Verificar si es restrictiva (genera alerta)
                    es_restrictiva = item.get('Restrictiva', False)
                    if es_restrictiva:
                        alerta_generada = True

                    # Calcular clasificación
                    tipo_lista_api = item.get('Tipo_Lista', '')
                    clasificacion = get_classification(tipo_lista_api)

                    # Crear resultado
                    Resultado.objects.create(
                        busqueda=busqueda_obj,
                        nombre_completo=item.get('NombreCompleto'),
                        identificacion=item.get('Id'),
                        tipo_lista=tipo_lista_api,
                        origen_lista=item.get('Origen_Lista'),
                        relacionado_con=item.get('Relacionado_Con'),
                        fuente=item.get('Fuente'),
                        es_restrictiva=es_restrictiva,
                        es_boletin=item.get('Boletin', False),
                        alias=item.get('Aka'),
                        coincidencia_nombre=item.get('CoincidenciaNombre', 0),
                        coincidencia_id=item.get('CoincidenciaID', 0),
                        tipo_persona=item.get('Tipo_Persona'),
                        fecha_update=item.get('Fecha_Update'),
                        estado=item.get('Estado'),
                        llaveimagen=item.get('LlaveImagen'),
                        clasificacion=clasificacion
                    )

                if alerta_generada:
                    busqueda_obj.genero_alerta = True
                busqueda_obj.save()

    context = {
        'busqueda_obj': busqueda_obj,
        'alerta_generada': alerta_generada,
    }
    return render(request, 'tu_app/busqueda.html', context)
```

---

## Flujo Completo de una Consulta

```
┌─────────────────────────────────────────────────────────────────┐
│                    USUARIO INGRESA DATOS                        │
│              (Identificación y/o Nombre)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SELECCIÓN DE MÉTODO                          │
│  ┌─────────────────┬─────────────────┬─────────────────────┐   │
│  │ Solo ID         │ Solo Nombre     │ ID + Nombre         │   │
│  │ PepsExactaID    │ PepsNombre      │ PepsIDNombre        │   │
│  └─────────────────┴─────────────────┴─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLAMADA AL API                               │
│  URL: {base_url}{metodo}/{token}/{parametros}                   │
│  Timeout: 20 segundos                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESAR RESPUESTA                           │
│  - Extraer lista de "Resultados"                                │
│  - Para cada resultado:                                         │
│    1. Clasificar por tipo_lista → Rojo/Amarillo/PEP's           │
│    2. Verificar si es_restrictiva → genera alerta               │
│    3. Guardar en modelo Resultado                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GUARDAR BÚSQUEDA                             │
│  - Crear registro en modelo Busqueda                            │
│  - Asociar resultados                                           │
│  - Marcar encontro_resultados y genero_alerta                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MOSTRAR AL USUARIO                           │
│  - Resultados con código de color                               │
│  - Barras de coincidencia (ID% y Nombre%)                       │
│  - Opción de generar PDF                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Sistema de Coincidencias

El API retorna porcentajes de coincidencia que indican qué tan cercano es el resultado a lo buscado:

| Campo | Descripción | Uso |
|-------|-------------|-----|
| `CoincidenciaID` | % de match con documento buscado | 100 = ID exacto |
| `CoincidenciaNombre` | % de match con nombre buscado | 100 = Nombre exacto |

### Colores según Nivel de Coincidencia

| Rango | Nivel | Color Sugerido |
|-------|-------|----------------|
| ≥70% | Alto | Verde (`#28a745`) |
| 50-69% | Medio | Amarillo (`#ffc107`) |
| <50% | Bajo | Gris (`#6c757d`) |

### Implementación CSS

```css
.coincidencia-alta { color: #28a745; }   /* ≥70% */
.coincidencia-media { color: #ffc107; }  /* 50-69% */
.coincidencia-baja { color: #6c757d; }   /* <50% */
```

---

## Restricciones del API

Según documentación del proveedor:

1. **No usar herramientas automatizadas** con llamados periódicos/masivos
2. **Formato de nombre recomendado:** `[PRIMER_APELLIDO] [SEGUNDO_APELLIDO] [PRIMER_NOMBRE] [SEGUNDO_NOMBRE]`
   - Ejemplo: `SANTOS CALDERON JUAN MANUEL`
3. **Enviar nombres en MAYÚSCULAS**
4. **Timeout recomendado:** 20 segundos

---

## Manejo de Errores

```python
def _realizar_peticion(url):
    try:
        response = requests.get(url, timeout=20)

        if response.status_code == 200:
            data = response.json()

            # Verificar si hay mensaje de error del API
            if data.get('MensajeError'):
                print(f"Error del API: {data['MensajeError']}")
                return None

            return data.get('Resultados', [])

        elif response.status_code == 401:
            print("Error: Token inválido o expirado")
            return None

        elif response.status_code == 404:
            print("Error: Endpoint no encontrado")
            return None

        else:
            print(f"Error HTTP: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        print("Error: Timeout de conexión (>20s)")
        return None

    except requests.exceptions.ConnectionError:
        print("Error: No se pudo conectar al servidor")
        return None

    except Exception as e:
        print(f"Error inesperado: {e}")
        return None
```

---

## Checklist de Integración

- [ ] Configurar variables de entorno (`API_TOKEN`, `API_BASE_URL`)
- [ ] Instalar dependencias (`requests`, `python-decouple`)
- [ ] Crear archivo `services.py` con funciones de conexión
- [ ] Crear modelos `Busqueda` y `Resultado`
- [ ] Ejecutar migraciones
- [ ] Implementar función `get_classification()`
- [ ] Crear vista de búsqueda
- [ ] Crear template con resultados coloreados
- [ ] Probar con datos reales

---

## Ejemplo de Uso Rápido

```python
from tu_app.services import consultar_api_por_id

# Consultar por cédula
resultados = consultar_api_por_id("79149126")

if resultados:
    for r in resultados:
        print(f"Nombre: {r['NombreCompleto']}")
        print(f"Lista: {r['Tipo_Lista']}")
        print(f"Restrictiva: {r['Restrictiva']}")
        print(f"Coincidencia ID: {r['CoincidenciaID']}%")
        print("---")
else:
    print("No se encontraron resultados o hubo un error")
```
