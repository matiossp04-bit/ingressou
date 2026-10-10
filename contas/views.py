from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q, Sum
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, redirect, render
from decimal import Decimal

from eventos.models import Evento, ListaVIP, TipoIngresso
from painel.exports import csv_participantes
from pedidos.models import Pedido
from .forms import CriarContaForm, ContaPortariaForm, EditarPortariaForm, GerarListaVIPForm
from .forms_evento import CriarEventoForm, GerenciarIngressoForm, PrimeiroIngressoForm
from .models import Perfil

IngressoFormSet = formset_factory(
    PrimeiroIngressoForm, extra=1, min_num=1, validate_min=True, max_num=15, validate_max=True
)


@login_required(login_url="/conta/entrar/")
def minha_conta(request):
    perfil = getattr(request.user, "perfil", None)
    if perfil and perfil.eh_recepcao:
        # Conta de portaria cai direto na tela de scanner
        return redirect("recepcao")
    contexto = {}
    if request.user.is_staff:
        contexto["requerimentos_pendentes"] = Evento.objects.filter(publicado=False).count()
    return render(request, "contas/conta.html", contexto)


def criar_conta(request):
    if request.user.is_authenticated:
        return redirect("minha_conta")
    form = CriarContaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.salvar()
        login(request, usuario)
        if usuario.perfil.eh_produtor:
            messages.success(request, "Conta de produtor criada! Solicite o cadastro do seu primeiro evento à equipe Ingressou.")
        else:
            messages.success(request, "Conta criada! Agora é só escolher seu próximo evento. 🎉")
        return redirect("minha_conta")
    return render(request, "contas/criar.html", {"form": form})


@login_required(login_url="/conta/entrar/")
def area_produtor(request):
    """Área do produtor (conta CNPJ): seus eventos, vendas e repasses."""
    perfil = getattr(request.user, "perfil", None)
    if not perfil or not perfil.eh_produtor:
        messages.warning(request, "A área do produtor é exclusiva para contas CNPJ.")
        return redirect("minha_conta")

    produtor = getattr(request.user, "produtor", None)
    if not produtor:
        # Conta CNPJ ainda não vinculada a um cadastro de produtor pelo admin
        return render(request, "contas/produtor_sem_vinculo.html")

    eventos = (
        produtor.eventos.prefetch_related("tipos_ingresso")
        .annotate(
            vendas=Count("pedidos", filter=Q(pedidos__status="pago")),
            repasse=Sum("pedidos__subtotal", filter=Q(pedidos__status="pago")),
        )
    )
    total_repasse = sum(e.repasse or 0 for e in eventos)
    total_vendas = sum(e.vendas or 0 for e in eventos)

    # Painel geral: métricas agregadas de todos os eventos do produtor
    pedidos = list(
        Pedido.objects.filter(evento__produtor=produtor, status="pago")
        .prefetch_related("itens__tipo_ingresso")
    )
    metricas = _metricas_vendas(pedidos)

    return render(request, "contas/area_produtor.html", {
        "produtor": produtor, "eventos": eventos,
        "total_repasse": total_repasse, "total_vendas": total_vendas,
        **metricas,
    })


def _produtor_do_usuario(request):
    perfil = getattr(request.user, "perfil", None)
    if not perfil or not perfil.eh_produtor:
        return None, redirect("minha_conta")
    produtor = getattr(request.user, "produtor", None)
    if not produtor:
        return None, render(request, "contas/produtor_sem_vinculo.html")
    return produtor, None


