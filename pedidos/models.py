import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.utils import timezone

from eventos.models import Configuracao, Evento, TipoIngresso

CENT = Decimal("0.01")


def q2(valor):
    return Decimal(valor).quantize(CENT, rounding=ROUND_HALF_UP)


class Pedido(models.Model):
    STATUS = [
        ("pendente", "Pendente"),
        ("pago", "Pago"),
        ("cancelado", "Cancelado"),
        ("expirado", "Expirado"),
    ]
    METODOS = [
        ("", "Não definido"),
        ("pix", "Pix"),
        ("cartao", "Cartão de crédito"),
        ("gratuito", "Gratuito (lista VIP)"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name="pedidos")
    comprador_nome = models.CharField(max_length=200)
    comprador_email = models.EmailField()
    comprador_cpf = models.CharField(max_length=14)
    comprador_whatsapp = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="pendente")
    metodo_pagamento = models.CharField(max_length=10, choices=METODOS, default="", blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                   help_text="Valor dos ingressos — repassado EXATO ao produtor.")
    taxa_plataforma = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                help_text="Total pago pelo comprador (subtotal + taxa).")
    custo_gateway = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        help_text="Taxa do Mercado Pago, calculada quando o pagamento é confirmado.")
    imposto = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                  help_text="Imposto do Ingressou sobre a taxa da plataforma.")

    mp_payment_id = models.CharField(max_length=50, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    pago_em = models.DateTimeField(null=True, blank=True)
    expira_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Pedido {str(self.uuid)[:8]} — {self.evento.titulo}"

    # ---- cálculos financeiros ----

    def calcular_totais(self):
        config = Configuracao.get_solo()
        self.subtotal = q2(sum(i.quantidade * i.preco_unitario for i in self.itens.all()))
        self.taxa_plataforma = q2(self.subtotal * config.taxa_plataforma / 100)
        self.total = self.subtotal + self.taxa_plataforma
        self.imposto = q2(self.taxa_plataforma * config.aliquota_imposto / 100)

    def confirmar_pagamento(self, metodo, payment_id=""):
        """Marca como pago e calcula o custo real do gateway conforme o método."""
        config = Configuracao.get_solo()
        self.metodo_pagamento = metodo
        if metodo == "gratuito":
            aliquota_mp = 0  # lista VIP free: sem custo de gateway
        else:
            aliquota_mp = config.taxa_mp_pix if metodo == "pix" else config.taxa_mp_cartao
        self.custo_gateway = q2(self.total * aliquota_mp / 100)
        self.status = "pago"
        self.pago_em = timezone.now()
        self.mp_payment_id = payment_id
        self.save()
        self.gerar_ingressos()

    @property
    def repasse_produtor(self):
        """O produtor recebe exatamente o preço que ele definiu. Impostos da parte dele são por conta dele."""
        return self.subtotal

    @property
    def lucro_plataforma(self):
        """Quanto sobra para o Ingressou: taxa - custo do gateway - imposto."""
        return self.taxa_plataforma - self.custo_gateway - self.imposto

    @property
    def expirado(self):
        return self.status == "pendente" and self.expira_em and timezone.now() > self.expira_em

    def gerar_ingressos(self):
        for item in self.itens.all():
            for _ in range(item.quantidade):
                ingresso = Ingresso.objects.create(item=item)
                ingresso.gerar_qrcode()


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    tipo_ingresso = models.ForeignKey(TipoIngresso, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2,
                                         help_text="Cópia do preço no momento da compra (preços mudam, o histórico não).")

    def __str__(self):
        return f"{self.quantidade}x {self.tipo_ingresso.nome}"

    @property
    def total(self):
        return self.quantidade * self.preco_unitario


class Ingresso(models.Model):
    item = models.ForeignKey(ItemPedido, on_delete=models.CASCADE, related_name="ingressos")
    codigo = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qrcode = models.ImageField(upload_to="qrcodes/", blank=True)
    usado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ingresso {str(self.codigo)[:8]}"

    @property
    def validado(self):
        return self.usado_em is not None

    def gerar_qrcode(self):
        import io
        import qrcode
        from django.core.files.base import ContentFile

        url = f"/validar/{self.codigo}/"
        img = qrcode.make(url)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        self.qrcode.save(f"{self.codigo}.png", ContentFile(buffer.getvalue()), save=True)
