# Integración Webservice ConsultaListasPeps — Guía Completa

Documento autocontenido para implementar consultas LAFT (Lavado de Activos y Financiamiento del Terrorismo) en cualquier proyecto, replicando la lógica de los sistemas VADOM (`automayor_listas`, `campesa_listas`, `comertex_listas`, `golden_listas`, `redp_listas`).

Con este archivo puedes:
- Conectarte al webservice externo `ConsultaListasPeps`.
- Guardar los resultados en tu base de datos.
- Clasificar cada resultado en **Rojo / Amarillo / Azul (PEP's)**.
- Mostrar barras de coincidencia con la misma paleta visual.

---

## 1. Descripción del Webservice

| Dato | Valor |
|---|---|
| Proveedor | ConsultaListasPeps (BLS) |
| Protocolo | REST sobre HTTPS |
| Formato | JSON |
| Autenticación | Token en URL (no header) |
| URL Base | `https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/` |
| Token (ejemplo VADOM) | `8495-4545-4487` |
| Timeout recomendado | 20 segundos |

### Restricciones del proveedor
1. **No usar herramientas automatizadas** con llamadas periódicas/masivas.
2. **Formato de nombre recomendado:** `[PRIMER_APELLIDO] [SEGUNDO_APELLIDO] [PRIMER_NOMBRE] [SEGUNDO_NOMBRE]`
   Ejemplo: `SANTOS CALDERON JUAN MANUEL`
3. **Nombres en MAYÚSCULAS.**

---

## 2. Endpoints

### Implementados en VADOM

| Función | URL relativa | Uso |
|---|---|---|
| `consultar_api_por_id(id)` | `PepsExactaID/{token}/{id}` | Match exacto por documento |
| `consultar_api_por_nombre(nombre)` | `PepsNombre/{token}/{nombre}` | Búsqueda por nombre |
| `consultar_api_por_id_y_nombre(id, nombre)` | `PepsIDNombre/{token}/{id}/{nombre}` | Combinada (más precisa) |

### Disponibles (no usados en VADOM)

| URL relativa | Descripción |
|---|---|
| `PepsExactaIDSimple/{token}/{id}` | Respuesta reducida por ID exacto |
| `PepsID/{token}/{id}` | Búsqueda aproximada (±1 dígito) |
| `PepsIDSimple/{token}/{id}` | Versión simple de `PepsID` |

### Selección automática del endpoint

```
ID + nombre  → PepsIDNombre   (más preciso)
solo ID      → PepsExactaID
solo nombre  → PepsNombre
```

---

## 3. Estructura de la Respuesta

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
      "Relacionado_Con": "Descripción del caso...",
      "Rol_o_Descripcion1": "Información adicional",
      "Rol_o_Descripcion2": "Info secundaria",
      "Aka": "TIMOLEON JIMENEZ",
      "Fuente": "HTTP://WWW.FISCALIA.GOV.CO",
      "Fecha_Update": "/Date(1500354000000-0500)/",
      "Estado": "INGRESA LISTA: 20160801",
      "LlaveImagen": "",
      "Boletin": true,
      "Restrictiva": false,
      "CoincidenciaID": 100,
      "CoincidenciaNombre": 0
    }
  ]
}
```

### Diccionario de campos

| Campo API | Tipo | Significado |
|---|---|---|
| `NombreCompleto` | string | Nombre completo |
| `Id` | string | Número de identificación |
| `Tipo_Id` | string | Tipo doc. (CC, NIT, CE…) |
| `Tipo_Lista` | string | Lista donde aparece (usado para clasificar) |
| `Origen_Lista` | string | País origen |
| `Tipo_Persona` | string | `INDIVIDUO` o `ENTIDAD` |
| `Relacionado_Con` | string | Descripción larga del caso |
| `Aka` | string | Alias / nombre alterno |
| `Fuente` | string | URL o fuente |
| `Fecha_Update` | string | Fecha .NET `/Date(ms-offset)/` |
| `Estado` | string | Ej. `INGRESA LISTA: 20160801` |
| `Boletin` | bool | Si es boletín |
| `Restrictiva` | bool | **Si es restrictiva → genera alerta** |
| `CoincidenciaID` | int 0-100 | % match con el documento buscado |
| `CoincidenciaNombre` | int 0-100 | % match con el nombre buscado |

### Caso “sin resultados”
La respuesta es `200 OK` con `Resultados: []`. **No es un error**.

### Caso “error del API”
`MensajeError` viene con texto → tratar como fallo y no guardar nada.

---

## 4. Sistema de Clasificación por Color (núcleo de la lógica)

Cada `Resultado` se clasifica en **una sola** categoría según `Tipo_Lista`:

| Color | Etiqueta interna | Significado | Disparador |
|---|---|---|---|
| 🔴 **Rojo** | `Rojo` | Alto riesgo. Default si no es Amarillo ni PEP. | OFAC, ONU, INTERPOL, FISCALIA, FBI, etc. |
| 🟡 **Amarillo** | `Amarillo` | Riesgo medio. Filtraciones. | `Tipo_Lista` ∈ lista fija (ver abajo) |
| 🔵 **Azul** | `PEP's` | Político / funcionario público | `Tipo_Lista` contiene cualquier keyword PEP |
| ⚪ — | `No Clasificado` | `Tipo_Lista` vacío | — |

