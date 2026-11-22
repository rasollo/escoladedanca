"""RF26 — aniversariantes do mês (alunos e professores ativos).

Todos os papéis veem o dia e o mês. A idade (a que a pessoa completa no
aniversário deste ano) só é calculada para Administrativo e Professor; para o
Aluno ela nem é enviada à página (LGPD — minimização). Quem não tem data de
nascimento cadastrada não entra na lista.
"""
from django.db.models.functions import ExtractDay
from django.utils import timezone

from alunos.models import Aluno
from professores.models import Professor

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]


def aniversariantes(mes=None, hoje=None, com_idade=False):
    """Lista ordenada por dia: [{'nome', 'perfil', 'dia', 'mes', 'hoje', 'idade'}]."""
    hoje = hoje or timezone.localdate()
    mes = mes or hoje.month
    lista = []
    for modelo, perfil in ((Aluno, "Aluno"), (Professor, "Professor")):
        qs = (modelo.objects.filter(ativo=True, data_nascimento__month=mes)
              .annotate(dia=ExtractDay("data_nascimento")).order_by("dia", "nome"))
        for pessoa in qs:
            lista.append({
                "nome": pessoa.nome, "perfil": perfil, "dia": pessoa.dia, "mes": mes,
                "hoje": mes == hoje.month and pessoa.dia == hoje.day,
                "idade": hoje.year - pessoa.data_nascimento.year if com_idade else None,
            })
    lista.sort(key=lambda p: (p["dia"], p["nome"]))
    return lista


def ve_idade(user):
    """Somente Administrativo e Professor veem a idade dos aniversariantes."""
    from .rbac import ADMINISTRATIVO, PROFESSOR, papel_do
    return papel_do(user) in (ADMINISTRATIVO, PROFESSOR)


def aniversariantes_do_mes(user, hoje=None):
    """Resumo para o quadro dos painéis iniciais."""
    hoje = hoje or timezone.localdate()
    lista = aniversariantes(hoje.month, hoje, com_idade=ve_idade(user))
    # No quadro, primeiro quem faz aniversário hoje e os próximos; depois os que já passaram.
    lista.sort(key=lambda p: (p["dia"] < hoje.day, p["dia"], p["nome"]))
    return {"lista": lista, "mes_nome": MESES[hoje.month - 1]}
