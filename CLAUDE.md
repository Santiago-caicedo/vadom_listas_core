# CLAUDE.md - Memoria del Proyecto

## Descripción General

Sistema Django para consultas de **Listas Restrictivas LAFT** (Lavado de Activos y Financiamiento del Terrorismo). Permite a empresas verificar clientes/proveedores contra listas restrictivas nacionales e internacionales mediante conexión a la API externa **ConsultaListasPeps**.

**Dominio de producción:** `comertex.vadomconsultas.com`

**Última actualización:** Enero 2026

---

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Framework | Django 5.2.7 |
| Base de Datos | PostgreSQL |
| Almacenamiento | AWS S3 (bucket: `vadomdata`) |
| Generación PDF | WeasyPrint |
| Config | python-decouple + python-dotenv |
| HTTP Client | requests |
| Frontend | Bootstrap 5.3.3 + Bootstrap Icons |
| Gráficos | Chart.js |

---

## Estructura del Proyecto

```
comertex_listas/
├── gestor_listas/          # Proyecto principal Django
│   ├── settings.py         # Configuración (S3, DB, API credentials)
│   ├── urls.py             # URLs raíz
│   └── wsgi.py / asgi.py
│
├── consultas/              # APP PRINCIPAL - Motor de búsquedas
│   ├── models.py           # Busqueda, Resultado
│   ├── services.py         # Conexión API ConsultaListasPeps
│   ├── views.py            # dashboard, pagina_busqueda, historial, PDF, gestion
│   ├── forms.py            # BusquedaForm
│   └── templates/consultas/
│       ├── base.html              # Template base con sidebar moderna
│       ├── dashboard.html         # Dashboard con KPIs y "Mis Últimas Búsquedas"
│       ├── pagina_busqueda.html
│       ├── historial.html
│       ├── detalle_busqueda.html  # Vista detalle con filtros y barras de coincidencia
│       ├── reporte_pdf.html
│       └── gestion/               # Vistas para rol Superior
│           ├── dashboard.html
│           ├── consultas_list.html
│           └── detalle_busqueda.html
│
├── usuarios/               # Autenticación
│   ├── models.py           # Usuario (extiende AbstractUser) + campo es_superior
│   ├── migrations/
│   │   └── 0002_usuario_es_superior.py
│   └── templates/usuarios/login.html
│
├── empresas/               # Multi-tenancy
│   └── models.py           # Empresa
│
├── cargas_masivas/         # Consultas en lote (Excel → PDF)
│   ├── models.py           # LoteConsultaMasiva
│   ├── views.py            # ListarLotes, SubirLote, descargar_plantilla
│   └── templates/cargas_masivas/
│
├── core_admin/             # Panel superadministrador
│   ├── views.py            # Dashboard global, gestión usuarios, lotes, reportes
│   ├── forms.py            # UsuarioCreateForm, UsuarioEditForm
│   ├── mixins.py           # SuperuserRequiredMixin
│   └── templates/core_admin/
│       ├── dashboard.html
│       ├── usuario_list.html
│       ├── usuario_form.html
│       └── usuario_confirm_delete.html
│
├── templates/              # Templates globales (páginas de error)
│   ├── 403.html            # Acceso denegado
│   ├── 404.html            # Página no encontrada
│   └── 500.html            # Error del servidor
│
└── DOCS/                   # Documentación del proveedor API
    └── WEB SERVICE CONSULTALISTASPEPS 2023 (3).pdf
```

---

## Apps y sus Responsabilidades

### 1. `consultas` - Motor Principal
**URLs base:** `/`

| Ruta | Vista | Función |
|------|-------|---------|
| `/` | `dashboard` | Panel KPIs con gráficos Chart.js |
| `/buscar/` | `pagina_busqueda` | Formulario de búsqueda (ID/Nombre) |
| `/historial/` | `historial_busquedas` | Lista búsquedas del usuario |
| `/historial/<id>/` | `detalle_busqueda` | Detalle con resultados |
| `/historial/<id>/pdf/` | `generar_pdf_busqueda` | Genera PDF (WeasyPrint) |
| `/gestion/` | `gestion_dashboard` | Dashboard para Superior de empresa |
| `/gestion/consultas/` | `gestion_consultas` | Lista consultas de la empresa |
| `/gestion/consultas/<id>/` | `gestion_detalle_busqueda` | Detalle (vista Superior) |

