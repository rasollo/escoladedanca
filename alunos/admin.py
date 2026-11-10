from django.contrib import admin

from .models import Aluno


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "email", "ativo"]
    list_filter = ["ativo"]
    search_fields = ["nome", "email", "telefone"]
