from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from alunos.models import Aluno
from aulas.models import Presenca, Turma
from escoladedanca.testutils import LogadoTestCase, entrada, saida, senha_aleatoria
from financeiro.models import Movimentacao

PAGINAS_PROTEGIDAS = [
    "index", "alunos:lista", "alunos:novo", "professores:lista", "aulas:agenda",
    "aulas:presencas", "aulas:modalidades", "financeiro:painel", "financeiro:movimentacoes",
    "financeiro:saldo", "financeiro:balanco", "financeiro:mensalidades",
    "financeiro:nova_entrada", "financeiro:salarios", "administradores:administradores",
    "proprietarios:proprietarios",
]


class SegurancaTests(TestCase):
    def test_paginas_exigem_login(self):
        """RNF03 / RNF04 — dados administrativos, financeiros e pessoais protegidos."""
        for nome in PAGINAS_PROTEGIDAS:
            with self.subTest(pagina=nome):
                resp = self.client.get(reverse(nome))
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(resp.url.startswith(reverse("login")))

    def test_login_e_logout(self):
        senha = senha_aleatoria()
        get_user_model().objects.create_user("resp", password=senha)
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        resp = self.client.post(reverse("login"), {"username": "resp", "password": senha_aleatoria()})
        self.assertContains(resp, "Usuário ou senha inválidos")
        resp = self.client.post(reverse("login"), {"username": "resp", "password": senha})
        self.assertRedirects(resp, reverse("index"))
        self.assertEqual(self.client.get(reverse("alunos:lista")).status_code, 200)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("alunos:lista")).status_code, 302)

    def test_post_sem_csrf_e_rejeitado(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.force_login(get_user_model().objects.create_user("resp"))
        self.assertEqual(c.post(reverse("alunos:novo"), {"nome": "Teste"}).status_code, 403)


class PaginasTests(LogadoTestCase):
    def test_todas_as_paginas_carregam(self):
        """RNF01 / RNF02 — navegação básica sem erros."""
        for nome in PAGINAS_PROTEGIDAS:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)

    def test_painel_inicial_resumo(self):
        entrada("100.00")
        saida("30.00")
        resp = self.client.get(reverse("index"))
        self.assertContains(resp, "R$ 70,00")

    def test_administracao_lista_usuarios(self):
        resp = self.client.get(reverse("administradores:administradores"))
        self.assertContains(resp, "responsavel")


class PopularDemoTests(TestCase):
    def test_comando_cria_dados_validos(self):
        call_command("popular_demo", verbosity=0, stdout=open("/dev/null", "w"))
        self.assertTrue(get_user_model().objects.filter(username="responsavel").exists())
        self.assertEqual(Aluno.objects.count(), 60)
        self.assertEqual(Turma.objects.count(), 10)
        self.assertTrue(Presenca.objects.exists())
        # RNF05 — todos os dados gerados respeitam as regras do modelo
        for obj in list(Turma.objects.all()) + list(Movimentacao.objects.all()):
            obj.full_clean()
        for t in Turma.objects.all():
            self.assertLessEqual(t.quantidade_alunos(), t.capacidade)

    def test_senha_vem_do_ambiente_ou_e_aleatoria(self):
        import io
        import os
        from unittest import mock
        senha = senha_aleatoria()
        with mock.patch.dict(os.environ, {"DJANGO_DEMO_SENHA": senha}):
            call_command("popular_demo", usuario="demo1", stdout=io.StringIO())
        self.assertTrue(get_user_model().objects.get(username="demo1").check_password(senha))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DJANGO_DEMO_SENHA", None)
            out = io.StringIO()
            call_command("popular_demo", usuario="demo2", stdout=out)
        gerada = out.getvalue().split("demo2 / ")[1].split()[0]
        self.assertGreaterEqual(len(gerada), 12)
        self.assertTrue(get_user_model().objects.get(username="demo2").check_password(gerada))

    def test_comando_idempotente(self):
        out = open("/dev/null", "w")
        call_command("popular_demo", stdout=out)
        call_command("popular_demo", stdout=out)
        self.assertEqual(Aluno.objects.count(), 60)