**Modelos:**
- `Busqueda`: Registro de cada consulta (usuario, término, fecha, flags)
- `Resultado`: Cada coincidencia del API (mapea BlsWsConsultaPeps)

**Decorador:** `@superior_required` - Verifica que el usuario sea `es_superior` o `is_superuser`

### 2. `usuarios` - Autenticación
**URLs base:** `/cuentas/`

| Ruta | Vista |
|------|-------|
| `/login/` | LoginView (Django auth) |
| `/logout/` | LogoutView |

**Modelo:** `Usuario` extiende `AbstractUser`
- `empresa`: FK a Empresa
- `es_superior`: BooleanField - Permite ver métricas y consultas de toda la empresa

### 3. `empresas` - Multi-Empresa
**Modelo:** `Empresa` (nombre, creado_en)

### 4. `cargas_masivas` - Consultas en Lote
**URLs base:** `/cargas-masivas/`

| Ruta | Vista |
|------|-------|
| `/` | `ListarLotesView` - Lotes del cliente |
| `/subir/` | `SubirLoteView` - Subir Excel |
| `/plantilla/` | `descargar_plantilla` |

**Modelo:** `LoteConsultaMasiva`
- Estados: `PENDIENTE` / `PROCESADO`
- `archivo_subido`: Excel cliente → S3
- `archivo_resultado`: PDF resultado → S3

### 5. `core_admin` - Panel Superusuario
**URLs base:** `/core-admin/`

| Ruta | Vista |
|------|-------|
| `/` | `DashboardView` - KPIs globales |
| `/usuarios/` | `UsuarioListView` - Listar usuarios |
| `/usuarios/crear/` | `UsuarioCreateView` - Crear usuario |
| `/usuarios/editar/<pk>/` | `UsuarioUpdateView` - Editar usuario |
| `/usuarios/eliminar/<pk>/` | `UsuarioDeleteView` - Eliminar usuario |
| `/cargas-masivas/` | `LoteListView` - Todos los lotes |
| `/cargas-masivas/procesar/<pk>/` | `LoteProcessView` |
| `/reporte-mensual/` | `ReporteMensualView` |

**Formularios:** `UsuarioCreateForm`, `UsuarioEditForm`, `ProcesarLoteForm`

---

## API Externa - ConsultaListasPeps

### Configuración
```python
# settings.py
API_TOKEN = config('API_TOKEN')      # Token del .env
API_BASE_URL = config('API_BASE_URL') # URL base del .env
```

### URL del Servicio
```
https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/
```

### Métodos Implementados (consultas/services.py)

| Función | Endpoint API | Descripción |
|---------|--------------|-------------|
| `consultar_api_por_id(id)` | `PepsExactaID/{token}/{id}` | Búsqueda exacta por cédula |
| `consultar_api_por_nombre(nombre)` | `PepsNombre/{token}/{nombre}` | Búsqueda por nombre |
| `consultar_api_por_id_y_nombre(id, nombre)` | `PepsIDNombre/{token}/{id}/{nombre}` | Búsqueda combinada |

### Métodos Disponibles (no implementados aún)
- `PepsExactaIDSimple` - Respuesta reducida por ID exacto
- `PepsID` - Búsqueda aproximada de ID (±1 dígito)
- `PepsIDSimple` - Versión simple de PepsID

### Estructura de Respuesta API
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

---

## Sistema de Clasificación de Riesgo

Implementado en `consultas/views.py:get_classification()`

| Clasificación | Criterio | Color |
|---------------|----------|-------|
| **Rojo** | Todo lo que no sea amarillo o PEP | Máximo riesgo |
| **Amarillo** | Filtraciones: Panama Papers, Paradise Papers, Bahamas Leaks, Offshore Leaks | Riesgo medio |
| **PEP's** | Palabras clave: PEP, GOBIERNO, MINISTERIO, SENADO, PRESIDENCIA, etc. | Personas políticamente expuestas |

---

## Relaciones de Modelos

```
Empresa (1) ←──── (N) Usuario (1) ←──── (N) Busqueda (1) ←──── (N) Resultado
    │
    └──── (N) LoteConsultaMasiva
```

---

## Variables de Entorno (.env)

