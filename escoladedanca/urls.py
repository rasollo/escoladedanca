from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import documentacao, index

urlpatterns = [
    path("", index, name="index"),
    path("entrar/", auth_views.LoginView.as_view(), name="login"),
    path("documentacao/", documentacao, name="documentacao"),
    path("documentacao/<slug:slug>/", documentacao, name="documentacao_doc"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("alunos/", include("alunos.urls")),
    path("professores/", include("professores.urls")),
    path("aulas/", include("aulas.urls")),
    path("financeiro/", include("financeiro.urls")),
    path("administradores/", include("administradores.urls")),
    path("proprietarios/", include("proprietarios.urls")),
    path("consultas/", include("consultas.urls")),
]
