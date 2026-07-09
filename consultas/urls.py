# archivo: consultas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # El dashboard ahora es la página principal
    path('', views.dashboard, name='dashboard'),

    # La página de búsqueda ahora está en /buscar/
    path('buscar/', views.pagina_busqueda, name='pagina_busqueda'),

    path('historial/', views.historial_busquedas, name='historial_busquedas'),
    path('historial/<int:busqueda_id>/', views.detalle_busqueda, name='detalle_busqueda'),

    path('historial/<int:busqueda_id>/pdf/', views.generar_pdf_busqueda, name='generar_pdf_busqueda'),

    # --- URLs para Superior de Empresa ---
    path('gestion/', views.gestion_dashboard, name='gestion_dashboard'),
    path('gestion/consultas/', views.gestion_consultas, name='gestion_consultas'),
    path('gestion/consultas/<int:busqueda_id>/', views.gestion_detalle_busqueda, name='gestion_detalle_busqueda'),
]