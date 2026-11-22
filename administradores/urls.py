from django.urls import path
from . import views

app_name = 'administradores'

urlpatterns = [
    path('', views.index, name='administradores'),
    path('usuarios/novo/', views.usuario_novo, name='usuario_novo'),
    path('usuarios/<int:pk>/situacao/', views.usuario_situacao, name='usuario_situacao'),
]
