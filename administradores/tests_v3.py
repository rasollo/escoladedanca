"""Funções trazidas do protótipo v3 (RF31–RF38)."""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alunos.models import Aluno
from aulas.models import Chamada, Matricula, Presenca, Turma
from escoladedanca.rbac import ADMINISTRATIVO, ALUNO, PROFESSOR, adicionar_papel, papeis_do
from escoladedanca.testutils import (SEGUNDA, criar_aluno, criar_presenca, criar_professor,
                                     criar_turma, criar_usuario, modalidade, sala, senha_aleatoria)
from financeiro.models import Cobranca
from financeiro.services import gerar_cobrancas


class VariosPapeisTests(TestCase):
    """RF31 — uma conta com mais de um papel escolhe o ambiente."""

    def setUp(self):
        self.user = criar_usuario("camila", papel=PROFESSOR)
        adicionar_papel(self.user, ALUNO)
        self.prof = criar_professor("Camila Prof", usuario=self.user)
        self.aluno = criar_aluno("Camila Aluna", usuario=self.user)
        self.client.force_login(self.user)

    def test_escolhe_e_troca_de_ambiente(self):
        self.assertRedirects(self.client.get(reverse("index")), reverse("ambiente"))
        self.assertRedirects(self.client.get(reverse("aulas:agenda")), reverse("ambiente"))
        resp = self.client.get(reverse("ambiente"))
        self.assertContains(resp, "Entrar como professor")
        self.assertContains(resp, "Entrar como aluno")
        self.client.post(reverse("ambiente"), {"papel": ALUNO})
        self.assertRedirects(self.client.get(reverse("index")), reverse("alunos:minha_area"))
        self.assertEqual(self.client.get(reverse("professores:minha_area")).status_code, 403)
        self.assertContains(self.client.get(reverse("alunos:minha_area")), "Trocar ambiente")
        self.client.post(reverse("ambiente"), {"papel": PROFESSOR})
        self.assertEqual(self.client.get(reverse("professores:minha_area")).status_code, 200)
        self.assertEqual(self.client.get(reverse("alunos:minha_area")).status_code, 403)

    def test_nao_escolhe_papel_que_nao_tem(self):
        self.client.post(reverse("ambiente"), {"papel": ADMINISTRATIVO})
        self.assertRedirects(self.client.get(reverse("index")), reverse("ambiente"))

    def test_administrativo_acrescenta_e_remove_papel(self):
        adm = criar_usuario("adm")
        outro = criar_usuario("joana", papel=PROFESSOR)
        criar_professor("Joana", usuario=outro)
        aluna = criar_aluno("Joana Aluna")
        self.client.force_login(adm)
        url = reverse("administradores:usuario_papeis", args=[outro.pk])
        resp = self.client.post(url, {"papel": ALUNO})
        self.assertContains(resp, "Escolha o cadastro de aluno")
        self.client.post(url, {"papel": ALUNO, "aluno": aluna.pk})
        outro = get_user_model().objects.get(pk=outro.pk)
        self.assertEqual(papeis_do(outro), [PROFESSOR, ALUNO])
        aluna.refresh_from_db()
        self.assertEqual(aluna.usuario, outro)
        self.client.post(url, {"remover": ALUNO})
        self.client.post(url, {"remover": PROFESSOR})  # último papel: não remove
        outro = get_user_model().objects.get(pk=outro.pk)
        self.assertEqual(papeis_do(outro), [PROFESSOR])


