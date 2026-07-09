# archivo: cargas_masivas/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Vista para que el cliente vea sus lotes subidos
    path('', views.ListarLotesView.as_view(), name='listar_lotes'),

    # Vista para que el cliente suba un nuevo lote
    path('subir/', views.SubirLoteView.as_view(), name='subir_lote'),

    # URL para el botón de descargar la plantilla
    path('plantilla/', views.descargar_plantilla, name='descargar_plantilla'),
]