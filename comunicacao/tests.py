"""Comunicados, solicitações e troca de senha por papel."""
from django.contrib.auth import authenticate
from django.test import TestCase
from django.urls import reverse

from escoladedanca.rbac import ALUNO, PROFESSOR
from escoladedanca.testutils import (criar_aluno, criar_professor, criar_turma, criar_usuario,
                                     senha_aleatoria)

from .models import Comunicado, Solicitacao


class ComunicadosTests(TestCase):
    def setUp(self):
        self.prof_user = criar_usuario("prof", papel=PROFESSOR)
        self.prof = criar_professor("Camila", usuario=self.prof_user)
        self.minha = criar_turma(professor=self.prof, nome="Forró da Camila")
        self.alheia = criar_turma(professor=criar_professor("Outro"), dia=1, nome="Zouk do Outro")
        self.aluno_user = criar_usuario("ana", papel=ALUNO)
        self.aluno = criar_aluno("Ana", usuario=self.aluno_user)
        self.minha.alunos.add(self.aluno)
        Comunicado.objects.create(turma=self.alheia, titulo="Aviso do Zouk", mensagem="x")

    def test_professor_publica_so_nas_proprias_aulas(self):
        self.client.force_login(self.prof_user)
        resp = self.client.get(reverse("comunicacao:comunicado_novo"))
        self.assertContains(resp, "Forró da Camila")
        self.assertNotContains(resp, "Zouk do Outro")
        resp = self.client.post(reverse("comunicacao:comunicado_novo"), {
            "turma": self.alheia.pk, "titulo": "Invasão", "mensagem": "não pode"})
        self.assertEqual(resp.status_code, 200)  # turma fora das opções
        self.assertFalse(Comunicado.objects.filter(titulo="Invasão").exists())
        self.client.post(reverse("comunicacao:comunicado_novo"), {
            "turma": self.minha.pk, "titulo": "Aula extra", "mensagem": "Sábado às 18h"})
        c = Comunicado.objects.get(titulo="Aula extra")
        self.assertEqual(c.autor, self.prof_user)
        resp = self.client.get(reverse("comunicacao:comunicados"))
        self.assertContains(resp, "Aula extra")
        self.assertNotContains(resp, "Aviso do Zouk")

    def test_aluno_ve_so_das_aulas_matriculadas_e_nao_publica(self):
        Comunicado.objects.create(turma=self.minha, titulo="Traje de festa", mensagem="Branco")
        self.client.force_login(self.aluno_user)
        resp = self.client.get(reverse("comunicacao:comunicados"))
        self.assertContains(resp, "Traje de festa")
        self.assertNotContains(resp, "Aviso do Zouk")
        self.assertNotContains(resp, "Novo comunicado")
        self.assertEqual(self.client.get(reverse("comunicacao:comunicado_novo")).status_code, 403)
        self.assertContains(self.client.get(reverse("alunos:minha_area")), "Traje de festa")

    def test_administrativo_publica_em_qualquer_aula(self):
        self.client.force_login(criar_usuario("adm"))
        self.client.post(reverse("comunicacao:comunicado_novo"), {
            "turma": self.alheia.pk, "titulo": "Feriado", "mensagem": "Sem aula"})
        self.assertTrue(Comunicado.objects.filter(titulo="Feriado").exists())


class SolicitacoesTests(TestCase):
    def setUp(self):
        self.aluno_user = criar_usuario("ana", papel=ALUNO)
        self.aluno = criar_aluno("Ana Solicitante", usuario=self.aluno_user)
        outro = criar_aluno("Bruno")
        Solicitacao.objects.create(aluno=outro, tipo="cadastro", mensagem="Mudei de telefone")

    def test_aluno_abre_e_ve_so_as_proprias(self):
        self.client.force_login(self.aluno_user)
        self.client.post(reverse("comunicacao:solicitacao_nova"), {
            "tipo": "frequencia", "mensagem": "Estava presente dia 10"})
        s = Solicitacao.objects.get(aluno=self.aluno)
        self.assertEqual(s.status, "pendente")
        resp = self.client.get(reverse("comunicacao:solicitacoes"))
        self.assertContains(resp, "Estava presente dia 10")
        self.assertNotContains(resp, "Mudei de telefone")
        self.assertEqual(self.client.get(
            reverse("comunicacao:solicitacao_responder", args=[s.pk])).status_code, 403)

    def test_administrativo_responde_e_recusa_exige_explicacao(self):
        s = Solicitacao.objects.get()
        adm = criar_usuario("adm")
        self.client.force_login(adm)
        resp = self.client.post(reverse("comunicacao:solicitacao_responder", args=[s.pk]),
                                {"status": "recusada", "resposta": ""})
        self.assertContains(resp, "Explique ao aluno")
        self.client.post(reverse("comunicacao:solicitacao_responder", args=[s.pk]),
                         {"status": "concluida", "resposta": "Telefone atualizado."})
        s.refresh_from_db()
        self.assertEqual((s.status, s.respondido_por), ("concluida", adm))

    def test_professor_nao_acessa_solicitacoes(self):
        user = criar_usuario("prof", papel=PROFESSOR)
        criar_professor("P", usuario=user)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("comunicacao:solicitacoes")).status_code, 403)


class TrocarSenhaTests(TestCase):
    def test_qualquer_papel_troca_a_propria_senha(self):
        antiga, nova = senha_aleatoria(), senha_aleatoria()
        user = criar_usuario("ana", papel=ALUNO, password=antiga)
        criar_aluno("Ana", usuario=user)
        self.client.force_login(user)
        resp = self.client.post(reverse("trocar_senha"), {
            "old_password": "errada", "new_password1": nova, "new_password2": nova})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse("trocar_senha"), {
            "old_password": antiga, "new_password1": nova, "new_password2": nova})
        self.assertRedirects(resp, reverse("index"), fetch_redirect_response=False)
        self.assertIsNotNone(authenticate(username="ana", password=nova))
        # a sessão continua válida após a troca
        self.assertEqual(self.client.get(reverse("alunos:minha_area")).status_code, 200)