### Algoritmo de clasificación (orden importa)

```python
def get_classification(tipo_lista: str) -> str:
    """
    Clasifica un resultado según su 'Tipo_Lista'.
    Devuelve: 'Rojo' | 'Amarillo' | "PEP's" | 'No Clasificado'.
    """
    if not tipo_lista:
        return 'No Clasificado'

    t = tipo_lista.upper()

    # 1) AMARILLO — filtraciones específicas (match EXACTO)
    AMARILLO = {
        "PARADISE PAPERS",
        "PANAMA PAPERS",
        "BAHAMAS LEAKS",
        "BOLETIN PANAMA PAPERS",
        "OFFSHORE LEAKS",
    }
    if t in AMARILLO:
        return "Amarillo"

    # 2) AZUL / PEP's — basta con que CONTENGA cualquiera de estas palabras
    PEP_KEYWORDS = [
        'PEP', 'GOBIERNO', 'CONSEJO', 'CORTE', 'EMBAJADAS',
        'MINISTERIO', 'PRESIDENCIA', 'SENADO', 'CAMARA',
        'ASAMBLEA', 'ALCALDIAS', 'CONCEJOS', 'NOTARIAS',
        'SIGEP', 'ELECTORAL', 'JUDICATURA', 'CANDIDATOS', 'PARTIDOS',
    ]
    if any(kw in t for kw in PEP_KEYWORDS):
        return "PEP's"

    # 3) ROJO — todo lo demás
    return "Rojo"
```

> **Notas críticas**
> - El orden es **Amarillo → PEP's → Rojo**. No cambiarlo: si `Tipo_Lista` fuera `"PARADISE PAPERS"` y reviraras el orden, la palabra `"PEP"` no aparece, pero el chequeo `in` puede romperse con otros casos.
> - Amarillo es **match exacto** (`==`), PEP's es **substring** (`in`).
> - Una alerta separada `genero_alerta` se marca cuando **al menos un resultado tiene `Restrictiva: true`**.

### Códigos de color exactos (producción)

Estos son los hex usados en los templates VADOM. Úsalos para mantener consistencia visual:

