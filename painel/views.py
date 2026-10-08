from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.shortcuts import render

from eventos.models import Evento
from pedidos.models import Pedido

ZERO = Decimal("0")


def _totais(pedidos):
    agg = pedidos.aggregate(
        bruto=Sum("total"), subtotal=Sum("subtotal"), taxa=Sum("taxa_plataforma"),
        gateway=Sum("custo_gateway"), imposto=Sum("imposto"),
    )
    bruto = agg["bruto"] or ZERO
    subtotal = agg["subtotal"] or ZERO
    taxa = agg["taxa"] or ZERO
    gateway = agg["gateway"] or ZERO
    imposto = agg["imposto"] or ZERO
    return {
        "vendas": pedidos.count(),
        "receita_bruta": bruto,          # tudo que entrou (comprador pagou)
        "custo_gateway": gateway,        # taxa do Mercado Pago
        "imposto_plataforma": imposto,   # imposto do Ingressou sobre a taxa
        "repasse_produtor": subtotal,    # exato para o produtor (impostos dele são dele)
        "taxa_plataforma": taxa,         # os 17%
        "lucro_plataforma": taxa - gateway - imposto,  # o que sobra para o Ingressou
    }


@staff_member_required
def dashboard(request):
    eventos = []
    for evento in Evento.objects.select_related("produtor"):
        pedidos_pagos = evento.pedidos.filter(status="pago")
        if pedidos_pagos.exists() or evento.publicado:
            t = _totais(pedidos_pagos)
            t["evento"] = evento
            eventos.append(t)

    geral = _totais(Pedido.objects.filter(status="pago"))
    pendentes = Pedido.objects.filter(status="pendente").count()

    return render(request, "painel/dashboard.html", {
        "eventos": eventos, "geral": geral, "pendentes": pendentes,
    })


@staff_member_required
def pedidos_evento(request, evento_id):
    evento = Evento.objects.get(pk=evento_id)
    pedidos = evento.pedidos.prefetch_related("itens__tipo_ingresso")
    return render(request, "painel/pedidos.html", {
        "evento": evento, "pedidos": pedidos, "totais": _totais(pedidos.filter(status="pago")),
    })
