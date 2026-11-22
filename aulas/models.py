from contextvars import ContextVar
from datetime import time
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone


def _hora(valor: str) -> time:
    h, m = valor.split(":")
    return time(int(h), int(m))


def horario_abertura() -> time:
    return _hora(settings.ESCOLA_HORARIO_ABERTURA)


def horario_fechamento() -> time:
    return _hora(settings.ESCOLA_HORARIO_FECHAMENTO)


class Modalidade(models.Model):
    """RF18 — modalidade / estilo de dança (forró, zouk, salsa...)."""

    nome = models.CharField(max_length=60, unique=True)
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Sala(models.Model):
    """RN09 — a escola possui duas salas com capacidade de até 40 alunos."""

    nome = models.CharField(max_length=40, unique=True)
    capacidade = models.PositiveSmallIntegerField(
        default=40, validators=[MinValueValidator(1)]
    )

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} (até {self.capacidade} alunos)"


class Turma(models.Model):
    """RF18/RF19 — aula agendada previamente (RN10).

    Uma turma é a aula semanal recorrente: modalidade, sala, dia, horário e
    professor responsável. Os alunos são vinculados sem matrícula obrigatória
    (RF21 / RN08).
    """

    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 0, "Segunda-feira"
        TERCA = 1, "Terça-feira"
        QUARTA = 2, "Quarta-feira"
        QUINTA = 3, "Quinta-feira"
        SEXTA = 4, "Sexta-feira"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    nome = models.CharField(
        max_length=80, blank=True, help_text="Ex.: Forró iniciante. Opcional."
    )
    modalidade = models.ForeignKey(
        Modalidade, on_delete=models.PROTECT, related_name="turmas"
    )
    professor = models.ForeignKey(
        "professores.Professor", on_delete=models.PROTECT, related_name="turmas",
        verbose_name="professor responsável",
    )
    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, related_name="turmas")
    dia_semana = models.IntegerField("dia", choices=DiaSemana.choices,
                                     help_text="Primeiro dia da semana da aula.")
    # Aula em mais de um dia da semana (mesmo horário): demais dias, ex.: "2,4".
    outros_dias = models.CharField("outros dias", max_length=20, blank=True, default="")
    # Vigência opcional (ex.: turma de verão); vazio = sem data de início/fim.
    vigencia_inicio = models.DateField("início das aulas", null=True, blank=True)
    vigencia_fim = models.DateField("fim das aulas", null=True, blank=True)
    hora_inicio = models.TimeField("início")
    hora_fim = models.TimeField("término")
    alunos = models.ManyToManyField(
        "alunos.Aluno", related_name="turmas", blank=True,
        verbose_name="alunos vinculados",
    )
    # Cobranças: mensalidade cobrada por matrícula nesta aula (0 = sem cobrança).
    valor_mensal = models.DecimalField(
        "mensalidade da aula (R$)", max_digits=8, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Valor mensal cobrado de cada aluno matriculado. Use 0 para não gerar cobrança.",
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["dia_semana", "hora_inicio", "sala__nome"]
        verbose_name = "aula agendada"
        verbose_name_plural = "aulas agendadas"

    def __str__(self):
        titulo = self.nome or self.modalidade.nome
        return (
            f"{titulo} — {self.get_dias_display()} "
            f"{self.hora_inicio:%H:%M}–{self.hora_fim:%H:%M} ({self.sala.nome})"
        )

    def get_absolute_url(self):
        return reverse("aulas:turma_detalhe", args=[self.pk])

    # ---- regras de agendamento -------------------------------------------------
    def clean(self):
        erros = {}
        if self.hora_inicio and self.hora_fim:
            if self.hora_fim <= self.hora_inicio:
                erros["hora_fim"] = "O término deve ser depois do início."
            abre, fecha = horario_abertura(), horario_fechamento()
            if self.hora_inicio < abre or self.hora_fim > fecha:
                erros["hora_inicio"] = (
                    f"A escola funciona das {abre:%H:%M} às {fecha:%H:%M}."
                )
        if erros:
            raise ValidationError(erros)

        if self.vigencia_inicio and self.vigencia_fim and self.vigencia_fim < self.vigencia_inicio:
            raise ValidationError({"vigencia_fim": "O fim das aulas deve ser depois do início."})
        if self.dia_semana is None or not (self.hora_inicio and self.hora_fim):
            return
        # RN14 — conflito em qualquer dia em comum, no mesmo horário e período de vigência
        meus_dias = set(self.dias)
        candidatas = [
            t for t in Turma.objects.filter(
                ativa=True, hora_inicio__lt=self.hora_fim, hora_fim__gt=self.hora_inicio,
            ).exclude(pk=self.pk)
            if meus_dias & set(t.dias) and self._vigencias_se_cruzam(t)
        ]
        if self.ativa and self.sala_id and any(t.sala_id == self.sala_id for t in candidatas):
            erros["sala"] = "Já existe uma aula nesta sala neste dia e horário."
        if self.ativa and self.professor_id and any(
                t.professor_id == self.professor_id for t in candidatas):
            erros["professor"] = "O professor já tem outra aula neste dia e horário."
        if self.pk and self.sala_id:
            total = self.alunos.count()
            if total > self.sala.capacidade:
                erros["sala"] = (
                    f"A turma tem {total} alunos vinculados e a sala comporta "
                    f"{self.sala.capacidade}."
                )
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Desativar a aula encerra as matrículas abertas (deixa de gerar salário).
        if not self.ativa:
            self.alunos.clear()

    # ---- RF20: quantidade e capacidade ---------------------------------------------
    @property
    def capacidade(self):
        return self.sala.capacidade

    def quantidade_alunos(self):
        return self.alunos.count()

    def vagas_restantes(self):
        return max(self.capacidade - self.quantidade_alunos(), 0)

    def validar_quantidade(self, quantidade: int):
        if quantidade > self.capacidade:
            raise ValidationError(
                f"A sala {self.sala.nome} comporta até {self.capacidade} alunos "
                f"({quantidade} selecionados). Revise a quantidade ou organize "
                "outra turma."
            )

    # ---- dias da semana e vigência -------------------------------------------------
    @property
    def dias(self) -> list[int]:
        extras = {int(d) for d in self.outros_dias.split(",") if d.strip().isdigit()}
        return sorted({self.dia_semana, *extras} - {None})

    def definir_dias(self, dias):
        dias = sorted({int(d) for d in dias})
        self.dia_semana = dias[0]
        self.outros_dias = ",".join(str(d) for d in dias[1:])

    def get_dias_display(self) -> str:
        rotulos = dict(self.DiaSemana.choices)
        if len(self.dias) == 1:
            return rotulos[self.dias[0]]
        return " · ".join(rotulos[d].replace("-feira", "") for d in self.dias)

    def acontece_em(self, dia_da_semana: int) -> bool:
        return dia_da_semana in self.dias

    def vigente_em(self, data) -> bool:
        if self.vigencia_inicio and data < self.vigencia_inicio:
            return False
        if self.vigencia_fim and data > self.vigencia_fim:
            return False
        return True

    def vigente_no_periodo(self, inicio, fim) -> bool:
        return not ((self.vigencia_fim and self.vigencia_fim < inicio)
                    or (self.vigencia_inicio and self.vigencia_inicio > fim))

    def _vigencias_se_cruzam(self, outra) -> bool:
        from datetime import date as _d
        ini = self.vigencia_inicio or _d.min
        fim = self.vigencia_fim or _d.max
        return outra.vigente_no_periodo(ini, fim)

    def data_valida(self, data) -> bool:
        return self.acontece_em(data.weekday()) and self.vigente_em(data)

    def mensagem_data_invalida(self, data) -> str:
        if not self.vigente_em(data):
            return "Esta data está fora do período de aulas desta turma."
        return f"Esta aula acontece: {self.get_dias_display()}."


class Presenca(models.Model):
    """RF03/RF04 — registro de presença ou falta de um aluno em uma aula.

    Pode registrar alunos não vinculados à turma (aluno avulso), pois a escola
    não exige matrícula para participar (RN08).
    """

    # PROTECT: remover uma aula não pode apagar o histórico de presenças que
    # serve de base para o salário dos professores (RN07 / RNF05).
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="presencas")
    aluno = models.ForeignKey(
        "alunos.Aluno", on_delete=models.CASCADE, related_name="presencas"
    )
    data = models.DateField()
    presente = models.BooleanField(default=True)
    registrado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "aluno__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["turma", "aluno", "data"], name="presenca_unica_por_aula"
            )
        ]
        verbose_name = "presença/falta"
        verbose_name_plural = "presenças e faltas"

    def __str__(self):
        status = "Presente" if self.presente else "Falta"
        return f"{self.aluno} — {self.turma} — {self.data:%d/%m/%Y}: {status}"

    def clean(self):
        if self.turma_id and self.data and not self.turma.data_valida(self.data):
            raise ValidationError({"data": self.turma.mensagem_data_invalida(self.data)})


