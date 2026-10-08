from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q, Sum
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, redirect, render
from decimal import Decimal

from eventos.models import Evento, TipoIngresso
from painel.exports import csv_participantes
from .forms import CriarContaForm
from .forms_evento import CriarEventoForm, GerenciarIngressoForm, PrimeiroIngressoForm

IngressoFormSet = formset_factory(
    PrimeiroIngressoForm, extra=1, min_num=1, validate_min=True, max_num=15, validate_max=True
)


@login_required(login_url="/conta/entrar/")
def minha_conta(request):
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
    return render(request, "contas/area_produtor.html", {
        "produtor": produtor, "eventos": eventos,
        "total_repasse": total_repasse, "total_vendas": total_vendas,
    })


def _produtor_do_usuario(request):
    perfil = getattr(request.user, "perfil", None)
    if not perfil or not perfil.eh_produtor:
        return None, redirect("minha_conta")
    produtor = getattr(request.user, "produtor", None)
    if not produtor:
        return None, render(request, "contas/produtor_sem_vinculo.html")
    return produtor, None


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

    return render(request, "contas/gerenciar_ingressos.html", {
        "evento": evento,
        "tipos": evento.tipos_ingresso.all(),
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
def criar_evento(request):
    """Produtor CNPJ cria seu evento. Entra como rascunho aguardando aprovação do admin."""
    produtor, resposta = _produtor_do_usuario(request)
    if not produtor:
        return resposta

    form = CriarEventoForm(request.POST or None, request.FILES or None)
    formset = IngressoFormSet(request.POST or None, prefix="ingressos")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        evento = form.save(commit=False)
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
