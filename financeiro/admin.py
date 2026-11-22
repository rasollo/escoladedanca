from django.contrib import admin

from .models import Cobranca, Movimentacao


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ["data_pagamento", "tipo", "valor", "origem", "categoria", "forma_pagamento"]
    list_filter = ["tipo", "origem", "categoria", "forma_pagamento"]
    date_hierarchy = "data_pagamento"
    search_fields = ["descricao", "aluno__nome", "professor__nome"]


@admin.register(Cobranca)
class CobrancaAdmin(admin.ModelAdmin):
    list_display = ["competencia", "aluno", "matricula", "valor", "vencimento", "cancelada"]
    list_filter = ["competencia", "cancelada"]
    search_fields = ["aluno__nome"]
    raw_id_fields = ["matricula", "aluno"]
