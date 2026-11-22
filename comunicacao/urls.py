from django.urls import path

from . import views

app_name = "comunicacao"

urlpatterns = [
    path("comunicados/", views.comunicados, name="comunicados"),
    path("comunicados/novo/", views.comunicado_novo, name="comunicado_novo"),
    path("solicitacoes/", views.solicitacoes, name="solicitacoes"),
    path("solicitacoes/nova/", views.solicitacao_nova, name="solicitacao_nova"),
    path("solicitacoes/<int:pk>/", views.solicitacao_responder, name="solicitacao_responder"),
]