```bash
# Django
SECRET_KEY=
DEBUG=False

# Dominios y Seguridad (CONFIGURACIÓN POR CLIENTE)
ALLOWED_HOSTS=micliente.vadomconsultas.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://micliente.vadomconsultas.com
MI_DOMINIO=https://micliente.vadomconsultas.com

# Base de datos PostgreSQL
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=5432

# API ConsultaListasPeps
API_TOKEN=8495-4545-4487
API_BASE_URL=https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/

# AWS S3 (CONFIGURACIÓN POR CLIENTE)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_CLIENT_PREFIX=micliente

# Email SMTP
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
ADMIN_EMAIL=
```

---

## Despliegue Multi-Cliente

El sistema está diseñado para desplegarse a múltiples clientes independientes. Cada cliente tiene su propia instancia con configuración aislada.

### Variables específicas por cliente

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `ALLOWED_HOSTS` | Dominios permitidos (separados por coma) | `cliente1.vadomconsultas.com,localhost` |
| `CSRF_TRUSTED_ORIGINS` | Orígenes CSRF (separados por coma) | `https://cliente1.vadomconsultas.com` |
| `MI_DOMINIO` | URL completa del dominio | `https://cliente1.vadomconsultas.com` |
| `S3_CLIENT_PREFIX` | Carpeta en S3 para este cliente | `cliente1` |
| `DB_NAME` | Base de datos del cliente | `cliente1_listas` |

### Ejemplo: Configuración para "Cliente ABC"

```bash
# .env para Cliente ABC
ALLOWED_HOSTS=abc.vadomconsultas.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://abc.vadomconsultas.com
MI_DOMINIO=https://abc.vadomconsultas.com
S3_CLIENT_PREFIX=abc
DB_NAME=abc_listas
```

### Estructura S3 resultante

```
vadomdata/
├── cliente1/
│   ├── static/
│   └── media/
├── cliente2/
│   ├── static/
│   └── media/
└── abc/
    ├── static/
    └── media/
```

---

## Almacenamiento S3

**Bucket:** `vadomdata`
**Estructura:**
```
vadomdata/
└── {S3_CLIENT_PREFIX}/     # ej: comertex/
    ├── static/             # Archivos estáticos (CSS, JS, imágenes)
    └── media/              # Archivos subidos
        └── cargas_masivas/
            └── empresa_{id}/
                ├── subidas/    # Excel de clientes
                └── resultados/ # PDF procesados
```

---

## Comandos Útiles

```bash
# Activar entorno virtual (Windows)
cd comertex_listas
.\venv\Scripts\activate

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Servidor desarrollo
python manage.py runserver

# Collectstatic (sube a S3)
python manage.py collectstatic

# Crear superusuario
python manage.py createsuperuser
```

---

## Notas de Desarrollo

### Autenticación
- `LOGIN_URL = '/cuentas/login/'`
- `LOGIN_REDIRECT_URL = '/'` (dashboard)
- `AUTH_USER_MODEL = 'usuarios.Usuario'`

### Seguridad en Vistas
- Todas las vistas de consultas usan `@login_required`
- Vistas de core_admin usan `SuperuserRequiredMixin`
- Filtros por `usuario=request.user` para aislar datos entre usuarios
- Filtros por `empresa=request.user.empresa` para aislar datos entre empresas

### Templates
- Base template: `consultas/templates/consultas/base.html`
- Gráficos: Chart.js
- PDF: `consultas/templates/consultas/reporte_pdf.html` (WeasyPrint)

### Restricciones del API (según documentación proveedor)
- No usar herramientas automatizadas con llamados periódicos/masivos
- Formato nombre recomendado: `[PA] [SA] [PN] [SN]` (ej: SANTOS CALDERON JUAN MANUEL)

---

## Archivos Clave para Modificaciones Comunes

| Tarea | Archivo(s) |
|-------|------------|
| Agregar método API | `consultas/services.py` |
| Modificar clasificación | `consultas/views.py` → `get_classification()` |
| Cambiar campos guardados | `consultas/models.py`, `consultas/views.py` |
| Dashboard cliente | `consultas/views.py` → `dashboard()`, `templates/consultas/dashboard.html` |
| Dashboard admin | `core_admin/views.py`, `templates/core_admin/dashboard.html` |
| Formulario búsqueda | `consultas/forms.py`, `templates/consultas/pagina_busqueda.html` |
| Autenticación | `usuarios/urls.py`, `templates/usuarios/login.html` |
| Configuración general | `gestor_listas/settings.py` |
| Sidebar / Navegación | `consultas/templates/consultas/base.html` |
| Páginas de error | `templates/403.html`, `404.html`, `500.html` |

