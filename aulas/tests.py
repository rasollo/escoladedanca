from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from escoladedanca.testutils import (SEGUNDA, LogadoTestCase, criar_aluno, criar_presenca,
                                     criar_professor, criar_turma, modalidade, sala)

from .forms import VinculoAlunosForm
from .models import Matricula, Modalidade, Presenca, Sala, Turma


class DadosIniciaisTests(TestCase):
    def test_duas_salas_com_40_lugares(self):
        """RN09 — a escola possui duas salas com capacidade de até 40 alunos."""
        self.assertEqual(
            list(Sala.objects.values_list("nome", "capacidade")),
            [("Sala 1", 40), ("Sala 2", 40)],
        )

    def test_modalidades_da_escola(self):
        """Seção 3.1 — forró, zouk, salsa, bachata, sertanejo e samba rock."""
        self.assertEqual(
            set(Modalidade.objects.values_list("nome", flat=True)),
            {"Forró", "Zouk", "Salsa", "Bachata", "Sertanejo", "Samba rock"},
        )


class TurmaRegrasTests(TestCase):
    def _turma(self, **kw):
        dados = dict(modalidade=modalidade(), professor=criar_professor(), sala=sala(),
                     dia_semana=0, hora_inicio=time(19), hora_fim=time(20))
        dados.update(kw)
        return Turma(**dados)

    def test_turma_valida(self):
        """RN10 — aula com modalidade, sala, dia e horário."""
        self._turma().full_clean()

    def test_termino_antes_do_inicio(self):
        with self.assertRaises(ValidationError) as ctx:
            self._turma(hora_inicio=time(20), hora_fim=time(19)).full_clean()
        self.assertIn("hora_fim", ctx.exception.message_dict)

    def test_fora_do_horario_de_funcionamento(self):
        """Seção 3.1 — funcionamento das 18h às 22h."""
        for ini, fim in [(time(17), time(18, 30)), (time(21), time(22, 30))]:
            with self.assertRaises(ValidationError):
                self._turma(hora_inicio=ini, hora_fim=fim).full_clean()
        self._turma(hora_inicio=time(18), hora_fim=time(22)).full_clean()

    def test_conflito_de_sala(self):
        """RNF05 — duas aulas na mesma sala e horário sobrepostos não são permitidas."""
        criar_turma(inicio="19:00", fim="20:00")
        nova = self._turma(hora_inicio=time(19, 30), hora_fim=time(20, 30))
        with self.assertRaises(ValidationError) as ctx:
            nova.full_clean()
        self.assertIn("sala", ctx.exception.message_dict)

    def test_horarios_encostados_nao_conflitam(self):
        criar_turma(inicio="19:00", fim="20:00")
        self._turma(hora_inicio=time(20), hora_fim=time(21)).full_clean()

    def test_outra_sala_ou_outro_dia_nao_conflitam(self):
        criar_turma(inicio="19:00", fim="20:00")
        self._turma(sala=sala("Sala 2")).full_clean()
        self._turma(dia_semana=1).full_clean()

    def test_conflito_de_professor(self):
        prof = criar_professor()
        criar_turma(professor=prof)
        with self.assertRaises(ValidationError) as ctx:
            self._turma(professor=prof, sala=sala("Sala 2")).full_clean()
        self.assertIn("professor", ctx.exception.message_dict)

    def test_turma_inativa_nao_bloqueia_agenda(self):
        criar_turma(ativa=False)
        self._turma().full_clean()

    def test_editar_a_propria_turma_nao_conflita(self):
        turma = criar_turma()
        turma.hora_fim = time(20, 30)
        turma.full_clean()


class CapacidadeTests(TestCase):
    def setUp(self):
        self.turma = criar_turma()
        self.alunos = [criar_aluno(f"Aluno {i:02d}") for i in range(41)]

    def test_quantidade_e_vagas(self):
        """RF20 — quantidade de alunos por aula e vagas restantes."""
        self.turma.alunos.set(self.alunos[:10])
        self.assertEqual(self.turma.quantidade_alunos(), 10)
        self.assertEqual(self.turma.vagas_restantes(), 30)

    def test_vinculo_ate_40_alunos(self):
        """RF20 / RF21 / RN09 — vínculo aceita até 40 alunos."""
        form = VinculoAlunosForm(data={"alunos": [a.pk for a in self.alunos[:40]]},
                                 turma=self.turma)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(self.turma.alunos.count(), 40)

    def test_vinculo_acima_da_capacidade(self):
        """Fluxo 04 — quantidade acima de 40 → revisar ou organizar outra turma."""
        form = VinculoAlunosForm(data={"alunos": [a.pk for a in self.alunos]}, turma=self.turma)
        self.assertFalse(form.is_valid())
        self.assertIn("organize outra turma", str(form.errors))

    def test_troca_para_sala_menor_que_a_turma(self):
        self.turma.alunos.set(self.alunos[:30])
        pequena = Sala.objects.create(nome="Sala pequena", capacidade=20)
        self.turma.sala = pequena
        with self.assertRaises(ValidationError):
            self.turma.full_clean()


