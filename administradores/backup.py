"""Exportação e restauração dos dados do sistema em JSON (somente superusuário)."""
import json
import os
import tempfile
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction

MODELOS = [
    "auth.group", "auth.user", "administradores.contaacesso", "alunos", "professores",
    "aulas", "financeiro", "comunicacao",
]
PERMITIDOS = {"auth.group", "auth.user", "administradores.contaacesso", "alunos.aluno",
              "professores.professor", "aulas.modalidade", "aulas.sala", "aulas.turma",
              "aulas.presenca", "aulas.chamada", "aulas.matricula", "financeiro.cobranca",
              "financeiro.movimentacao", "comunicacao.comunicado", "comunicacao.solicitacao"}


def exportar() -> str:
    saida = StringIO()
    call_command("dumpdata", *MODELOS, indent=1, stdout=saida,
                 use_natural_foreign_keys=True, use_natural_primary_keys=True)
    return saida.getvalue()


def validar(texto: str) -> list:
    try:
        dados = json.loads(texto)
    except ValueError:
        raise ValueError("O arquivo não é um JSON válido.")
    if not isinstance(dados, list) or not dados:
        raise ValueError("O arquivo não contém uma exportação do sistema.")
    for item in dados:
        if not isinstance(item, dict) or item.get("model") not in PERMITIDOS:
            raise ValueError("O arquivo contém dados que não pertencem a uma exportação do sistema.")
    if not any(i["model"] == "auth.user" and i.get("fields", {}).get("is_superuser")
               and i.get("fields", {}).get("is_active") for i in dados):
        raise ValueError("O backup precisa ter ao menos um superusuário ativo; restauração cancelada.")
    return dados


def _apagar_tudo():
    from alunos.models import Aluno
    from aulas.models import Chamada, Matricula, Modalidade, Presenca, Sala, Turma
    from comunicacao.models import Comunicado, Solicitacao
    from financeiro.models import Cobranca, Movimentacao
    from professores.models import Professor
    from .models import ContaAcesso
    Comunicado.objects.all().delete()
    Solicitacao.objects.all().delete()
    Movimentacao.objects.filter(estorno_de__isnull=False).delete()
    Movimentacao.objects.all().delete()
    Cobranca.objects.all().delete()
    Chamada.objects.all().delete()
    Presenca.objects.all().delete()
    Matricula.objects.all().delete()
    Turma.alunos.through.objects.all().delete()
    Turma.objects.all().delete()
    Modalidade.objects.all().delete()
    Sala.objects.all().delete()
    Professor.objects.all().delete()
    Aluno.objects.all().delete()
    ContaAcesso.objects.all().delete()
    get_user_model().objects.all().delete()


def restaurar(texto: str) -> int:
    """Substitui os dados atuais pelos do backup, numa única transação."""
    from aulas.models import IMPORTANDO_BACKUP
    dados = validar(texto)
    caminho = None
    token = IMPORTANDO_BACKUP.set(True)
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(texto)
            caminho = f.name
        with transaction.atomic():
            _apagar_tudo()
            call_command("loaddata", caminho, verbosity=0)
    finally:
        IMPORTANDO_BACKUP.reset(token)
        if caminho:
            os.unlink(caminho)
    return len(dados)
