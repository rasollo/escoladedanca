from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Movimentacao(models.Model):
    """RF06–RF12 / RN01–RN07 / RN11 — movimentação financeira diária.

    Um único modelo representa entradas e saídas, o que garante que o saldo e o
    balanço mensal sejam calculados sobre a mesma fonte (RNF05).
    """

    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"

    class FormaPagamento(models.TextChoices):  # RN12
        PIX = "pix", "Pix"
        DINHEIRO = "dinheiro", "Dinheiro"
        CARTAO = "cartao", "Cartão"

    class Origem(models.TextChoices):  # RN02
        MENSALIDADE = "mensalidade", "Mensalidade"
        ALUGUEL_SALA = "aluguel_sala", "Aluguel de sala"
        BEBIDAS = "bebidas", "Bebidas"
        CAMISETAS = "camisetas", "Camisetas"

    class Categoria(models.TextChoices):  # RN03
        CONTAS_GERAIS = "contas_gerais", "Contas em geral"
        MANUTENCAO = "manutencao", "Manutenção"
        LUZ = "luz", "Luz"
        AGUA = "agua", "Água"
        TAXAS = "taxas", "Taxas"
        PREFEITURA = "prefeitura", "Prefeitura"
        SALARIO = "salario", "Salário de professor"

    tipo = models.CharField(max_length=7, choices=Tipo.choices)
    valor = models.DecimalField(
        "valor (R$)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    data_pagamento = models.DateField("data do pagamento")
    validade = models.DateField(
        null=True, blank=True,
        help_text="Quando aplicável (ex.: até quando a mensalidade vale).",
    )
    descricao = models.CharField("descrição", max_length=200, blank=True)
    forma_pagamento = models.CharField(
        "forma de pagamento", max_length=10, choices=FormaPagamento.choices, blank=True
    )
    origem = models.CharField(max_length=20, choices=Origem.choices, blank=True)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, blank=True)
    aluno = models.ForeignKey(
        "alunos.Aluno", on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimentacoes",
    )
    professor = models.ForeignKey(
        "professores.Professor", on_delete=models.PROTECT, null=True, blank=True,
        related_name="pagamentos",
    )
    # Período de referência do salário (RF13): mês/ano das presenças usadas no cálculo.
    referencia = models.DateField(
        "mês de referência", null=True, blank=True,
        help_text="Para salários: primeiro dia do mês calculado.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_pagamento", "-pk"]
        verbose_name = "movimentação financeira"
        verbose_name_plural = "movimentações financeiras"

    def __str__(self):
        sinal = "+" if self.tipo == self.Tipo.ENTRADA else "−"
        return f"{self.data_pagamento:%d/%m/%Y} {sinal} R$ {self.valor} ({self.classificacao})"

    @property
    def classificacao(self):
        if self.tipo == self.Tipo.ENTRADA:
            return self.get_origem_display()
        return self.get_categoria_display()

    @property
    def valor_com_sinal(self):
        return self.valor if self.tipo == self.Tipo.ENTRADA else -self.valor

    def clean(self):
        erros = {}
        if self.tipo == self.Tipo.ENTRADA:
            # RN02 / RN12 — entrada indica forma de pagamento e origem
            if not self.forma_pagamento:
                erros["forma_pagamento"] = "Informe a forma de pagamento (Pix, dinheiro ou cartão)."
            if not self.origem:
                erros["origem"] = "Informe a origem da entrada."
            if self.categoria:
                erros["categoria"] = "Categoria de saída não se aplica a uma entrada."
            if self.professor_id:
                erros["professor"] = "Professor só é informado em pagamento de salário."
            # RN06 — mensalidade é entrada de um aluno
            if self.origem == self.Origem.MENSALIDADE and not self.aluno_id:
                erros["aluno"] = "Selecione o aluno da mensalidade."
        elif self.tipo == self.Tipo.SAIDA:
            # RN03 — saídas classificadas nas categorias da escola
            if not self.categoria:
                erros["categoria"] = "Informe a categoria da saída."
            if self.origem:
                erros["origem"] = "Origem de entrada não se aplica a uma saída."
            if self.aluno_id:
                erros["aluno"] = "Aluno só é informado em entradas."
            # RN07 — salário é saída vinculada a um professor
            if self.categoria == self.Categoria.SALARIO and not self.professor_id:
                erros["professor"] = "Selecione o professor do salário."
            if self.categoria != self.Categoria.SALARIO and self.professor_id:
                erros["professor"] = "Professor só é informado na categoria salário."
        else:
            erros["tipo"] = "A movimentação deve ser uma entrada ou uma saída."  # RN01

        # RN04 — validade não pode ser anterior ao pagamento
        if self.validade and self.data_pagamento and self.validade < self.data_pagamento:
            erros["validade"] = "A validade não pode ser anterior à data do pagamento."
        if erros:
            raise ValidationError(erros)
