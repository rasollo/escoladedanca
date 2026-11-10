from datetime import timedelta

from django.urls import reverse

from escoladedanca.testutils import (SEGUNDA, LogadoTestCase, criar_aluno, criar_presenca,
                                     criar_turma, entrada)

from .forms import AlunoForm
from .models import Aluno


class AlunoModelTests(LogadoTestCase):
    def test_situacao_mensalidade_informativa(self):
        """RF11 / RN08 — situação da mensalidade é calculada pela validade."""
        aluno = criar_aluno()
        self.assertFalse(aluno.mensalidade_em_dia(SEGUNDA))
        entrada(origem="mensalidade", aluno=aluno, validade=SEGUNDA + timedelta(days=30))
        self.assertTrue(aluno.mensalidade_em_dia(SEGUNDA))
        self.assertFalse(aluno.mensalidade_em_dia(SEGUNDA + timedelta(days=31)))

    def test_contagem_presencas_e_faltas(self):
        """RF03 / RF04 — totais por aluno."""
        aluno, turma = criar_aluno(), criar_turma()
        criar_presenca(turma, aluno, SEGUNDA, True)
        criar_presenca(turma, aluno, SEGUNDA + timedelta(days=7), False)
        criar_presenca(turma, aluno, SEGUNDA + timedelta(days=14), True)
        self.assertEqual(aluno.total_presencas(), 2)
        self.assertEqual(aluno.total_faltas(), 1)


class AlunoFormTests(LogadoTestCase):
    def test_nome_obrigatorio(self):
        """Fluxo 01 — dados obrigatórios não informados → solicitar correção."""
        form = AlunoForm(data={"nome": "", "ativo": True})
        self.assertFalse(form.is_valid())
        self.assertIn("nome", form.errors)

    def test_nome_curto_rejeitado_e_espacos_normalizados(self):
        self.assertFalse(AlunoForm(data={"nome": "Al"}).is_valid())
        form = AlunoForm(data={"nome": "  Maria   Eduarda  ", "ativo": True})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["nome"], "Maria Eduarda")

    def test_email_invalido(self):
        self.assertFalse(AlunoForm(data={"nome": "Maria", "email": "nao-e-email"}).is_valid())


class AlunoViewTests(LogadoTestCase):
    def test_cadastro_de_aluno(self):
        """RF01 — cadastro de alunos."""
        resp = self.client.post(reverse("alunos:novo"), {
            "nome": "Bruno Santos", "telefone": "(13) 99999-0000", "ativo": "on",
        })
        aluno = Aluno.objects.get(nome="Bruno Santos")
        self.assertRedirects(resp, aluno.get_absolute_url())

    def test_cadastro_invalido_nao_salva(self):
        """Fluxo 01 — dados inválidos não são cadastrados (correção do fluxograma)."""
        resp = self.client.post(reverse("alunos:novo"), {"nome": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Aluno.objects.exists())

    def test_consulta_e_busca(self):
        """RF02 — consulta dos alunos cadastrados com busca."""
        criar_aluno("Carla Lima")
        criar_aluno("Diego Costa")
        resp = self.client.get(reverse("alunos:lista"), {"q": "carla"})
        self.assertContains(resp, "Carla Lima")
        self.assertNotContains(resp, "Diego Costa")

    def test_filtro_inativos(self):
        criar_aluno("Ativo Um")
        criar_aluno("Inativo Dois", ativo=False)
        resp = self.client.get(reverse("alunos:lista"))
        self.assertNotContains(resp, "Inativo Dois")
        resp = self.client.get(reverse("alunos:lista"), {"status": "inativos"})
        self.assertContains(resp, "Inativo Dois")
        self.assertNotContains(resp, "Ativo Um")

    def test_detalhe_e_edicao(self):
        aluno = criar_aluno()
        self.assertContains(self.client.get(aluno.get_absolute_url()), aluno.nome)
        self.client.post(reverse("alunos:editar", args=[aluno.pk]), {"nome": "Ana Souza"})
        aluno.refresh_from_db()
        self.assertEqual(aluno.nome, "Ana Souza")
        self.assertFalse(aluno.ativo)  # checkbox não enviado = desativado

    def test_detalhe_inexistente_404(self):
        self.assertEqual(self.client.get(reverse("alunos:detalhe", args=[999])).status_code, 404)
