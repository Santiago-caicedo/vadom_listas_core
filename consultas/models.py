# archivo: consultas/models.py

from django.db import models
from usuarios.models import Usuario

class Busqueda(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='busquedas')
    termino_buscado = models.CharField(max_length=100)
    fecha_busqueda = models.DateTimeField(auto_now_add=True)
    encontro_resultados = models.BooleanField(default=False)
    genero_alerta = models.BooleanField(default=False)

    def __str__(self):
        return f"Búsqueda de '{self.termino_buscado}' por {self.usuario.username}"

class Resultado(models.Model):
    # Relación con la búsqueda a la que pertenece
    busqueda = models.ForeignKey(Busqueda, related_name='resultados', on_delete=models.CASCADE)
    
    # Campos originales del API
    nombre_completo = models.CharField(max_length=255, null=True, blank=True)
    identificacion = models.CharField(max_length=50, null=True, blank=True) # Mapeado desde 'Id' del API
    tipo_lista = models.CharField(max_length=100, null=True, blank=True)
    origen_lista = models.CharField(max_length=100, null=True, blank=True)
    relacionado_con = models.TextField(null=True, blank=True) # Descripción principal
    fuente = models.CharField(max_length=255, null=True, blank=True)
    es_restrictiva = models.BooleanField(default=False) # Campo 'Restrictiva' del API
    
    # Campos adicionales identificados en los PDFs
    es_boletin = models.BooleanField(default=False) # Campo 'Boletin' del API
    alias = models.CharField(max_length=255, null=True, blank=True) # Campo 'Aka' del API
    coincidencia_nombre = models.IntegerField(default=0) # Campo 'CoincidenciaNombre' del API
    coincidencia_id = models.IntegerField(default=0) # Campo 'CoincidenciaID' del API
    tipo_persona = models.CharField(max_length=50, null=True, blank=True) # Campo 'Tipo_Persona' del API
    
    # Campos de la guía SIDIF (Página 41) - Opcionales pero útiles
    fecha_update = models.CharField(max_length=100, null=True, blank=True) # Formato /Date(...)/
    estado = models.CharField(max_length=100, null=True, blank=True) # Ej: INGRESA LISTA: 20160801
    llaveimagen = models.CharField(max_length=255, null=True, blank=True) # Sub-clasificación
    
    # Campo para nuestra clasificación interna
    clasificacion = models.CharField(max_length=20, default='No Clasificado') # Opciones: Rojo, Amarillo, PEP's

    def __str__(self):
        return f"Resultado para {self.nombre_completo or 'Desconocido'} ({self.identificacion or 'N/A'})"