class PresencaModelTests(TestCase):
    def test_data_deve_corresponder_ao_dia_da_aula(self):
        turma = criar_turma(dia=0)
        p = Presenca(turma=turma, aluno=criar_aluno(), data=SEGUNDA + timedelta(days=1))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_um_registro_por_aluno_por_aula(self):
        """RNF05 — não duplica presença do mesmo aluno na mesma aula."""
        turma, aluno = criar_turma(), criar_aluno()
        criar_presenca(turma, aluno)
        with self.assertRaises(IntegrityError):
            criar_presenca(turma, aluno)

    def test_remover_aula_nao_apaga_historico(self):
        """RN07 / RNF05 — histórico de presença é protegido."""
        turma = criar_turma()
        criar_presenca(turma, criar_aluno())
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            turma.delete()


class AgendaViewTests(LogadoTestCase):
    def test_agendar_aula(self):
        """RF19 — agendar aula com antecedência associando professor."""
        prof = criar_professor()
        resp = self.client.post(reverse("aulas:turma_nova"), {
            "nome": "Zouk iniciante", "modalidade": modalidade("Zouk").pk, "dia_semana": 2,
            "hora_inicio": "20:00", "hora_fim": "21:00", "sala": sala().pk,
            "professor": prof.pk, "ativa": "on",
        })
        turma = Turma.objects.get()
        self.assertRedirects(resp, turma.get_absolute_url())
        self.assertEqual(turma.professor, prof)

    def test_agendamento_em_conflito_exibe_erro(self):
        criar_turma()
        resp = self.client.post(reverse("aulas:turma_nova"), {
            "modalidade": modalidade().pk, "dia_semana": 0, "hora_inicio": "19:00",
            "hora_fim": "20:00", "sala": sala().pk, "professor": criar_professor("Outro Prof").pk,
            "ativa": "on",
        })
        self.assertContains(resp, "Já existe uma aula nesta sala")
        self.assertEqual(Turma.objects.count(), 1)

    def test_consulta_agenda_com_filtros(self):
        """RF05 / fluxo 14 — consulta por dia, modalidade e sala."""
        criar_turma(nome="Forró segunda", dia=0)
        criar_turma(nome="Zouk terça", dia=1, mod="Zouk", professor=criar_professor("P2"))
        resp = self.client.get(reverse("aulas:agenda"))
        self.assertContains(resp, "Forró segunda")
        self.assertContains(resp, "Zouk terça")
        resp = self.client.get(reverse("aulas:agenda"), {"dia": 1})
        self.assertNotContains(resp, "Forró segunda")
        self.assertContains(resp, "Zouk terça")
        resp = self.client.get(reverse("aulas:agenda"), {"modalidade": modalidade("Forró").pk})
        self.assertContains(resp, "Forró segunda")
        self.assertNotContains(resp, "Zouk terça")

    def test_agenda_sem_resultados(self):
        """Fluxo 14 — informar que não há aulas correspondentes."""
        resp = self.client.get(reverse("aulas:agenda"), {"dia": 6})
        self.assertContains(resp, "Não há aulas correspondentes")

    def test_atualizar_e_remover_aula(self):
        """RF18 / RF19 — atualizar e remover aula."""
        turma = criar_turma()
        self.client.post(reverse("aulas:turma_editar", args=[turma.pk]), {
            "modalidade": turma.modalidade.pk, "dia_semana": 3, "hora_inicio": "19:00",
            "hora_fim": "20:00", "sala": turma.sala.pk, "professor": turma.professor.pk,
            "ativa": "on",
        })
        turma.refresh_from_db()
        self.assertEqual(turma.dia_semana, 3)
        self.client.post(reverse("aulas:turma_excluir", args=[turma.pk]))
        self.assertFalse(Turma.objects.exists())

    def test_remover_aula_com_historico_orienta_desativar(self):
        turma = criar_turma()
        criar_presenca(turma, criar_aluno())
        resp = self.client.post(reverse("aulas:turma_excluir", args=[turma.pk]), follow=True)
        self.assertContains(resp, "não pode ser removido")
        self.assertTrue(Turma.objects.filter(pk=turma.pk).exists())

    def test_vincular_alunos_pela_tela(self):
        """RF21 — associar alunos à aula e atualizar o vínculo."""
        turma = criar_turma()
        a1, a2 = criar_aluno("Aluno Um"), criar_aluno("Aluno Dois")
        self.client.post(reverse("aulas:turma_alunos", args=[turma.pk]), {"alunos": [a1.pk, a2.pk]})
        self.assertEqual(set(turma.alunos.all()), {a1, a2})
        self.client.post(reverse("aulas:turma_alunos", args=[turma.pk]), {"alunos": [a2.pk]})
        self.assertEqual(list(turma.alunos.all()), [a2])


