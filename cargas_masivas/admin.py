# archivo: cargas_masivas/admin.py
from django.contrib import admin
from .models import LoteConsultaMasiva
from django.utils.html import format_html

@admin.register(LoteConsultaMasiva)
class LoteAdmin(admin.ModelAdmin):
    list_display = ('fecha_solicitud', 'empresa', 'usuario_solicitante', 'estado', 'archivo_subido_link')
    list_filter = ('estado', 'empresa')
    search_fields = ('usuario_solicitante__username', 'empresa__nombre')

    # Define los campos que se muestran en el formulario de edición
    fields = ('empresa', 'usuario_solicitante', 'fecha_solicitud', 'archivo_subido_link', 'estado', 'archivo_resultado')

    # Hacemos que los campos informativos no se puedan editar
    readonly_fields = ('empresa', 'usuario_solicitante', 'fecha_solicitud', 'archivo_subido_link')

    def get_fields(self, request, obj=None):
        # Lógica para mostrar todos los campos (incluidos los readonly) al editar
        if obj:
            return ('empresa', 'usuario_solicitante', 'fecha_solicitud', 'archivo_subido_link', 'estado', 'archivo_resultado')
        # Lógica para crear (aunque no lo haremos desde aquí)
        return ('empresa', 'usuario_solicitante', 'archivo_subido', 'estado', 'archivo_resultado')

    @admin.display(description="Archivo del Cliente")
    def archivo_subido_link(self, obj):
        # Permite al admin descargar el archivo del cliente
        if obj.archivo_subido:
            return format_html('<a href="{}" download>Descargar Excel</a>', obj.archivo_subido.url)
        return "N/A"

    def get_readonly_fields(self, request, obj=None):
        # Sobrescribimos para asegurar que los campos sean readonly al editar
        if obj: # obj is not None, so this is an edit
            return self.readonly_fields
        return () # No hay readonly al crear (aunque no aplica mucho aquí)