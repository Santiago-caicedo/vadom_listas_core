# empresas/models.py
from django.db import models

class Empresa(models.Model):
    nombre = models.CharField(max_length=100)
    creado_en = models.DateField(auto_now_add=True)

    # Esto le dice a django-tenants que cree un nuevo esquema 
    # automáticamente cuando se crea una nueva Empresa
    auto_create_schema = True

    def __str__(self):
        return self.nombre