class DocumentacaoTests(LogadoTestCase):
    def test_documentos_renderizados(self):
        resp = self.client.get(reverse("documentacao"))
        self.assertContains(resp, "<h2>Observações da professora</h2>", html=False)
        self.assertContains(resp, "DJANGO_DEMO_SENHA")
        resp = self.client.get(reverse("documentacao_doc", args=["analise"]))
        self.assertContains(resp, "<table>")
        self.assertContains(resp, "Rastreabilidade")

    def test_slug_desconhecido_404(self):
        for slug in ["nao-existe", "settings", "RESUMO"]:
            self.assertEqual(self.client.get(f"/documentacao/{slug}/").status_code, 404)

    def test_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("documentacao")).status_code, 302)


class MarkdownSimplesTests(TestCase):
    def test_elementos(self):
        from escoladedanca.markdown_simples import converter
        out = converter("# T\n\nTexto **forte** e `x<y`.\n\n- a\n  - b\n- c\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```\n<pre>\n```")
        self.assertIn("<h1>T</h1>", out)
        self.assertIn("<strong>forte</strong>", out)
        self.assertIn("<code>x&lt;y</code>", out)
        self.assertEqual(out.count("<ul>"), 2)
        self.assertEqual(out.count("<ul>"), out.count("</ul>"))
        self.assertIn("<td>1</td><td>2</td>", out)
        self.assertIn("&lt;pre&gt;", out)

    def test_escapa_html_e_bloqueia_javascript(self):
        from escoladedanca.markdown_simples import converter
        out = converter('<script>alert(1)</script> [x](javascript:alert(1)) [ok](https://a.b)')
        self.assertNotIn("<script>", out)
        self.assertNotIn('href="javascript', out)
        self.assertIn('<a href="https://a.b">ok</a>', out)