| Categoría | Hex (fondo / borde) | Texto sobre fondo | Bootstrap equivalente |
|---|---|---|---|
| **Rojo** | `#dc3545` | `#ffffff` | `danger` |
| **Amarillo** | `#ffc107` | `#212529` | `warning` |
| **Azul (PEP's)** | `#0dcaf0` | `#212529` | `info` |
| No Clasificado | `#6c757d` | `#ffffff` | `secondary` |

### Iconos (Bootstrap Icons)

| Categoría | Icono |
|---|---|
| Rojo | `bi-exclamation-triangle-fill` |
| Amarillo | `bi-exclamation-circle-fill` |
| PEP's | `bi-person-badge-fill` |
| No Clasificado | `bi-dash-circle` |

### CSS listo para usar

```css
/* === Borde lateral de la tarjeta de resultado === */
.result-card.clasificacion-rojo     { border-left: 5px solid #dc3545; }
.result-card.clasificacion-amarillo { border-left: 5px solid #ffc107; }
.result-card.clasificacion-pep      { border-left: 5px solid #0dcaf0; }
.result-card.clasificacion-default  { border-left: 5px solid #6c757d; }

/* === Badge tipo "pill" === */
.clasificacion-badge {
    padding: 0.5rem 1rem;
    border-radius: 50px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
}
.clasificacion-badge.rojo     { background-color: #dc3545; color: #ffffff; }
.clasificacion-badge.amarillo { background-color: #ffc107; color: #212529; }
.clasificacion-badge.pep      { background-color: #0dcaf0; color: #212529; }
.clasificacion-badge.default  { background-color: #6c757d; color: #ffffff; }

/* === Badge "Lista Restrictiva" (independiente del color de clasificación) === */
.restrictive-badge.yes { background-color: #f8d7da; color: #842029; }
.restrictive-badge.no  { background-color: #e9ecef; color: #495057; }
```

---

## 5. Sistema de Coincidencias (segunda capa de color)

El API devuelve dos porcentajes independientes:

- `CoincidenciaID` — match con el documento (0–100).
- `CoincidenciaNombre` — match con el nombre (0–100).

Se muestran como **barras de progreso** con color según el rango:

| Rango | Nivel | Hex barra | Hex texto | Clase CSS |
|---|---|---|---|---|
| ≥ 70 % | Alto | `#198754` | `#198754` (`text-success`) | `.high` |
| 50–69 % | Medio | `#ffc107` | `#ffc107` (`text-warning`) | `.medium` |
| < 50 % | Bajo | `#6c757d` | `#6c757d` (`text-secondary`) | `.low` |

```css
.progress              { height: 8px; border-radius: 4px; background-color: #e9ecef; }
.progress-bar.high     { background-color: #198754; }
.progress-bar.medium   { background-color: #ffc107; }
.progress-bar.low      { background-color: #6c757d; }
```

```django
{% if resultado.coincidencia_id >= 70 %}high
{% elif resultado.coincidencia_id >= 50 %}medium
{% else %}low{% endif %}
```

> En el filtro frontal se usa el **mayor** de los dos:
> `data-coincidencia="{{ max(coincidencia_id, coincidencia_nombre) }}"`

---

## 6. Implementación de Referencia (Django)

### 6.1 `settings.py`

```python
from decouple import config

API_TOKEN    = config('API_TOKEN')
API_BASE_URL = config('API_BASE_URL')  # debe terminar en /
```

```bash
# .env
API_TOKEN=8495-4545-4487
API_BASE_URL=https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/
```

### 6.2 `services.py`

```python
import requests
from django.conf import settings


def _realizar_peticion(url):
    """GET con timeout 20s. Retorna lista 'Resultados' o None si hay error."""
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if data.get('MensajeError'):
                print(f"Error API: {data['MensajeError']}")
                return None
            return data.get('Resultados', [])
        print(f"HTTP {response.status_code}: {response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Conexión: {e}")
        return None


def consultar_api_por_id(identificacion):
    url = f"{settings.API_BASE_URL}PepsExactaID/{settings.API_TOKEN}/{identificacion}"
    return _realizar_peticion(url)


def consultar_api_por_nombre(nombres):
    url = f"{settings.API_BASE_URL}PepsNombre/{settings.API_TOKEN}/{nombres.upper()}"
    return _realizar_peticion(url)


def consultar_api_por_id_y_nombre(identificacion, nombres):
    url = f"{settings.API_BASE_URL}PepsIDNombre/{settings.API_TOKEN}/{identificacion}/{nombres.upper()}"
    return _realizar_peticion(url)
```

### 6.3 `models.py`

```python
from django.db import models
from django.conf import settings


class Busqueda(models.Model):
    usuario             = models.ForeignKey(settings.AUTH_USER_MODEL,
                                            on_delete=models.SET_NULL,
                                            null=True, related_name='busquedas')
    termino_buscado     = models.CharField(max_length=100)
    fecha_busqueda      = models.DateTimeField(auto_now_add=True)
    encontro_resultados = models.BooleanField(default=False)
    genero_alerta       = models.BooleanField(default=False)  # algún Restrictiva=true

    def __str__(self):
        return f"Búsqueda: {self.termino_buscado}"


class Resultado(models.Model):
    busqueda = models.ForeignKey(Busqueda, related_name='resultados',
                                 on_delete=models.CASCADE)

    # Campos API
    nombre_completo     = models.CharField(max_length=255, null=True, blank=True)
    identificacion      = models.CharField(max_length=50,  null=True, blank=True)
    tipo_lista          = models.CharField(max_length=100, null=True, blank=True)
    origen_lista        = models.CharField(max_length=100, null=True, blank=True)
    relacionado_con     = models.TextField(null=True, blank=True)
    fuente              = models.CharField(max_length=255, null=True, blank=True)
    es_restrictiva      = models.BooleanField(default=False)
    es_boletin          = models.BooleanField(default=False)
    alias               = models.CharField(max_length=255, null=True, blank=True)
    coincidencia_nombre = models.IntegerField(default=0)
    coincidencia_id     = models.IntegerField(default=0)
    tipo_persona        = models.CharField(max_length=50,  null=True, blank=True)
    fecha_update        = models.CharField(max_length=100, null=True, blank=True)
    estado              = models.CharField(max_length=100, null=True, blank=True)
    llaveimagen         = models.CharField(max_length=255, null=True, blank=True)

    # Clasificación interna: 'Rojo' | 'Amarillo' | "PEP's" | 'No Clasificado'
    clasificacion = models.CharField(max_length=20, default='No Clasificado')
```

### 6.4 Mapeo API → Modelo

| Campo API | Campo Modelo |
|---|---|
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
| — *(calculado)* | `clasificacion` |

### 6.5 Vista de búsqueda (flujo completo)

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services import (
    consultar_api_por_id,
    consultar_api_por_nombre,
    consultar_api_por_id_y_nombre,
)
from .models import Busqueda, Resultado


def get_classification(tipo_lista):
    # ... (ver sección 4) ...
    ...


@login_required
def pagina_busqueda(request):
    busqueda_obj = None
    alerta_generada = False

    if request.method == 'POST':
        identificacion = (request.POST.get('identificacion') or '').strip()
        nombres        = (request.POST.get('nombres') or '').strip()
        termino_buscado = ""
        resultados_api = None

        # 1) Selección del endpoint
        if identificacion and nombres:
            termino_buscado = f"ID: {identificacion} y Nombre: {nombres}"
            resultados_api  = consultar_api_por_id_y_nombre(identificacion, nombres)
        elif identificacion:
            termino_buscado = f"ID: {identificacion}"
            resultados_api  = consultar_api_por_id(identificacion)
        elif nombres:
            termino_buscado = f"Nombre: {nombres}"
            resultados_api  = consultar_api_por_nombre(nombres)

        # 2) Persistencia
        if termino_buscado:
            busqueda_obj = Busqueda.objects.create(
                usuario=request.user,
                termino_buscado=termino_buscado,
            )

            if resultados_api is not None:
                busqueda_obj.encontro_resultados = bool(resultados_api)

                for item in resultados_api:
                    es_restrictiva = item.get('Restrictiva', False)
                    if es_restrictiva:
                        alerta_generada = True

                    tipo_lista_api = item.get('Tipo_Lista', '')
                    clasificacion  = get_classification(tipo_lista_api)

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
                        clasificacion=clasificacion,
                    )

                busqueda_obj.genero_alerta = alerta_generada
                busqueda_obj.save()

    return render(request, 'app/busqueda.html', {
        'busqueda_obj': busqueda_obj,
        'alerta_generada': alerta_generada,
    })
