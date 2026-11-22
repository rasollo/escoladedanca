from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .rbac import qualquer_usuario
from .views import (ambiente, aniversariantes, documentacao, index, relatorio_pdf,
                    trocar_senha)

urlpatterns = [
    path("", index, name="index"),
    path("entrar/", auth_views.LoginView.as_view(), name="login"),
    path("aniversariantes/", aniversariantes, name="aniversariantes"),
    path("senha/", trocar_senha, name="trocar_senha"),
    path("ambiente/", ambiente, name="ambiente"),
    path("documentacao/", documentacao, name="documentacao"),
    path("documentacao/relatorio.pdf", relatorio_pdf, name="relatorio_pdf"),
    path("documentacao/<slug:slug>/", documentacao, name="documentacao_doc"),
    path("sair/", qualquer_usuario(auth_views.LogoutView.as_view()), name="logout"),
    path("admin/", admin.site.urls),
    path("alunos/", include("alunos.urls")),
    path("professores/", include("professores.urls")),
    path("aulas/", include("aulas.urls")),
    path("financeiro/", include("financeiro.urls")),
    path("administradores/", include("administradores.urls")),
    path("proprietarios/", include("proprietarios.urls")),
    path("consultas/", include("consultas.urls")),
    path("comunicacao/", include("comunicacao.urls")),
]
