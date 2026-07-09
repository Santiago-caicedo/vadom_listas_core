# archivo: cargas_masivas/views.py

from django.shortcuts import render, redirect
from django.views.generic import CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.conf import settings
from .models import LoteConsultaMasiva
from .forms import LoteForm
import os

class ListarLotesView(LoginRequiredMixin, ListView):
    model = LoteConsultaMasiva
    template_name = 'cargas_masivas/listar_lotes.html'
    context_object_name = 'lotes'

    def get_queryset(self):
        # El cliente solo ve las solicitudes de su propia empresa
        return LoteConsultaMasiva.objects.filter(empresa=self.request.user.empresa).order_by('-fecha_solicitud')

class SubirLoteView(LoginRequiredMixin, CreateView):
    model = LoteConsultaMasiva
    form_class = LoteForm
    template_name = 'cargas_masivas/subir_lote.html'
    success_url = reverse_lazy('listar_lotes') # Redirige a la lista después de subir

    def form_valid(self, form):
        # Asignamos la empresa y el usuario automáticamente
        form.instance.usuario_solicitante = self.request.user
        form.instance.empresa = self.request.user.empresa
        return super().form_valid(form)

@login_required
def descargar_plantilla(request):
    # La plantilla vive en static/ (viaja por git y se despliega en cada cliente).
    # Se lee desde el directorio fuente (BASE_DIR/static), independiente de S3/collectstatic.
    plantilla_path = os.path.join(settings.BASE_DIR, 'static', 'plantillas', 'plantilla_consultas.xlsx')

    try:
        with open(plantilla_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="plantilla_consultas.xlsx"'
            return response
    except FileNotFoundError:
        # Esta página de error simple es suficiente por ahora
        return HttpResponse("Archivo de plantilla no encontrado. Contacte al administrador.", status=404)