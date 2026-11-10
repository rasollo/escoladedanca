from django.contrib import admin

from .models import Matricula, Modalidade, Presenca, Sala, Turma

admin.site.register(Modalidade)
admin.site.register(Sala)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ["__str__", "professor", "ativa"]
    list_filter = ["dia_semana", "modalidade", "sala", "ativa"]
    filter_horizontal = ["alunos"]


@admin.register(Presenca)
class PresencaAdmin(admin.ModelAdmin):
    list_display = ["aluno", "turma", "data", "presente"]
    list_filter = ["presente", "turma__modalidade"]
    date_hierarchy = "data"


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ["aluno", "turma", "data_inicio", "data_fim"]
    list_filter = ["turma__modalidade", "turma__professor"]
    date_hierarchy = "data_inicio"
    search_fields = ["aluno__nome"]
