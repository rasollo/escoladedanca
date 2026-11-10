from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from escoladedanca.testutils import (SEGUNDA, LogadoTestCase, criar_aluno, criar_presenca,
                                     criar_professor, criar_turma, entrada, saida)

from .forms import EntradaForm, MensalidadeForm, SaidaForm, um_mes_depois
from .models import Movimentacao
from .services import balanco_mensal, calcular_salario, calcular_saldo
from .templatetags.moeda import brl


class MovimentacaoRegrasTests(TestCase):
    def _mov(self, **kw):
        dados = dict(valor=Decimal("10"), data_pagamento=SEGUNDA)
        dados.update(kw)
        return Movimentacao(**dados)

    def test_tipo_obrigatorio(self):
        """RN01 — toda movimentação é entrada ou saída."""
        with self.assertRaises(ValidationError):
            self._mov(tipo="").full_clean()
        with self.assertRaises(ValidationError):
            self._mov(tipo="outro", categoria="luz").full_clean()

    def test_entrada_exige_forma_e_origem(self):
        """RN02 / RN12 — entrada indica forma de pagamento e origem."""
        with self.assertRaises(ValidationError) as ctx:
            self._mov(tipo="entrada").full_clean()
        self.assertIn("forma_pagamento", ctx.exception.message_dict)
        self.assertIn("origem", ctx.exception.message_dict)
        self._mov(tipo="entrada", forma_pagamento="pix", origem="bebidas").full_clean()

    def test_formas_de_pagamento_aceitas(self):
        """RN12 — Pix, dinheiro ou cartão."""
        self.assertEqual(set(Movimentacao.FormaPagamento.values), {"pix", "dinheiro", "cartao"})
        with self.assertRaises(ValidationError):
            self._mov(tipo="entrada", forma_pagamento="cheque", origem="bebidas").full_clean()

    def test_origens_de_entrada(self):
        """RF08 / RN02 — mensalidade, aluguel de sala, bebidas, camisetas."""
        self.assertEqual(set(Movimentacao.Origem.values),
                         {"mensalidade", "aluguel_sala", "bebidas", "camisetas"})

    def test_categorias_de_saida(self):
        """RF09 / RN03 — categorias usadas pela escola."""
        self.assertEqual(set(Movimentacao.Categoria.values), {
            "contas_gerais", "manutencao", "luz", "agua", "taxas", "prefeitura", "salario"})

    def test_saida_exige_categoria_e_nao_aceita_origem(self):
        with self.assertRaises(ValidationError) as ctx:
            self._mov(tipo="saida", origem="bebidas").full_clean()
        self.assertIn("categoria", ctx.exception.message_dict)
        self.assertIn("origem", ctx.exception.message_dict)

    def test_entrada_nao_aceita_categoria(self):
        with self.assertRaises(ValidationError):
            self._mov(tipo="entrada", forma_pagamento="pix", origem="bebidas",
                      categoria="luz").full_clean()

    def test_mensalidade_exige_aluno(self):
        """RN06 — mensalidade é entrada vinculada a um aluno."""
        with self.assertRaises(ValidationError) as ctx:
            self._mov(tipo="entrada", forma_pagamento="pix", origem="mensalidade").full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_salario_exige_professor(self):
        """RN07 — salário é saída vinculada a um professor."""
        with self.assertRaises(ValidationError):
            self._mov(tipo="saida", categoria="salario").full_clean()
        self._mov(tipo="saida", categoria="salario", professor=criar_professor()).full_clean()

    def test_professor_so_em_salario(self):
        with self.assertRaises(ValidationError):
            self._mov(tipo="saida", categoria="luz", professor=criar_professor()).full_clean()

    def test_valor_positivo(self):
        with self.assertRaises(ValidationError):
            self._mov(tipo="saida", categoria="luz", valor=Decimal("0")).full_clean()
        with self.assertRaises(ValidationError):
            self._mov(tipo="saida", categoria="luz", valor=Decimal("-5")).full_clean()

    def test_validade_nao_anterior_ao_pagamento(self):
        """RN04 / RF10 — data de pagamento e validade coerentes."""
        with self.assertRaises(ValidationError) as ctx:
            self._mov(tipo="saida", categoria="luz",
                      validade=SEGUNDA - timedelta(days=1)).full_clean()
        self.assertIn("validade", ctx.exception.message_dict)
        self._mov(tipo="saida", categoria="luz", validade=SEGUNDA).full_clean()

    def test_validade_opcional(self):
        """RN04 — validade apenas quando aplicável."""
        self._mov(tipo="saida", categoria="taxas", validade=None).full_clean()

    def test_valor_com_sinal(self):
        self.assertEqual(entrada("10.00").valor_com_sinal, Decimal("10.00"))
        self.assertEqual(saida("4.00").valor_com_sinal, Decimal("-4.00"))


