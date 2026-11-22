from django.conf import settings
from django.db import models


class Comunicado(models.Model):
    """Aviso publicado para uma turma (administração ou professor da turma)."""

    turma = models.ForeignKey("aulas.Turma", on_delete=models.PROTECT, related_name="comunicados")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              related_name="comunicados")
    titulo = models.CharField("título", max_length=120)
    mensagem = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "comunicado"
        verbose_name_plural = "comunicados"

    def __str__(self):
        return f"{self.titulo} ({self.turma})"


class Solicitacao(models.Model):
    """Pedido do aluno à administração; não altera nenhum dado automaticamente."""

    class Tipo(models.TextChoices):
        CADASTRO = "cadastro", "Correção cadastral"
        FREQUENCIA = "frequencia", "Revisão de frequência"
        MATRICULA = "matricula", "Alteração de matrícula"
        FINANCEIRO = "financeiro", "Dúvida sobre mensalidade"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EM_ANALISE = "em_analise", "Em análise"
        CONCLUIDA = "concluida", "Concluída"
        RECUSADA = "recusada", "Recusada"

    aluno = models.ForeignKey("alunos.Aluno", on_delete=models.PROTECT, related_name="solicitacoes")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    mensagem = models.TextField(max_length=1000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    resposta = models.TextField("resposta da administração", blank=True)
    respondido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "solicitação"
        verbose_name_plural = "solicitações"

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.aluno}"

    @property
    def aberta(self):
        return self.status in (self.Status.PENDENTE, self.Status.EM_ANALISE)
