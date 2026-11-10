from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("movimentacoes/", views.movimentacoes, name="movimentacoes"),
    path("movimentacoes/<int:pk>/editar/", views.editar, name="editar"),
    path("movimentacoes/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("entradas/nova/", views.nova_entrada, name="nova_entrada"),
    path("saidas/nova/", views.nova_saida, name="nova_saida"),
    path("saldo/", views.saldo, name="saldo"),
    path("balanco/", views.balanco, name="balanco"),
    path("mensalidades/", views.mensalidades, name="mensalidades"),
    path("mensalidades/nova/", views.nova_mensalidade, name="nova_mensalidade"),
    path("despesas/", views.despesas, name="despesas"),
    path("salarios/", views.salarios, name="salarios"),
    path("salarios/registrar/", views.registrar_salario, name="registrar_salario"),
]
