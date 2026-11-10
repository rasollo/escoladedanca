"""Fábricas e base comum para a suíte de testes."""
import secrets
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from alunos.models import Aluno
from aulas.models import Modalidade, Presenca, Sala, Turma
from financeiro.models import Movimentacao
from professores.models import Professor

SEGUNDA = date(2026, 11, 2)  # uma segunda-feira


def senha_aleatoria() -> str:
    """Senha gerada a cada execução: nenhuma credencial fica fixa no código."""
    return secrets.token_urlsafe(16)


def criar_aluno(nome="Ana Silva", **kw):
    return Aluno.objects.create(nome=nome, **kw)


def criar_professor(nome="Camila Rocha", valor="4.00", **kw):
    return Professor.objects.create(nome=nome, valor_por_aluno=Decimal(valor), **kw)


def sala(nome="Sala 1"):
    return Sala.objects.get_or_create(nome=nome, defaults={"capacidade": 40})[0]


def modalidade(nome="Forró"):
    return Modalidade.objects.get_or_create(nome=nome)[0]


def criar_turma(professor=None, dia=0, inicio="19:00", fim="20:00", sala_nome="Sala 1",
                mod="Forró", **kw):
    hm = lambda s: time(*map(int, s.split(":")))
    return Turma.objects.create(
        modalidade=modalidade(mod), professor=professor or criar_professor(),
        sala=sala(sala_nome), dia_semana=dia, hora_inicio=hm(inicio), hora_fim=hm(fim), **kw,
    )


def criar_presenca(turma, aluno, data=SEGUNDA, presente=True):
    return Presenca.objects.create(turma=turma, aluno=aluno, data=data, presente=presente)


def entrada(valor="100.00", data=SEGUNDA, origem="bebidas", forma="pix", **kw):
    return Movimentacao.objects.create(
        tipo="entrada", valor=Decimal(valor), data_pagamento=data, origem=origem,
        forma_pagamento=forma, **kw,
    )


def saida(valor="50.00", data=SEGUNDA, categoria="luz", **kw):
    return Movimentacao.objects.create(
        tipo="saida", valor=Decimal(valor), data_pagamento=data, categoria=categoria, **kw,
    )


def proxima(data, dias=7):
    return data + timedelta(days=dias)


class LogadoTestCase(TestCase):
    """Base para testes de views: o responsável já está autenticado (RNF03)."""

    def setUp(self):
        # force_login dispensa senha; o usuário fica com senha inutilizável.
        self.usuario = get_user_model().objects.create_user("responsavel")
        self.client.force_login(self.usuario)
