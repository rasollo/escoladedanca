from django.conf import settings
from django.db import models


class ContaAcesso(models.Model):
    """Dados de acesso que o usuário padrão do Django não tem."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="conta")
    deve_trocar_senha = models.BooleanField(
        "trocar a senha no próximo acesso", default=False,
        help_text="A senha foi definida pela administração; o usuário escolhe a dele ao entrar.")

    class Meta:
        verbose_name = "conta de acesso"
        verbose_name_plural = "contas de acesso"

    def __str__(self):
        return str(self.usuario)


def deve_trocar_senha(user) -> bool:
    return ContaAcesso.objects.filter(usuario=user, deve_trocar_senha=True).exists()


def marcar_troca_de_senha(user, exigir: bool):
    ContaAcesso.objects.update_or_create(usuario=user, defaults={"deve_trocar_senha": exigir})
