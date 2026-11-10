"""Popula o banco com dados fictícios para demonstrar o protótipo.

Uso:  python manage.py popular_demo            (cria usuário + dados)
      python manage.py popular_demo --limpar   (apaga alunos/aulas/financeiro antes)

A senha do usuário criado vem de --senha ou da variável DJANGO_DEMO_SENHA.
Sem nenhuma das duas, uma senha aleatória é gerada e exibida uma única vez.
"""
import os
import random
import secrets
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from alunos.models import Aluno
from aulas.models import Matricula, Modalidade, Presenca, Sala, Turma
from financeiro.models import Movimentacao
from professores.models import Professor

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Eduarda", "Felipe", "Gabriela", "Henrique",
         "Isabela", "João", "Karen", "Lucas", "Mariana", "Nicolas", "Olívia", "Pedro",
         "Quésia", "Rafael", "Sabrina", "Thiago", "Úrsula", "Vinícius", "Wesley", "Yasmin"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Lima", "Costa", "Pereira",
              "Almeida", "Ferreira", "Rodrigues", "Gomes", "Martins"]
# (nome, valor mensal por aluno inscrito)
PROFESSORES = [("Camila Rocha", "25.00"), ("Rogério Matos", "22.00"),
               ("Juliana Prado", "28.00"), ("Marcos Vieira", "20.00")]
# (modalidade, nível, dia, início, fim, sala, índice do professor)
GRADE = [
    ("Forró", "iniciante", 0, "19:00", "20:00", "Sala 1", 0),
    ("Zouk", "iniciante", 0, "20:00", "21:00", "Sala 1", 1),
    ("Salsa", "básico", 0, "19:00", "20:00", "Sala 2", 2),
    ("Forró", "intermediário", 1, "20:00", "21:30", "Sala 1", 0),
    ("Bachata", "básico", 1, "19:00", "20:00", "Sala 2", 2),
    ("Zouk", "intermediário", 2, "20:00", "21:30", "Sala 1", 1),
    ("Sertanejo", "básico", 2, "19:00", "20:00", "Sala 2", 3),
    ("Samba rock", "básico", 3, "19:30", "20:30", "Sala 1", 3),
    ("Forró", "avançado", 4, "20:00", "21:30", "Sala 1", 0),
    ("Zouk", "avançado", 5, "18:30", "20:00", "Sala 2", 1),
]


