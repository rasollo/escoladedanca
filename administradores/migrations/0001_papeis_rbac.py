"""RF25 — cria os papéis (grupos) e mantém o acesso de quem já usava o sistema.

Antes do RBAC todo usuário logado acessava tudo. Para ninguém perder o acesso
na atualização, os usuários existentes sem papel passam a ser Administrativo.
"""
from django.db import migrations

PAPEIS = ("Administrativo", "Professor", "Aluno")


def criar_papeis(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")
    for nome in PAPEIS:
        Group.objects.get_or_create(name=nome)
    administrativo = Group.objects.get(name="Administrativo")
    for user in User.objects.filter(is_superuser=False, groups__isnull=True):
        user.groups.add(administrativo)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [
        migrations.RunPython(criar_papeis, migrations.RunPython.noop),
    ]
