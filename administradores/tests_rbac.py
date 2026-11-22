"""RF25 — controle de acesso baseado em papéis (RBAC) e datas em dd/mm/aaaa."""
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from aulas.models import Presenca, Turma
from escoladedanca.rbac import ADMINISTRATIVO, ALUNO, PAPEIS, PROFESSOR, papel_do
from escoladedanca.testutils import (SEGUNDA, criar_aluno, criar_presenca, criar_professor,
                                     criar_turma, criar_usuario, entrada, sala, senha_aleatoria)

SO_ADMINISTRATIVO = [
    "alunos:lista", "alunos:novo", "professores:lista", "aulas:modalidades",
    "financeiro:painel", "financeiro:movimentacoes", "financeiro:saldo", "financeiro:balanco",
    "financeiro:mensalidades", "financeiro:nova_entrada", "financeiro:salarios",
    "administradores:administradores", "administradores:usuario_novo",
    "proprietarios:proprietarios", "consultas:painel", "documentacao",
]


class PapeisTests(TestCase):
    def test_grupos_criados_no_migrate(self):
        self.assertEqual(set(Group.objects.values_list("name", flat=True)) & set(PAPEIS),
                         set(PAPEIS))

    def test_superusuario_e_administrativo(self):
        su = get_user_model().objects.create_superuser("su", "", senha_aleatoria())
        self.assertEqual(papel_do(su), ADMINISTRATIVO)

    def test_usuario_sem_papel_e_negado_mas_pode_sair(self):
        user = get_user_model().objects.create_user("semPapel")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("index")).status_code, 403)
        self.assertEqual(self.client.get(reverse("aulas:agenda")).status_code, 403)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("index")).status_code, 302)

    def test_usuario_bloqueado_nao_entra(self):
        senha = senha_aleatoria()
        criar_usuario("bloq", password=senha, is_active=False)
        resp = self.client.post(reverse("login"), {"username": "bloq", "password": senha})
        self.assertEqual(resp.status_code, 200)  # volta ao formulário de login
        self.assertEqual(self.client.get(reverse("index")).status_code, 302)


class AlunoTests(TestCase):
    def setUp(self):
        self.user = criar_usuario("ana", papel=ALUNO)
        self.aluno = criar_aluno("Ana Aluna", usuario=self.user)
        self.outro = criar_aluno("Bruno Outro")
        self.turma = criar_turma()
        self.turma.alunos.add(self.aluno)
        criar_presenca(self.turma, self.aluno)
        criar_presenca(self.turma, self.outro, presente=False)
        entrada("150.00", origem="mensalidade", aluno=self.aluno, validade=date(2099, 1, 1))
        self.client.force_login(self.user)

    def test_inicio_leva_ao_portal_do_aluno(self):
        self.assertRedirects(self.client.get(reverse("index")), reverse("alunos:minha_area"))

    def test_ve_somente_os_proprios_dados(self):
        resp = self.client.get(reverse("alunos:minha_area"))
        self.assertContains(resp, "Ana Aluna")
        self.assertContains(resp, "Em dia")
        self.assertContains(resp, "R$ 150,00")
        self.assertContains(resp, SEGUNDA.strftime("%d/%m/%Y"))
        self.assertNotContains(resp, "Bruno Outro")

    def test_agenda_somente_leitura(self):
        resp = self.client.get(reverse("aulas:agenda"))
        self.assertContains(resp, "Matriculado")
        self.assertNotContains(resp, "Agendar aula")
        self.assertNotContains(resp, reverse("aulas:chamada", args=[self.turma.pk]))

    def test_paginas_administrativas_negadas(self):
        for nome in SO_ADMINISTRATIVO + ["aulas:presencas", "aulas:turma_nova"]:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)
        for nome in ["alunos:detalhe", "aulas:turma_detalhe", "aulas:chamada", "aulas:turma_alunos"]:
            with self.subTest(pagina=nome):
                pk = self.outro.pk if nome.startswith("alunos") else self.turma.pk
                self.assertEqual(self.client.get(reverse(nome, args=[pk])).status_code, 403)

    def test_aluno_sem_cadastro_vinculado(self):
        self.client.force_login(criar_usuario("solto", papel=ALUNO))
        self.assertEqual(self.client.get(reverse("alunos:minha_area")).status_code, 403)


