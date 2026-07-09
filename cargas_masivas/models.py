# cargas_masivas/models.py
from django.db import models
from usuarios.models import Usuario
from empresas.models import Empresa
import os

# Función para definir rutas de subida dinámicas
def ruta_archivo_subido(instance, filename):
    # CORREGIDO: Usamos .id en lugar de .schema_name
    return f'cargas_masivas/empresa_{instance.empresa.id}/subidas/{filename}'

def ruta_archivo_resultado(instance, filename):
    # CORREGIDO: Usamos .id en lugar de .schema_name
    return f'cargas_masivas/empresa_{instance.empresa.id}/resultados/{filename}'

class LoteConsultaMasiva(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Procesar'),
        ('PROCESADO', 'Procesado y Completado'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    usuario_solicitante = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    
    # El Excel que sube el cliente
    archivo_subido = models.FileField(upload_to=ruta_archivo_subido)
    # El PDF que sube el admin
    archivo_resultado = models.FileField(upload_to=ruta_archivo_resultado, null=True, blank=True)

    class Meta:
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"Lote de {self.empresa.nombre} - {self.fecha_solicitud.strftime('%Y-%m-%d')}"