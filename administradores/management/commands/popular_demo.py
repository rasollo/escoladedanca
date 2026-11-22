"""Popula o banco com dados fictícios para demonstrar o protótipo.

Uso:  python manage.py popular_demo            (cria usuário + dados)
      python manage.py popular_demo --limpar   (apaga alunos/aulas/financeiro antes)

A senha do usuário criado vem de --senha ou da variável DJANGO_DEMO_SENHA.
Sem nenhuma das duas, uma senha aleatória é gerada e exibida uma única vez.
"""
import os
import random
import secrets
import unicodedata
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from alunos.models import Aluno
from escoladedanca.rbac import ALUNO, PROFESSOR, adicionar_papel, atribuir_papel
from aulas.models import Chamada, Matricula, Modalidade, Presenca, Sala, Turma
from comunicacao.models import Comunicado, Solicitacao
from financeiro.models import Cobranca, Movimentacao
from financeiro.services import estornar, periodo_do_mes, receber, vencimento_da
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


def preencher_aniversarios(rnd, alunos, profs, hoje=None):
    """RF26 — datas de nascimento fictícias para a demonstração.

    A data é opcional: cerca de 15% dos alunos ficam sem ela. Para a tela de
    aniversariantes nunca ficar vazia na demonstração, alguns alunos e um
    professor fazem aniversário no mês atual, um deles no próprio dia.
    """
    hoje = hoje or timezone.localdate()
    alunos, profs = list(alunos), list(profs)

    def data(ano_min, ano_max, mes=None, dia=None):
        mes = mes or rnd.randint(1, 12)
        return date(rnd.randint(ano_min, ano_max), mes, dia or rnd.randint(1, 28))

    total = 0
    for k, a in enumerate(alunos):
        if k < 6:  # aniversariantes do mês atual (o primeiro, hoje)
            a.data_nascimento = data(1975, 2008, hoje.month, min(hoje.day, 28) if k == 0 else None)
        elif rnd.random() < 0.15:
            continue  # sem data: o campo não é obrigatório
        else:
            a.data_nascimento = data(1965, 2008)
        a.save(update_fields=["data_nascimento"])
        total += 1
    for k, p in enumerate(profs):
        p.data_nascimento = data(1975, 1998, hoje.month if k == 0 else None)
        p.save(update_fields=["data_nascimento"])
        total += 1
    return total


