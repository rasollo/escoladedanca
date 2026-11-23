"""Comando criar_usuarios_padrao (local, fora do repositório)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from escoladedanca.rbac import PROFESSOR, papeis_do
from escoladedanca.testutils import criar_aluno, criar_professor, criar_turma

class UsuariosPadraoTests(TestCase):
    """Comando criar_usuarios_padrao: idempotente e sem apagar nada."""

    def _rodar(self, *args):
        from io import StringIO
        from django.core.management import call_command
        saida = StringIO()
        call_command("criar_usuarios_padrao", *args, stdout=saida)
        return saida.getvalue()

    def test_banco_vazio_cria_so_o_responsavel(self):
        saida = self._rodar("--senha", "senha-forte-123x")
        self.assertTrue(get_user_model().objects.get(username="responsavel").is_superuser)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertIn("nenhum cadastro ativo", saida)

    def test_vincula_professor_e_aluno_e_nao_duplica(self):
        from django.contrib.auth import authenticate
        from administradores.models import deve_trocar_senha
        prof = criar_professor("Juliana Prado")
        turma = criar_turma(professor=prof)
        aluna = criar_aluno("Bianca Souza")
        turma.alunos.add(aluna)
        self._rodar("--senha", "senha-forte-123x", "--trocar-senha")
        prof.refresh_from_db()
        aluna.refresh_from_db()
        self.assertEqual((prof.usuario.username, aluna.usuario.username), ("juliana.prado", "bianca.souza"))
        self.assertEqual(papeis_do(prof.usuario), [PROFESSOR])
        self.assertTrue(deve_trocar_senha(aluna.usuario))
        self.assertIsNotNone(authenticate(username="juliana.prado", password="senha-forte-123x"))
        total = get_user_model().objects.count()
        saida = self._rodar("--senha", "outra-senha-456y")
        self.assertEqual(get_user_model().objects.count(), total)
        self.assertIn("já tinha acesso", saida)
        self.assertIsNotNone(authenticate(username="responsavel", password="senha-forte-123x"))

    def test_escolhe_professor_pelo_nome(self):
        criar_professor("Ana Primeira")
        escolhido = criar_professor("Zeca Escolhido")
        self._rodar("--senha", "senha-forte-123x", "--professor", "Zeca Escolhido")
        escolhido.refresh_from_db()
        self.assertEqual(escolhido.usuario.username, "zeca.escolhido")
