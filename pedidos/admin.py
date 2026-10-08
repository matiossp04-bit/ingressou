from django.contrib import admin

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

    def uuid_curto(self, obj):
        return str(obj.uuid)[:8]
    uuid_curto.short_description = "Pedido"


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
