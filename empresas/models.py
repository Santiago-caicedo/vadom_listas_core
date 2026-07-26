# empresas/models.py
from django.db import models

class Empresa(models.Model):
    nombre = models.CharField(max_length=100)
    creado_en = models.DateField(auto_now_add=True)

    # Cupo mensual de consultas contratado (0 = ilimitado).
    limite_consultas_mensual = models.PositiveIntegerField(default=0)
    # Bloqueo manual: si True, no deja hacer consultas (lo activa el superusuario).
    bloqueado = models.BooleanField(default=False)
    # 'YYYY-MM' del último mes en que ya se envió el aviso de exceso (evita spam).
    mes_alerta_cupo = models.CharField(max_length=7, blank=True, default='')

    # Esto le dice a django-tenants que cree un nuevo esquema 
    # automáticamente cuando se crea una nueva Empresa
    auto_create_schema = True

    def __str__(self):
        return self.nombre

    def consultas_mes_actual(self):
        """Número de búsquedas de esta empresa en el mes en curso."""
        from django.utils import timezone
        from consultas.models import Busqueda
        hoy = timezone.now()
        return Busqueda.objects.filter(
            usuario__empresa=self,
            fecha_busqueda__year=hoy.year,
            fecha_busqueda__month=hoy.month,
        ).count()

    def cupo_excedido(self):
        """True si tiene cupo (>0) y ya lo superó este mes."""
        return (self.limite_consultas_mensual > 0
                and self.consultas_mes_actual() > self.limite_consultas_mensual)
