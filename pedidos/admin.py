from django.contrib import admin, messages

from . import services
from .emails import enviar_aviso_reembolso
from .models import Ingresso, ItemPedido, Pedido


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    readonly_fields = ("tipo_ingresso", "quantidade", "preco_unitario")
    can_delete = False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("uuid_curto", "evento", "comprador_nome", "status",
                    "metodo_pagamento", "total", "lucro_plataforma", "criado_em")
    list_filter = ("status", "metodo_pagamento", "evento")
    search_fields = ("comprador_nome", "comprador_email", "uuid")
    readonly_fields = ("uuid", "subtotal", "taxa_plataforma", "total",
                       "custo_gateway", "imposto", "repasse_produtor",
                       "lucro_plataforma", "pago_em", "mp_payment_id")
    inlines = [ItemPedidoInline]
    actions = ["estornar_pedidos"]

    def uuid_curto(self, obj):
        return str(obj.uuid)[:8]
    uuid_curto.short_description = "Pedido"

    @admin.action(description="💸 Estornar no Mercado Pago e concluir reembolso")
    def estornar_pedidos(self, request, queryset):
        """Estorna pedidos com 'reembolso_solicitado' (ou pagos) e invalida os ingressos."""
        for pedido in queryset:
            if pedido.status not in ("reembolso_solicitado", "pago"):
                self.message_user(
                    request,
                    f"Pedido {str(pedido.uuid)[:8]}: status '{pedido.get_status_display()}' não permite estorno.",
                    messages.WARNING,
                )
                continue

            if pedido.metodo_pagamento in ("pix", "cartao") and pedido.mp_payment_id:
                ok, detalhe = services.estornar_pagamento(pedido.mp_payment_id)
                if not ok:
                    self.message_user(
                        request,
                        f"Pedido {str(pedido.uuid)[:8]}: FALHA no estorno MP — {detalhe}",
                        messages.ERROR,
                    )
                    continue

            pedido.concluir_reembolso()
            enviar_aviso_reembolso(pedido)
            self.message_user(
                request,
                f"Pedido {str(pedido.uuid)[:8]}: reembolsado — R$ {pedido.total} devolvidos, "
                "ingressos cancelados e estoque liberado. ✅",
                messages.SUCCESS,
            )


@admin.register(Ingresso)
class IngressoAdmin(admin.ModelAdmin):
    list_display = ("codigo_curto", "evento", "validado", "usado_em")
    list_filter = ("item__pedido__evento",)
    search_fields = ("codigo",)

    def codigo_curto(self, obj):
        return str(obj.codigo)[:8]
    codigo_curto.short_description = "Código"

    def evento(self, obj):
        return obj.item.pedido.evento.titulo