class Chamada(models.Model):
    """Situação da chamada de uma aula em uma data.

    Aberta: professor e administração marcam presenças. Concluída: só a
    administração corrige, com motivo. Cancelada: a aula não aconteceu.
    """

    class Situacao(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="chamadas")
    data = models.DateField()
    situacao = models.CharField("situação", max_length=10, choices=Situacao.choices,
                                default=Situacao.ABERTA)
    motivo = models.CharField("motivo (cancelamento ou última correção)", max_length=200, blank=True)
    atualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="+")
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data"]
        constraints = [models.UniqueConstraint(fields=["turma", "data"], name="uma_chamada_por_aula_e_data")]
        verbose_name = "chamada"
        verbose_name_plural = "chamadas"

    def __str__(self):
        return f"{self.turma} — {self.data:%d/%m/%Y}: {self.get_situacao_display()}"


def pode_editar_chamada(papel, situacao) -> bool:
    """Aluno nunca edita; professor só edita chamada aberta; administração sempre,
    exceto aula cancelada (precisa reabrir antes)."""
    from escoladedanca.rbac import ADMINISTRATIVO, PROFESSOR
    if situacao == Chamada.Situacao.CANCELADA:
        return False
    if papel == ADMINISTRATIVO:
        return True
    return papel == PROFESSOR and situacao != Chamada.Situacao.CONCLUIDA