class FormsTests(TestCase):
    def test_entrada_form_define_tipo(self):
        form = EntradaForm(data={"valor": "30", "data_pagamento": "2026-11-02",
                                 "origem": "camisetas", "forma_pagamento": "dinheiro"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().tipo, "entrada")

    def test_entrada_form_sem_forma_pagamento(self):
        form = EntradaForm(data={"valor": "30", "data_pagamento": "2026-11-02", "origem": "camisetas"})
        self.assertFalse(form.is_valid())

    def test_mensalidade_form_fixa_origem(self):
        aluno = criar_aluno()
        form = MensalidadeForm(data={"aluno": aluno.pk, "valor": "150", "data_pagamento": "2026-11-02",
                                     "forma_pagamento": "pix", "validade": "2026-12-02"})
        self.assertTrue(form.is_valid(), form.errors)
        mov = form.save()
        self.assertEqual((mov.tipo, mov.origem, mov.aluno), ("entrada", "mensalidade", aluno))

    def test_mensalidade_form_exige_forma_de_pagamento(self):
        """Correção do fluxo 10 — mensalidade também informa a forma de pagamento (RN02)."""
        form = MensalidadeForm(data={"aluno": criar_aluno().pk, "valor": "150",
                                     "data_pagamento": "2026-11-02"})
        self.assertFalse(form.is_valid())
        self.assertIn("forma_pagamento", form.errors)

    def test_saida_form(self):
        form = SaidaForm(data={"valor": "480", "data_pagamento": "2026-11-02", "categoria": "luz"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().tipo, "saida")

    def test_um_mes_depois(self):
        self.assertEqual(um_mes_depois(date(2026, 1, 31)), date(2026, 2, 28))
        self.assertEqual(um_mes_depois(date(2026, 12, 10)), date(2027, 1, 10))


class SaldoBalancoTests(TestCase):
    def test_saldo(self):
        """RF15 — soma das entradas menos as saídas (fluxo 12)."""
        entrada("300.00")
        entrada("50.50", origem="camisetas", forma="dinheiro")
        saida("100.25")
        r = calcular_saldo()
        self.assertEqual(r["entradas"], Decimal("350.50"))
        self.assertEqual(r["saidas"], Decimal("100.25"))
        self.assertEqual(r["saldo"], Decimal("250.25"))

    def test_saldo_vazio_e_negativo(self):
        self.assertEqual(calcular_saldo()["saldo"], Decimal("0"))
        saida("10.00")
        self.assertEqual(calcular_saldo()["saldo"], Decimal("-10.00"))

    def test_balanco_mensal_considera_apenas_o_periodo(self):
        """RF16 / RN05 — compara entradas e saídas realizadas no mês."""
        entrada("200.00", data=date(2026, 11, 1))
        entrada("100.00", data=date(2026, 11, 30), origem="mensalidade", aluno=criar_aluno())
        saida("50.00", data=date(2026, 11, 15))
        entrada("999.00", data=date(2026, 10, 31))  # fora do período
        saida("999.00", data=date(2026, 12, 1))  # fora do período
        b = balanco_mensal(2026, 11)
        self.assertEqual(b.total_entradas, Decimal("300.00"))
        self.assertEqual(b.total_saidas, Decimal("50.00"))
        self.assertEqual(b.saldo, Decimal("250.00"))
        self.assertEqual(b.quantidade, 3)
        origens = {l["rotulo"]: l["total"] for l in b.entradas_por_origem}
        self.assertEqual(origens, {"Bebidas": Decimal("200.00"), "Mensalidade": Decimal("100.00")})

    def test_balanco_sem_movimentacoes(self):
        """Fluxo 13 — período sem movimentações registradas."""
        b = balanco_mensal(2020, 2)
        self.assertFalse(b.tem_movimentacoes)
        self.assertEqual(b.saldo, Decimal("0"))


class SalarioTests(TestCase):
    """RF13 / RN07 — salário = inscrições ativas no mês × valor por aluno."""

    def _matricular(self, turma, aluno, inicio, fim=None):
        from aulas.models import Matricula
        return Matricula.objects.create(turma=turma, aluno=aluno, data_inicio=inicio, data_fim=fim)

    def test_salario_por_inscricao(self):
        """Exemplo do relatório: 20 + 15 inscrições, 5 alunos repetidos → 35."""
        prof = criar_professor(valor="25.00")
        seg = criar_turma(professor=prof, dia=0)
        sex = criar_turma(professor=prof, dia=4)
        alunos = [criar_aluno(f"Aluno {i:02d}") for i in range(30)]
        seg.alunos.set(alunos[:20])
        sex.alunos.set(alunos[15:30])
        from aulas.models import Matricula
        Matricula.objects.update(data_inicio=date(2026, 10, 1))
        c = calcular_salario(prof, 2026, 11)
        self.assertEqual(c.inscricoes, 35)
        self.assertEqual(c.valor, Decimal("875.00"))
        self.assertEqual([l["inscritos"] for l in c.por_aula], [20, 15])
        self.assertEqual(c.por_aula[0]["valor"], Decimal("500.00"))

    def test_respeita_inicio_e_fim_da_matricula(self):
        prof = criar_professor(valor="10.00")
        turma = criar_turma(professor=prof)
        a = [criar_aluno(f"Aluno {i}") for i in range(5)]
        self._matricular(turma, a[0], date(2026, 9, 1))                    # ativa
        self._matricular(turma, a[1], date(2026, 9, 1), date(2026, 11, 3))  # saiu em nov
        self._matricular(turma, a[2], date(2026, 9, 1), date(2026, 10, 31))  # saiu antes
        self._matricular(turma, a[3], date(2026, 12, 1))                   # entrou depois
        self._matricular(turma, a[4], date(2026, 11, 30))                  # entrou no fim
        self.assertEqual(calcular_salario(prof, 2026, 11).inscricoes, 3)
        # em outubro: a0, a1 e a2 (que saiu em 31/10) estavam inscritos
        self.assertEqual(calcular_salario(prof, 2026, 10).inscricoes, 3)

    def test_matricula_cancelada_no_mesmo_dia_nao_conta(self):
        prof = criar_professor(valor="10.00")
        turma = criar_turma(professor=prof)
        self._matricular(turma, criar_aluno(), date(2026, 11, 5), date(2026, 11, 5))
        self.assertEqual(calcular_salario(prof, 2026, 11).inscricoes, 0)

    def test_saiu_e_voltou_no_mes_conta_uma_vez(self):
        prof = criar_professor(valor="10.00")
        turma, aluno = criar_turma(professor=prof), criar_aluno()
        self._matricular(turma, aluno, date(2026, 11, 2), date(2026, 11, 9))
        self._matricular(turma, aluno, date(2026, 11, 20))
        self.assertEqual(calcular_salario(prof, 2026, 11).inscricoes, 1)

    def test_avulso_e_outro_professor_nao_contam(self):
        prof = criar_professor(valor="10.00")
        turma = criar_turma(professor=prof)
        criar_presenca(turma, criar_aluno("Avulso"), SEGUNDA)  # presença sem matrícula
        outra = criar_turma(professor=criar_professor("Outro"), sala_nome="Sala 2")
        self._matricular(outra, criar_aluno("De outro"), date(2026, 10, 1))
        self.assertEqual(calcular_salario(prof, 2026, 11).inscricoes, 0)

    def test_presenca_nao_altera_salario(self):
        """A regra antiga (por presença) não vale mais: faltas não reduzem o salário."""
        prof = criar_professor(valor="10.00")
        turma, aluno = criar_turma(professor=prof), criar_aluno()
        self._matricular(turma, aluno, date(2026, 10, 1))
        antes = calcular_salario(prof, 2026, 11).valor
        criar_presenca(turma, aluno, SEGUNDA, presente=False)
        self.assertEqual(calcular_salario(prof, 2026, 11).valor, antes)

    def test_salario_ja_pago_na_referencia(self):
        prof = criar_professor(valor="10.00")
        turma = criar_turma(professor=prof)
        self._matricular(turma, criar_aluno(), date(2026, 10, 1))
        saida("4.00", categoria="salario", professor=prof, referencia=date(2026, 11, 1))
        c = calcular_salario(prof, 2026, 11)
        self.assertEqual(c.ja_pago, Decimal("4.00"))
        self.assertEqual(c.pendente, Decimal("6.00"))
        self.assertEqual(calcular_salario(prof, 2026, 10).ja_pago, Decimal("0"))


class MoedaFilterTests(SimpleTestCase):
    def test_formato_brasileiro(self):
        self.assertEqual(brl(Decimal("1234.5")), "R$ 1.234,50")
        self.assertEqual(brl(Decimal("-10")), "-R$ 10,00")
        self.assertEqual(brl(None), "R$ 0,00")
        self.assertEqual(brl("abc"), "abc")


class FinanceiroViewTests(LogadoTestCase):
    def test_registrar_entrada(self):
        """RF06 / RF08 / RF10 — fluxo 08."""
        resp = self.client.post(reverse("financeiro:nova_entrada"), {
            "valor": "25.00", "data_pagamento": "2026-11-02", "origem": "bebidas",
            "forma_pagamento": "cartao",
        })
        self.assertRedirects(resp, reverse("financeiro:movimentacoes"))
        mov = Movimentacao.objects.get()
        self.assertEqual((mov.tipo, mov.origem, mov.forma_pagamento), ("entrada", "bebidas", "cartao"))

    def test_registrar_saida(self):
        """RF07 / RF09 / RF12 — fluxo 09."""
        self.client.post(reverse("financeiro:nova_saida"), {
            "valor": "120.00", "data_pagamento": "2026-11-02", "categoria": "agua",
            "validade": "2026-12-02",
        })
        mov = Movimentacao.objects.get()
        self.assertEqual((mov.tipo, mov.categoria), ("saida", "agua"))
        self.assertEqual(mov.validade, date(2026, 12, 2))

    def test_entrada_invalida_nao_salva(self):
        resp = self.client.post(reverse("financeiro:nova_entrada"), {
            "valor": "25.00", "data_pagamento": "2026-11-02", "origem": "mensalidade",
            "forma_pagamento": "pix",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Selecione o aluno da mensalidade")
        self.assertFalse(Movimentacao.objects.exists())

    def test_registrar_e_consultar_mensalidade(self):
        """RF11 / RN06 — fluxo 10."""
        aluno = criar_aluno("Carla Lima")
        self.client.post(reverse("financeiro:nova_mensalidade"), {
            "aluno": aluno.pk, "valor": "150.00", "data_pagamento": "2026-11-02",
            "forma_pagamento": "pix", "validade": "2026-12-02",
        })
        self.assertEqual(Movimentacao.objects.get().origem, "mensalidade")
        resp = self.client.get(reverse("financeiro:mensalidades"), {"aluno": aluno.pk})
        self.assertContains(resp, "Carla Lima")

    def test_mensalidade_sem_registro(self):
        """Fluxo 10 — exibir ausência de registro."""
        resp = self.client.get(reverse("financeiro:mensalidades"))
        self.assertContains(resp, "Não há mensalidades registradas")

    def test_next_externo_e_ignorado(self):
        """Segurança — evita redirecionamento para sites externos."""
        resp = self.client.post(reverse("financeiro:nova_saida"), {
            "valor": "1", "data_pagamento": "2026-11-02", "categoria": "taxas",
            "next": "https://malicioso.example.com/",
        })
        self.assertRedirects(resp, reverse("financeiro:movimentacoes"))

    def test_next_interno_e_respeitado(self):
        aluno = criar_aluno()
        resp = self.client.post(reverse("financeiro:nova_mensalidade"), {
            "aluno": aluno.pk, "valor": "150", "data_pagamento": "2026-11-02",
            "forma_pagamento": "pix", "next": aluno.get_absolute_url(),
        })
        self.assertRedirects(resp, aluno.get_absolute_url())

    def test_consulta_movimentacoes_filtrada(self):
        """RF14 — consulta das movimentações por período e tipo."""
        entrada("10.00", data=date(2026, 11, 2), descricao="Água mineral")
        saida("20.00", data=date(2026, 10, 2), descricao="Conta de luz")
        url = reverse("financeiro:movimentacoes")
        self.assertEqual(self.client.get(url).context["total"], 2)
        self.assertEqual(self.client.get(url, {"tipo": "saida"}).context["total"], 1)
        resp = self.client.get(url, {"inicio": "2026-11-01", "fim": "2026-11-30"})
        self.assertEqual(resp.context["total"], 1)
        self.assertEqual(self.client.get(url, {"q": "luz"}).context["total"], 1)

    def test_filtro_periodo_invertido(self):
        resp = self.client.get(reverse("financeiro:movimentacoes"),
                               {"inicio": "2026-12-01", "fim": "2026-11-01"})
        self.assertContains(resp, "data inicial deve ser anterior")

    def test_editar_e_excluir(self):
        mov = entrada("10.00")
        self.client.post(reverse("financeiro:editar", args=[mov.pk]), {
            "valor": "12.00", "data_pagamento": "2026-11-02", "origem": "bebidas",
            "forma_pagamento": "pix",
        })
        mov.refresh_from_db()
        self.assertEqual(mov.valor, Decimal("12.00"))
        self.client.post(reverse("financeiro:excluir", args=[mov.pk]))
        self.assertFalse(Movimentacao.objects.exists())

    def test_editar_saida_mantem_tipo(self):
        mov = saida("10.00")
        self.client.post(reverse("financeiro:editar", args=[mov.pk]), {
            "valor": "15.00", "data_pagamento": "2026-11-02", "categoria": "manutencao",
        })
        mov.refresh_from_db()
        self.assertEqual((mov.tipo, mov.categoria), ("saida", "manutencao"))

    def test_paginas_de_consulta(self):
        """RF12 / RF15 / RF16 — despesas, saldo e balanço."""
        entrada("100.00", data=date(2026, 11, 2))
        saida("40.00", data=date(2026, 11, 3), categoria="taxas")
        resp = self.client.get(reverse("financeiro:saldo"))
        self.assertContains(resp, "R$ 60,00")
        resp = self.client.get(reverse("financeiro:despesas"), {"categoria": "taxas"})
        self.assertEqual(resp.context["total"], 1)
        resp = self.client.get(reverse("financeiro:balanco"), {"mes": "2026-11"})
        self.assertContains(resp, "R$ 100,00")
        self.assertContains(resp, "R$ 40,00")
        resp = self.client.get(reverse("financeiro:balanco"), {"mes": "2019-01"})
        self.assertContains(resp, "Período sem movimentações")
        resp = self.client.get(reverse("financeiro:balanco"), {"mes": "lixo"})
        self.assertEqual(resp.status_code, 200)

    def test_calcular_e_registrar_salario(self):
        """RF13 — cálculo pela tela e registro do salário como saída."""
        from aulas.models import Matricula
        prof = criar_professor(valor="5.00")
        turma = criar_turma(professor=prof)
        Matricula.objects.create(turma=turma, aluno=criar_aluno(), data_inicio=date(2026, 10, 1))
        resp = self.client.get(reverse("financeiro:salarios"),
                               {"professor": prof.pk, "mes": "2026-11"})
        self.assertEqual(resp.context["calculo"].valor, Decimal("5.00"))
        self.assertContains(resp, "1 aluno inscrito")
        self.client.post(reverse("financeiro:registrar_salario"), {
            "valor": "5.00", "data_pagamento": "2026-11-30", "categoria": "salario",
            "professor": prof.pk, "referencia": "2026-11-01",
        })
        mov = Movimentacao.objects.get()
        self.assertEqual((mov.tipo, mov.categoria, mov.professor), ("saida", "salario", prof))

    def test_salario_mes_invalido(self):
        resp = self.client.get(reverse("financeiro:salarios"),
                               {"professor": criar_professor().pk, "mes": "xx"})
        self.assertIsNone(resp.context["calculo"])
