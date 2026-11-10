from django.db import models
from django.urls import reverse
from django.utils import timezone


class Aluno(models.Model):
    """RF01/RF02 — aluno da Portal da Dança.

    RNF04 (LGPD): apenas os dados necessários à gestão da escola são coletados
    (minimização). Não há CPF, endereço ou dados sensíveis de saúde, já que a
    escola não exige exame/atestado médico (RN08).
    """

    nome = models.CharField("nome completo", max_length=150)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    observacoes = models.TextField("observações", blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "aluno"
        verbose_name_plural = "alunos"

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("alunos:detalhe", args=[self.pk])

    def ultima_mensalidade(self):
        return (
            self.movimentacoes.filter(origem="mensalidade")
            .order_by("-data_pagamento", "-pk")
            .first()
        )

    def mensalidade_em_dia(self, data=None):
        """Informativo apenas: RN08 proíbe bloquear o aluno por pagamento."""
        data = data or timezone.localdate()
        return self.movimentacoes.filter(
            origem="mensalidade", validade__gte=data
        ).exists()

    def total_presencas(self):
        return self.presencas.filter(presente=True).count()

    def total_faltas(self):
        return self.presencas.filter(presente=False).count()
