"""Controle de acesso baseado em papéis (RBAC) — RF25 / RNF03.

Papéis (grupos do Django, criados automaticamente no ``migrate``):

* **Administrativo** — proprietário/secretaria: acesso a todo o sistema e à
  criação dos acessos de professores e alunos. Superusuários contam como
  Administrativo.
* **Professor** — agenda e edita as próprias aulas (respeitando a lotação da
  sala, o horário de funcionamento e os conflitos), vincula alunos às suas
  aulas, faz a chamada e consulta as presenças das suas turmas.
* **Aluno** — consulta as aulas em que está matriculado, a agenda, as próprias
  presenças/faltas e mensalidades.

A regra é **negar por padrão**: uma página só é liberada para Professor ou Aluno
quando a view é marcada com ``@permitir(...)``. As demais ficam restritas ao
Administrativo pelo ``PapelMiddleware``, do mesmo jeito que o
``LoginRequiredMiddleware`` exige login em todas as páginas.
"""
from functools import wraps

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

ADMINISTRATIVO = "Administrativo"
PROFESSOR = "Professor"
ALUNO = "Aluno"
PAPEIS = (ADMINISTRATIVO, PROFESSOR, ALUNO)


SESSAO_PAPEL = "papel_ativo"


def papeis_do(user) -> list[str]:
    """Todos os papéis do usuário, do maior para o menor privilégio."""
    if user is None or not user.is_authenticated or not user.is_active:
        return []
    if not hasattr(user, "_papeis_cache"):
        grupos = set(user.groups.values_list("name", flat=True))
        if user.is_superuser:
            grupos.add(ADMINISTRATIVO)
        user._papeis_cache = [p for p in PAPEIS if p in grupos]
    return user._papeis_cache


def papel_do(user):
    """Papel ativo do usuário.

    Numa requisição, é o ambiente escolhido na sessão (contas com mais de um
    papel). Fora dela, o de maior privilégio.
    """
    if user is None or not user.is_authenticated or not user.is_active:
        return None
    if not hasattr(user, "_papel_cache"):
        papeis = papeis_do(user)
        user._papel_cache = papeis[0] if papeis else None
    return user._papel_cache


def _limpar_cache(user):
    user.__dict__.pop("_papel_cache", None)
    user.__dict__.pop("_papeis_cache", None)


def atribuir_papel(user, papel):
    """Define o papel do usuário (substitui os papéis anteriores)."""
    if papel not in PAPEIS:
        raise ValueError(f"Papel desconhecido: {papel}")
    user.groups.remove(*Group.objects.filter(name__in=PAPEIS))
    user.groups.add(Group.objects.get_or_create(name=papel)[0])
    _limpar_cache(user)


def adicionar_papel(user, papel):
    """Acrescenta um papel à conta (ex.: professor que também é aluno)."""
    if papel not in PAPEIS:
        raise ValueError(f"Papel desconhecido: {papel}")
    user.groups.add(Group.objects.get_or_create(name=papel)[0])
    _limpar_cache(user)


def remover_papel(user, papel):
    user.groups.remove(*Group.objects.filter(name=papel))
    _limpar_cache(user)


def criar_grupos(**kwargs):
    """Garante que os três grupos existem (executado após cada migrate)."""
    for papel in PAPEIS:
        Group.objects.get_or_create(name=papel)


def permitir(*papeis):
    """Libera a view para os papéis informados, além do Administrativo."""
    def decorador(view):
        @wraps(view)
        def envolvida(*args, **kwargs):
            return view(*args, **kwargs)
        envolvida.papeis_permitidos = frozenset(papeis) | {ADMINISTRATIVO}
        return envolvida
    return decorador


def qualquer_usuario(view):
    """Libera a view para qualquer usuário logado, mesmo sem papel (ex.: sair)."""
    @wraps(view)
    def envolvida(*args, **kwargs):
        return view(*args, **kwargs)
    envolvida.papeis_permitidos = None
    return envolvida


class PapelMiddleware:
    """Nega por padrão: sem ``@permitir``, só o Administrativo acessa a página."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            papeis = papeis_do(user)
            escolhido = request.session.get(SESSAO_PAPEL)
            if escolhido in papeis:
                user._papel_cache = escolhido
            elif len(papeis) > 1:
                # Conta com mais de um papel: precisa escolher o ambiente.
                user._papel_cache = None
                request.escolher_ambiente = True
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None  # o LoginRequiredMiddleware cuida (ou a página é pública)
        if not getattr(view_func, "login_required", True):
            return None  # páginas públicas (tela de login)
        match = request.resolver_match
        if match is not None and match.namespace == "admin":
            return None  # painel do Django: exige is_staff por conta própria
        nome_url = match.url_name if match is not None else None
        if nome_url not in ("trocar_senha", "logout"):
            from administradores.models import deve_trocar_senha
            if deve_trocar_senha(request.user):
                from django.contrib import messages
                from django.shortcuts import redirect
                messages.warning(request, "Primeiro acesso: escolha uma nova senha para continuar.")
                return redirect("trocar_senha")
        permitidos = getattr(view_func, "papeis_permitidos", frozenset({ADMINISTRATIVO}))
        if permitidos is None:
            return None
        if getattr(request, "escolher_ambiente", False):
            from django.shortcuts import redirect
            return redirect("ambiente")
        if papel_do(request.user) not in permitidos:
            raise PermissionDenied("Seu perfil não tem acesso a esta página.")
        return None


def professor_do(user):
    """Cadastro de professor vinculado ao usuário (ou None)."""
    from professores.models import Professor
    return Professor.objects.filter(usuario=user, ativo=True).first()


def aluno_do(user):
    """Cadastro de aluno vinculado ao usuário (ou None)."""
    from alunos.models import Aluno
    return Aluno.objects.filter(usuario=user).first()


def exigir_turma_propria(request, turma):
    """O professor só mexe nas próprias aulas; o Administrativo, em todas."""
    papel = papel_do(request.user)
    if papel == ADMINISTRATIVO:
        return
    if papel == PROFESSOR and turma.professor.usuario_id == request.user.pk:
        return
    raise PermissionDenied("Esta aula é de outro professor.")


def contexto(request):
    """Disponibiliza o papel do usuário nos templates (menu e botões)."""
    user = getattr(request, "user", None)
    papel = papel_do(user)
    papeis = papeis_do(user)
    return {
        "papel": papel,
        "papeis": papeis,
        "varios_papeis": len(papeis) > 1,
        "eh_admin": papel == ADMINISTRATIVO,
        "eh_professor": papel == PROFESSOR,
        "eh_aluno": papel == ALUNO,
    }