```

### 6.6 Template — tarjeta de resultado (extracto clave)

```django
<div class="result-card
    {% if resultado.clasificacion == 'Rojo'        %}clasificacion-rojo{% endif %}
    {% if resultado.clasificacion == 'Amarillo'    %}clasificacion-amarillo{% endif %}
    {% if resultado.clasificacion == "PEP's"       %}clasificacion-pep{% endif %}
    {% if resultado.clasificacion == 'No Clasificado' %}clasificacion-default{% endif %}">

  <span class="clasificacion-badge
      {% if resultado.clasificacion == 'Rojo'     %}rojo{% endif %}
      {% if resultado.clasificacion == 'Amarillo' %}amarillo{% endif %}
      {% if resultado.clasificacion == "PEP's"    %}pep{% endif %}
      {% if resultado.clasificacion == 'No Clasificado' %}default{% endif %}">
    {% if resultado.clasificacion == 'Rojo' %}<i class="bi bi-exclamation-triangle-fill"></i>
    {% elif resultado.clasificacion == 'Amarillo' %}<i class="bi bi-exclamation-circle-fill"></i>
    {% elif resultado.clasificacion == "PEP's" %}<i class="bi bi-person-badge-fill"></i>
    {% else %}<i class="bi bi-dash-circle"></i>{% endif %}
    {{ resultado.clasificacion }}
  </span>

  <!-- Barras de coincidencia -->
  <div class="progress">
    <div class="progress-bar
        {% if resultado.coincidencia_id >= 70 %}high
        {% elif resultado.coincidencia_id >= 50 %}medium
        {% else %}low{% endif %}"
        style="width: {{ resultado.coincidencia_id }}%"></div>
  </div>
