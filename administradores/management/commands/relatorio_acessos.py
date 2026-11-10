"""Resumo da auditoria: quantos usuários acessaram, de quais IPs e quando.

Uso:  python manage.py relatorio_acessos            (últimos 30 dias)
      python manage.py relatorio_acessos --dias 7
      python manage.py relatorio_acessos --eventos  (lista logins, falhas e logouts)
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from escoladedanca.auditoria import ler_eventos, resumo_acessos


class Command(BaseCommand):
    help = "Mostra quantos usuários acessaram o sistema, a partir de logs/acessos.log."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=30)
        parser.add_argument("--eventos", action="store_true",
                            help="Lista cada login, falha de login e logout.")

    def handle(self, *args, dias, eventos, **kw):
        desde = datetime.now() - timedelta(days=dias)
        r = resumo_acessos(desde)
        self.stdout.write(f"Período: últimos {dias} dias (desde {desde:%d/%m/%Y %H:%M})")
        self.stdout.write(
            f"Usuários que acessaram: {r['total_usuarios']} · IPs distintos: {r['total_ips']} · "
            f"logins: {r['total_logins']} · falhas de login: {r['total_falhas']}\n"
        )
        if not r["usuarios"]:
            self.stdout.write("Nenhum acesso registrado no período.")
        for u in r["usuarios"]:
            self.stdout.write(
                f"  {u['usuario']:<20} logins={u['logins']:<3} falhas={u['falhas']:<3} "
                f"páginas={u['requisicoes']:<5} último={u['ultimo']:%d/%m %H:%M}  "
                f"IPs={', '.join(sorted(u['ips']))}"
            )
        if eventos:
            self.stdout.write("\nEventos de autenticação:")
            for e in ler_eventos("acessos.log", desde, {"LOGIN_OK", "LOGIN_FALHOU", "LOGOUT"}):
                quem = e.get("usuario") or e.get("usuario_informado", "-")
                self.stdout.write(f"  {e['quando']:%d/%m/%Y %H:%M:%S}  {e['evento']:<13} {quem:<20} {e.get('ip', '-')}")