class MatriculaSituacaoTests(TestCase):
    """RF32 — matrícula suspensa ou cancelada com motivo."""

    def setUp(self):
        self.client.force_login(criar_usuario("adm"))
        self.turma = criar_turma()
        self.turma.valor_mensal = Decimal("100.00")
        self.turma.save()
        self.aluno = criar_aluno("Ana")
        self.turma.alunos.add(self.aluno)
        self.m = Matricula.objects.get()
        self.m.desconto_tipo, self.m.desconto = "fixo", Decimal("10.00")
        self.m.save()

    def test_suspender_exige_motivo_e_reativar_mantem_valores(self):
        url = reverse("aulas:matricula_encerrar", args=[self.m.pk])
        self.client.post(url, {"situacao": "suspensa", "motivo": ""})
        self.assertTrue(Matricula.objects.get(pk=self.m.pk).ativa)
        self.client.post(url, {"situacao": "suspensa", "motivo": "Viagem de 2 meses"})
        m = Matricula.objects.get(pk=self.m.pk)
        self.assertEqual((m.situacao, m.motivo), ("suspensa", "Viagem de 2 meses"))
        self.assertFalse(self.turma.alunos.exists())
        self.assertEqual(gerar_cobrancas(timezone.localdate().replace(day=1) + timedelta(days=40)), 0)
        self.client.post(reverse("aulas:matricula_reativar", args=[m.pk]))
        nova = Matricula.objects.get(data_fim__isnull=True)
        self.assertEqual((nova.situacao, nova.valor_final), ("ativa", Decimal("90.00")))

    def test_cancelada_nao_reativa_e_vinculo_removido_vira_encerrada(self):
        self.client.post(reverse("aulas:matricula_encerrar", args=[self.m.pk]),
                         {"situacao": "cancelada", "motivo": "Mudou de cidade"})
        resp = self.client.post(reverse("aulas:matricula_reativar", args=[self.m.pk]))
        self.assertEqual(resp.status_code, 404)
        outro = criar_aluno("Bia")
        self.turma.alunos.add(outro)
        self.turma.alunos.remove(outro)
        self.assertEqual(Matricula.objects.get(aluno=outro).situacao, "encerrada")
        resp = self.client.get(self.aluno.get_absolute_url())
        self.assertContains(resp, "Mudou de cidade")


class ChamadaSituacaoTests(TestCase):
    """RF33 — chamada aberta, concluída ou cancelada; correção com motivo."""

    def setUp(self):
        self.prof_user = criar_usuario("prof", papel=PROFESSOR)
        prof = criar_professor("P", usuario=self.prof_user)
        self.turma = criar_turma(professor=prof)
        self.aluno = criar_aluno("Ana")
        self.turma.alunos.add(self.aluno)
        self.url = reverse("aulas:chamada", args=[self.turma.pk])
        self.data = SEGUNDA.strftime("%d/%m/%Y")

    def test_professor_conclui_e_nao_altera_depois(self):
        self.client.force_login(self.prof_user)
        self.client.post(self.url, {"data": self.data, f"aluno_{self.aluno.pk}": "F", "acao": "concluir"})
        self.assertEqual(Chamada.objects.get().situacao, "concluida")
        self.client.post(self.url, {"data": self.data, f"aluno_{self.aluno.pk}": "P"})
        self.assertFalse(Presenca.objects.get().presente)  # não mudou
        resp = self.client.post(self.url, {"data": self.data, "acao": "reabrir"})
        self.assertEqual(resp.status_code, 403)

    def test_administracao_corrige_com_motivo_e_reabre(self):
        Chamada.objects.create(turma=self.turma, data=SEGUNDA, situacao="concluida")
        criar_presenca(self.turma, self.aluno, presente=False)
        self.client.force_login(criar_usuario("adm"))
        self.client.post(self.url, {"data": self.data, f"aluno_{self.aluno.pk}": "P"})
        self.assertFalse(Presenca.objects.get().presente)  # sem motivo: recusado
        self.client.post(self.url, {"data": self.data, f"aluno_{self.aluno.pk}": "P",
                                    "motivo": "Aluna estava presente"})
        self.assertTrue(Presenca.objects.get().presente)
        self.assertIn("Aluna estava presente", Chamada.objects.get().motivo)
        self.client.post(self.url, {"data": self.data, "acao": "reabrir"})
        self.assertEqual(Chamada.objects.get().situacao, "aberta")

    def test_cancelar_aula_com_motivo(self):
        self.client.force_login(self.prof_user)
        self.client.post(self.url, {"data": self.data, "acao": "cancelar", "motivo": ""})
        self.assertFalse(Chamada.objects.exists())
        self.client.post(self.url, {"data": self.data, "acao": "cancelar", "motivo": "Feriado"})
        c = Chamada.objects.get()
        self.assertEqual((c.situacao, c.motivo), ("cancelada", "Feriado"))
        self.client.post(self.url, {"data": self.data, f"aluno_{self.aluno.pk}": "P"})
        self.assertFalse(Presenca.objects.exists())