---

## Características de UI/UX

### Sidebar Moderna
- **Diseño:** Gradiente verde aguamarina (#1b7783 → #145a63)
- **Iconos:** En cajas con fondo semi-transparente
- **Indicador activo:** Línea blanca lateral + fondo destacado
- **Secciones:** Menu Principal, Gestión (superiores), Administración (superusers)
- **Footer:** Tarjeta de usuario con avatar + botón logout

### Página Detalle de Búsqueda (`detalle_busqueda.html`)
- **Header:** Resumen con término buscado, fecha, estadísticas
- **Filtros:** Por coincidencia (0%, 50%, 70%, 90%) y por clasificación
- **Animación de carga:** Overlay con spinner al filtrar (800ms)
- **Tarjetas de resultado:**
  - Borde lateral de color según clasificación
  - Panel de coincidencias con barras de progreso (ID% y Nombre%)
  - Badges de clasificación y lista restrictiva
  - Grid de información (tipo lista, origen, fuente)
  - Fuente muestra URL real clickeable

### Sistema de Coincidencias
El API retorna dos campos de coincidencia:
- `CoincidenciaID`: Porcentaje de match con el documento (0-100)
- `CoincidenciaNombre`: Porcentaje de match con el nombre (0-100)

**Colores según nivel:**
| Rango | Color | Clase CSS |
|-------|-------|-----------|
| ≥70% | Verde | `.high` / `text-success` |
| 50-69% | Amarillo | `.medium` / `text-warning` |
| <50% | Gris | `.low` / `text-secondary` |

### Páginas de Error Personalizadas
- **403:** Acceso denegado (escudo rojo con animación shake)
- **404:** Página no encontrada (animación pulse)
- **500:** Error del servidor (engranaje giratorio)
- Todas con diseño consistente, logo VADOM, botones de acción

---

## Roles de Usuario

| Rol | Campo | Permisos |
|-----|-------|----------|
| **Usuario normal** | - | Ver sus propias búsquedas y dashboard personal |
| **Superior de empresa** | `es_superior=True` | Ver métricas y búsquedas de TODA la empresa |
| **Superusuario** | `is_superuser=True` | Acceso total + Panel Admin + gestión de usuarios |

### Acceso en Sidebar
```
Usuario normal:     Menu Principal (Dashboard, Búsqueda, Historial, Cargas)
Superior:           Menu Principal + Gestión (Panel de Gestión)
Superusuario:       Menu Principal + Gestión + Administración (Panel Admin)
```

---

## Historial de Cambios Recientes

### Enero 2026

#### Funcionalidades Nuevas
- **Rol Superior de Empresa:** Nuevo campo `es_superior` en Usuario con decorador `@superior_required`
- **Panel de Gestión:** Dashboard y vistas para supervisores de empresa (`/gestion/`)
- **Gestión de Usuarios:** CRUD completo en core_admin (crear, editar, eliminar usuarios)
- **Páginas de Error:** Templates personalizados para 403, 404, 500

#### Mejoras de UI/UX
- **Sidebar Rediseñada:** Gradiente, iconos en cajas, secciones separadas, tarjeta de usuario
- **Detalle de Búsqueda Rediseñado:**
  - Header con resumen de búsqueda
  - Filtros por coincidencia y clasificación
  - Animación de carga al filtrar (800ms)
  - Barras de progreso para coincidencia ID y Nombre
  - Badges visuales mejorados
  - Fuente muestra URL real
- **Dashboard:** Sección "Mis Últimas Búsquedas" (solo del usuario actual)

#### Migraciones
- `usuarios/migrations/0002_usuario_es_superior.py` - Campo es_superior

#### Archivos Modificados
```
consultas/views.py              # Vistas gestion_*, dashboard actualizado
consultas/templates/consultas/base.html           # Sidebar moderna
consultas/templates/consultas/dashboard.html      # Mis últimas búsquedas
consultas/templates/consultas/detalle_busqueda.html  # Rediseño completo
consultas/templates/consultas/gestion/            # Nuevos templates
core_admin/views.py             # CRUD usuarios
core_admin/forms.py             # Formularios usuarios
core_admin/urls.py              # URLs usuarios
templates/403.html, 404.html, 500.html           # Páginas de error
usuarios/models.py              # Campo es_superior
```
