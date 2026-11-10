"""Cria uma matrícula aberta para cada vínculo aluno–aula já existente.

A data de início é a primeira presença do aluno naquela aula, quando houver;
senão, a data da migração. Assim o salário de meses anteriores continua
coerente com o histórico de presenças já registrado.
"""
from django.db import migrations
from django.db.models import Min
from django.utils import timezone


def criar(apps, schema_editor):
    Turma = apps.get_model("aulas", "Turma")
    Presenca = apps.get_model("aulas", "Presenca")
    Matricula = apps.get_model("aulas", "Matricula")
    hoje = timezone.localdate()
    primeiras = {
        (p["turma_id"], p["aluno_id"]): p["inicio"]
        for p in Presenca.objects.values("turma_id", "aluno_id").annotate(inicio=Min("data"))
    }
    novas = []
    for vinculo in Turma.alunos.through.objects.all():
        chave = (vinculo.turma_id, vinculo.aluno_id)
        novas.append(Matricula(turma_id=chave[0], aluno_id=chave[1],
                               data_inicio=primeiras.get(chave, hoje)))
    Matricula.objects.bulk_create(novas)


class Migration(migrations.Migration):
    dependencies = [("aulas", "0004_matricula")]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
