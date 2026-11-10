from django.apps import AppConfig


class AdministradoresConfig(AppConfig):
    name = 'administradores'

    def ready(self):
        # Conecta os sinais de auditoria (login, logout, alterações de dados).
        from escoladedanca import auditoria  # noqa: F401