class RelatoriosTests(TestCase):
    """RF34 — relatórios do período e exportação CSV."""

    def test_csv_com_bom_separador_e_protecao_contra_formula(self):
        turma = criar_turma()
        criar_presenca(turma, criar_aluno("=HYPERLINK(1)"))
        self.client.force_login(criar_usuario("adm"))
        resp = self.client.get(reverse("consultas:relatorios"), {"inicio": "01/11/2026", "fim": "30/11/2026"})
        self.assertContains(resp, "Relatórios do período")
        resp = self.client.get(reverse("consultas:relatorios"),
                               {"inicio": "01/11/2026", "fim": "30/11/2026", "exportar": "presencas"})
        corpo = resp.content.decode("utf-8")
        self.assertTrue(corpo.startswith("﻿Data;Aula;Professor;Aluno;Situação"))
        self.assertIn("'=HYPERLINK(1)", corpo)
        self.assertIn("02/11/2026", corpo)

    def test_somente_administrativo(self):
        u = criar_usuario("prof", papel=PROFESSOR)
        criar_professor("P", usuario=u)
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("consultas:relatorios")).status_code, 403)


class BackupTests(TestCase):
    """RF35 — exportar e restaurar os dados em JSON (superusuário)."""

    def setUp(self):
        self.su = get_user_model().objects.create_superuser("su", "", senha_aleatoria())
        self.client.force_login(self.su)
        turma = criar_turma()
        turma.alunos.add(criar_aluno("Ana Backup"))

    def _restaurar(self, conteudo, confirmacao="RESTAURAR"):
        arquivo = SimpleUploadedFile("backup.json", conteudo.encode(), content_type="application/json")
        return self.client.post(reverse("administradores:backup_restaurar"),
                                {"arquivo": arquivo, "confirmacao": confirmacao})

    def test_ida_e_volta(self):
        dados = self.client.get(reverse("administradores:backup_exportar")).content.decode()
        self.assertIn('"model": "alunos.aluno"', dados)
        criar_aluno("Depois do backup")
        Turma.objects.get().alunos.add(criar_aluno("Outro"))
        self._restaurar(dados)
        self.assertEqual(list(Aluno.objects.values_list("nome", flat=True)), ["Ana Backup"])
        self.assertEqual(Matricula.objects.count(), 1)
        self.assertTrue(get_user_model().objects.filter(username="su", is_superuser=True).exists())

    def test_recusas(self):
        dados = self.client.get(reverse("administradores:backup_exportar")).content.decode()
        self._restaurar(dados, confirmacao="sim")
        self._restaurar("{nao é json")
        sem_su = [i for i in json.loads(dados) if i["model"] != "auth.user"]
        self._restaurar(json.dumps(sem_su))
        self._restaurar(json.dumps([{"model": "sessions.session", "fields": {}}]))
        self.assertTrue(Aluno.objects.filter(nome="Ana Backup").exists())

    def test_somente_superusuario(self):
        self.client.force_login(criar_usuario("adm"))
        self.assertEqual(self.client.get(reverse("administradores:backup_exportar")).status_code, 403)