</div>
```

---

## 7. Flujo Completo

```
Usuario ingresa Identificación y/o Nombre
        │
        ▼
 Selección del endpoint
   ID+Nombre → PepsIDNombre
   solo ID   → PepsExactaID
   solo Nom  → PepsNombre
        │
        ▼
 GET {base}/{endpoint}/{token}/{params}   (timeout 20 s)
        │
        ▼
 Parsear "Resultados"
   Por cada item:
     - clasificación = get_classification(Tipo_Lista)
     - alerta       |= Restrictiva
     - guardar Resultado
        │
        ▼
 Marcar Busqueda.encontro_resultados / genero_alerta
        │
        ▼
 Renderizar tarjetas coloreadas + barras de coincidencia
```

---

## 8. Checklist de Integración

- [ ] Variables `.env`: `API_TOKEN`, `API_BASE_URL` (terminar en `/`).
- [ ] `pip install requests python-decouple` (`django-decouple` si no usas Django, ajustar).
- [ ] Crear `services.py` con `_realizar_peticion`, `consultar_api_por_id`, `consultar_api_por_nombre`, `consultar_api_por_id_y_nombre`.
- [ ] Crear modelos `Busqueda` y `Resultado` + migración.
- [ ] Copiar `get_classification()` **tal cual** (orden Amarillo → PEP's → Rojo).
- [ ] Implementar vista: seleccionar endpoint, llamar, guardar, clasificar.
- [ ] Copiar CSS de la sección 4 y 5 (hex exactos).
- [ ] Renderizar tarjetas con borde lateral según `clasificacion`.
- [ ] Renderizar barras de coincidencia con clases `.high/.medium/.low`.

---

## 9. Mini-ejemplo standalone (sin Django)

```python
import requests

TOKEN = "8495-4545-4487"
BASE  = "https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/"


def get_classification(tipo_lista: str) -> str:
    if not tipo_lista:
        return 'No Clasificado'
    t = tipo_lista.upper()
    if t in {"PARADISE PAPERS", "PANAMA PAPERS", "BAHAMAS LEAKS",
             "BOLETIN PANAMA PAPERS", "OFFSHORE LEAKS"}:
        return "Amarillo"
    pep = ['PEP', 'GOBIERNO', 'CONSEJO', 'CORTE', 'EMBAJADAS',
           'MINISTERIO', 'PRESIDENCIA', 'SENADO', 'CAMARA', 'ASAMBLEA',
           'ALCALDIAS', 'CONCEJOS', 'NOTARIAS', 'SIGEP', 'ELECTORAL',
           'JUDICATURA', 'CANDIDATOS', 'PARTIDOS']
    if any(k in t for k in pep):
        return "PEP's"
    return "Rojo"


def consultar_id(identificacion):
    r = requests.get(f"{BASE}PepsExactaID/{TOKEN}/{identificacion}", timeout=20)
    r.raise_for_status()
    return r.json().get('Resultados', [])


if __name__ == "__main__":
    for item in consultar_id("79149126"):
        color = get_classification(item.get('Tipo_Lista', ''))
        print(f"[{color}] {item['NombreCompleto']} - {item['Tipo_Lista']} "
              f"(ID match: {item['CoincidenciaID']}%, Restrictiva: {item['Restrictiva']})")
```

---

## 10. Resumen visual rápido

```
┌──────────────────────────────────────────────────────┐
│  CLASIFICACIÓN (color de la tarjeta)                 │
│                                                      │
│   🔴 Rojo      #dc3545   ← OFAC, ONU, Fiscalía…     │
│   🟡 Amarillo  #ffc107   ← Panama / Paradise / etc. │
│   🔵 Azul      #0dcaf0   ← PEP's (gobierno, etc.)   │
│   ⚪ Default   #6c757d   ← sin Tipo_Lista           │
│                                                      │
│  COINCIDENCIA (color de las barras)                  │
│                                                      │
│   🟢 Alta   ≥70%   #198754                          │
│   🟡 Media  50-69% #ffc107                          │
│   ⚫ Baja   <50%   #6c757d                          │
└──────────────────────────────────────────────────────┘
```
