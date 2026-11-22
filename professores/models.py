from django.conf import settings
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Professor(models.Model):
    """RF17 — professor responsável pelas aulas."""

    nome = models.CharField("nome completo", max_length=150)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    # RF26 — opcional; usada só na lista de aniversariantes (dia e mês).
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    # RN07 / RF13: a remuneração tem como base a quantidade de alunos inscritos
    # (matriculados) nas aulas do professor no mês. O valor por aluno é
    # configurável porque o relatório não informa o valor praticado pela escola.
    valor_por_aluno = models.DecimalField(
        "valor por aluno inscrito (R$/mês)",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Salário do mês = inscrições ativas nas aulas do professor × este valor.",
    )
    # RF25 — acesso ao portal: login usado por este professor (opcional).
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="professor", verbose_name="usuário de acesso",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "professor"
        verbose_name_plural = "professores"

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("professores:detalhe", args=[self.pk])
