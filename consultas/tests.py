from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse

from escoladedanca.testutils import (SEGUNDA, LogadoTestCase, criar_aluno, criar_presenca,
                                     criar_turma, sala)

from .services import classificar, consulta, indicadores_por_turma

HOJE = SEGUNDA + timedelta(days=1)  # terça: as segundas anteriores entram no período


def alunos(n, prefixo="Aluno"):
    return [criar_aluno(f"{prefixo} {k}") for k in range(n)]


class ClassificacaoTests(TestCase):
    def test_faixas_de_temperatura(self):
        self.assertEqual(classificar(90), "quente")
        self.assertEqual(classificar(85), "quente")
        self.assertEqual(classificar(75), "morna")
        self.assertEqual(classificar(50), "fria")
        self.assertEqual(classificar(10), "gelada")
        self.assertEqual(classificar(None), "sem_dados")

    @override_settings(CONSULTAS_FAIXAS={"quente": 95})
    def test_limites_configuraveis(self):
        self.assertEqual(classificar(90), "morna")


class IndicadoresTests(TestCase):
    def setUp(self):
        sala().__class__.objects.filter(nome="Sala 1").update(capacidade=10)
        self.turma = criar_turma()

    def _indicador(self):
        inicio = SEGUNDA - timedelta(weeks=8)
        return next(i for i in indicadores_por_turma(inicio, HOJE) if i.turma == self.turma)

    def test_ocupacao_usa_presentes_e_nao_inscritos(self):
        grupo = alunos(8)
        self.turma.alunos.set(grupo)  # 8 inscritos
        for a in grupo[:4]:
            criar_presenca(self.turma, a)
        for a in grupo[4:]:
            criar_presenca(self.turma, a, presente=False)
        i = self._indicador()
        self.assertEqual(i.aulas, 1)
        self.assertEqual(i.media, 4)
        self.assertEqual(i.ocupacao, 40)        # 4 presentes / sala de 10
        self.assertEqual(i.ocupacao_inscricao, 80)
        self.assertEqual(i.frequencia, 50)
        self.assertEqual(i.lugares_livres, 6)

    def test_media_por_aula_em_varias_semanas(self):
        grupo = alunos(9)
        for a in grupo:                                   # semana 1: 9 presentes
            criar_presenca(self.turma, a, data=SEGUNDA - timedelta(weeks=1))
        for a in grupo[:3]:                               # semana 2: 3 presentes
            criar_presenca(self.turma, a, data=SEGUNDA)
        i = self._indicador()
        self.assertEqual(i.aulas, 2)
        self.assertEqual(i.media, 6)
        self.assertEqual(i.faixa, "fria")

    def test_avulsos_sao_presencas_sem_inscricao(self):
        inscrito, avulso = criar_aluno("Inscrito"), criar_aluno("Avulso")
        self.turma.alunos.add(inscrito)
        criar_presenca(self.turma, inscrito, data=HOJE + timedelta(days=6))  # fora do período
        criar_presenca(self.turma, avulso)
        i = self._indicador()
        self.assertEqual(i.avulsos, 1)
        self.assertEqual(i.pct_avulsos, 100)
        self.assertTrue(any("avulsos" in r for r in i.recomendacoes))

    def test_tendencia_de_queda(self):
        grupo = alunos(8)
        for semana, qtd in enumerate([8, 8, 4, 4]):
            data = SEGUNDA - timedelta(weeks=3 - semana)
            for a in grupo[:qtd]:
                criar_presenca(self.turma, a, data=data)
        i = self._indicador()
        self.assertEqual(i.tendencia, -50)
        self.assertTrue(any("caiu 50%" in r for r in i.recomendacoes))

    def test_turma_sem_chamada(self):
        i = self._indicador()
        self.assertEqual(i.faixa, "sem_dados")
        self.assertIsNone(i.ocupacao)


class ConsultaTests(TestCase):
    def test_oportunidades_e_ranking(self):
        sala().__class__.objects.update(capacidade=10)
        cheia = criar_turma(nome="Cheia")
        vazia = criar_turma(nome="Vazia", inicio="20:00", fim="21:00")
        inativa = criar_turma(nome="Inativa", dia=1, ativa=False)
        grupo = alunos(10)
        for a in grupo[:9]:
            criar_presenca(cheia, a)
        criar_presenca(vazia, grupo[0])

        dados = consulta(8, hoje=HOJE)
        self.assertEqual([i.turma for i in dados["ranking"]], [cheia, vazia])
        self.assertEqual([i.turma for i in dados["oportunidades"]], [vazia])
        self.assertEqual([i.turma for i in dados["lotando"]], [cheia])
        self.assertNotIn(inativa, [i.turma for i in dados["indicadores"]])
        self.assertEqual(dados["resumo"]["ocupacao"], 50)   # 10 presentes / 20 lugares
        self.assertEqual(dados["resumo"]["lugares_livres"], 10)


class OcupacaoSemanalTests(TestCase):
    def test_semana_com_menos_aulas_nao_parece_queda(self):
        """Mesma lotação nas duas semanas; a segunda tem uma aula a menos."""
        sala().__class__.objects.update(capacidade=10)
        a = criar_turma(nome="A")
        b = criar_turma(nome="B", inicio="20:00", fim="21:00")
        grupo = alunos(5)
        semana1, semana2 = SEGUNDA - timedelta(weeks=1), SEGUNDA
        for turma in (a, b):
            for aluno in grupo:
                criar_presenca(turma, aluno, data=semana1)
        for aluno in grupo:                       # semana 2: só a aula A teve chamada
            criar_presenca(a, aluno, data=semana2)
        criar_presenca(a, criar_aluno("Faltou"), data=semana2, presente=False)

        semanas = {s["inicio"]: s for s in consulta(2, hoje=HOJE)["semanal"]}
        s1 = next(s for d, s in semanas.items() if d <= semana1 < d + timedelta(weeks=1))
        s2 = next(s for d, s in semanas.items() if d <= semana2 < d + timedelta(weeks=1))
        self.assertEqual((s1["presencas"], s2["presencas"]), (10, 5))   # total cai à metade
        self.assertEqual((s1["aulas"], s2["aulas"]), (2, 1))
        self.assertEqual(s1["ocupacao"], 50)                             # ocupação igual
        self.assertEqual(s2["ocupacao"], 50)
        self.assertAlmostEqual(s2["frequencia"], 100 * 5 / 6)

    def test_semana_sem_chamada(self):
        s = consulta(1, hoje=HOJE)["semanal"][0]
        self.assertIsNone(s["ocupacao"])
        self.assertEqual(s["altura"], 0)


class ConsultaViewTests(LogadoTestCase):
    def test_pagina_abre_com_e_sem_dados(self):
        url = reverse("consultas:painel")
        self.assertContains(self.client.get(url), "Frequência e oportunidades")
        turma = criar_turma()
        criar_presenca(turma, criar_aluno())
        resposta = self.client.get(url, {"semanas": "12"})
        self.assertContains(resposta, "Termômetro da agenda")
        self.assertContains(resposta, "Ocupação por semana")
        self.assertNotContains(resposta, "/40<")      # nada de "18,7/40"
        self.assertEqual(resposta.context["semanas"], 12)

    def test_periodo_invalido_usa_padrao(self):
        for valor in ("abc", "999"):
            resposta = self.client.get(reverse("consultas:painel"), {"semanas": valor})
            self.assertEqual(resposta.context["semanas"], 8)

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("consultas:painel"))
        self.assertEqual(resposta.status_code, 302)
