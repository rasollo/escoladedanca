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


def papel_do(user):
    """Papel do usuário autenticado (o de maior privilégio, se tiver mais de um)."""
    if user is None or not user.is_authenticated or not user.is_active:
        return None
    if not hasattr(user, "_papel_cache"):
        if user.is_superuser:
            papel = ADMINISTRATIVO
        else:
            grupos = set(user.groups.values_list("name", flat=True))
            papel = next((p for p in PAPEIS if p in grupos), None)
        user._papel_cache = papel
    return user._papel_cache


def atribuir_papel(user, papel):
    """Define o papel do usuário (substitui os papéis anteriores)."""
    if papel not in PAPEIS:
        raise ValueError(f"Papel desconhecido: {papel}")
    user.groups.remove(*Group.objects.filter(name__in=PAPEIS))
    user.groups.add(Group.objects.get_or_create(name=papel)[0])
    user.__dict__.pop("_papel_cache", None)


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
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None  # o LoginRequiredMiddleware cuida (ou a página é pública)
        if not getattr(view_func, "login_required", True):
            return None  # páginas públicas (tela de login)
        match = request.resolver_match
        if match is not None and match.namespace == "admin":
            return None  # painel do Django: exige is_staff por conta própria
        permitidos = getattr(view_func, "papeis_permitidos", frozenset({ADMINISTRATIVO}))
        if permitidos is None:
            return None
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
    papel = papel_do(getattr(request, "user", None))
    return {
        "papel": papel,
        "eh_admin": papel == ADMINISTRATIVO,
        "eh_professor": papel == PROFESSOR,
        "eh_aluno": papel == ALUNO,
    }
