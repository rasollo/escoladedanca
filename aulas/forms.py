from django import forms
from django.core.exceptions import ValidationError

from alunos.models import Aluno
from professores.models import Professor

from .models import Modalidade, Sala, Turma

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
                  "professor", "ativa"]
        widgets = {"hora_inicio": TIME, "hora_fim": TIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["professor"].queryset = Professor.objects.filter(ativo=True)


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

    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

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