def _metricas_vendas(pedidos):
    """Métricas e roscas (vendas por método / público) de uma lista de pedidos pagos.

    Usada tanto no dashboard do evento quanto no painel geral da área do produtor.
    """
    def qtd_ingressos(ps):
        return sum(i.quantidade for p in ps for i in p.itens.all())

    total_vendido = sum(p.subtotal for p in pedidos)
    n_pedidos = len(pedidos)
    n_ingressos = qtd_ingressos(pedidos)

    # Rosca "Vendas" por método de pagamento (R$ e quantidade de ingressos)
    metodos = [("pix", "Pix", "#111827"), ("cartao", "Cartão", "#8b9dc3"), ("gratuito", "Gratuito (lista VIP)", "#f87171")]
    vendas_rosca = []
    for chave, rotulo, cor in metodos:
        ps = [p for p in pedidos if p.metodo_pagamento == chave]
        valor = sum(p.subtotal for p in ps)
        qtd = qtd_ingressos(ps)
        if valor or qtd:
            vendas_rosca.append({"rotulo": rotulo, "valor": valor, "qtd": qtd, "cor": cor})

    # Rosca "Público": pagantes vs gratuitos (lista VIP free)
    pagantes = [p for p in pedidos if p.metodo_pagamento != "gratuito"]
    gratis = [p for p in pedidos if p.metodo_pagamento == "gratuito"]
    publico_rosca = [
        {"rotulo": "Pagantes", "qtd": qtd_ingressos(pagantes), "cor": "#1e3a8a"},
        {"rotulo": "Lista VIP free", "qtd": qtd_ingressos(gratis), "cor": "#f87171"},
    ]

    def gradiente(fatias, chave_valor):
        """Monta o conic-gradient da rosca a partir das fatias."""
        total = sum(f[chave_valor] for f in fatias) or 1
        partes, acum = [], 0.0
        for f in fatias:
            pct = float(f[chave_valor]) / float(total) * 100
            partes.append(f"{f['cor']} {acum:.1f}% {acum + pct:.1f}%")
            acum += pct
        return ", ".join(partes) if partes else "#e5e7eb 0% 100%"

    return {
        "total_vendido": total_vendido,
        "n_ingressos": n_ingressos,
        "ticket_pedido": (total_vendido / n_pedidos) if n_pedidos else 0,
        "ticket_ingresso": (total_vendido / n_ingressos) if n_ingressos else 0,
        "vendas_rosca": vendas_rosca,
        "vendas_gradiente": gradiente(vendas_rosca, "valor"),
        "publico_rosca": publico_rosca,
        "publico_gradiente": gradiente([f for f in publico_rosca if f["qtd"]], "qtd"),
    }


@login_required(login_url="/conta/entrar/")
def gerenciar_ingressos(request, evento_id):
    """Produtor gerencia os tipos de ingresso do seu evento:
    adicionar, editar, ativar/desativar, excluir (sem vendas) e montar lotes."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta
    evento = get_object_or_404(Evento, pk=evento_id, produtor=produtor)

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "adicionar":
            form = GerenciarIngressoForm(request.POST)
            if form.is_valid():
                dados = form.cleaned_data
                eh_lote = dados.pop("lote")
                ordem = 0
                if eh_lote:
                    ordem = (evento.tipos_ingresso.aggregate(m=Max("ordem"))["m"] or 0) + 1
                TipoIngresso.objects.create(evento=evento, ordem=ordem, **dados)
                messages.success(request, f"Ingresso '{dados['nome']}' adicionado!")
            else:
                messages.error(request, "Confira os campos do novo ingresso.")
            return redirect("gerenciar_ingressos", evento_id=evento.id)

        tipo = get_object_or_404(TipoIngresso, pk=request.POST.get("tipo_id"), evento=evento)

        if acao == "alternar":
            tipo.ativo = not tipo.ativo
            tipo.save(update_fields=["ativo"])
            messages.success(request, f"'{tipo.nome}' {'reativado' if tipo.ativo else 'pausado'}.")
        elif acao == "excluir":
            if tipo.quantidade_vendida > 0:
                messages.error(request, f"'{tipo.nome}' já tem vendas — não dá para excluir, apenas pausar.")
            else:
                nome = tipo.nome
                tipo.delete()
                messages.success(request, f"'{nome}' excluído.")
        elif acao == "editar":
            nome = request.POST.get("nome", "").strip()
            try:
                preco = Decimal(request.POST.get("preco", "0"))
                quantidade = int(request.POST.get("quantidade_total", "0"))
            except (ValueError, ArithmeticError):
                messages.error(request, "Preço ou quantidade inválidos.")
                return redirect("gerenciar_ingressos", evento_id=evento.id)
            if not nome or preco < 1 or quantidade < 1:
                messages.error(request, "Preencha nome, preço (mín. R$ 1) e quantidade.")
            elif quantidade < tipo.quantidade_vendida:
                messages.error(
                    request,
                    f"'{tipo.nome}' já vendeu {tipo.quantidade_vendida} — a quantidade não pode ser menor que isso.",
                )
            else:
                tipo.nome, tipo.preco, tipo.quantidade_total = nome, preco, quantidade
                tipo.save(update_fields=["nome", "preco", "quantidade_total"])
                messages.success(request, f"'{nome}' atualizado!")
        return redirect("gerenciar_ingressos", evento_id=evento.id)

    tipos_visiveis = evento.tipos_ingresso.filter(lista_vip_origem__isnull=True)
    return render(request, "contas/gerenciar_ingressos.html", {
        "evento": evento,
        "tipos": tipos_visiveis,
        "vendaveis_ids": {t.id for t in evento.tipos_disponiveis},
        "espera_ids": {t.id for t in evento.lotes_em_espera},
        "form": GerenciarIngressoForm(),
    })


@login_required(login_url="/conta/entrar/")
def exportar_participantes_produtor(request, evento_id):
    """Produtor baixa a lista de participantes do próprio evento."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta
    evento = get_object_or_404(Evento, pk=evento_id, produtor=produtor)
    return csv_participantes(evento)


