"""Integração com Mercado Pago.

MODO SIMULADO (padrão): enquanto MP_ACCESS_TOKEN não estiver no .env,
o pagamento é simulado localmente — ideal para testar todo o fluxo.

MODO REAL: basta preencher MP_ACCESS_TOKEN e MP_PUBLIC_KEY no .env.
O Checkout Pro do Mercado Pago redireciona o comprador para a página
segura deles (Pix ou cartão) e confirma via webhook — nenhum dado de
cartão passa pelo Ingressou.
"""

from django.conf import settings


def mercado_pago_ativo():
    return bool(settings.MP_ACCESS_TOKEN)


def criar_preferencia(pedido, request):
    """Cria a preferência de pagamento no Mercado Pago (Checkout Pro).

    Retorna a URL para redirecionar o comprador, ou None em modo simulado.
    """
    if not mercado_pago_ativo():
        return None

    import mercadopago

    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    itens = [
        {
            "title": f"{item.tipo_ingresso.nome} — {pedido.evento.titulo}",
            "quantity": item.quantidade,
            "unit_price": float(item.preco_unitario),
            "currency_id": "BRL",
        }
        for item in pedido.itens.all()
    ]
    # A taxa da plataforma entra como item separado — transparente no checkout do MP
    itens.append({
        "title": "Taxa de serviço Ingressou",
        "quantity": 1,
        "unit_price": float(pedido.taxa_plataforma),
        "currency_id": "BRL",
    })

    base = settings.SITE_URL.rstrip("/")
    preferencia = sdk.preference().create({
        "items": itens,
        "payer": {
            "name": pedido.comprador_nome,
            "email": pedido.comprador_email,
        },
        "external_reference": str(pedido.uuid),
        "back_urls": {
            "success": f"{base}/pedido/{pedido.uuid}/confirmado/",
            "failure": f"{base}/pagamento/{pedido.uuid}/",
            "pending": f"{base}/pagamento/{pedido.uuid}/",
        },
        "notification_url": f"{base}/pagamentos/webhook/",
        "statement_descriptor": "INGRESSOU",
    })
    resposta = preferencia.get("response", {})
    # Com credenciais de teste, o checkout correto é o sandbox
    if settings.MP_SANDBOX:
        return resposta.get("sandbox_init_point") or resposta.get("init_point")
    return resposta.get("init_point") or resposta.get("sandbox_init_point")


def consultar_pagamento(payment_id):
    """Consulta um pagamento no Mercado Pago. Retorna dict ou None."""
    if not mercado_pago_ativo():
        return None

    import mercadopago

    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    resposta = sdk.payment().get(payment_id)
    return resposta.get("response")
