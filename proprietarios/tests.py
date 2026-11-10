from datetime import date

from django.urls import reverse
from django.utils import timezone

from escoladedanca.testutils import LogadoTestCase, entrada, saida


class ProprietarioTests(LogadoTestCase):
    def test_resultado_ultimos_seis_meses(self):
        """RF15 / RF16 — visão consolidada para o proprietário."""
        hoje = timezone.localdate()
        entrada("500.00", data=hoje)
        saida("200.00", data=hoje)
        resp = self.client.get(reverse("proprietarios:proprietarios"))
        self.assertEqual(len(resp.context["meses"]), 6)
        atual = resp.context["meses"][0]
        self.assertEqual((atual.ano, atual.mes), (hoje.year, hoje.month))
        self.assertContains(resp, "R$ 300,00")

    def test_virada_de_ano(self):
        resp = self.client.get(reverse("proprietarios:proprietarios"))
        meses = [(b.ano, b.mes) for b in resp.context["meses"]]
        self.assertEqual(len(set(meses)), 6)
        for ano, mes in meses:
            date(ano, mes, 1)