@login_required(login_url="/conta/entrar/")
def portaria(request):
    """Produtor gerencia as contas de portaria (recepção) dos seus eventos."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta
    contas = (
        Perfil.objects.filter(tipo="recepcao", produtor=produtor)
        .select_related("usuario")
        .prefetch_related("eventos_liberados")
        .order_by("usuario__first_name")
    )
    return render(request, "contas/portaria.html", {"produtor": produtor, "contas": contas})


@login_required(login_url="/conta/entrar/")
def portaria_nova(request):
    """Produtor cria uma conta de portaria escolhendo os eventos que ela pode bipar."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta
    form = ContaPortariaForm(produtor, request.POST or None)
    if request.method == "POST" and form.is_valid():
        perfil = form.salvar(produtor)
        messages.success(
            request,
            f"Conta de portaria criada para '{perfil.usuario.first_name}'! "
            f"Passe o e-mail e a senha para a equipe — eles entram em 'Minha conta' e caem direto no scanner.",
        )
        return redirect("portaria")
    return render(request, "contas/portaria_form.html", {
        "form": form, "titulo_pagina": "Nova conta de portaria",
    })


@login_required(login_url="/conta/entrar/")
def portaria_editar(request, perfil_id):
    """Edita eventos liberados / senha de uma conta de portaria, ou a exclui."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta
    perfil = get_object_or_404(Perfil, pk=perfil_id, tipo="recepcao", produtor=produtor)

    if request.method == "POST" and request.POST.get("acao") == "excluir":
        nome = perfil.usuario.first_name
        perfil.usuario.delete()  # apaga usuário e perfil em cascata
        messages.success(request, f"Conta de portaria '{nome}' excluída.")
        return redirect("portaria")

    form = EditarPortariaForm(produtor, perfil, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.salvar(perfil)
        messages.success(request, f"Conta '{perfil.usuario.first_name}' atualizada!")
        return redirect("portaria")
    return render(request, "contas/portaria_form.html", {
        "form": form, "titulo_pagina": f"Editar conta — {perfil.usuario.first_name}",
        "editando": perfil,
    })


@login_required(login_url="/conta/entrar/")
def dashboard_evento(request, evento_id):
    """Dashboard do evento (estilo Clube do Ingresso): total vendido, ingressos,
    tickets médios, roscas de vendas/público, URL e QR de divulgação.

    Filtro opcional por período: ?inicio=AAAA-MM-DD&fim=AAAA-MM-DD (sobre pago_em).
    """
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta
    evento = get_object_or_404(Evento, pk=evento_id, produtor=produtor)

    pedidos = (
        Pedido.objects.filter(evento=evento, status="pago")
        .prefetch_related("itens__tipo_ingresso")
        .order_by("-pago_em")
    )
    inicio, fim = request.GET.get("inicio", ""), request.GET.get("fim", "")

    from datetime import datetime

    def data_valida(valor):
        try:
            datetime.strptime(valor, "%Y-%m-%d")
            return True
        except (ValueError, TypeError):
            return False

    if inicio and data_valida(inicio):
        pedidos = pedidos.filter(pago_em__date__gte=inicio)
    else:
        inicio = ""
    if fim and data_valida(fim):
        pedidos = pedidos.filter(pago_em__date__lte=fim)
    else:
        fim = ""
    pedidos = list(pedidos)
    metricas = _metricas_vendas(pedidos)

    ultimas = [
        {
            "nome": p.comprador_nome,
            "itens": ", ".join(f"{i.quantidade}x {i.tipo_ingresso.nome}" for i in p.itens.all()),
            "total": p.total,
            "quando": p.pago_em,
            "metodo": p.get_metodo_pagamento_display(),
        }
        for p in pedidos[:8]
    ]

    # QR Code de divulgação do evento (aponta para a página pública)
    import base64
    import io

    import qrcode

    from django.urls import reverse

    url_evento = request.build_absolute_uri(reverse("evento_detalhe", args=[evento.slug]))
    img = qrcode.make(url_evento, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    qr_evento_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, "contas/dashboard_evento.html", {
        "evento": evento,
        "inicio": inicio, "fim": fim,
        **metricas,
        "vendas_total_qtd": metricas["n_ingressos"],
        "publico_total": metricas["n_ingressos"],
        "ultimas": ultimas,
        "url_evento": url_evento,
        "qr_evento_b64": qr_evento_b64,
    })


@login_required(login_url="/conta/entrar/")
def lista_vip(request):
    """Aba Lista VIP: produtor gera listas (free ou pagas) para seus eventos
    e acompanha as vagas. Cada lista tem um link de captura próprio."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "criar":
            form = GerarListaVIPForm(produtor, request.POST)
            if form.is_valid():
                lista = form.salvar()
                messages.success(
                    request,
                    f"Lista VIP {'gratuita' if lista.tipo == 'free' else 'paga'} criada para "
                    f"'{lista.evento.titulo}'! Divulgue o link de captura abaixo. 🎉",
                )
                return redirect("lista_vip")
        else:
            lista = get_object_or_404(ListaVIP, pk=request.POST.get("lista_id"), evento__produtor=produtor)
            if acao == "alternar":
                lista.ativa = not lista.ativa
                lista.save(update_fields=["ativa"])
                messages.success(request, f"Lista de '{lista.evento.titulo}' {'reativada' if lista.ativa else 'pausada'}.")
            elif acao == "excluir":
                if lista.vagas_usadas > 0:
                    messages.error(request, "Essa lista já tem gente cadastrada — não dá para excluir, apenas pausar.")
                else:
                    tipo_oculto = lista.tipo_ingresso
                    lista.delete()
                    if tipo_oculto:
                        tipo_oculto.delete()
                    messages.success(request, "Lista VIP excluída.")
            return redirect("lista_vip")
    else:
        form = GerarListaVIPForm(produtor)

    listas = (
        ListaVIP.objects.filter(evento__produtor=produtor)
        .select_related("evento", "tipo_ingresso")
        .order_by("-criado_em")
    )
    return render(request, "contas/lista_vip.html", {
        "produtor": produtor, "listas": listas, "form": form,
    })


