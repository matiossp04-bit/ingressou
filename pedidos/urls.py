from django.urls import path

from . import views

urlpatterns = [
    path("evento/<slug:slug>/comprar/", views.comprar, name="comprar"),
    path("evento/<slug:slug>/lista-vip/", views.lista_vip_captura, name="lista_vip_captura"),
    path("checkout/", views.checkout, name="checkout"),
    path("pagamento/<uuid:uuid>/", views.pagamento, name="pagamento"),
    path("pagamento/<uuid:uuid>/simular/", views.simular_pagamento, name="simular_pagamento"),
    path("pagamentos/webhook/", views.webhook_mercado_pago, name="webhook_mp"),
    path("pedido/<uuid:uuid>/confirmado/", views.pedido_confirmado, name="pedido_confirmado"),
    path("meus-ingressos/", views.meus_ingressos, name="meus_ingressos"),
    path("pedido/<uuid:uuid>/reenviar/", views.reenviar_ingressos, name="reenviar_ingressos"),
    path("validar/<uuid:codigo>/", views.validar_ingresso, name="validar_ingresso"),
    path("recepcao/", views.recepcao, name="recepcao"),
    path("recepcao/bipar/", views.bipar_ingresso, name="bipar_ingresso"),
]
