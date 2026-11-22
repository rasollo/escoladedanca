from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AdministradoresConfig(AppConfig):
    name = 'administradores'

    def ready(self):
        # Conecta os sinais de auditoria (login, logout, alterações de dados).
        from escoladedanca import auditoria  # noqa: F401
        # RF25 — cria os grupos Administrativo, Professor e Aluno após o migrate.
        from escoladedanca.rbac import criar_grupos
        post_migrate.connect(criar_grupos, sender=self)
        # Django 6.1 usa "- Select an option -" nas listas, ainda sem tradução
        # para o português; a troca no ready() é a forma documentada.
        from django.db.models import fields
        fields.BLANK_CHOICE_LABEL = "- Selecione -"
