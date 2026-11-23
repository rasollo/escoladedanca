"""Cria os usuários padrão do sistema sem mexer nos dados (pode rodar de novo).

Uso:
    python manage.py criar_usuarios_padrao [--senha SENHA]
        [--professor "Nome do professor"] [--aluno "Nome do aluno"]
        [--trocar-senha] [--redefinir]

Cria, se ainda não existirem:
  * responsavel  — Administrativo (superusuário), dono do sistema;
  * um acesso de Professor vinculado a um professor cadastrado;
  * um acesso de Aluno vinculado a um aluno cadastrado (de preferência matriculado).

Sem --professor/--aluno, usa o primeiro professor ativo e o primeiro aluno ativo
com matrícula. Cadastros que já têm acesso são mantidos. Nada é apagado.
A senha vem de --senha, de $DJANGO_USUARIOS_SENHA ou é gerada e exibida uma vez.
"""
import os
import secrets
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administradores.models import marcar_troca_de_senha
from alunos.models import Aluno
from escoladedanca.rbac import ADMINISTRATIVO, ALUNO, PROFESSOR, adicionar_papel, papeis_do
from professores.models import Professor


def login_para(nome: str) -> str:
    base = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    base = ".".join(p for p in base.replace("-", " ").split() if p)
    User = get_user_model()
    login, n = base, 1
    while User.objects.filter(username=login).exists():
        n += 1
        login = f"{base}{n}"
    return login


class Command(BaseCommand):
    help = "Cria os usuários padrão (Administrativo, Professor e Aluno) sem alterar os dados."

    def add_arguments(self, parser):
        parser.add_argument("--senha", help="Senha dos usuários criados (padrão: gerada).")
        parser.add_argument("--professor", help="Nome do professor a vincular (padrão: o primeiro ativo).")
        parser.add_argument("--aluno", help="Nome do aluno a vincular (padrão: o primeiro ativo matriculado).")
        parser.add_argument("--trocar-senha", action="store_true",
                            help="Exige que cada usuário troque a senha no primeiro acesso.")
        parser.add_argument("--redefinir", action="store_true",
                            help="Também redefine a senha do 'responsavel' se ele já existir.")

    def _senha(self, senha):
        senha = senha or os.environ.get("DJANGO_USUARIOS_SENHA")
        if senha:
            try:
                validate_password(senha)
            except ValidationError as erro:
                self.stdout.write(self.style.WARNING("Aviso: senha fraca — " + " ".join(erro.messages)))
            return senha, False
        return secrets.token_urlsafe(12), True

    def _cadastro(self, modelo, nome, padrao_qs, rotulo):
        if nome:
            achados = modelo.objects.filter(nome__iexact=nome.strip(), ativo=True)
            if not achados.exists():
                achados = modelo.objects.filter(nome__icontains=nome.strip(), ativo=True)
            if achados.count() != 1:
                raise CommandError(f"{rotulo} '{nome}': {achados.count()} cadastros encontrados; "
                                   "informe o nome completo.")
            return achados.get()
        return padrao_qs.first()

    @transaction.atomic
    def handle(self, *args, senha=None, professor=None, aluno=None, trocar_senha=False,
               redefinir=False, **kw):
        User = get_user_model()
        senha, gerada = self._senha(senha)
        linhas = []

        # 1) Administrativo
        adm = User.objects.filter(username="responsavel").first()
        if adm is None:
            adm = User.objects.create_superuser("responsavel", "", senha, first_name="Responsável")
            marcar_troca_de_senha(adm, trocar_senha)
            linhas.append(("responsavel", ADMINISTRATIVO, "—", "criado"))
        else:
            if redefinir:
                try:
                    validate_password(senha, adm)
                except ValidationError as erro:
                    self.stdout.write(self.style.WARNING("Aviso: senha fraca — " + " ".join(erro.messages)))
                adm.set_password(senha)
                adm.is_active = True
                adm.save()
            if ADMINISTRATIVO not in papeis_do(adm):
                adicionar_papel(adm, ADMINISTRATIVO)
            linhas.append(("responsavel", ADMINISTRATIVO, "—",
                           "senha redefinida" if redefinir else "já existia (senha mantida)"))

        # 2) Professor e 3) Aluno
        alvos = [
            (PROFESSOR, self._cadastro(Professor, professor,
                                       Professor.objects.filter(ativo=True).order_by("nome"), "Professor")),
            (ALUNO, self._cadastro(Aluno, aluno,
                                   Aluno.objects.filter(ativo=True, turmas__isnull=False)
                                   .distinct().order_by("nome"), "Aluno")),
        ]
        for papel, cadastro in alvos:
            if cadastro is None:
                linhas.append(("—", papel, "—", "nenhum cadastro ativo; cadastre e rode de novo"))
                continue
            if cadastro.usuario_id:
                linhas.append((cadastro.usuario.username, papel, cadastro.nome, "já tinha acesso"))
                continue
            user = User.objects.create_user(login_para(cadastro.nome), cadastro.email or "", senha,
                                            first_name=cadastro.nome)
            adicionar_papel(user, papel)
            marcar_troca_de_senha(user, trocar_senha)
            cadastro.usuario = user
            cadastro.save(update_fields=["usuario"])
            linhas.append((user.username, papel, cadastro.nome, "criado"))

        largura = max(len(l[0]) for l in linhas)
        self.stdout.write("")
        for login, papel, nome, situacao in linhas:
            self.stdout.write(f"  {login:<{largura}}  {papel:<14}  {nome:<30}  {situacao}")
        if any(l[3] in ("criado", "senha redefinida") for l in linhas):
            self.stdout.write("")
            if gerada:
                self.stdout.write(self.style.WARNING(f"Senha dos usuários criados: {senha}  "
                                                     "(anote: não será exibida de novo)"))
            else:
                self.stdout.write("Senha dos usuários criados: a informada em --senha.")
            if trocar_senha:
                self.stdout.write("Cada usuário criado vai trocar a senha no primeiro acesso.")
        self.stdout.write(self.style.SUCCESS("Usuários padrão conferidos."))
