"""Cobranças de mensalidade: geração, recebimento parcial, estorno e situação."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from aulas.models import Matricula
from escoladedanca.rbac import ALUNO, PROFESSOR
from escoladedanca.testutils import (LogadoTestCase, criar_aluno, criar_professor, criar_turma,
                                     criar_usuario)

from .models import Cobranca, Movimentacao
from .services import calcular_saldo, estornar, gerar_cobrancas, receber, vencimento_da

NOV = date(2026, 11, 1)


def turma_com_valor(valor="120.00", **kw):
    t = criar_turma(**kw)
    t.valor_mensal = Decimal(valor)
    t.save()
    return t


class MatriculaValorTests(TestCase):
    def test_matricula_copia_o_valor_da_aula(self):
        turma = turma_com_valor("120.00")
        turma.alunos.add(criar_aluno())
        m = Matricula.objects.get()
        self.assertEqual(m.valor_mensal, Decimal("120.00"))
        turma.valor_mensal = Decimal("200.00")  # reajuste não muda matrícula feita
        turma.save()
        m.refresh_from_db()
        self.assertEqual(m.valor_final, Decimal("120.00"))

    def test_descontos(self):
        m = Matricula(valor_mensal=Decimal("150.00"))
        m.desconto_tipo, m.desconto = "percentual", Decimal("10")
        self.assertEqual(m.valor_final, Decimal("135.00"))
        m.desconto_tipo, m.desconto = "fixo", Decimal("30")
        self.assertEqual(m.valor_final, Decimal("120.00"))
        m.desconto_tipo, m.desconto = "percentual", Decimal("120")
        with self.assertRaises(ValidationError):
            m.clean()
        m.desconto_tipo, m.desconto = "fixo", Decimal("151")
        with self.assertRaises(ValidationError):
            m.clean()


class GerarCobrancasTests(TestCase):
    def setUp(self):
        self.turma = turma_com_valor("100.00")
        self.a1, self.a2 = criar_aluno("Ana"), criar_aluno("Bia")
        self.turma.alunos.add(self.a1, self.a2)

    def test_gera_uma_por_matricula_e_nao_duplica(self):
        self.assertEqual(gerar_cobrancas(NOV), 2)
        self.assertEqual(gerar_cobrancas(NOV), 0)
        c = Cobranca.objects.first()
        self.assertEqual(c.vencimento, date(2026, 11, 5))
        self.assertEqual(c.valor, Decimal("100.00"))
        self.assertEqual(calcular_saldo()["saldo"], 0)  # cobrança não mexe no caixa

    def test_respeita_desconto_e_ignora_sem_valor_ou_aula_inativa(self):
        m = Matricula.objects.get(aluno=self.a1)
        m.desconto_tipo, m.desconto = "fixo", Decimal("100.00")  # 100% de desconto
        m.save()
        gratis = criar_turma(dia=1, professor=criar_professor("P2"))  # valor 0
        gratis.alunos.add(criar_aluno("Caio"))
        inativa = turma_com_valor("90.00", dia=2, professor=criar_professor("P3"))
        inativa.alunos.add(criar_aluno("Davi"))
        inativa.ativa = False
        inativa.save()
        self.assertEqual(gerar_cobrancas(NOV), 1)
        self.assertEqual(Cobranca.objects.get().aluno, self.a2)

    def test_vencimento_no_fim_de_mes_curto(self):
        with self.settings(ESCOLA_DIA_VENCIMENTO=31):
            self.assertEqual(vencimento_da(date(2026, 2, 1)), date(2026, 2, 28))


class RecebimentoEstornoTests(TestCase):
    def setUp(self):
        turma = turma_com_valor("100.00")
        self.aluno = criar_aluno("Ana")
        turma.alunos.add(self.aluno)
        gerar_cobrancas(NOV)
        self.c = Cobranca.objects.get()

    def test_situacoes(self):
        self.assertEqual(self.c.situacao(date(2026, 11, 3)), "pendente")
        self.assertEqual(self.c.situacao(date(2026, 11, 6)), "atrasada")
        receber(self.c, Decimal("40.00"), date(2026, 11, 6), "pix")
        self.assertEqual(self.c.situacao(date(2026, 11, 6)), "parcial")
        self.assertEqual(self.c.saldo, Decimal("60.00"))
        receber(self.c, Decimal("60.00"), date(2026, 11, 7), "dinheiro")
        self.assertEqual(self.c.situacao(), "paga")
        self.assertEqual(calcular_saldo()["saldo"], Decimal("100.00"))

    def test_nao_recebe_acima_do_saldo(self):
        with self.assertRaises(ValueError):
            receber(self.c, Decimal("100.01"), date(2026, 11, 3), "pix")
        with self.assertRaises(ValueError):
            receber(self.c, Decimal("0"), date(2026, 11, 3), "pix")

    def test_estorno_exige_motivo_e_devolve_o_saldo(self):
        r = receber(self.c, Decimal("100.00"), date(2026, 11, 3), "pix")
        with self.assertRaises(ValueError):
            estornar(r, "   ")
        saida = estornar(r, "Pagamento em duplicidade")
        self.assertEqual((saida.tipo, saida.categoria, saida.valor), ("saida", "estorno", Decimal("100.00")))
        self.assertEqual(self.c.saldo, Decimal("100.00"))
        self.assertEqual(calcular_saldo()["saldo"], 0)  # entrada + estorno se anulam
        r.refresh_from_db()
        with self.assertRaises(ValueError):
            estornar(r, "de novo")

    def test_estorno_avulso_nao_e_permitido(self):
        m = Movimentacao(tipo="saida", categoria="estorno", valor=Decimal("10"),
                         data_pagamento=NOV)
        with self.assertRaises(ValidationError):
            m.full_clean()


class CobrancaTelasTests(LogadoTestCase):
    def setUp(self):
        super().setUp()
        turma = turma_com_valor("100.00")
        self.aluno = criar_aluno("Ana Cobrada")
        turma.alunos.add(self.aluno)

    def test_gerar_receber_estornar_pela_tela(self):
        resp = self.client.post(reverse("financeiro:gerar_cobrancas"), {"mes": "11/2026"})
        self.assertRedirects(resp, f"{reverse('financeiro:mensalidades')}?mes=11/2026")
        c = Cobranca.objects.get()
        resp = self.client.get(reverse("financeiro:mensalidades"), {"mes": "11/2026"})
        self.assertContains(resp, "Ana Cobrada")
        # recebimento acima do saldo é recusado
        resp = self.client.post(reverse("financeiro:cobranca", args=[c.pk]), {
            "valor": "150.00", "data_pagamento": "03/11/2026", "forma_pagamento": "pix"})
        self.assertContains(resp, "não pode ser maior que o saldo")
        self.client.post(reverse("financeiro:cobranca", args=[c.pk]), {
            "valor": "100.00", "data_pagamento": "03/11/2026", "forma_pagamento": "pix"})
        r = c.recebimentos.get()
        # recebimento de cobrança não é editado nem excluído: corrige-se por estorno
        resp = self.client.get(reverse("financeiro:editar", args=[r.pk]))
        self.assertRedirects(resp, reverse("financeiro:cobranca", args=[c.pk]))
        self.client.post(reverse("financeiro:excluir", args=[r.pk]))
        self.assertTrue(Movimentacao.objects.filter(pk=r.pk).exists())
        self.client.post(reverse("financeiro:estornar", args=[r.pk]), {"motivo": "Valor errado"})
        self.assertTrue(Movimentacao.objects.filter(estorno_de=r).exists())

    def test_cancelar_so_sem_recebimento(self):
        gerar_cobrancas(NOV)
        c = Cobranca.objects.get()
        receber(c, Decimal("10.00"), date(2026, 11, 3), "pix")
        self.client.post(reverse("financeiro:cancelar_cobranca", args=[c.pk]), {"motivo": "x"})
        c.refresh_from_db()
        self.assertFalse(c.cancelada)
        estornar(c.recebimentos.get(), "devolvido")
        self.client.post(reverse("financeiro:cancelar_cobranca", args=[c.pk]), {"motivo": "Aluno saiu"})
        c.refresh_from_db()
        self.assertTrue(c.cancelada)
        self.assertEqual(c.situacao(), "cancelada")

    def test_desconto_pela_tela(self):
        m = Matricula.objects.get()
        self.client.post(reverse("aulas:matricula_editar", args=[m.pk]), {
            "valor_mensal": "100.00", "desconto_tipo": "percentual", "desconto": "15"})
        m.refresh_from_db()
        self.assertEqual(m.valor_final, Decimal("85.00"))
        gerar_cobrancas(NOV)
        self.assertEqual(Cobranca.objects.get().valor, Decimal("85.00"))


class CobrancaPapeisTests(TestCase):
    def setUp(self):
        turma = turma_com_valor("100.00")
        self.user = criar_usuario("ana", papel=ALUNO)
        self.aluno = criar_aluno("Ana Própria", usuario=self.user)
        outro = criar_aluno("Bruno Alheio")
        turma.alunos.add(self.aluno, outro)
        Matricula.objects.update(data_inicio=date(2020, 1, 1))
        gerar_cobrancas(date(2020, 1, 1))  # já vencida → em atraso

    def test_aluno_ve_so_as_proprias_e_situacao_informativa(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("alunos:minha_area"))
        self.assertContains(resp, "Minhas mensalidades")
        self.assertContains(resp, "Em atraso")
        self.assertContains(resp, "01/2020")
        self.assertNotContains(resp, "Bruno Alheio")
        self.assertEqual(self.client.get(reverse("financeiro:mensalidades")).status_code, 403)
        c = Cobranca.objects.get(aluno=self.aluno)
        self.assertEqual(self.client.get(reverse("financeiro:cobranca", args=[c.pk])).status_code, 403)

    def test_professor_nao_acessa_cobrancas(self):
        user = criar_usuario("prof", papel=PROFESSOR)
        criar_professor("Prof X", usuario=user)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("financeiro:mensalidades")).status_code, 403)
