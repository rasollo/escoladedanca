from django.urls import path

from . import views

app_name = "professores"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("minha-area/", views.minha_area, name="minha_area"),
    path("meus-alunos/", views.meus_alunos, name="meus_alunos"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.editar, name="editar"),
]
