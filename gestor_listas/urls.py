# archivo: gestor_listas/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # La ruta del admin ahora es la pública, para superusuarios
    path('admin/', admin.site.urls),

    # Añadimos una ruta "cuentas/" que manejará el login, logout, etc.
    path('cuentas/', include('usuarios.urls')), 
    
    # La ruta raíz la manejará nuestra app de consultas
    path('', include('consultas.urls')),

    path('cargas-masivas/', include('cargas_masivas.urls')),

    path('core-admin/', include('core_admin.urls')),
]

# Servir archivos estáticos y media en desarrollo (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)