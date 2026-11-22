from django.urls import path
from . import views

app_name = 'administradores'

urlpatterns = [
    path('', views.index, name='administradores'),
    path('usuarios/novo/', views.usuario_novo, name='usuario_novo'),
    path('usuarios/<int:pk>/situacao/', views.usuario_situacao, name='usuario_situacao'),
    path('usuarios/<int:pk>/papeis/', views.usuario_papeis, name='usuario_papeis'),
    path('backup/', views.backup_exportar, name='backup_exportar'),
    path('backup/restaurar/', views.backup_restaurar, name='backup_restaurar'),
]
