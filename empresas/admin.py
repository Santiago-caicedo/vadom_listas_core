# archivo: empresas/admin.py

from django.contrib import admin
from .models import Empresa

# Ya no necesitamos el DomainInline

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin): # <-- Sin TenantAdminMixin
    """
    Configuración simple para el modelo Empresa en el Admin.
    """
    list_display = ('nombre', 'creado_en') # Campos a mostrar
    search_fields = ('nombre',) # Campos por los que se puede buscar
    # Ya no hay 'inlines' porque borramos el modelo Domain