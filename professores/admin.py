from django.contrib import admin

from .models import Professor


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "valor_por_aluno", "usuario", "ativo"]
    raw_id_fields = ["usuario"]
    search_fields = ["nome"]
