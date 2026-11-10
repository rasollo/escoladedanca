"""Trilha de auditoria (RNF03 / RNF04 — LGPD).

Dois registros, configurados em settings.LOGGING:

* ``auditoria.acesso``  → logs/acessos.log
  Cada requisição de página (usuário, IP, método, caminho, status) e os eventos
  de autenticação: LOGIN_OK, LOGIN_FALHOU, LOGOUT.
* ``auditoria.dados``   → logs/auditoria.log
  Criação, alteração e exclusão de alunos, professores, aulas, presenças e
  movimentações financeiras, com o usuário que fez a operação.

Formato de cada linha:  data hora | EVENTO | chave=valor | chave=valor ...
Nunca são registradas senhas nem o conteúdo dos dados pessoais, apenas o
identificador do registro afetado.
"""
import logging
import re
from contextvars import ContextVar

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

log_acesso = logging.getLogger("auditoria.acesso")
log_dados = logging.getLogger("auditoria.dados")

_requisicao_atual: ContextVar = ContextVar("requisicao_atual", default=None)

# Requisições que não interessam à auditoria (arquivos estáticos, ícone).
_IGNORAR = ("/static/", "/favicon.ico")
_CONTROLE = re.compile(r"[\x00-\x1f\x7f|]")


def limpar(valor, limite=150) -> str:
    """Evita injeção de linhas no log: remove quebras de linha e o separador '|'."""
    texto = _CONTROLE.sub(" ", str(valor))
    return texto[:limite]


def ip_do_cliente(request) -> str:
    # REMOTE_ADDR é o endereço real da conexão. X-Forwarded-For só deve ser
    # considerado atrás de um proxy confiável, o que não é o caso do protótipo.
    return limpar(request.META.get("REMOTE_ADDR", "-"), 45) if request else "-"


def usuario_da(request) -> str:
    user = getattr(request, "user", None) if request else None
    if user is not None and user.is_authenticated:
        return limpar(user.get_username())
    return "anonimo"


def registrar(logger, evento, **campos):
    partes = [evento] + [f"{k}={limpar(v)}" for k, v in campos.items()]
    logger.info(" | ".join(partes))


