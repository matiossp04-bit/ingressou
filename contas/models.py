from django.contrib.auth import get_user_model
from django.db import models


class Perfil(models.Model):
    """Perfil do usuário: define o nível de acesso (comprador ou produtor)."""

    TIPOS = [
        ("comprador", "Comprador (CPF) — compra ingressos"),
        ("produtor", "Produtor (CNPJ) — cria eventos"),
        ("recepcao", "Recepção — valida ingressos na entrada do evento"),
    ]

    usuario = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name="perfil")
    tipo = models.CharField(max_length=10, choices=TIPOS)
    documento = models.CharField("CPF/CNPJ", max_length=18, unique=True)
    data_nascimento = models.DateField("Data de nascimento", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.email} ({self.get_tipo_display()})"

    @property
    def eh_produtor(self):
        return self.tipo == "produtor"

    @property
    def eh_recepcao(self):
        return self.tipo == "recepcao"
