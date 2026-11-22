from decimal import Decimal

from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from alunos.models import Aluno
from escoladedanca.utils import DataBR
from professores.models import Professor

from .models import Matricula, Modalidade, Sala, Turma

TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class ModalidadeForm(forms.ModelForm):
    class Meta:
        model = Modalidade
        fields = ["nome", "descricao"]


class SalaForm(forms.ModelForm):
    class Meta:
        model = Sala
        fields = ["nome", "capacidade"]


class TurmaForm(forms.ModelForm):
    """RF19 / RN10 — agendamento prévio com modalidade, dia, horário, sala e professor."""

    class Meta:
        model = Turma
        fields = ["nome", "modalidade", "dia_semana", "hora_inicio", "hora_fim", "sala",
                  "professor", "valor_mensal", "ativa"]
        widgets = {"hora_inicio": TIME, "hora_fim": TIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "professor" in self.fields:
            self.fields["professor"].queryset = Professor.objects.filter(ativo=True)
        if "valor_mensal" in self.fields:
            self.fields["valor_mensal"].required = False

    def clean_valor_mensal(self):
        return self.cleaned_data.get("valor_mensal") or Decimal("0.00")


class TurmaProfessorForm(TurmaForm):
    """RF25 — o professor agenda/edita apenas as próprias aulas.

    O professor responsável é fixado no usuário logado. As validações do modelo
    continuam valendo: lotação da sala (RN09), horário 18h–22h (RN13) e
    conflitos de sala e de professor (RN14). Desativar ou remover aulas segue
    com o Administrativo.
    """

    class Meta(TurmaForm.Meta):
        fields = ["nome", "modalidade", "dia_semana", "hora_inicio", "hora_fim", "sala"]

    def __init__(self, *args, professor, **kwargs):
        super().__init__(*args, **kwargs)
        # Definido antes da validação para o modelo checar conflitos do professor.
        self.instance.professor = professor

    def _update_errors(self, errors):
        # O campo "professor" não aparece neste formulário: o choque de horário
        # do professor (RN14) vira mensagem geral do formulário.
        if hasattr(errors, "error_dict") and "professor" in errors.error_dict:
            mensagens = errors.error_dict.pop("professor")
            errors.error_dict.setdefault(NON_FIELD_ERRORS, []).extend(mensagens)
        super()._update_errors(errors)


class MatriculaFinanceiroForm(forms.ModelForm):
    """Mensalidade combinada e desconto de uma matrícula (base das cobranças)."""

    class Meta:
        model = Matricula
        fields = ["valor_mensal", "desconto_tipo", "desconto"]


class VinculoAlunosForm(forms.Form):
    """RF20 / RF21 — vínculo de alunos à turma respeitando a capacidade da sala."""

    alunos = forms.ModelMultipleChoiceField(
        queryset=Aluno.objects.filter(ativo=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Alunos que frequentam esta aula",
    )

    def __init__(self, *args, turma: Turma, **kwargs):
        self.turma = turma
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["alunos"] = list(turma.alunos.values_list("pk", flat=True))

    def clean_alunos(self):
        alunos = self.cleaned_data["alunos"]
        self.turma.validar_quantidade(len(alunos))
        return alunos

    def save(self):
        self.turma.alunos.set(self.cleaned_data["alunos"])
        return self.turma


class FiltroAgendaForm(forms.Form):
    """RF05 — filtros opcionais da agenda (fluxo 14)."""

    dia = forms.TypedChoiceField(
        required=False, coerce=int, empty_value=None,
        choices=[("", "Todos os dias")] + list(Turma.DiaSemana.choices),
    )
    modalidade = forms.ModelChoiceField(
        queryset=Modalidade.objects.all(), required=False, empty_label="Todas as modalidades"
    )
    sala = forms.ModelChoiceField(
        queryset=Sala.objects.all(), required=False, empty_label="Todas as salas"
    )


class ChamadaForm(forms.Form):
    """RF03 / RF04 — escolha da data da aula para registrar presença/falta."""

    data = forms.DateField(widget=DataBR())

    def __init__(self, *args, turma: Turma, **kwargs):
        self.turma = turma
        super().__init__(*args, **kwargs)

    def clean_data(self):
        data = self.cleaned_data["data"]
        if not self.turma.data_valida(data):
            raise ValidationError(
                f"Esta aula acontece às {self.turma.get_dia_semana_display()}s."
            )
        return data