class ModalidadeViewTests(LogadoTestCase):
    def test_crud_modalidade(self):
        """RF18 / fluxo 03 — cadastrar, consultar, atualizar e remover modalidade."""
        self.client.post(reverse("aulas:modalidade_nova"), {"nome": "Tango"})
        tango = Modalidade.objects.get(nome="Tango")
        self.assertContains(self.client.get(reverse("aulas:modalidades")), "Tango")
        self.client.post(reverse("aulas:modalidade_editar", args=[tango.pk]), {"nome": "Tango argentino"})
        tango.refresh_from_db()
        self.assertEqual(tango.nome, "Tango argentino")
        self.client.post(reverse("aulas:modalidade_excluir", args=[tango.pk]))
        self.assertFalse(Modalidade.objects.filter(pk=tango.pk).exists())

    def test_modalidade_duplicada(self):
        resp = self.client.post(reverse("aulas:modalidade_nova"), {"nome": "Forró"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Modalidade.objects.filter(nome="Forró").count(), 1)

    def test_modalidade_em_uso_nao_e_removida(self):
        turma = criar_turma()
        resp = self.client.post(
            reverse("aulas:modalidade_excluir", args=[turma.modalidade.pk]), follow=True
        )
        self.assertContains(resp, "não pode ser removido")


class ChamadaViewTests(LogadoTestCase):
    def setUp(self):
        super().setUp()
        self.turma = criar_turma(dia=0)
        self.a1, self.a2 = criar_aluno("Aluno Um"), criar_aluno("Aluno Dois")
        self.turma.alunos.set([self.a1, self.a2])
        self.url = reverse("aulas:chamada", args=[self.turma.pk])

    def test_lista_alunos_vinculados(self):
        """Fluxo 06 — consultar lista de alunos vinculados."""
        resp = self.client.get(self.url, {"data": SEGUNDA.isoformat()})
        self.assertContains(resp, "Aluno Um")
        self.assertContains(resp, "Aluno Dois")

    def test_registrar_presenca_e_falta(self):
        """RF03 / RF04 — registrar presença e falta."""
        self.client.post(self.url, {
            "data": SEGUNDA.isoformat(), f"aluno_{self.a1.pk}": "P", f"aluno_{self.a2.pk}": "F",
        })
        self.assertTrue(Presenca.objects.get(aluno=self.a1, data=SEGUNDA).presente)
        self.assertFalse(Presenca.objects.get(aluno=self.a2, data=SEGUNDA).presente)

    def test_corrigir_chamada_nao_duplica(self):
        self.client.post(self.url, {"data": SEGUNDA.isoformat(), f"aluno_{self.a1.pk}": "F"})
        self.client.post(self.url, {"data": SEGUNDA.isoformat(), f"aluno_{self.a1.pk}": "P"})
        self.assertEqual(Presenca.objects.filter(aluno=self.a1).count(), 1)
        self.assertTrue(Presenca.objects.get(aluno=self.a1).presente)

    def test_aluno_avulso_sem_matricula(self):
        """RN08 — aluno não vinculado pode participar e ter presença registrada."""
        avulso = criar_aluno("Visitante Avulso")
        self.client.post(self.url, {"data": SEGUNDA.isoformat(), "avulso": avulso.pk})
        self.assertTrue(Presenca.objects.get(aluno=avulso).presente)
        resp = self.client.get(self.url, {"data": SEGUNDA.isoformat()})
        self.assertContains(resp, "Visitante Avulso")

    def test_aluno_sem_mensalidade_pode_ter_presenca(self):
        """RN08 — pagamento em dia não é condição para participar."""
        self.assertFalse(self.a1.mensalidade_em_dia(SEGUNDA))
        self.client.post(self.url, {"data": SEGUNDA.isoformat(), f"aluno_{self.a1.pk}": "P"})
        self.assertTrue(Presenca.objects.filter(aluno=self.a1, presente=True).exists())

    def test_data_em_dia_errado(self):
        terca = SEGUNDA + timedelta(days=1)
        resp = self.client.post(self.url, {"data": terca.isoformat(), f"aluno_{self.a1.pk}": "P"})
        self.assertContains(resp, "Esta aula acontece")
        self.assertFalse(Presenca.objects.exists())

    def test_presentes_acima_da_capacidade(self):
        self.turma.sala.capacidade = 1
        self.turma.sala.save()
        resp = self.client.post(self.url, {
            "data": SEGUNDA.isoformat(), f"aluno_{self.a1.pk}": "P", f"aluno_{self.a2.pk}": "P",
        }, follow=True)
        self.assertContains(resp, "comporta até 1")
        self.assertFalse(Presenca.objects.exists())

    def test_varios_avulsos_de_uma_vez(self):
        """RN08 — o botão “+” envia vários alunos avulsos no mesmo salvamento."""
        v1, v2 = criar_aluno("Visitante Um"), criar_aluno("Visitante Dois")
        resp = self.client.post(self.url, {"data": SEGUNDA.isoformat(), "avulso": [v1.pk, v2.pk]},
                                follow=True)
        self.assertEqual(set(Presenca.objects.filter(presente=True).values_list("aluno", flat=True)),
                         {v1.pk, v2.pk})
        self.assertContains(resp, "2 avulsos incluídos")

    def test_avulsos_vazios_repetidos_e_invalidos_ignorados(self):
        v1 = criar_aluno("Visitante Um")
        inativo = criar_aluno("Inativo", ativo=False)
        self.client.post(self.url, {"data": SEGUNDA.isoformat(),
                                    "avulso": ["", str(v1.pk), str(v1.pk), "abc", "9999",
                                               str(inativo.pk)]})
        self.assertEqual(list(Presenca.objects.values_list("aluno", flat=True)), [v1.pk])

    def test_inscrito_enviado_como_avulso_mantem_marcacao(self):
        """Um aluno já inscrito não vira avulso nem sobrescreve a falta marcada."""
        self.client.post(self.url, {"data": SEGUNDA.isoformat(),
                                    f"aluno_{self.a1.pk}": "F", "avulso": [self.a1.pk]})
        self.assertFalse(Presenca.objects.get(aluno=self.a1).presente)

    def test_remover_avulso_salvo_por_engano(self):
        """Erro do operador: o avulso sai da chamada em vez de virar falta."""
        v1 = criar_aluno("Visitante Um")
        self.client.post(self.url, {"data": SEGUNDA.isoformat(), "avulso": [v1.pk]})
        resp = self.client.get(self.url, {"data": SEGUNDA.isoformat()})
        self.assertContains(resp, f'name="remover_{v1.pk}"')
        resp = self.client.post(self.url, {"data": SEGUNDA.isoformat(), f"remover_{v1.pk}": "1",
                                           f"aluno_{v1.pk}": "F"}, follow=True)
        self.assertFalse(Presenca.objects.filter(aluno=v1).exists())
        self.assertContains(resp, "1 removido da chamada")
        self.assertNotContains(self.client.get(self.url, {"data": SEGUNDA.isoformat()}), "Visitante Um</td>")

    def test_inscrito_nao_pode_ser_removido_da_chamada(self):
        criar_presenca(self.turma, self.a1, SEGUNDA, True)
        resp = self.client.get(self.url, {"data": SEGUNDA.isoformat()})
        self.assertNotContains(resp, f'name="remover_{self.a1.pk}"')
        self.client.post(self.url, {"data": SEGUNDA.isoformat(), f"remover_{self.a1.pk}": "1"})
        self.assertTrue(Presenca.objects.filter(aluno=self.a1).exists())

    def test_capacidade_conta_presencas_ja_salvas(self):
        """A capacidade considera o resultado final, inclusive presenças já salvas."""
        self.turma.sala.capacidade = 2
        self.turma.sala.save()
        criar_presenca(self.turma, self.a1, SEGUNDA, True)
        criar_presenca(self.turma, self.a2, SEGUNDA, True)
        v1 = criar_aluno("Visitante Um")
        resp = self.client.post(self.url, {"data": SEGUNDA.isoformat(), "avulso": [v1.pk]}, follow=True)
        self.assertContains(resp, "comporta até 2")
        self.assertFalse(Presenca.objects.filter(aluno=v1).exists())

    def test_tela_tem_botao_mais_e_remover_linha(self):
        resp = self.client.get(self.url, {"data": SEGUNDA.isoformat()})
        self.assertContains(resp, "+ Adicionar aluno avulso")
        self.assertContains(resp, "data-remover")

    def test_consulta_presencas_e_faltas(self):
        """RF04 / fim do fluxo 06 — consultar presenças e faltas com filtros."""
        criar_presenca(self.turma, self.a1, SEGUNDA, True)
        criar_presenca(self.turma, self.a2, SEGUNDA, False)
        url = reverse("aulas:presencas")
        resp = self.client.get(url, {"status": "falta"})
        self.assertEqual(resp.context["total_faltas"], 1)
        self.assertEqual(resp.context["total_presencas"], 0)
        resp = self.client.get(url, {"aluno": self.a1.pk})
        self.assertEqual(resp.context["total_presencas"], 1)
        resp = self.client.get(url, {"inicio": "data-invalida"})
        self.assertEqual(resp.status_code, 200)


class MatriculaTests(TestCase):
    """RF21 / RN07 — o vínculo gera histórico de matrículas com início e fim."""

    def setUp(self):
        from django.utils import timezone
        self.hoje = timezone.localdate()
        self.turma = criar_turma()
        self.a1, self.a2 = criar_aluno("Aluno Um"), criar_aluno("Aluno Dois")

    def test_vincular_abre_matricula(self):
        self.turma.alunos.add(self.a1)
        m = Matricula.objects.get()
        self.assertEqual((m.turma, m.aluno, m.data_inicio, m.data_fim),
                         (self.turma, self.a1, self.hoje, None))

    def test_desvincular_encerra_sem_apagar(self):
        self.turma.alunos.add(self.a1, self.a2)
        self.turma.alunos.remove(self.a1)
        self.assertEqual(Matricula.objects.get(aluno=self.a1).data_fim, self.hoje)
        self.assertIsNone(Matricula.objects.get(aluno=self.a2).data_fim)

    def test_set_e_clear_sincronizam(self):
        self.turma.alunos.set([self.a1])
        self.turma.alunos.set([self.a2])
        self.assertEqual(Matricula.objects.filter(data_fim__isnull=True).get().aluno, self.a2)
        self.turma.alunos.clear()
        self.assertFalse(Matricula.objects.filter(data_fim__isnull=True).exists())
        self.assertEqual(Matricula.objects.count(), 2)

    def test_pelo_lado_do_aluno(self):
        self.a1.turmas.add(self.turma)
        self.assertTrue(Matricula.objects.filter(aluno=self.a1, data_fim=None).exists())
        self.a1.turmas.remove(self.turma)
        self.assertFalse(Matricula.objects.filter(data_fim=None).exists())

    def test_rematricula_cria_novo_registro(self):
        self.turma.alunos.add(self.a1)
        self.turma.alunos.remove(self.a1)
        self.turma.alunos.add(self.a1)
        self.assertEqual(Matricula.objects.filter(aluno=self.a1).count(), 2)

    def test_add_repetido_nao_duplica(self):
        self.turma.alunos.add(self.a1)
        self.turma.alunos.add(self.a1)
        self.assertEqual(Matricula.objects.count(), 1)

    def test_desativar_aula_encerra_matriculas(self):
        self.turma.alunos.add(self.a1, self.a2)
        self.turma.ativa = False
        self.turma.save()
        self.assertEqual(self.turma.alunos.count(), 0)
        self.assertFalse(Matricula.objects.filter(data_fim=None).exists())

    def test_uma_matricula_aberta_por_aluno_e_aula(self):
        Matricula.objects.create(turma=self.turma, aluno=self.a1, data_inicio=SEGUNDA)
        with self.assertRaises(IntegrityError):
            Matricula.objects.create(turma=self.turma, aluno=self.a1, data_inicio=SEGUNDA)

    def test_fim_nao_antes_do_inicio(self):
        with self.assertRaises(IntegrityError):
            Matricula.objects.create(turma=self.turma, aluno=self.a1, data_inicio=SEGUNDA,
                                     data_fim=SEGUNDA - timedelta(days=1))

    def test_aula_com_matricula_nao_e_excluida(self):
        from django.db.models import ProtectedError
        self.turma.alunos.add(self.a1)
        with self.assertRaises(ProtectedError):
            self.turma.delete()

    def test_historico_na_tela_da_aula(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_user("resp"))
        self.turma.alunos.add(self.a1)
        resp = self.client.get(self.turma.get_absolute_url())
        self.assertContains(resp, "Histórico de matrículas")
        self.assertContains(resp, "Aluno Um")
