"""RF26 — aniversariantes do mês para Administrativo, Professor e Aluno."""
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alunos.models import Aluno
from escoladedanca.aniversarios import aniversariantes
from escoladedanca.rbac import ALUNO, PROFESSOR
from escoladedanca.testutils import criar_aluno, criar_professor, criar_usuario
from professores.models import Professor

HOJE = date(2026, 11, 22)


class AniversariantesTests(TestCase):
    def setUp(self):
        criar_aluno("Ana Hoje", data_nascimento=date(1995, 11, 22))
        criar_aluno("Bruno Começo", data_nascimento=date(2001, 11, 3))
        criar_aluno("Carla Dezembro", data_nascimento=date(1990, 12, 1))
        criar_aluno("Diego Sem Data")
        criar_aluno("Eva Inativa", data_nascimento=date(1999, 11, 10), ativo=False)
        criar_professor("Fábio Professor", data_nascimento=date(1980, 11, 15))

    def test_idade_so_quando_pedida(self):
        self.assertIsNone(aniversariantes(11, HOJE)[0]["idade"])
        self.assertEqual(aniversariantes(11, HOJE, com_idade=True)[0]["idade"], 25)  # 2001 → 2026

    def test_lista_do_mes_ordenada_por_dia(self):
        lista = aniversariantes(11, HOJE)
        self.assertEqual([p["nome"] for p in lista],
                         ["Bruno Começo", "Fábio Professor", "Ana Hoje"])
        self.assertEqual([p["perfil"] for p in lista], ["Aluno", "Professor", "Aluno"])
        self.assertTrue(lista[2]["hoje"])
        self.assertFalse(lista[0]["hoje"])

    def test_todos_os_papeis_veem_a_tela(self):
        aluno_user = criar_usuario("ana", papel=ALUNO)
        Aluno.objects.filter(nome="Ana Hoje").update(usuario=aluno_user)
        prof_user = criar_usuario("fabio", papel=PROFESSOR)
        Professor.objects.filter(nome="Fábio Professor").update(usuario=prof_user)
        ano = timezone.localdate().year
        for user in (criar_usuario("adm"), prof_user, aluno_user):
            with self.subTest(usuario=user.username):
                self.client.force_login(user)
                resp = self.client.get(reverse("aniversariantes"), {"mes": 11})
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, "Bruno Começo")
                self.assertContains(resp, "03/11")
                self.assertNotContains(resp, "2001")  # ano de nascimento nunca aparece
                self.assertNotContains(resp, "Diego Sem Data")
                self.assertNotContains(resp, "Eva Inativa")
                idade = f"completa {ano - 2001} anos"
                if user == aluno_user:  # aluno não vê a idade, nem no contexto
                    self.assertNotContains(resp, "completa ")
                    self.assertTrue(all(p["idade"] is None for p in resp.context["lista"]))
                else:
                    self.assertContains(resp, idade)

    def test_quadro_nos_paineis_iniciais(self):
        aluno_user = criar_usuario("ana", papel=ALUNO)
        Aluno.objects.filter(nome="Ana Hoje").update(usuario=aluno_user)
        prof_user = criar_usuario("fabio", papel=PROFESSOR)
        Professor.objects.filter(nome="Fábio Professor").update(usuario=prof_user)
        paginas = [(criar_usuario("adm"), "index"), (prof_user, "professores:minha_area"),
                   (aluno_user, "alunos:minha_area")]
        with mock.patch("django.utils.timezone.localdate", return_value=HOJE):
            for user, pagina in paginas:
                with self.subTest(pagina=pagina):
                    self.client.force_login(user)
                    resp = self.client.get(reverse(pagina))
                    self.assertContains(resp, "Aniversariantes de novembro")
                    self.assertContains(resp, "Hoje! · 22/11")
                    if pagina == "alunos:minha_area":
                        self.assertNotContains(resp, " anos</small>")
                    else:
                        self.assertContains(resp, "completa 31 anos")  # Ana: 1995 → 2026

    def test_mes_invalido_volta_para_o_atual(self):
        self.client.force_login(criar_usuario("adm"))
        for valor in ("13", "abc", "0"):
            self.assertEqual(self.client.get(reverse("aniversariantes"), {"mes": valor}).status_code, 200)

    def test_data_de_nascimento_opcional_e_nao_futura(self):
        self.client.force_login(criar_usuario("adm"))
        self.client.post(reverse("alunos:novo"), {"nome": "Sem Data", "ativo": "on"})
        self.assertTrue(Aluno.objects.filter(nome="Sem Data", data_nascimento__isnull=True).exists())
        amanha = timezone.localdate() + timedelta(days=1)
        resp = self.client.post(reverse("alunos:novo"), {
            "nome": "Do Futuro", "data_nascimento": amanha.strftime("%d/%m/%Y"), "ativo": "on"})
        self.assertContains(resp, "não pode estar no futuro")
        resp = self.client.post(reverse("professores:novo"), {
            "nome": "Prof Novo", "data_nascimento": "15/11/1985", "valor_por_aluno": "20", "ativo": "on"})
        self.assertEqual(Professor.objects.get(nome="Prof Novo").data_nascimento, date(1985, 11, 15))


class DemoAniversariosTests(TestCase):
    def test_demo_tem_aniversariantes_no_mes(self):
        call_command("popular_demo", "--senha", "x" * 20, stdout=StringIO())
        hoje = timezone.localdate()
        lista = aniversariantes(hoje.month, hoje)
        self.assertGreaterEqual(len(lista), 6)
        self.assertTrue(any(p["perfil"] == "Professor" for p in lista))
        self.assertTrue(any(p["hoje"] for p in lista))
        self.assertTrue(Aluno.objects.filter(data_nascimento__isnull=True).exists())  # opcional

    def test_demo_cria_acessos_de_professor_e_aluno(self):
        from django.contrib.auth import authenticate
        from escoladedanca.rbac import papel_do
        call_command("popular_demo", "--senha", "senha-de-teste-123", stdout=StringIO())
        prof = Professor.objects.exclude(usuario=None).get()
        aluno = Aluno.objects.exclude(usuario=None).get()
        self.assertEqual(papel_do(prof.usuario), PROFESSOR)
        self.assertEqual(papel_do(aluno.usuario), ALUNO)
        self.assertEqual(aluno.data_nascimento.month, timezone.localdate().month)
        self.assertIsNotNone(authenticate(username=aluno.usuario.username, password="senha-de-teste-123"))
        self.assertTrue(aluno.usuario.username.isascii())

    def test_reinstalar_completa_so_os_dados_de_demonstracao(self):
        call_command("popular_demo", "--senha", "x" * 20, stdout=StringIO())
        Aluno.objects.update(data_nascimento=None)
        Professor.objects.update(data_nascimento=None)
        real = criar_aluno("Aluno Real", email="real@escola.com.br")
        call_command("popular_demo", stdout=StringIO())
        real.refresh_from_db()
        self.assertIsNone(real.data_nascimento)
        self.assertTrue(Aluno.objects.filter(email__endswith="@exemplo.com",
                                             data_nascimento__isnull=False).exists())
        self.assertFalse(Professor.objects.filter(data_nascimento__isnull=True).exists())
