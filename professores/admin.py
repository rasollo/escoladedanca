from django.contrib import admin

from .models import Professor


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "valor_por_aluno", "ativo"]
    search_fields = ["nome"]
