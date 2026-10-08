from datetime import datetime, time, timedelta

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Evento


def _fim_de_semana(qs):
    """Eventos do próximo fim de semana (sexta a domingo)."""
    hoje = timezone.localdate()
    wd = hoje.weekday()  # seg=0 ... dom=6
    domingo = hoje + timedelta(days=6 - wd)
    fim_fds = timezone.make_aware(datetime.combine(domingo, time.max))
    return qs.filter(data_inicio__lte=fim_fds).order_by("data_inicio")


def _mais_vendidos(qs):
    return (
        qs.annotate(total_vendido=Sum("tipos_ingresso__quantidade_vendida"))
        .filter(total_vendido__gt=0)
        .order_by("-total_vendido", "data_inicio")
    )


def home(request):
    qs = (
        Evento.objects.filter(publicado=True, data_inicio__gte=timezone.now())
        .prefetch_related("tipos_ingresso")
    )
    q = request.GET.get("q", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    secao = request.GET.get("secao", "").strip()

    destaques = qs.filter(destaque=True)
    if q:
        qs = qs.filter(
            Q(titulo__icontains=q) | Q(descricao__icontains=q)
            | Q(local__icontains=q) | Q(cidade__icontains=q)
        )
    if categoria:
        qs = qs.filter(categoria=categoria)

    categorias = [
        {"valor": valor, "nome": nome, "icone": Evento.CATEGORIA_ICONES.get(valor, "ticket")}
        for valor, nome in Evento.CATEGORIAS
    ]
    categoria_nome = dict(Evento.CATEGORIAS).get(categoria, "")

    contexto = {
        "q": q,
        "categorias": categorias,
        "categoria_ativa": categoria,
        "categoria_nome": categoria_nome,
        "categoria_icone": Evento.CATEGORIA_ICONES.get(categoria, "ticket"),
    }

    # Modo listagem completa: busca, categoria ou "Ver tudo" de uma seção
    if q or categoria or secao:
        if secao == "mais-vendidos":
            contexto["eventos"] = _mais_vendidos(qs)
            contexto["titulo_lista"] = "Mais vendidos"
            contexto["icone_lista"] = "flame"
        elif secao == "fim-de-semana":
            contexto["eventos"] = _fim_de_semana(qs)
            contexto["titulo_lista"] = "Nesse fim de semana"
            contexto["icone_lista"] = "calendar"
        else:
            contexto["eventos"] = qs.order_by("data_inicio")
            contexto["icone_lista"] = "ticket"
        return render(request, "eventos/home.html", contexto)

    # Home em seções (estilo Sympla)
    contexto["destaques"] = destaques
    contexto["secoes"] = [
        {"slug": "proximos", "titulo": "Próximos eventos", "icone": "ticket",
         "eventos": qs.order_by("data_inicio")[:12]},
        {"slug": "mais-vendidos", "titulo": "Mais vendidos", "icone": "flame",
         "eventos": _mais_vendidos(qs)[:12]},
        {"slug": "fim-de-semana", "titulo": "Nesse fim de semana", "icone": "calendar",
         "eventos": _fim_de_semana(qs)[:12]},
    ]
    if not any(s["eventos"] for s in contexto["secoes"]):
        contexto["eventos"] = []
        contexto["titulo_lista"] = "Próximos eventos"
        contexto["icone_lista"] = "ticket"
    return render(request, "eventos/home.html", contexto)


def evento_detalhe(request, slug):
    evento = get_object_or_404(
        Evento.objects.prefetch_related("tipos_ingresso"), slug=slug, publicado=True
    )
    return render(request, "eventos/detalhe.html", {"evento": evento})