class AuditoriaTests(TestCase):
    """RNF03 / RNF04 — trilha de auditoria de acessos e alterações."""

    def setUp(self):
        self.senha = senha_aleatoria()
        self.user = get_user_model().objects.create_user("resp", password=self.senha)

    def test_login_ok_falha_e_logout_com_ip(self):
        with self.assertLogs("auditoria.acesso", "INFO") as cm:
            self.client.post(reverse("login"), {"username": "resp", "password": senha_aleatoria()},
                             REMOTE_ADDR="10.0.0.7")
            self.client.post(reverse("login"), {"username": "resp", "password": self.senha},
                             REMOTE_ADDR="10.0.0.7")
            self.client.post(reverse("logout"), REMOTE_ADDR="10.0.0.7")
        log = "\n".join(cm.output)
        self.assertIn("LOGIN_FALHOU | usuario_informado=resp | ip=10.0.0.7", log)
        self.assertIn("LOGIN_OK | usuario=resp | ip=10.0.0.7", log)
        self.assertIn("LOGOUT | usuario=resp | ip=10.0.0.7", log)
        self.assertNotIn(self.senha, log)

    def test_requisicoes_registradas_sem_estaticos(self):
        self.client.force_login(self.user)
        with self.assertLogs("auditoria.acesso", "INFO") as cm:
            self.client.get(reverse("alunos:lista"), REMOTE_ADDR="10.0.0.8")
            self.client.get("/static/css/dashboard.css")
        self.assertEqual(len(cm.output), 1)
        self.assertIn("usuario=resp | ip=10.0.0.8 | metodo=GET | caminho=/alunos/ | status=200",
                      cm.output[0])

    def test_alteracao_de_dados_registra_autor(self):
        from alunos.models import Aluno
        self.client.force_login(self.user)
        with self.assertLogs("auditoria.dados", "INFO") as cm:
            self.client.post(reverse("alunos:novo"), {"nome": "Ana Silva", "ativo": "on"},
                             REMOTE_ADDR="10.0.0.9")
        aluno = Aluno.objects.get()
        self.assertIn(f"CRIADO | modelo=alunos.Aluno | id={aluno.pk} | usuario=resp | ip=10.0.0.9",
                      "\n".join(cm.output))
        # o nome do aluno (dado pessoal) não vai para o log
        self.assertNotIn("Ana Silva", "\n".join(cm.output))

    def test_exclusao_e_vinculo(self):
        from escoladedanca.testutils import criar_aluno, criar_turma
        turma, aluno = criar_turma(), criar_aluno()
        vazia = criar_turma(dia=3)
        turma_id = turma.pk
        with self.assertLogs("auditoria.dados", "INFO") as cm:
            turma.alunos.add(aluno)
            vazia.delete()
        log = "\n".join(cm.output)
        self.assertIn(f"VINCULO_ADD | modelo=aulas.Turma | id={turma_id} | alunos={aluno.pk} | usuario=sistema", log)
        self.assertIn("EXCLUIDO | modelo=aulas.Turma", log)

    def test_injecao_de_linhas_neutralizada(self):
        with self.assertLogs("auditoria.acesso", "INFO") as cm:
            self.client.post(reverse("login"), {"username": "x\n2026-01-01 | LOGIN_OK | usuario=admin",
                                                "password": senha_aleatoria()})
        self.assertNotIn("\n", cm.output[0])
        self.assertEqual(cm.output[0].count(" | "), 2)

    def test_resumo_e_relatorio(self):
        import io
        import tempfile
        from pathlib import Path

        from django.test import override_settings

        from escoladedanca.auditoria import resumo_acessos
        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "acessos.log.2026-11-08").write_text(
                "2026-11-08 20:00:00 | LOGIN_OK | usuario=ana | ip=10.0.0.1\n", encoding="utf-8")
            Path(pasta, "acessos.log").write_text(
                "2026-11-09 19:00:00 | LOGIN_FALHOU | usuario_informado=bob | ip=10.0.0.2\n"
                "2026-11-09 19:01:00 | LOGIN_OK | usuario=ana | ip=10.0.0.3\n"
                "2026-11-09 19:01:01 | REQUISICAO | usuario=ana | ip=10.0.0.3 | metodo=GET | caminho=/ | status=200\n"
                "linha quebrada\n", encoding="utf-8")
            with override_settings(LOGS_DIR=Path(pasta)):
                r = resumo_acessos()
                out = io.StringIO()
                call_command("relatorio_acessos", "--dias", "100000", "--eventos", stdout=out)
        self.assertEqual(r["total_usuarios"], 1)  # bob só falhou, não acessou
        self.assertEqual(r["total_logins"], 2)
        self.assertEqual(r["total_falhas"], 1)
        self.assertEqual(r["total_ips"], 3)
        ana = next(u for u in r["usuarios"] if u["usuario"] == "ana")
        self.assertEqual(ana["ips"], {"10.0.0.1", "10.0.0.3"})
        self.assertIn("Usuários que acessaram: 1", out.getvalue())
        self.assertIn("LOGIN_FALHOU", out.getvalue())

    def test_tela_de_auditoria_so_para_equipe(self):
        import tempfile
        from datetime import datetime
        from pathlib import Path

        from django.test import override_settings
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "acessos.log").write_text(
                f"{agora} | LOGIN_FALHOU | usuario_informado=intruso | ip=10.0.0.66\n"
                f"{agora} | LOGIN_OK | usuario=resp | ip=10.0.0.7\n"
                f"{agora} | LOGOUT | usuario=resp | ip=10.0.0.7\n", encoding="utf-8")
            Path(pasta, "auditoria.log").write_text(
                f"{agora} | CRIADO | modelo=alunos.Aluno | id=5 | usuario=resp | ip=10.0.0.7\n",
                encoding="utf-8")
            with override_settings(LOGS_DIR=Path(pasta)):
                self.client.force_login(self.user)
                resp = self.client.get(reverse("administradores:administradores"))
                self.assertNotContains(resp, "Quem acessou o sistema")
                self.assertNotContains(resp, "10.0.0.66")
                self.user.is_staff = True
                self.user.save()
                resp = self.client.get(reverse("administradores:administradores"))
        self.assertContains(resp, "Quem acessou o sistema")
        self.assertContains(resp, "intruso")  # falha de login mostra o usuário digitado
        self.assertContains(resp, "alunos.Aluno #5")
