"""RN07 revisado: o salário passa a ser calculado por aluno inscrito (matrícula),
não mais por presença. O campo é renomeado para preservar os valores cadastrados."""
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("professores", "0001_initial")]

    operations = [
        migrations.RenameField("professor", "valor_por_presenca", "valor_por_aluno"),
        migrations.AlterField(
            model_name="professor",
            name="valor_por_aluno",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=8,
                help_text="Salário do mês = inscrições ativas nas aulas do professor × este valor.",
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
                verbose_name="valor por aluno inscrito (R$/mês)",
            ),
        ),
    ]
