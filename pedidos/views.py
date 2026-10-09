from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from eventos.models import Configuracao, Evento, TipoIngresso
from . import services
from .emails import enviar_ingressos
from .models import Ingresso, ItemPedido, Pedido


def _pode_validar(user):
    """Staff ou conta do tipo Recepção podem bipar ingressos na entrada."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    perfil = getattr(user, "perfil", None)
    return bool(perfil and perfil.eh_recepcao)


def recepcao_required(view):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not _pode_validar(request.user):
            messages.error(request, "Esta área é exclusiva da equipe de recepção.")
            return redirect("home")
        return view(request, *args, **kwargs)
    return wrapper


def _pode_bipar_evento(user, evento_id):
    """Staff bipa qualquer evento; conta de recepção só bipa os eventos
    que o produtor liberou para ela."""
    if user.is_staff:
        return True
    perfil = getattr(user, "perfil", None)
    return bool(perfil and perfil.eventos_liberados.filter(pk=evento_id).exists())


@require_POST
def comprar(request, slug):
    """Recebe as quantidades escolhidas na página do evento e abre o checkout."""
    evento = get_object_or_404(Evento, slug=slug, publicado=True)
    selecao = {}
    for tipo in evento.tipos_disponiveis:
        qtd = int(request.POST.get(f"tipo_{tipo.id}", 0) or 0)
        if qtd > 0:
            selecao[str(tipo.id)] = min(qtd, tipo.max_por_pedido)
    if not selecao:
        messages.warning(request, "Escolha pelo menos um ingresso.")
        return redirect("evento_detalhe", slug=slug)
    request.session["selecao"] = {"evento_id": evento.id, "itens": selecao}
    return redirect("checkout")


def checkout(request):
    """Dados do comprador + resumo com valores discrimindos (ingresso + taxa 17% + total)."""
    selecao = request.session.get("selecao")
    if not selecao:
        return redirect("home")

    evento = get_object_or_404(Evento, pk=selecao["evento_id"], publicado=True)
    config = Configuracao.get_solo()
    linhas, subtotal = [], 0
    for tipo_id, qtd in selecao["itens"].items():
        tipo = get_object_or_404(TipoIngresso, pk=tipo_id, evento=evento, ativo=True)
        total_linha = tipo.preco * qtd
        subtotal += total_linha
        linhas.append({"tipo": tipo, "quantidade": qtd, "total": total_linha})

    taxa = (subtotal * config.taxa_plataforma / 100).quantize(Decimal("0.01"))
    total = subtotal + taxa

    if request.method == "POST":
        pedido = _criar_pedido(request, evento, selecao)
        if pedido:
            del request.session["selecao"]
            return redirect("pagamento", uuid=pedido.uuid)
        messages.error(request, "Ingressos esgotados para um dos tipos escolhidos. Tente novamente.")
        return redirect("evento_detalhe", slug=evento.slug)

    return render(request, "pedidos/checkout.html", {
        "evento": evento, "linhas": linhas, "subtotal": subtotal,
        "taxa": taxa, "total": total, "config": config,
    })


@transaction.atomic
def _criar_pedido(request, evento, selecao):
    """Cria o pedido pendente reservando estoque com lock (sem vender além da capacidade)."""
    config = Configuracao.get_solo()
    tipos = {
        t.id: t
        for t in TipoIngresso.objects.select_for_update().filter(pk__in=selecao["itens"].keys())
    }
    pedido = Pedido.objects.create(
        evento=evento,
        comprador_nome=request.POST["nome"],
        comprador_email=request.POST["email"],
        comprador_cpf=request.POST["cpf"],
        expira_em=timezone.now() + timedelta(minutes=config.minutos_expiracao_pedido),
    )
    for tipo_id, qtd in selecao["itens"].items():
        tipo = tipos[int(tipo_id)]
        if tipo.disponivel < qtd:
            transaction.set_rollback(True)
            return None
        tipo.quantidade_vendida += qtd
        tipo.save(update_fields=["quantidade_vendida"])
        ItemPedido.objects.create(
            pedido=pedido, tipo_ingresso=tipo, quantidade=qtd, preco_unitario=tipo.preco
        )
    pedido.calcular_totais()
    pedido.save()
    return pedido


def pagamento(request, uuid):
    pedido = get_object_or_404(Pedido, uuid=uuid)
    if pedido.status == "pago":
        return redirect("pedido_confirmado", uuid=uuid)
    if pedido.expirado:
        return render(request, "pedidos/expirado.html", {"pedido": pedido})

    url_mp = None
    if services.mercado_pago_ativo():
        url_mp = services.criar_preferencia(pedido, request)

    return render(request, "pedidos/pagamento.html", {
        "pedido": pedido, "url_mp": url_mp, "modo_simulado": not services.mercado_pago_ativo(),
    })


@require_POST
def simular_pagamento(request, uuid):
    """Modo simulado: confirma o pagamento sem Mercado Pago (somente DEBUG)."""
    from django.conf import settings

    if settings.DEBUG is False:
        return redirect("home")
    pedido = get_object_or_404(Pedido, uuid=uuid, status="pendente")
    metodo = request.POST.get("metodo", "pix")
    pedido.confirmar_pagamento(metodo if metodo in ("pix", "cartao") else "pix")
    enviar_ingressos(pedido)
    return redirect("pedido_confirmado", uuid=uuid)


@csrf_exempt
@require_POST
def webhook_mercado_pago(request):
    """O Mercado Pago confirma o pagamento aqui — única fonte confiável de confirmação."""
    payment_id = request.POST.get("data.id") or request.GET.get("data.id")
    if not payment_id:
        return JsonResponse({"ok": True})

    dados = services.consultar_pagamento(payment_id)
    if dados and dados.get("status") == "approved":
        try:
            pedido = Pedido.objects.get(uuid=dados.get("external_reference"), status="pendente")
        except Pedido.DoesNotExist:
            return JsonResponse({"ok": True})
        tipo_pagamento = dados.get("payment_type_id", "")
        metodo = "pix" if tipo_pagamento == "bank_transfer" else "cartao"
        pedido.confirmar_pagamento(metodo, payment_id=str(payment_id))
        enviar_ingressos(pedido)
    return JsonResponse({"ok": True})


def meus_ingressos(request):
    """Comprador recupera seus ingressos com e-mail + CPF (sem precisar de conta)."""
    pedidos = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        cpf = request.POST.get("cpf", "").strip()
        pedidos = (
            Pedido.objects.filter(comprador_email__iexact=email, comprador_cpf=cpf, status="pago")
            .select_related("evento")
            .prefetch_related("itens__ingressos", "itens__tipo_ingresso")
        )
        if not pedidos.exists():
            messages.warning(request, "Nenhum pedido pago encontrado para esse e-mail e CPF.")
    return render(request, "pedidos/meus_ingressos.html", {"pedidos": pedidos})


@require_POST
def reenviar_ingressos(request, uuid):
    pedido = get_object_or_404(Pedido, uuid=uuid, status="pago")
    if enviar_ingressos(pedido):
        messages.success(request, "Ingressos reenviados para seu e-mail!")
    else:
        messages.error(request, "Não conseguimos reenviar agora. Tente novamente em instantes.")
    return redirect("meus_ingressos")


def pedido_confirmado(request, uuid):
    pedido = get_object_or_404(Pedido, uuid=uuid)
    return render(request, "pedidos/confirmado.html", {"pedido": pedido})


@recepcao_required
def validar_ingresso(request, codigo):
    """Página de validação na entrada do evento (recepção/staff, logada)."""
    ingresso = get_object_or_404(Ingresso, codigo=codigo)
    if not _pode_bipar_evento(request.user, ingresso.item.pedido.evento_id):
        messages.error(
            request,
            f"Este ingresso é do evento '{ingresso.item.pedido.evento.titulo}', "
            "que a sua conta de portaria não está autorizada a bipar.",
        )
        return redirect("recepcao")
    if request.method == "POST" and not ingresso.validado:
        ingresso.usado_em = timezone.now()
        ingresso.save(update_fields=["usado_em"])
        messages.success(request, "Ingresso validado. Boa festa!")
    return render(request, "pedidos/validar.html", {"ingresso": ingresso})


@recepcao_required
def recepcao(request):
    """Tela de scanner da portaria: bipa QR codes em sequência com a câmera."""
    return render(request, "pedidos/recepcao.html")


@recepcao_required
@require_POST
def bipar_ingresso(request):
    """API da portaria: dá baixa no ingresso pelo código lido no QR.

    Respostas: ok (liberado) | repetido (já usado) | invalido (não existe).
    """
    codigo = (request.POST.get("codigo") or "").strip().lower()
    # O QR contém /validar/<uuid>/ — extrai só o uuid
    import re
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", codigo)
    if not m:
        return JsonResponse({"status": "invalido"}, status=404)

    with transaction.atomic():
        ingresso = (
            Ingresso.objects.select_for_update()
            .select_related("item__tipo_ingresso", "item__pedido__evento")
            .filter(codigo=m.group(1))
            .first()
        )
        if not ingresso:
            return JsonResponse({"status": "invalido"}, status=404)

        if not _pode_bipar_evento(request.user, ingresso.item.pedido.evento_id):
            return JsonResponse(
                {"status": "sem_permissao", "evento": ingresso.item.pedido.evento.titulo},
                status=403,
            )

        dados = {
            "tipo": ingresso.item.tipo_ingresso.nome,
            "evento": ingresso.item.pedido.evento.titulo,
            "comprador": ingresso.item.pedido.comprador_nome,
        }
        if ingresso.validado:
            dados["status"] = "repetido"
            dados["usado_em"] = timezone.localtime(ingresso.usado_em).strftime("%H:%M")
            return JsonResponse(dados, status=409)

        ingresso.usado_em = timezone.now()
        ingresso.save(update_fields=["usado_em"])

    dados["status"] = "ok"
    return JsonResponse(dados)