class AuditoriaMiddleware:
    """Registra cada requisição e disponibiliza a requisição atual aos sinais."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _requisicao_atual.set(request)
        try:
            response = self.get_response(request)
        finally:
            _requisicao_atual.reset(token)
        if not request.path.startswith(_IGNORAR):
            registrar(
                log_acesso, "REQUISICAO",
                usuario=usuario_da(request), ip=ip_do_cliente(request),
                metodo=request.method, caminho=request.path, status=response.status_code,
            )
        return response


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
@receiver(user_logged_in)
def _login_ok(sender, request, user, **kwargs):
    registrar(log_acesso, "LOGIN_OK", usuario=user.get_username(), ip=ip_do_cliente(request))


@receiver(user_login_failed)
def _login_falhou(sender, credentials, request=None, **kwargs):
    # 'credentials' já vem com a senha mascarada pelo Django; só o usuário é usado.
    registrar(log_acesso, "LOGIN_FALHOU",
              usuario_informado=credentials.get("username", "-"), ip=ip_do_cliente(request))


@receiver(user_logged_out)
def _logout(sender, request, user, **kwargs):
    registrar(log_acesso, "LOGOUT",
              usuario=user.get_username() if user else "-", ip=ip_do_cliente(request))


# ---------------------------------------------------------------------------
# Alterações de dados
# ---------------------------------------------------------------------------
MODELOS_AUDITADOS = {
    "alunos.Aluno", "professores.Professor", "aulas.Modalidade", "aulas.Sala",
    "aulas.Turma", "aulas.Presenca", "financeiro.Movimentacao", "auth.User",
}


def _rotulo(sender) -> str:
    return f"{sender._meta.app_label}.{sender.__name__}"


def _autor():
    request = _requisicao_atual.get()
    if request is None:
        return "sistema", "-"  # comando de terminal, migração, shell
    return usuario_da(request), ip_do_cliente(request)


@receiver(post_save)
def _salvo(sender, instance, created, raw=False, **kwargs):
    if raw or _rotulo(sender) not in MODELOS_AUDITADOS:
        return
    usuario, ip = _autor()
    registrar(log_dados, "CRIADO" if created else "ALTERADO",
              modelo=_rotulo(sender), id=instance.pk, usuario=usuario, ip=ip)


@receiver(post_delete)
def _excluido(sender, instance, **kwargs):
    if _rotulo(sender) not in MODELOS_AUDITADOS:
        return
    usuario, ip = _autor()
    registrar(log_dados, "EXCLUIDO", modelo=_rotulo(sender), id=instance.pk,
              usuario=usuario, ip=ip)


@receiver(m2m_changed)
def _vinculo(sender, instance, action, pk_set, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if _rotulo(type(instance)) != "aulas.Turma":
        return
    usuario, ip = _autor()
    ids = ",".join(str(i) for i in sorted(pk_set or []))
    registrar(log_dados, "VINCULO_" + action.split("_")[1].upper(),
              modelo="aulas.Turma", id=instance.pk, alunos=ids or "todos",
              usuario=usuario, ip=ip)


# ---------------------------------------------------------------------------
# Leitura dos logs (relatório e tela de Administração)
# ---------------------------------------------------------------------------
def ler_eventos(nome="acessos.log", desde=None, eventos=None):
    """Lê o log atual e os rotacionados (nome.AAAA-MM-DD) e devolve dicionários.

    ``desde``: datetime ingênuo (horário local) para filtrar; ``eventos``: conjunto
    de nomes de evento (ex.: {"LOGIN_OK"}).
    """
    from datetime import datetime

    from django.conf import settings

    arquivos = sorted(settings.LOGS_DIR.glob(f"{nome}.*")) + [settings.LOGS_DIR / nome]
    resultado = []
    for arquivo in arquivos:
        if not arquivo.exists():
            continue
        for linha in arquivo.read_text(encoding="utf-8", errors="replace").splitlines():
            partes = [p.strip() for p in linha.split(" | ")]
            if len(partes) < 2:
                continue
            try:
                quando = datetime.strptime(partes[0], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if desde and quando < desde:
                continue
            if eventos and partes[1] not in eventos:
                continue
            campos = dict(p.split("=", 1) for p in partes[2:] if "=" in p)
            # "quem": usuário autenticado ou, na falha de login, o usuário digitado
            quem = campos.get("usuario") or campos.get("usuario_informado") or "-"
            resultado.append({"quando": quando, "evento": partes[1], "quem": quem,
                              "ip": campos.get("ip", "-"), **campos})
    return resultado


def resumo_acessos(desde=None):
    """Quantos usuários e IPs acessaram, com logins por usuário."""
    eventos = ler_eventos("acessos.log", desde=desde)
    por_usuario = {}
    for e in eventos:
        usuario = e.get("usuario") or e.get("usuario_informado") or "-"
        if e["evento"] == "REQUISICAO" and usuario == "anonimo":
            continue
        info = por_usuario.setdefault(usuario, {
            "usuario": usuario, "logins": 0, "falhas": 0, "requisicoes": 0,
            "ips": set(), "primeiro": e["quando"], "ultimo": e["quando"],
        })
        info["ips"].add(e.get("ip", "-"))
        info["ultimo"] = max(info["ultimo"], e["quando"])
        info["primeiro"] = min(info["primeiro"], e["quando"])
        if e["evento"] == "LOGIN_OK":
            info["logins"] += 1
        elif e["evento"] == "LOGIN_FALHOU":
            info["falhas"] += 1
        elif e["evento"] == "REQUISICAO":
            info["requisicoes"] += 1
    autenticados = [u for u in por_usuario.values() if u["logins"] or u["requisicoes"]]
    return {
        "usuarios": sorted(por_usuario.values(), key=lambda u: u["ultimo"], reverse=True),
        "total_usuarios": len(autenticados),
        "total_ips": len({e.get("ip") for e in eventos if e.get("ip")}),
        "total_logins": sum(u["logins"] for u in por_usuario.values()),
        "total_falhas": sum(u["falhas"] for u in por_usuario.values()),
    }