class Matricula(models.Model):
    """RF21 / RN07 — inscrição do aluno em uma aula, com início e fim.

    O vínculo atual (Turma.alunos) diz quem está inscrito agora; a matrícula
    guarda o histórico e é a base do salário do professor: cada inscrição ativa
    no mês conta uma vez. É criada e encerrada automaticamente sempre que o
    vínculo muda (ver sincronizar_matriculas). A matrícula não é condição para
    participar da aula: alunos avulsos podem ter presença (RN08), mas não contam
    para o salário.
    """

    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="matriculas")
    aluno = models.ForeignKey("alunos.Aluno", on_delete=models.PROTECT, related_name="matriculas")
    data_inicio = models.DateField("início")
    data_fim = models.DateField("fim", null=True, blank=True)

    class Situacao(models.TextChoices):
        ATIVA = "ativa", "Ativa"
        SUSPENSA = "suspensa", "Suspensa"
        CANCELADA = "cancelada", "Cancelada"
        ENCERRADA = "encerrada", "Encerrada"

    situacao = models.CharField("situação", max_length=10, choices=Situacao.choices,
                                default=Situacao.ATIVA)
    motivo = models.CharField("motivo do encerramento", max_length=200, blank=True)

    class TipoDesconto(models.TextChoices):
        NENHUM = "nenhum", "Sem desconto"
        PERCENTUAL = "percentual", "Percentual (%)"
        FIXO = "fixo", "Valor fixo (R$)"

    # Mensalidade combinada na matrícula (copiada da aula ao matricular, para que
    # um reajuste da aula não altere matrículas já feitas) e desconto opcional.
    valor_mensal = models.DecimalField(
        "mensalidade (R$)", max_digits=8, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    desconto_tipo = models.CharField(
        "tipo de desconto", max_length=10, choices=TipoDesconto.choices,
        default=TipoDesconto.NENHUM,
    )
    desconto = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Percentual (0 a 100) ou valor em reais, conforme o tipo.",
    )

    class Meta:
        ordering = ["-data_inicio", "aluno__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["turma", "aluno"], condition=Q(data_fim__isnull=True),
                name="uma_matricula_aberta_por_aula",
            ),
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_fim__gte=F("data_inicio")),
                name="matricula_fim_apos_inicio",
            ),
        ]
        verbose_name = "matrícula"
        verbose_name_plural = "matrículas"

    def __str__(self):
        fim = f" até {self.data_fim:%d/%m/%Y}" if self.data_fim else ""
        return f"{self.aluno} em {self.turma} desde {self.data_inicio:%d/%m/%Y}{fim}"

    @property
    def ativa(self):
        return self.data_fim is None

    @property
    def valor_final(self) -> Decimal:
        """Mensalidade com desconto, nunca negativa."""
        if self.desconto_tipo == self.TipoDesconto.PERCENTUAL:
            abatimento = (self.valor_mensal * self.desconto / 100).quantize(Decimal("0.01"))
        elif self.desconto_tipo == self.TipoDesconto.FIXO:
            abatimento = self.desconto
        else:
            abatimento = Decimal("0.00")
        return max(self.valor_mensal - abatimento, Decimal("0.00"))

    def clean(self):
        if self.desconto_tipo == self.TipoDesconto.PERCENTUAL and self.desconto > 100:
            raise ValidationError({"desconto": "O desconto percentual vai de 0 a 100."})
        if self.desconto_tipo == self.TipoDesconto.FIXO and self.desconto > self.valor_mensal:
            raise ValidationError({"desconto": "O desconto não pode ser maior que a mensalidade."})
        if self.desconto_tipo == self.TipoDesconto.NENHUM and self.desconto:
            raise ValidationError({"desconto": "Escolha o tipo de desconto ou deixe o valor em 0."})

    @classmethod
    def ativas_no_periodo(cls, inicio, fim):
        """Inscrições que estiveram ativas em algum dia do período.

        Matrículas abertas e encerradas no mesmo dia (inscrição feita por engano)
        não contam.
        """
        return cls.objects.filter(data_inicio__lte=fim).filter(
            Q(data_fim__isnull=True) | Q(data_fim__gte=inicio, data_fim__gt=F("data_inicio"))
        )


