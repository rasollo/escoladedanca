from decimal import Decimal

from django.urls import reverse

from escoladedanca.testutils import LogadoTestCase, criar_professor, criar_turma

from .forms import ProfessorForm
from .models import Professor


class ProfessorTests(LogadoTestCase):
    def test_cadastro(self):
        """RF17 — cadastrar professor."""
        resp = self.client.post(reverse("professores:novo"), {
            "nome": "Rogério Matos", "valor_por_aluno": "3.50", "ativo": "on",
        })
        prof = Professor.objects.get()
        self.assertRedirects(resp, prof.get_absolute_url())
        self.assertEqual(prof.valor_por_aluno, Decimal("3.50"))

    def test_dados_incompletos_revisar(self):
        """Fluxo 02 — dados incompletos voltam para revisão."""
        self.assertFalse(ProfessorForm(data={"nome": "", "valor_por_aluno": "1"}).is_valid())

    def test_valor_negativo_rejeitado(self):
        form = ProfessorForm(data={"nome": "Fulano de Tal", "valor_por_aluno": "-1"})
        self.assertFalse(form.is_valid())

    def test_consulta_e_atualizacao(self):
        """RF17 — consultar e atualizar professor."""
        prof = criar_professor()
        criar_turma(professor=prof)
        resp = self.client.get(reverse("professores:lista"))
        self.assertContains(resp, prof.nome)
        resp = self.client.get(prof.get_absolute_url())
        self.assertContains(resp, "Forró")
        self.client.post(reverse("professores:editar", args=[prof.pk]), {
            "nome": "Camila R. Rocha", "valor_por_aluno": "5.00", "ativo": "on",
        })
        prof.refresh_from_db()
        self.assertEqual(prof.nome, "Camila R. Rocha")
        self.assertEqual(prof.valor_por_aluno, Decimal("5.00"))

    def test_busca(self):
        criar_professor("Juliana Prado")
        criar_professor("Marcos Vieira")
        resp = self.client.get(reverse("professores:lista"), {"q": "juli"})
        self.assertContains(resp, "Juliana Prado")
        self.assertNotContains(resp, "Marcos Vieira")