class ProfessorTests(TestCase):
    def setUp(self):
        self.user = criar_usuario("camila", papel=PROFESSOR)
        self.prof = criar_professor("Camila Rocha", usuario=self.user)
        self.outro_prof = criar_professor("Rogério Matos")
        self.minha = criar_turma(professor=self.prof, inicio="19:00", fim="20:00")
        self.alheia = criar_turma(professor=self.outro_prof, inicio="20:00", fim="21:00")
        self.a1 = criar_aluno("Aluno Um")
        self.client.force_login(self.user)

    def _dados_aula(self, **extra):
        dados = {"nome": "Zouk", "modalidade": self.minha.modalidade.pk, "dia_semana": 2,
                 "hora_inicio": "19:00", "hora_fim": "20:00", "sala": self.minha.sala.pk}
        dados.update(extra)
        return dados

    def test_inicio_leva_ao_portal_do_professor(self):
        self.assertRedirects(self.client.get(reverse("index")), reverse("professores:minha_area"))
        resp = self.client.get(reverse("professores:minha_area"))
        self.assertContains(resp, "Camila Rocha")
        self.assertContains(resp, "Salário estimado")

    def test_agenda_aula_sempre_em_seu_nome(self):
        # Mesmo forjando outro professor no POST, a aula fica com o professor logado.
        resp = self.client.post(reverse("aulas:turma_nova"),
                                self._dados_aula(professor=self.outro_prof.pk))
        turma = Turma.objects.get(nome="Zouk")
        self.assertRedirects(resp, turma.get_absolute_url())
        self.assertEqual(turma.professor, self.prof)

    def test_agendamento_respeita_regras(self):
        # RN13 — fora do horário de funcionamento
        resp = self.client.post(reverse("aulas:turma_nova"),
                                self._dados_aula(hora_inicio="17:00", hora_fim="18:30"))
        self.assertContains(resp, "A escola funciona das 18:00 às 22:00")
        # RN14 — choque com a própria aula
        resp = self.client.post(reverse("aulas:turma_nova"), self._dados_aula(
            dia_semana=0, sala=sala("Sala 2").pk))
        self.assertContains(resp, "O professor já tem outra aula neste dia e horário.")
        self.assertFalse(Turma.objects.filter(nome="Zouk").exists())

    def test_lotacao_da_sala_ao_trocar_de_sala(self):
        pequena = sala("Sala P")
        pequena.capacidade = 1
        pequena.save()
        self.minha.alunos.add(self.a1, criar_aluno("Aluno Dois"))
        resp = self.client.post(reverse("aulas:turma_editar", args=[self.minha.pk]),
                                self._dados_aula(dia_semana=0, sala=pequena.pk))
        self.assertContains(resp, "a sala comporta 1")

    def test_vinculo_de_alunos_respeita_lotacao(self):
        self.minha.sala.capacidade = 1
        self.minha.sala.save()
        a2 = criar_aluno("Aluno Dois")
        resp = self.client.post(reverse("aulas:turma_alunos", args=[self.minha.pk]),
                                {"alunos": [self.a1.pk, a2.pk]})
        self.assertContains(resp, "comporta até 1 alunos")
        self.client.post(reverse("aulas:turma_alunos", args=[self.minha.pk]),
                         {"alunos": [self.a1.pk]})
        self.assertEqual(list(self.minha.alunos.all()), [self.a1])

    def test_nao_mexe_em_aula_de_outro_professor(self):
        for nome in ["aulas:turma_detalhe", "aulas:turma_editar", "aulas:turma_alunos",
                     "aulas:chamada"]:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(nome, args=[self.alheia.pk])).status_code, 403)
        resp = self.client.post(reverse("aulas:chamada", args=[self.alheia.pk]),
                                {"data": SEGUNDA.strftime("%d/%m/%Y"), f"aluno_{self.a1.pk}": "P"})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Presenca.objects.exists())

    def test_chamada_da_propria_aula_com_data_brasileira(self):
        self.minha.alunos.add(self.a1)
        url = reverse("aulas:chamada", args=[self.minha.pk])
        resp = self.client.post(url, {"data": SEGUNDA.strftime("%d/%m/%Y"),
                                      f"aluno_{self.a1.pk}": "P"})
        self.assertRedirects(resp, f"{url}?data={SEGUNDA:%d/%m/%Y}")
        self.assertTrue(Presenca.objects.get(aluno=self.a1, data=SEGUNDA).presente)
        resp = self.client.get(url, {"data": SEGUNDA.strftime("%d/%m/%Y")})
        self.assertContains(resp, f'value="{SEGUNDA:%d/%m/%Y}"')

    def test_presencas_somente_das_proprias_aulas(self):
        b = criar_aluno("Aluno Alheio")
        criar_presenca(self.minha, self.a1)
        criar_presenca(self.alheia, b)
        resp = self.client.get(reverse("aulas:presencas"))
        self.assertContains(resp, "Aluno Um")
        self.assertNotContains(resp, "Aluno Alheio")

    def test_paginas_administrativas_negadas(self):
        for nome in SO_ADMINISTRATIVO:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)
        self.assertEqual(self.client.get(
            reverse("aulas:turma_excluir", args=[self.minha.pk])).status_code, 403)
        self.assertEqual(self.client.get(
            reverse("professores:detalhe", args=[self.prof.pk])).status_code, 403)