def criar_acesso_demo(cadastro, papel, senha):
    """Cria o usuário de demonstração vinculado ao professor/aluno (se ainda não existir)."""
    if cadastro.usuario_id:
        return None
    User = get_user_model()
    sem_acento = unicodedata.normalize("NFKD", cadastro.nome).encode("ascii", "ignore").decode()
    base = sem_acento.lower().replace(" ", ".")
    # Reinstalação com --limpar: o login de demonstração ficou sem cadastro.
    # Ele é reaproveitado (nova senha), em vez de criar "nome2".
    sobra = User.objects.filter(username=base, is_superuser=False, professor__isnull=True,
                                aluno__isnull=True).first()
    if sobra:
        try:
            validate_password(senha, sobra)
        except ValidationError as erro:  # demonstração: avisa, mas não impede a instalação
            print(f"Aviso: senha de demonstração fraca para {base}: {' '.join(erro.messages)}")
        sobra.set_password(senha)
        sobra.first_name = cadastro.nome
        sobra.is_active = True
        sobra.save()
        user, login = sobra, base
    else:
        login, n = base, 1
        while User.objects.filter(username=login).exists():
            n += 1
            login = f"{base}{n}"
        user = User.objects.create_user(login, "", senha, first_name=cadastro.nome)
    atribuir_papel(user, papel)
    cadastro.usuario = user
    cadastro.save(update_fields=["usuario"])
    return login


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
            Comunicado.objects.all().delete()
            Solicitacao.objects.all().delete()
            Movimentacao.objects.filter(estorno_de__isnull=False).delete()
            Movimentacao.objects.all().delete()
            Cobranca.objects.all().delete()
            Presenca.objects.all().delete()
            Chamada.objects.all().delete()
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
            # Reinstalação: completa as datas de nascimento da demonstração (RF26)
            # sem tocar em cadastros reais (só e-mails @exemplo.com e professores demo).
            n = preencher_aniversarios(
                random.Random(1990),
                Aluno.objects.filter(email__endswith="@exemplo.com", data_nascimento__isnull=True),
                Professor.objects.filter(nome__in=[n for n, _ in PROFESSORES],
                                         data_nascimento__isnull=True),
            )
            if n:
                self.stdout.write(f"Datas de nascimento da demonstração preenchidas: {n}.")
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

        # Gerador próprio: não altera o restante dos dados de demonstração.
        preencher_aniversarios(random.Random(1990), alunos, profs)

        hm = lambda s: time(*map(int, s.split(":")))
        turmas = []
        for mod, nivel, dia, ini, fim, sala, p in GRADE:
            t = Turma.objects.create(
                nome=f"{mod} {nivel}", modalidade=Modalidade.objects.get(nome=mod),
                professor=profs[p], sala=Sala.objects.get(nome=sala),
                dia_semana=dia, hora_inicio=hm(ini), hora_fim=hm(fim),
                # Mensalidade por aula: 1h = R$ 90,00; 1h30 = R$ 110,00.
                valor_mensal=Decimal("110.00") if (hm(fim).hour * 60 + hm(fim).minute)
                - (hm(ini).hour * 60 + hm(ini).minute) > 60 else Decimal("90.00"),
            )
            t.alunos.set(rnd.sample(alunos, rnd.randint(12, 30)))
            turmas.append(t)
        # RF36 — aula em mais de um dia: o Forró iniciante também acontece às quartas.
        Turma.objects.filter(pk=turmas[0].pk).update(outros_dias="2")
        turmas[0].refresh_from_db()
        # RF31 — a professora Camila também é aluna (Zouk iniciante): conta com dois papéis.
        camila_aluna = Aluno.objects.create(
            nome=profs[0].nome, telefone=profs[0].telefone, email="camila.rocha@exemplo.com",
            data_nascimento=profs[0].data_nascimento)
        turmas[1].alunos.add(camila_aluna)

        hoje = timezone.localdate()
        inicio = hoje - timedelta(days=70)
        # Matrículas com histórico: todas começam há 70 dias e alguns alunos
        # saíram há 3 semanas (matrícula encerrada), para o salário variar por mês.
        Matricula.objects.update(data_inicio=inicio)
        for t in turmas:
            saidas = rnd.sample(list(t.alunos.all()), 2)
            t.alunos.remove(*saidas)
            Matricula.objects.filter(turma=t, aluno__in=saidas).update(data_fim=hoje - timedelta(days=21))
            # RF32 — encerramentos com motivo: um suspenso (pode voltar) e um cancelado.
            Matricula.objects.filter(turma=t, aluno=saidas[0]).update(
                situacao="suspensa", motivo=rnd.choice(["Viagem a trabalho", "Lesão no joelho",
                                                        "Pausa por motivo financeiro"]))
            Matricula.objects.filter(turma=t, aluno=saidas[1]).update(
                situacao="cancelada", motivo=rnd.choice(["Mudou de cidade", "Trocou de horário",
                                                         "Não se adaptou à modalidade"]))
        for t in turmas:
            vinculados = list(t.alunos.all())
            d = inicio
            while d < hoje:
                if t.data_valida(d):
                    for a in vinculados:
                        Presenca.objects.create(turma=t, aluno=a, data=d, presente=rnd.random() < 0.82)
                d += timedelta(days=1)

        # RF33 — chamadas: as antigas concluídas, as da última semana abertas,
        # uma aula cancelada (feriado) e uma correção registrada pela administração.
        for t in turmas:
            for d in sorted(set(t.presencas.values_list("data", flat=True))):
                Chamada.objects.create(turma=t, data=d,
                                       situacao="concluida" if d < hoje - timedelta(days=7) else "aberta")
        datas_salsa = sorted(set(turmas[2].presencas.values_list("data", flat=True)))
        if len(datas_salsa) > 3:
            feriado = datas_salsa[-3]
            turmas[2].presencas.filter(data=feriado).delete()
            Chamada.objects.filter(turma=turmas[2], data=feriado).update(
                situacao="cancelada", motivo="Feriado municipal")
        corrigida = Chamada.objects.filter(turma=turmas[0], situacao="concluida").order_by("-data").first()
        if corrigida:
            Chamada.objects.filter(pk=corrigida.pk).update(
                motivo="Correção: aluna estava presente (registro trocado)")

        # Descontos combinados em algumas matrículas (percentual ou valor fixo).
        abertas = list(Matricula.objects.filter(data_fim__isnull=True).order_by("pk"))
        for m in rnd.sample(abertas, min(8, len(abertas))):
            if rnd.random() < 0.5:
                m.desconto_tipo, m.desconto = "percentual", Decimal("10")
            else:
                m.desconto_tipo, m.desconto = "fixo", Decimal("20.00")
            m.save(update_fields=["desconto_tipo", "desconto"])

        # Financeiro: 3 meses de movimentações e de cobranças de mensalidade
        recebimentos = []
        for meses_atras in (2, 1, 0):
            ano, mes = hoje.year, hoje.month - meses_atras
            while mes < 1:
                ano, mes = ano - 1, mes + 12
            ultimo_dia = hoje.day if meses_atras == 0 else 28
            competencia = date(ano, mes, 1)
            _, fim_mes = periodo_do_mes(ano, mes)
            # Uma cobrança por matrícula ativa em algum dia do mês.
            for m in Matricula.ativas_no_periodo(competencia, fim_mes).select_related("turma"):
                if m.valor_final <= 0:
                    continue
                c = Cobranca.objects.create(matricula=m, aluno_id=m.aluno_id, competencia=competencia,
                                            valor=m.valor_final, vencimento=vencimento_da(competencia))
                sorte = rnd.random()
                pago_ate = min(10, ultimo_dia)
                if meses_atras == 0 and hoje.day < 5:
                    sorte += 0.4  # início do mês: muitas ainda não venceram
                forma = rnd.choice(["pix", "pix", "dinheiro", "cartao"])
                if sorte < 0.86:      # paga em dia (ou até o dia 10)
                    recebimentos.append(receber(c, c.valor, date(ano, mes, rnd.randint(1, pago_ate)), forma))
                elif sorte < 0.92:    # pagamento parcial
                    receber(c, (c.valor / 2).quantize(Decimal("0.01")),
                            date(ano, mes, rnd.randint(1, pago_ate)), forma)
                # demais: em aberto (pendentes ou em atraso)
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

        # Um estorno de exemplo, com motivo registrado (histórico preservado).
        if recebimentos:
            estornar(recebimentos[len(recebimentos) // 3], "Pagamento lançado em duplicidade",
                     data=recebimentos[len(recebimentos) // 3].data_pagamento)

        # RF25 — acessos de demonstração para testar os papéis Professor e Aluno.
        # O aluno escolhido faz aniversário no mês e frequenta várias aulas (RF26).
        senha_demo = senha or os.environ.get("DJANGO_DEMO_SENHA") or secrets.token_urlsafe(12)
        aluno_demo = max(alunos[:6], key=lambda a: (a.turmas.count(), -a.pk))
        for papel, cadastro in ((PROFESSOR, profs[0]), (ALUNO, aluno_demo)):
            login = criar_acesso_demo(cadastro, papel, senha_demo)
            if login:
                self.stdout.write(f"Acesso {papel}: {login} / {senha_demo}  ({cadastro.nome})")
        if profs[0].usuario_id and not camila_aluna.usuario_id:
            adicionar_papel(profs[0].usuario, ALUNO)
            Aluno.objects.filter(pk=camila_aluna.pk).update(usuario=profs[0].usuario)
            self.stdout.write(f"  {profs[0].usuario.username} também é aluno: ao entrar, escolhe o ambiente.")

        # Comunicados das turmas e solicitações de alunos.
        avisos = [
            (turmas[0], profs[0], "Aula aberta no sábado", "Neste sábado teremos aula aberta de forró "
             "às 18h. Tragam amigos!"),
            (turmas[1], profs[1], "Troca de sala", "Nesta segunda a aula será na Sala 2."),
            (turmas[3], profs[0], "Ensaio para a apresentação", "Vamos ensaiar a coreografia do baile "
             "de fim de ano nas próximas duas aulas."),
            (turmas[8], None, "Feriado", "Não haverá aula no próximo feriado municipal."),
        ]
        responsavel = User.objects.filter(username=usuario).first()
        for turma, prof, titulo, msg in avisos:
            autor = prof.usuario if prof and prof.usuario_id else responsavel
            Comunicado.objects.create(turma=turma, autor=autor, titulo=titulo, mensagem=msg)
        pedidos = [
            (aluno_demo, "frequencia", "Estive na aula de terça passada, mas aparece falta.", "pendente", ""),
            (alunos[10], "cadastro", "Mudei de telefone, por favor atualizem.", "concluida",
             "Telefone atualizado no cadastro."),
            (alunos[20], "financeiro", "Posso pagar a mensalidade em duas vezes?", "em_analise", ""),
        ]
        for aluno, tipo, msg, status, resposta in pedidos:
            Solicitacao.objects.create(aluno=aluno, tipo=tipo, mensagem=msg, status=status,
                                       resposta=resposta,
                                       respondido_por=responsavel if resposta else None)

        self.stdout.write(self.style.SUCCESS(
            f"Demo criada: {len(alunos)} alunos, {len(profs)} professores, {len(turmas)} aulas, "
            f"{Presenca.objects.count()} presenças/faltas, {Cobranca.objects.count()} cobranças, "
            f"{Movimentacao.objects.count()} movimentações."
        ))
