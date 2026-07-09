# Sistema de Consultas de Listas Restrictivas LAFT — Lógica de Negocio

> Documento maestro que describe **en qué consiste el sistema** y **toda su lógica de negocio**, extraído directamente del código fuente de los proyectos VADOM (`automayor_listas`, `campesa_listas`, `comertex_listas`, `golden_listas`, `redp_listas`).
>
> Para el detalle técnico de la **integración con el webservice externo** (endpoints, formato de respuesta, tabla de campos), ver el documento complementario [`WEBSERVICE_LAFT.md`](./WEBSERVICE_LAFT.md).

---

## 1. ¿Qué es este sistema?

Es una plataforma web que permite a las empresas cumplir con sus obligaciones de **prevención de LAFT** (Lavado de Activos y Financiación del Terrorismo — el marco regulatorio colombiano también conocido como **SARLAFT / SAGRLAFT**).

En términos simples: antes de vincular a un cliente, proveedor, empleado o tercero, la empresa está obligada a **verificar que esa persona (o entidad) no aparezca en listas restrictivas** nacionales e internacionales (OFAC, ONU, Interpol, Fiscalía, listas de PEP, filtraciones tipo Panama Papers, etc.).

El sistema automatiza esa verificación:

1. El usuario ingresa una **identificación** y/o un **nombre**.
2. El sistema consulta el webservice externo **ConsultaListasPeps (BLS)**.
3. Guarda cada coincidencia encontrada, la **clasifica por nivel de riesgo** (Rojo / Amarillo / PEP's) y muestra el **porcentaje de coincidencia**.
4. Deja **trazabilidad** de toda consulta (quién, cuándo, qué buscó, qué encontró) — evidencia clave para las auditorías de cumplimiento.
5. Genera **reportes en PDF** y **alertas por correo** cuando hay hallazgos.

El valor de negocio no es solo "buscar en una lista": es **dejar registro auditable** de la debida diligencia y **alertar** a los responsables de cumplimiento cuando aparece un riesgo.

### Modelo multi-cliente

VADOM Consulting presta este servicio a varias empresas. Cada cliente tiene su **propia instancia independiente** (código idéntico, despliegue, base de datos y dominio separados):

| Proyecto | Cliente | Prefijo S3 |
|---|---|---|
| `automayor_listas` | Automayor | `automayor` |
| `campesa_listas` | Campesa | `campesa` |
| `comertex_listas` | Comertex | `comertex` |
| `golden_listas` | Golden | `golden` |
| `redp_listas` | Red Papaz | `redpapaz` |

Todas las instancias comparten el mismo bucket S3 (`vadomdata`), separadas por carpeta/prefijo. Ver [`comertex_listas/s3.md`](./comertex_listas/s3.md) para el detalle de almacenamiento.

---

## 2. Actores y roles

El sistema tiene **tres niveles de permisos**, controlados por campos del modelo `Usuario`:

| Rol | Campo que lo define | Qué puede hacer | Alcance de datos |
|---|---|---|---|
| **Usuario normal** | (ninguno especial) | Buscar, ver su propio historial, descargar sus PDF, subir lotes | Solo **sus propias** búsquedas |
| **Superior de empresa** | `es_superior = True` | Todo lo anterior + panel de gestión con métricas y consultas de **toda su empresa** | Todas las búsquedas de **su empresa** |
| **Superusuario** | `is_superuser = True` | Todo + panel de administración global, gestión de usuarios, procesamiento de lotes, reportes | **Global** (todas las empresas) |

Dos mecanismos de control de acceso conviven en el código:

- **`@superior_required`** (decorador para vistas de función): si el usuario no es `es_superior` ni `is_superuser`, lanza `PermissionDenied` → **error 403**.
- **`SuperuserRequiredMixin`** (mixin para vistas de clase): si el usuario no es `is_superuser`, lanza `Http404` → **error 404** (oculta deliberadamente la existencia del panel admin a usuarios normales).

---

## 3. Flujo de negocio principal — Consulta individual

Este es el corazón del sistema (`consultas/views.py → pagina_busqueda`).

```
Usuario ingresa Identificación y/o Nombre
        │
        ▼
[Validación] Debe venir al menos un criterio (ID o Nombre), si no → error de formulario
        │
        ▼
[Selección automática de endpoint]
   ID + Nombre  → PepsIDNombre    (más preciso)
   solo ID      → PepsExactaID
   solo Nombre  → PepsNombre      (nombre se envía en MAYÚSCULAS)
        │
        ▼
[Llamada al webservice]  GET {base}/{endpoint}/{token}/{params}   (timeout 20 s)
        │
        ▼
[Persistencia] Se crea SIEMPRE un registro Busqueda (aunque no haya resultados)
        │
        ▼
   Por cada coincidencia devuelta:
     - Se calcula la clasificación de riesgo (get_classification)
     - Si algún resultado es Restrictiva=true → se marca la alerta
     - Se guarda un registro Resultado con todos los campos del API + la clasificación
        │
        ▼
[Marcado de la búsqueda]
     - encontro_resultados = (hubo al menos 1 resultado)
     - genero_alerta       = (hubo al menos 1 resultado con Restrictiva=true)
        │
        ▼
[Notificación] Si encontro_resultados → email a los superiores de la empresa
        │
        ▼
[Respuesta] Banner con enlace al detalle de la búsqueda recién creada
```

### Reglas importantes de este flujo

- **Siempre se registra la búsqueda**, incluso si no hubo resultados o si el API falló. Esto es intencional: la trazabilidad exige registrar que *se hizo la consulta*.
- **"Sin resultados" no es error.** El API responde `200 OK` con lista vacía. Se guarda `encontro_resultados = False`.
- **Error del API** (sin conexión, HTTP ≠ 200, o `MensajeError` presente): la capa de servicios devuelve `None`. En ese caso se crea la `Busqueda` pero **no se guarda ningún `Resultado`** y **no se envía notificación**.
- La `identificacion` y el `nombres` del formulario son **ambos opcionales por separado**, pero **al menos uno es obligatorio** (validación en `BusquedaForm.clean`).

---

## 4. Motor de clasificación de riesgo (núcleo del negocio)

Cada coincidencia se clasifica en **una sola** categoría según su campo `Tipo_Lista`. La función `get_classification()` (en `consultas/views.py`) es la regla de negocio más importante del sistema.

**El orden de evaluación es crítico y NO debe alterarse:** Amarillo → PEP's → Rojo.

```python
def get_classification(tipo_lista):
    if not tipo_lista:
        return 'No Clasificado'          # Tipo_Lista vacío

    t = tipo_lista.upper()

    # 1) AMARILLO — filtraciones específicas (coincidencia EXACTA, ==)
    if t in {"PARADISE PAPERS", "PANAMA PAPERS", "BAHAMAS LEAKS",
             "BOLETIN PANAMA PAPERS", "OFFSHORE LEAKS"}:
        return "Amarillo"

    # 2) PEP's — persona políticamente expuesta (coincidencia por SUBSTRING, in)
    #    basta con que Tipo_Lista CONTENGA cualquiera de estas palabras
    PEP = ['PEP','GOBIERNO','CONSEJO','CORTE','EMBAJADAS','MINISTERIO',
           'PRESIDENCIA','SENADO','CAMARA','ASAMBLEA','ALCALDIAS','CONCEJOS',
           'NOTARIAS','SIGEP','ELECTORAL','JUDICATURA','CANDIDATOS','PARTIDOS']
    if any(kw in t for kw in PEP):
        return "PEP's"

    # 3) ROJO — todo lo demás (OFAC, ONU, Interpol, Fiscalía, FBI, etc.)
    return "Rojo"
```

| Categoría | Significado de negocio | Regla | Color (hex) |
|---|---|---|---|
| 🔴 **Rojo** | **Alto riesgo.** Listas restrictivas duras (OFAC, ONU, Interpol, Fiscalía…). Es el *default* si no cae en las otras. | Todo lo que no sea Amarillo ni PEP | `#dc3545` |
| 🟡 **Amarillo** | **Riesgo medio.** Filtraciones periodísticas (Panama/Paradise Papers, etc.). | `Tipo_Lista` **igual** a un valor de la lista fija | `#ffc107` |
| 🔵 **PEP's** | **Persona Políticamente Expuesta.** Funcionarios públicos, cargos de elección. No es "malo" en sí, pero exige debida diligencia reforzada. | `Tipo_Lista` **contiene** una palabra clave PEP | `#0dcaf0` |
| ⚪ **No Clasificado** | `Tipo_Lista` vacío. | Sin `Tipo_Lista` | `#6c757d` |

> ⚠️ Matiz técnico clave: **Amarillo se evalúa con igualdad exacta (`==`)** y **PEP's con substring (`in`)**. Por eso el orden importa: si se evaluara PEP's antes, un valor que contenga "PEP" nunca podría ser Amarillo, y viceversa se producirían clasificaciones erróneas.

### Bandera de alerta restrictiva (independiente del color)

Además del color, existe la bandera **`genero_alerta`** a nivel de búsqueda. Se activa cuando **al menos un resultado** trae `Restrictiva = true` en el API. Es una segunda señal, independiente de la clasificación por color, que indica que la persona está en una lista de carácter **restrictivo** (la más grave para cumplimiento).

---

## 5. Sistema de coincidencias (segunda capa visual)

El API devuelve dos porcentajes independientes por cada resultado:

- **`CoincidenciaID`** (0–100): qué tanto coincide el **documento** buscado.
- **`CoincidenciaNombre`** (0–100): qué tanto coincide el **nombre** buscado.

Sirven para que el analista juzgue si la coincidencia es real o un falso positivo. Se muestran como barras de progreso con código de color:

| Rango | Nivel | Color |
|---|---|---|
| ≥ 70 % | Alto | Verde `#198754` |
| 50–69 % | Medio | Amarillo `#ffc107` |
| < 50 % | Bajo | Gris `#6c757d` |

---

## 6. Consultas masivas (por lote)

Para verificar muchas personas de una vez (`cargas_masivas`). **Es un proceso semi-manual y asíncrono**, no una consulta automática en tiempo real:

```
1. El cliente descarga la PLANTILLA Excel oficial (FORMATO CONSULTAS MASIVAS, v LVCON-2025)
   Columnas: "Documento Identificación" y "Nombre Completo"
        │
        ▼
2. La llena con su lista y la SUBE  → se crea un LoteConsultaMasiva en estado PENDIENTE
   El Excel se guarda en S3: vadomdata/{cliente}/media/cargas_masivas/empresa_{id}/subidas/
        │
        ▼
3. [Automático] Se dispara un email:
     - al ADMIN de VADOM ("nueva solicitud de carga masiva")
     - al USUARIO ("hemos recibido tu solicitud")
        │
        ▼
4. El SUPERUSUARIO procesa el lote MANUALMENTE (fuera de la app), genera el PDF de
   resultados, lo sube y cambia el estado a PROCESADO
   El PDF se guarda en S3: .../empresa_{id}/resultados/
        │
        ▼
5. [Automático] Se dispara un email al USUARIO: "tu reporte está listo"
```

Puntos de negocio:

- El procesamiento del lote **no está automatizado dentro de la aplicación**: el superusuario lo resuelve por fuera y sube el PDF final. La app orquesta la **solicitud, el almacenamiento y las notificaciones**, no el cruce masivo contra el API.
- Los estados posibles son solo dos: **`PENDIENTE`** y **`PROCESADO`**.
- Los correos se disparan por una **señal `post_save`** sobre `LoteConsultaMasiva` (`cargas_masivas/signals.py`).

---

## 7. Notificaciones por correo

El sistema envía correos HTML en tres momentos:

| Evento | Destinatario | Disparador |
|---|---|---|
| Una búsqueda individual **encuentra resultados** | Los **superiores** (`es_superior`) de la empresa con email | `notificar_superiores_hallazgo()` tras guardar la búsqueda |
| Se **sube un lote** de carga masiva | Admin de VADOM + el usuario solicitante | Señal `post_save` (created) |
| Un lote pasa a **PROCESADO** | El usuario solicitante | Señal `post_save` (estado + PDF listo) |

Todas las notificaciones son **tolerantes a fallos**: si el envío de correo falla, se registra el error pero **no se interrumpe** el flujo principal (la búsqueda o la subida del lote se completan igual).

> Nota de estado: la notificación a superiores por hallazgo está implementada y activa en `comertex_listas`; su réplica a los demás proyectos está pendiente.

---

## 8. Dashboards y métricas

El sistema tiene **tres paneles** distintos según el rol, todos con gráficos Chart.js sobre una ventana de **últimos 30 días**:

### 8.1 Dashboard del usuario (`/`)
- KPIs por clasificación (Rojo / Amarillo / PEP's) del **mes** y de **hoy**.
- Tendencia de consultas por día y tendencia de hallazgos Rojos.
- Top 5 de fuentes (tipos de lista) Rojas más frecuentes.
- "Mis últimas búsquedas" (solo del usuario).

> Matiz: los KPIs de este panel se calculan a nivel de **empresa** (`usuario__empresa`), aunque "mis últimas búsquedas" sí es individual.

### 8.2 Panel de gestión del Superior (`/gestion/`)
- KPIs de **toda la empresa**: total de consultas, usuarios activos, hallazgos por clasificación.
- Tendencia de consultas, top 5 usuarios más activos, últimas 10 búsquedas de la empresa.
- Listado filtrable de **todas** las consultas de la empresa (por usuario, rango de fechas, término, con/sin resultados), paginado.

### 8.3 Panel de administración del Superusuario (`/core-admin/`)
- KPIs **globales**: total de consultas, lotes, empresas, usuarios, lotes pendientes.
- Consultas por mes (todas las empresas) y actividad por empresa.
- **Reporte mensual** de consultas por día (mes seleccionable).
- **Gestión de lotes**: listar, procesar (subir PDF, cambiar estado).
- **CRUD de usuarios**: crear, editar, eliminar/desactivar (no toca superusuarios).

---

## 9. Modelo de datos

```
Empresa (1) ─────< (N) Usuario (1) ─────< (N) Busqueda (1) ─────< (N) Resultado
   │
   └────< (N) LoteConsultaMasiva
```

### Entidades

- **`Empresa`** — el cliente/tenant lógico. Campos: `nombre`, `creado_en`.
  - ⚠️ Tiene un atributo `auto_create_schema = True` y un comentario que alude a `django-tenants`, pero el sistema **no usa multi-schema**: cada cliente es una instancia/BD independiente. Ese atributo es vestigial (sin efecto) en el despliegue actual.

- **`Usuario`** — extiende `AbstractUser` de Django. Campos extra: `empresa` (FK, opcional) y `es_superior` (bool). El modelo de autenticación es `AUTH_USER_MODEL = 'usuarios.Usuario'`.

- **`Busqueda`** — una consulta individual. Campos: `usuario`, `termino_buscado`, `fecha_busqueda` (auto), `encontro_resultados` (bool), `genero_alerta` (bool).

- **`Resultado`** — cada coincidencia devuelta por el API para una búsqueda. Mapea los campos del webservice (`nombre_completo`, `identificacion`, `tipo_lista`, `origen_lista`, `relacionado_con`, `fuente`, `es_restrictiva`, `es_boletin`, `alias`, `coincidencia_nombre`, `coincidencia_id`, `tipo_persona`, `fecha_update`, `estado`, `llaveimagen`) **más** el campo interno calculado `clasificacion` (Rojo/Amarillo/PEP's/No Clasificado).

- **`LoteConsultaMasiva`** — solicitud de consulta por lote. Campos: `empresa`, `usuario_solicitante`, `fecha_solicitud`, `estado` (PENDIENTE/PROCESADO), `archivo_subido` (Excel → S3), `archivo_resultado` (PDF → S3).

---

## 10. Mapa de rutas (URLs)

| Ruta | Vista | Acceso |
|---|---|---|
| `/` | Dashboard del usuario | login |
| `/buscar/` | Formulario de búsqueda individual | login |
| `/historial/` | Historial propio | login |
| `/historial/<id>/` | Detalle de una búsqueda | login (solo dueño) |
| `/historial/<id>/pdf/` | Genera PDF (WeasyPrint) | login (solo dueño) |
| `/gestion/` | Dashboard de gestión de empresa | `es_superior` o superuser |
| `/gestion/consultas/` | Listado filtrable de consultas de la empresa | `es_superior` o superuser |
| `/gestion/consultas/<id>/` | Detalle (vista Superior, cualquier búsqueda de su empresa) | `es_superior` o superuser |
| `/cargas-masivas/` | Lotes del cliente | login |
| `/cargas-masivas/subir/` | Subir lote Excel | login |
| `/cargas-masivas/plantilla/` | Descargar plantilla oficial | login |
| `/cuentas/login/` · `/cuentas/logout/` | Autenticación | público / login |
| `/core-admin/…` | Panel global (dashboard, usuarios, lotes, reporte mensual) | **solo** superuser |
| `/admin/` | Django admin | superuser |

---

## 11. Aislamiento y seguridad de datos

La segregación de datos es una exigencia de negocio (una empresa jamás debe ver consultas de otra):

- **Usuario normal:** todas sus vistas filtran por `usuario=request.user`. El detalle de una búsqueda usa `get_object_or_404(Busqueda, pk=id, usuario=request.user)` — no puede acceder por URL a búsquedas ajenas.
- **Superior:** filtra por `usuario__empresa=request.user.empresa` — ve toda su empresa, nada más.
- **Superusuario:** acceso global, protegido por `SuperuserRequiredMixin` (404 a no-superusuarios).
- Toda vista requiere sesión (`@login_required` / mixins). `LOGIN_URL = '/cuentas/login/'`.

---

## 12. Integración con el webservice externo (resumen)

| Dato | Valor |
|---|---|
| Proveedor | ConsultaListasPeps (BLS) |
| Protocolo | REST sobre HTTPS, respuesta JSON |
| Autenticación | Token embebido en la URL (no header) |
| URL base | `https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/` |
| Timeout | 20 segundos |

Endpoints usados: `PepsExactaID` (por documento), `PepsNombre` (por nombre), `PepsIDNombre` (combinado). El detalle completo del contrato del API está en [`WEBSERVICE_LAFT.md`](./WEBSERVICE_LAFT.md).

**Restricciones del proveedor** (relevantes para el negocio): no se permiten llamadas automatizadas masivas/periódicas, los nombres deben ir en MAYÚSCULAS y en formato `[PRIMER_APELLIDO] [SEGUNDO_APELLIDO] [PRIMER_NOMBRE] [SEGUNDO_NOMBRE]`.

---

## 13. Arquitectura técnica

| Componente | Tecnología |
|---|---|
| Framework | Django 5.2.7 |
| Base de datos | PostgreSQL (AWS RDS) |
| Almacenamiento | AWS S3 (bucket `vadomdata`, carpeta por cliente); local en desarrollo (`DEBUG=True`) |
| PDF | WeasyPrint |
| Config | python-decouple + python-dotenv (variables en `.env`) |
| HTTP | requests |
| Frontend | Bootstrap 5.3 + Bootstrap Icons + Chart.js |
| Autenticación | Modelo `Usuario` custom (extiende `AbstractUser`) |

**Apps Django:**
- `consultas` — motor de búsqueda, clasificación, dashboards, PDF, notificación a superiores.
- `usuarios` — autenticación y roles.
- `empresas` — entidad cliente (multi-empresa lógico).
- `cargas_masivas` — consultas por lote y sus notificaciones por señal.
- `core_admin` — panel del superusuario (KPIs globales, CRUD usuarios, procesamiento de lotes, reportes).

---

## 14. Glosario

| Término | Significado |
|---|---|
| **LAFT** | Lavado de Activos y Financiación del Terrorismo (el riesgo que se busca prevenir). |
| **SARLAFT / SAGRLAFT** | Sistema de Administración del Riesgo de LAFT (el marco normativo colombiano de cumplimiento). |
| **PEP** | Persona Políticamente Expuesta: funcionario público o persona con poder de decisión estatal; requiere debida diligencia reforzada. |
| **Lista restrictiva** | Lista oficial (OFAC, ONU, Interpol, Fiscalía…) de personas/entidades sancionadas o investigadas. |
| **Boletín** | Registro de tipo informativo/noticioso dentro del API. |
| **Coincidencia (ID / Nombre)** | Porcentaje 0–100 de similitud entre lo buscado y el registro encontrado. |
| **Hallazgo** | Una búsqueda que devolvió al menos un resultado. |
```