class GestaoDeAcessosTests(TestCase):
    def setUp(self):
        self.admin = criar_usuario("secretaria")
        self.client.force_login(self.admin)

    def _novo(self, **dados):
        senha = senha_aleatoria()
        base = {"username": "novo", "first_name": "Novo", "email": "",
                "password1": senha, "password2": senha}
        base.update(dados)
        return self.client.post(reverse("administradores:usuario_novo"), base)

    def test_cria_acesso_de_professor_vinculado(self):
        prof = criar_professor("Juliana Prado")
        resp = self._novo(papel=PROFESSOR, professor=prof.pk)
        self.assertRedirects(resp, reverse("administradores:administradores"))
        user = get_user_model().objects.get(username="novo")
        prof.refresh_from_db()
        self.assertEqual(prof.usuario, user)
        self.assertEqual(papel_do(user), PROFESSOR)
        self.assertTrue(user.has_usable_password())

    def test_professor_ou_aluno_exige_vinculo(self):
        resp = self._novo(papel=ALUNO)
        self.assertContains(resp, "Escolha o aluno que vai usar este acesso.")
        resp = self._novo(papel=PROFESSOR)
        self.assertContains(resp, "Escolha o professor que vai usar este acesso.")
        self.assertFalse(get_user_model().objects.filter(username="novo").exists())

    def test_cria_acesso_de_aluno_e_administrativo(self):
        aluno = criar_aluno("Carla Lima")
        self._novo(papel=ALUNO, aluno=aluno.pk)
        aluno.refresh_from_db()
        self.assertEqual(papel_do(aluno.usuario), ALUNO)
        self._novo(username="adm2", papel=ADMINISTRATIVO)
        adm2 = get_user_model().objects.get(username="adm2")
        self.assertEqual(papel_do(adm2), ADMINISTRATIVO)
        self.assertFalse(adm2.is_staff)  # auditoria segue restrita à equipe técnica

    def test_senha_fraca_rejeitada(self):
        resp = self._novo(papel=ADMINISTRATIVO, password1="123", password2="123")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="novo").exists())

    def test_bloquear_e_desbloquear(self):
        user = criar_usuario("alvo", papel=ALUNO)
        url = reverse("administradores:usuario_situacao", args=[user.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.client.post(url)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_nao_bloqueia_a_si_mesmo(self):
        self.client.post(reverse("administradores:usuario_situacao", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_lista_mostra_papel_e_vinculo(self):
        prof = criar_professor("Marcos Vieira", usuario=criar_usuario("marcos", papel=PROFESSOR))
        resp = self.client.get(reverse("administradores:administradores"))
        self.assertContains(resp, "marcos")
        self.assertContains(resp, prof.get_absolute_url())
        self.assertContains(resp, ">Professor<")


class DatasBrasileirasTests(TestCase):
    def setUp(self):
        self.client.force_login(criar_usuario("secretaria"))

    def test_formulario_exibe_dd_mm_aaaa(self):
        resp = self.client.get(reverse("financeiro:nova_entrada"))
        self.assertContains(resp, 'placeholder="dd/mm/aaaa"')
        from django.utils import timezone
        self.assertContains(resp, f'value="{timezone.localdate():%d/%m/%Y}"')

    def test_entrada_aceita_dd_mm_aaaa(self):
        from financeiro.models import Movimentacao
        self.client.post(reverse("financeiro:nova_entrada"), {
            "valor": "25.00", "data_pagamento": "02/11/2026", "origem": "bebidas",
            "forma_pagamento": "pix"})
        self.assertEqual(Movimentacao.objects.get().data_pagamento, date(2026, 11, 2))

    def test_filtro_de_presencas_em_dd_mm_aaaa(self):
        turma = criar_turma()
        criar_presenca(turma, criar_aluno("Dentro"), data=SEGUNDA)
        criar_presenca(turma, criar_aluno("Fora"), data=date(2026, 10, 26))
        resp = self.client.get(reverse("aulas:presencas"),
                               {"inicio": "01/11/2026", "fim": "30/11/2026"})
        self.assertContains(resp, "Dentro")
        self.assertNotContains(resp, "Fora</a>")
        resp = self.client.get(reverse("aulas:presencas"), {"inicio": "31/02/2026"})
        self.assertContains(resp, "Data inválida no filtro.")

    def test_mes_em_mm_aaaa(self):
        entrada("100.00", data=SEGUNDA)
        resp = self.client.get(reverse("financeiro:balanco"), {"mes": "11/2026"})
        self.assertContains(resp, "R$ 100,00")
        self.assertContains(resp, 'value="11/2026"')
        prof = criar_professor()
        resp = self.client.get(reverse("financeiro:salarios"), {"professor": prof.pk, "mes": "11/2026"})
        self.assertIsNotNone(resp.context["calculo"])
        resp = self.client.get(reverse("financeiro:salarios"), {"professor": prof.pk, "mes": "13/2026"})
        self.assertContains(resp, "Informe o mês no formato mm/aaaa.")