class Command(BaseCommand):
    help = "Cria dados de demonstração para o protótipo da Portal da Dança."

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true")
        parser.add_argument("--usuario", default="responsavel")
        parser.add_argument("--senha", default=None,
                            help="Padrão: $DJANGO_DEMO_SENHA ou uma senha aleatória.")

    @transaction.atomic
    def handle(self, *args, limpar=False, usuario="responsavel", senha=None, **kw):
        rnd = random.Random(2026)
        if limpar:
            Movimentacao.objects.all().delete()
            Presenca.objects.all().delete()
            Matricula.objects.all().delete()
            Turma.alunos.through.objects.all().delete()
            Turma.objects.all().delete()
            Aluno.objects.all().delete()
            Professor.objects.all().delete()

        User = get_user_model()
        if not User.objects.filter(username=usuario).exists():
            senha = senha or os.environ.get("DJANGO_DEMO_SENHA") or secrets.token_urlsafe(12)
            User.objects.create_superuser(usuario, "", senha, first_name="Responsável")
            self.stdout.write(f"Usuário criado: {usuario} / {senha}  (anote: não será exibida de novo)")

        if Aluno.objects.exists():
            self.stdout.write(self.style.WARNING("Já existem dados; use --limpar para recriar."))
            return

        for nome in ["Sala 1", "Sala 2"]:
            Sala.objects.get_or_create(nome=nome, defaults={"capacidade": 40})
        for nome in ["Forró", "Zouk", "Salsa", "Bachata", "Sertanejo", "Samba rock"]:
            Modalidade.objects.get_or_create(nome=nome)

        profs = [Professor.objects.create(nome=n, valor_por_aluno=Decimal(v),
                                          telefone=f"(13) 9{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}")
                 for n, v in PROFESSORES]
        alunos = []
        usados = set()
        while len(alunos) < 60:
            nome = f"{rnd.choice(NOMES)} {rnd.choice(SOBRENOMES)}"
            if nome in usados:
                continue
            usados.add(nome)
            alunos.append(Aluno.objects.create(
                nome=nome, telefone=f"(13) 9{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}",
                email=f"{nome.lower().replace(' ', '.')}@exemplo.com".encode("ascii", "ignore").decode(),
            ))

        hm = lambda s: time(*map(int, s.split(":")))
        turmas = []
        for mod, nivel, dia, ini, fim, sala, p in GRADE:
            t = Turma.objects.create(
                nome=f"{mod} {nivel}", modalidade=Modalidade.objects.get(nome=mod),
                professor=profs[p], sala=Sala.objects.get(nome=sala),
                dia_semana=dia, hora_inicio=hm(ini), hora_fim=hm(fim),
            )
            t.alunos.set(rnd.sample(alunos, rnd.randint(12, 30)))
            turmas.append(t)

        hoje = timezone.localdate()
        inicio = hoje - timedelta(days=70)
        # Matrículas com histórico: todas começam há 70 dias e alguns alunos
        # saíram há 3 semanas (matrícula encerrada), para o salário variar por mês.
        Matricula.objects.update(data_inicio=inicio)
        for t in turmas:
            saidas = rnd.sample(list(t.alunos.all()), 2)
            t.alunos.remove(*saidas)
            Matricula.objects.filter(turma=t, aluno__in=saidas).update(data_fim=hoje - timedelta(days=21))
        for t in turmas:
            d = inicio + timedelta(days=(t.dia_semana - inicio.weekday()) % 7)
            vinculados = list(t.alunos.all())
            while d < hoje:
                for a in vinculados:
                    Presenca.objects.create(turma=t, aluno=a, data=d, presente=rnd.random() < 0.82)
                d += timedelta(days=7)

        # Financeiro: 3 meses de movimentações
        for meses_atras in (2, 1, 0):
            ano, mes = hoje.year, hoje.month - meses_atras
            while mes < 1:
                ano, mes = ano - 1, mes + 12
            ultimo_dia = hoje.day if meses_atras == 0 else 28
            for a in alunos:
                if rnd.random() < 0.85:
                    dia = rnd.randint(1, min(10, ultimo_dia))
                    pago = date(ano, mes, dia)
                    Movimentacao.objects.create(
                        tipo="entrada", origem="mensalidade", aluno=a, valor=Decimal("150.00"),
                        data_pagamento=pago, validade=pago + timedelta(days=30),
                        forma_pagamento=rnd.choice(["pix", "pix", "dinheiro", "cartao"]),
                    )
            for _ in range(12):
                Movimentacao.objects.create(
                    tipo="entrada", origem=rnd.choice(["bebidas", "bebidas", "camisetas", "aluguel_sala"]),
                    valor=Decimal(rnd.choice(["12.00", "25.00", "60.00", "200.00"])),
                    data_pagamento=date(ano, mes, rnd.randint(1, ultimo_dia)),
                    forma_pagamento=rnd.choice(["pix", "dinheiro", "cartao"]),
                )
            for cat, valor in [("luz", "480.00"), ("agua", "120.00"), ("taxas", "90.00"),
                               ("prefeitura", "150.00"), ("contas_gerais", "2500.00"),
                               ("manutencao", "300.00")]:
                Movimentacao.objects.create(
                    tipo="saida", categoria=cat, valor=Decimal(valor),
                    data_pagamento=date(ano, mes, min(15, ultimo_dia)),
                    validade=date(ano, mes, min(15, ultimo_dia)) + timedelta(days=30) if cat in ("luz", "agua") else None,
                )
            if meses_atras:  # salários do mês anterior já fechados
                from financeiro.services import calcular_salario
                for p in profs:
                    c = calcular_salario(p, ano, mes)
                    if c.valor:
                        Movimentacao.objects.create(
                            tipo="saida", categoria="salario", professor=p, valor=c.valor,
                            referencia=c.referencia, forma_pagamento="pix",
                            data_pagamento=date(ano, mes, 28), descricao=f"Salário {mes:02d}/{ano}",
                        )

        self.stdout.write(self.style.SUCCESS(
            f"Demo criada: {len(alunos)} alunos, {len(profs)} professores, {len(turmas)} aulas, "
            f"{Presenca.objects.count()} presenças/faltas, {Movimentacao.objects.count()} movimentações."
        ))
