from django.urls import path

from . import views

app_name = "aulas"

urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("nova/", views.turma_nova, name="turma_nova"),
    path("<int:pk>/", views.turma_detalhe, name="turma_detalhe"),
    path("<int:pk>/editar/", views.turma_editar, name="turma_editar"),
    path("<int:pk>/excluir/", views.turma_excluir, name="turma_excluir"),
    path("<int:pk>/alunos/", views.turma_alunos, name="turma_alunos"),
    path("<int:pk>/chamada/", views.chamada, name="chamada"),
    path("presencas/", views.presencas, name="presencas"),
    path("modalidades/", views.modalidades, name="modalidades"),
    path("modalidades/nova/", views.modalidade_nova, name="modalidade_nova"),
    path("modalidades/<int:pk>/editar/", views.modalidade_editar, name="modalidade_editar"),
    path("modalidades/<int:pk>/excluir/", views.modalidade_excluir, name="modalidade_excluir"),
    path("salas/nova/", views.sala_nova, name="sala_nova"),
    path("salas/<int:pk>/editar/", views.sala_editar, name="sala_editar"),
]
