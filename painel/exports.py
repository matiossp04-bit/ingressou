"""Exportação de lista de participantes em CSV (abre direto no Excel)."""
import csv

from django.http import HttpResponse
from django.utils import timezone


def csv_participantes(evento):
    """Uma linha por ingresso (pedidos pagos). UTF-8 com BOM para o Excel
    reconhecer acentos."""
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f'attachment; filename="participantes-{evento.slug}.csv"'
    )
    resposta.write("﻿")  # BOM

    writer = csv.writer(resposta, delimiter=";")
    writer.writerow([
        "Nome do comprador", "E-mail", "CPF", "Tipo de ingresso",
        "Preço unitário (R$)", "Comprado em", "Código do ingresso",
        "Check-in", "Status na entrada",
    ])

    pedidos = (
        evento.pedidos.filter(status="pago")
        .prefetch_related("itens__tipo_ingresso", "itens__ingressos")
        .order_by("pago_em")
    )
    for pedido in pedidos:
        for item in pedido.itens.all():
            for ingresso in item.ingressos.all():
                writer.writerow([
                    pedido.comprador_nome,
                    pedido.comprador_email,
                    pedido.comprador_cpf,
                    item.tipo_ingresso.nome,
                    str(item.preco_unitario).replace(".", ","),
                    timezone.localtime(pedido.pago_em).strftime("%d/%m/%Y %H:%M") if pedido.pago_em else "",
                    str(ingresso.codigo),
                    timezone.localtime(ingresso.usado_em).strftime("%d/%m/%Y %H:%M") if ingresso.usado_em else "",
                    "Já entrou" if ingresso.validado else "Não entrou",
                ])
    return resposta