@login_required(login_url="/conta/entrar/")
def criar_evento(request):
    """Produtor CNPJ cria seu evento. Entra como rascunho aguardando aprovação do admin."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta

    form = CriarEventoForm(request.POST or None, request.FILES or None)
    formset = IngressoFormSet(request.POST or None, prefix="ingressos")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        evento = form.save(commit=False)
        evento.local = form.local_completo()  # endereço discriminado em uma linha
        evento.produtor = produtor
        evento.publicado = False   # admin aprova antes de ir ao ar
        evento.destaque = False    # admin decide o que vai ao carrossel
        evento.save()
        tipos = 0
        proxima_ordem = 1
        for form_ingresso in formset:
            if form_ingresso.cleaned_data:
                eh_lote = form_ingresso.cleaned_data.get("lote")
                ordem = proxima_ordem if eh_lote else 0
                form_ingresso.salvar(evento, ordem=ordem)
                if eh_lote:
                    proxima_ordem += 1
                tipos += 1
        messages.success(
            request,
            f"Evento '{evento.titulo}' enviado com {tipos} tipo(s) de ingresso! "
            "Nossa equipe vai revisar e publicar em breve.",
        )
        return redirect("area_produtor")

    return render(request, "contas/criar_evento.html", {
        "form": form, "formset": formset,
    })
