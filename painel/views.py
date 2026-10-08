from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from eventos.models import Evento, Repasse
from pedidos.models import Pedido
from .exports import csv_participantes

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
    total_a_repassar = ZERO
    for evento in Evento.objects.select_related("produtor"):
        pedidos_pagos = evento.pedidos.filter(status="pago")
        if pedidos_pagos.exists() or evento.publicado:
            t = _totais(pedidos_pagos)
            t["evento"] = evento
            repasse = getattr(evento, "repasse_controle", None)
            valor_pago = repasse.valor_pago if repasse else ZERO
            t["repasse_pago_em"] = repasse.pago_em if repasse else None
            t["repasse_valor_pago"] = valor_pago
            t["repasse_pendente"] = max(t["repasse_produtor"] - valor_pago, ZERO)
            total_a_repassar += t["repasse_pendente"]
            eventos.append(t)

    geral = _totais(Pedido.objects.filter(status="pago"))
    pendentes = Pedido.objects.filter(status="pendente").count()

    return render(request, "painel/dashboard.html", {
        "eventos": eventos, "geral": geral, "pendentes": pendentes,
        "total_a_repassar": total_a_repassar,
    })


@staff_member_required
@require_POST
def marcar_repasse(request, evento_id):
    """Marca (ou desfaz) o repasse do evento como pago ao produtor."""
    evento = get_object_or_404(Evento, pk=evento_id)
    repasse, _ = Repasse.objects.get_or_create(evento=evento)

    if request.POST.get("desfazer"):
        repasse.valor_pago = ZERO
        repasse.pago_em = None
        repasse.observacao = ""
        repasse.save()
        messages.success(request, f"Repasse de '{evento.titulo}' voltou para pendente.")
        return redirect("painel_dashboard")

    devido = evento.pedidos.filter(status="pago").aggregate(s=Sum("subtotal"))["s"] or ZERO
    pendente = devido - repasse.valor_pago
    if pendente <= 0:
        messages.warning(request, "Não há valor pendente para repassar neste evento.")
        return redirect("painel_dashboard")

    repasse.valor_pago = devido
    repasse.pago_em = timezone.now()
    repasse.observacao = request.POST.get("observacao", "").strip()[:200]
    repasse.save()
    messages.success(
        request,
        f"Repasse de '{evento.titulo}' marcado como pago (R$ {pendente:.2f}).",
    )
    return redirect("painel_dashboard")


@staff_member_required
def exportar_participantes(request, evento_id):
    """Lista de participantes do evento em CSV (abre no Excel)."""
    evento = get_object_or_404(Evento, pk=evento_id)
    return csv_participantes(evento)


@staff_member_required
def pedidos_evento(request, evento_id):
    evento = Evento.objects.get(pk=evento_id)
    pedidos = evento.pedidos.prefetch_related("itens__tipo_ingresso")
    return render(request, "painel/pedidos.html", {
        "evento": evento, "pedidos": pedidos, "totais": _totais(pedidos.filter(status="pago")),
    })