# Restauração de backup: as matrículas vêm do próprio arquivo e não devem ser
# recriadas a partir do vínculo aluno–aula.
IMPORTANDO_BACKUP = ContextVar("importando_backup", default=False)


@receiver(m2m_changed, sender=Turma.alunos.through)
def sincronizar_matriculas(sender, instance, action, reverse, pk_set, **kwargs):
    """Mantém o histórico de matrículas igual ao vínculo atual, venha a mudança
    da tela, do admin ou do shell (turma.alunos.add/remove/set/clear)."""
    if IMPORTANDO_BACKUP.get():
        return
    hoje = timezone.localdate()
    if action == "post_add":
        pares = [(p, instance.pk) for p in pk_set] if reverse else [(instance.pk, p) for p in pk_set]
        valores = dict(Turma.objects.filter(pk__in={t for t, _ in pares})
                       .values_list("pk", "valor_mensal"))
        for turma_id, aluno_id in pares:
            Matricula.objects.get_or_create(
                turma_id=turma_id, aluno_id=aluno_id, data_fim=None,
                defaults={"data_inicio": hoje, "valor_mensal": valores.get(turma_id, 0)},
            )
    elif action in ("post_remove", "pre_clear"):
        abertas = Matricula.objects.filter(data_fim__isnull=True)
        if reverse:
            abertas = abertas.filter(aluno_id=instance.pk)
            if action == "post_remove":
                abertas = abertas.filter(turma_id__in=pk_set)
        else:
            abertas = abertas.filter(turma_id=instance.pk)
            if action == "post_remove":
                abertas = abertas.filter(aluno_id__in=pk_set)
        # Sem motivo informado (vínculo removido na tela da aula): "encerrada".
        abertas.update(data_fim=hoje, situacao=Matricula.Situacao.ENCERRADA)
