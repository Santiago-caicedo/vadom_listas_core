# usuarios/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    # Añadimos un campo para relacionar al usuario con su empresa
    # Lo hacemos opcional (null=True) para que el superusuario no necesite empresa
    empresa = models.ForeignKey(
        'empresas.Empresa',
        related_name="usuarios",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Superior de empresa: puede ver métricas y consultas de todos los usuarios de su empresa
    es_superior = models.BooleanField(
        default=False,
        verbose_name="Superior de empresa",
        help_text="Permite ver métricas y consultas de todos los usuarios de la empresa."
    )