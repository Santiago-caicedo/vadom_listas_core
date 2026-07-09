# core_admin/urls.py
from django.urls import path
from . import views

app_name = 'core_admin'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Cargas Masivas
    path('cargas-masivas/', views.LoteListView.as_view(), name='lote_list'),
    path('cargas-masivas/procesar/<int:pk>/', views.LoteProcessView.as_view(), name='lote_process'),

    # Reportes
    path('reporte-mensual/', views.ReporteMensualView.as_view(), name='reporte_mensual'),

    # Gestión de Usuarios
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/crear/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/editar/<int:pk>/', views.UsuarioUpdateView.as_view(), name='usuario_edit'),
    path('usuarios/eliminar/<int:pk>/', views.UsuarioDeleteView.as_view(), name='usuario_delete'),
]