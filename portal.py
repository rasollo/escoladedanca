#!/usr/bin/env python3
"""Portal da Dança — instalação e execução em um comando (Windows, macOS e Linux).

Requer apenas o Python 3.12 ou mais novo. Uso, na pasta do projeto:

    Windows:        py portal.py instalar      (ou: python portal.py instalar)
    macOS / Linux:  python3 portal.py instalar

Comandos:
    instalar   cria o ambiente (.venv), instala as dependências, cria o banco,
               carrega os dados de demonstração e prepara os arquivos de estilo
    iniciar    abre o sistema em http://127.0.0.1:8000/
    testar     roda a suíte de testes automatizados
    senha      troca a senha de um usuário (padrão: responsavel)

Pode ser executado mais de uma vez: o que já está pronto não é refeito, e os
dados de demonstração não são duplicados.
"""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

PASTA = Path(__file__).resolve().parent
VENV = PASTA / ".venv"
PYTHON_MINIMO = (3, 12)  # exigido pelo Django 6.1


def python_do_venv() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def passo(texto):
    print(f"\n==> {texto}", flush=True)


def erro(texto, codigo=1):
    print(f"\nERRO: {texto}", file=sys.stderr)
    sys.exit(codigo)


def rodar(*args, **kw):
    """Roda um comando e encerra com mensagem clara se ele falhar."""
    resultado = subprocess.run([str(a) for a in args], cwd=PASTA, **kw)
    if resultado.returncode != 0:
        erro(f"o comando falhou: {' '.join(str(a) for a in args)}", resultado.returncode)
    return resultado


def manage(*args):
    return rodar(python_do_venv(), "manage.py", *args)


def exigir_instalacao():
    if not python_do_venv().exists():
        erro("o sistema ainda não foi instalado. Rode primeiro o comando 'instalar'.")


def comando_python():
    return "py" if os.name == "nt" else "python3"


# ---------------------------------------------------------------- comandos
def instalar(args):
    if sys.version_info < PYTHON_MINIMO:
        erro(f"é preciso o Python {'.'.join(map(str, PYTHON_MINIMO))} ou mais novo "
             f"(este é o {sys.version.split()[0]}). Baixe em https://www.python.org/downloads/")

    if python_do_venv().exists():
        passo("Ambiente Python (.venv) já existe")
    else:
        passo("Criando o ambiente Python (.venv)")
        try:
            venv.EnvBuilder(with_pip=True).create(VENV)
        except Exception as exc:  # noqa: BLE001 — mensagem amigável para o usuário
            dica = ""
            if sys.platform.startswith("linux"):
                v = f"{sys.version_info.major}.{sys.version_info.minor}"
                dica = (f"\nNo Ubuntu/Debian, instale o módulo venv e tente de novo:\n"
                        f"    sudo apt install python{v}-venv")
            erro(f"não foi possível criar o ambiente: {exc}{dica}")

    passo("Instalando as dependências (requirements.txt)")
    rodar(python_do_venv(), "-m", "pip", "install", "--disable-pip-version-check", "-q",
          "-r", "requirements.txt")

    passo("Criando/atualizando o banco de dados")
    manage("migrate", "--noinput")

    if args.sem_demo:
        passo("Dados de demonstração não carregados (--sem-demo)")
        print("    Crie um usuário com:  " + comando_python() + " portal.py senha --novo")
    else:
        passo("Carregando os dados de demonstração")
        extra = ["--senha", args.senha] if args.senha else []
        manage("popular_demo", *extra)

    passo("Preparando os arquivos de estilo")
    manage("collectstatic", "--noinput", "-v", "0")

    print(f"""
Instalação concluída.

Para abrir o sistema:   {comando_python()} portal.py iniciar
Depois acesse:          http://127.0.0.1:8000/
Usuário:                responsavel  (a senha aparece acima, na criação do usuário)
Esqueceu a senha?       {comando_python()} portal.py senha""")


def iniciar(args):
    exigir_instalacao()
    host = "0.0.0.0" if args.rede else "127.0.0.1"
    print(f"\nPortal da Dança rodando em http://127.0.0.1:{args.porta}/")
    if args.rede:
        print(f"Outras máquinas da rede acessam pelo IP deste computador, porta {args.porta}.")
    print("Para parar, pressione Ctrl+C.\n", flush=True)
    try:
        subprocess.run([str(python_do_venv()), "manage.py", "runserver", f"{host}:{args.porta}"],
                       cwd=PASTA)
    except KeyboardInterrupt:
        print("\nSistema encerrado.")


def testar(args):
    exigir_instalacao()
    manage("test")


def senha(args):
    exigir_instalacao()
    if args.novo:
        manage("createsuperuser")
    else:
        manage("changepassword", args.usuario)


def main():
    parser = argparse.ArgumentParser(
        prog="portal.py", description="Portal da Dança — instalação e execução.",
        epilog=f"Exemplo: {comando_python()} portal.py instalar")
    sub = parser.add_subparsers(dest="comando", metavar="comando")

    p = sub.add_parser("instalar", help="instala tudo e carrega os dados de demonstração")
    p.add_argument("--sem-demo", action="store_true", help="não carrega os dados de demonstração")
    p.add_argument("--senha", help="senha do usuário de demonstração (padrão: gerada e exibida)")
    p.set_defaults(func=instalar)

    p = sub.add_parser("iniciar", help="abre o sistema no navegador local")
    p.add_argument("--porta", type=int, default=8000, help="porta (padrão: 8000)")
    p.add_argument("--rede", action="store_true",
                   help="permite o acesso de outras máquinas da rede")
    p.set_defaults(func=iniciar)

    p = sub.add_parser("testar", help="roda os testes automatizados")
    p.set_defaults(func=testar)

    p = sub.add_parser("senha", help="troca a senha de um usuário")
    p.add_argument("--usuario", default="responsavel", help="padrão: responsavel")
    p.add_argument("--novo", action="store_true", help="cria um novo usuário administrador")
    p.set_defaults(func=senha)

    args = parser.parse_args()
    if not args.comando:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
