from django.urls import path

from . import relatorios, views

app_name = 'consultas'

urlpatterns = [
    path('', views.index, name='painel'),
    path("relatorios/", relatorios.relatorios, name="relatorios"),
]
