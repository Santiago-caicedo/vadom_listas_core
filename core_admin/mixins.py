# core_admin/mixins.py
from django.contrib.auth.mixins import AccessMixin
from django.http import Http404

class SuperuserRequiredMixin(AccessMixin):
    """
    Mixin para Vistas Basadas en Clases (CBV).
    Asegura que solo un superusuario pueda acceder.
    Si no está logueado, lo redirige al login.
    Si está logueado pero NO es superusuario, devuelve 404.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not request.user.is_superuser:
            raise Http404 # 404 para usuarios normales

        return super().dispatch(request, *args, **kwargs)