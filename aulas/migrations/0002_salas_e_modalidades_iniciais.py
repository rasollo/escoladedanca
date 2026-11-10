"""RN09 — duas salas com capacidade de 40 alunos; seção 3.1 — modalidades oferecidas."""
from django.db import migrations

SALAS = ["Sala 1", "Sala 2"]
MODALIDADES = ["Forró", "Zouk", "Salsa", "Bachata", "Sertanejo", "Samba rock"]


def criar(apps, schema_editor):
    Sala = apps.get_model("aulas", "Sala")
    Modalidade = apps.get_model("aulas", "Modalidade")
    for nome in SALAS:
        Sala.objects.get_or_create(nome=nome, defaults={"capacidade": 40})
    for nome in MODALIDADES:
        Modalidade.objects.get_or_create(nome=nome)


def remover(apps, schema_editor):
    apps.get_model("aulas", "Sala").objects.filter(nome__in=SALAS, turmas__isnull=True).delete()
    apps.get_model("aulas", "Modalidade").objects.filter(
        nome__in=MODALIDADES, turmas__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("aulas", "0001_initial")]
    operations = [migrations.RunPython(criar, remover)]