class VariosDiasTests(TestCase):
    """RF36 — aula em vários dias da semana e período de vigência."""

    def setUp(self):
        self.client.force_login(criar_usuario("adm"))
        self.prof = criar_professor()

    def _agendar(self, dias, **extra):
        dados = {"nome": "Forró", "modalidade": modalidade().pk, "dia_semana": dias,
                 "hora_inicio": "19:00", "hora_fim": "20:00", "sala": sala().pk,
                 "professor": self.prof.pk, "ativa": "on"}
        dados.update(extra)
        return self.client.post(reverse("aulas:turma_nova"), dados)

    def test_aula_em_dois_dias_e_conflito_em_dia_comum(self):
        self._agendar([0, 2])
        t = Turma.objects.get()
        self.assertEqual(t.dias, [0, 2])
        self.assertTrue(t.data_valida(SEGUNDA + timedelta(days=2)))  # quarta
        self.assertFalse(t.data_valida(SEGUNDA + timedelta(days=1)))  # terça
        resp = self._agendar([2], nome="Outra")
        self.assertContains(resp, "Já existe uma aula nesta sala")
        resp = self.client.get(reverse("aulas:agenda"), {"dia": 2})
        self.assertContains(resp, "Forró")

    def test_vigencia_limita_chamada_e_cobranca(self):
        self._agendar([0], vigencia_inicio="01/12/2026", vigencia_fim="31/01/2027", valor_mensal="80")
        t = Turma.objects.get()
        self.assertFalse(t.data_valida(SEGUNDA))  # 02/11/2026: antes do início
        self.assertTrue(t.data_valida(date(2026, 12, 7)))
        t.alunos.add(criar_aluno())
        Matricula.objects.update(data_inicio=date(2026, 10, 1))
        self.assertEqual(gerar_cobrancas(date(2026, 11, 1)), 0)
        self.assertEqual(gerar_cobrancas(date(2026, 12, 1)), 1)
        self.assertEqual(Cobranca.objects.get().valor, Decimal("80.00"))


class PrimeiroAcessoTests(TestCase):
    """RF37 — troca de senha obrigatória no primeiro acesso."""

    def test_novo_acesso_exige_troca(self):
        adm = criar_usuario("adm")
        self.client.force_login(adm)
        prof = criar_professor("Nova Prof")
        provisoria, nova = senha_aleatoria(), senha_aleatoria()
        self.client.post(reverse("administradores:usuario_novo"), {
            "papel": PROFESSOR, "professor": prof.pk, "username": "nova", "first_name": "Nova",
            "email": "", "password1": provisoria, "password2": provisoria, "exigir_troca": "on"})
        self.client.logout()
        self.client.login(username="nova", password=provisoria)
        self.assertRedirects(self.client.get(reverse("index")), reverse("trocar_senha"))
        self.assertRedirects(self.client.get(reverse("aulas:agenda")), reverse("trocar_senha"))
        self.client.post(reverse("trocar_senha"), {"old_password": provisoria,
                                                  "new_password1": nova, "new_password2": nova})
        self.assertRedirects(self.client.get(reverse("index")), reverse("professores:minha_area"))


class MeusAlunosTests(TestCase):
    """RF38 — professor vê a lista de alunos das próprias aulas."""

    def test_so_alunos_das_proprias_aulas(self):
        u = criar_usuario("prof", papel=PROFESSOR)
        prof = criar_professor("Camila", usuario=u)
        minha = criar_turma(professor=prof)
        alheia = criar_turma(professor=criar_professor("Outro"), dia=1)
        minha.alunos.add(criar_aluno("Aluna da Camila", telefone="(13) 99999-0000"))
        alheia.alunos.add(criar_aluno("Aluno Alheio"))
        criar_presenca(minha, Aluno.objects.get(nome="Aluna da Camila"))
        self.client.force_login(u)
        resp = self.client.get(reverse("professores:meus_alunos"))
        self.assertContains(resp, "Aluna da Camila")
        self.assertContains(resp, "(13) 99999-0000")
        self.assertContains(resp, "100%")
        self.assertNotContains(resp, "Aluno Alheio")

    def test_aluno_nao_acessa(self):
        u = criar_usuario("ana", papel=ALUNO)
        criar_aluno("Ana", usuario=u)
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("professores:meus_alunos")).status_code, 403)
