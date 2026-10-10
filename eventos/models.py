from decimal import Decimal

from django.db import models
from django.utils.text import slugify


class Configuracao(models.Model):
    """Configurações financeiras da plataforma (registro único, editável no admin)."""

    taxa_plataforma = models.DecimalField(
        "Taxa da plataforma (%)", max_digits=5, decimal_places=2, default=Decimal("17.00"),
        help_text="Percentual cobrado em cima do preço de cada ingresso. Ex.: 17.00",
    )
    aliquota_imposto = models.DecimalField(
        "Alíquota de imposto sobre a taxa (%)", max_digits=5, decimal_places=2, default=Decimal("15.00"),
        help_text="Imposto do Ingressou, calculado SOMENTE sobre a taxa da plataforma. Ajuste com seu contador.",
    )
    taxa_mp_pix = models.DecimalField(
        "Taxa Mercado Pago — Pix (%)", max_digits=5, decimal_places=2, default=Decimal("0.99"),
    )
    taxa_mp_cartao = models.DecimalField(
        "Taxa Mercado Pago — Cartão (%)", max_digits=5, decimal_places=2, default=Decimal("4.99"),
    )
    minutos_expiracao_pedido = models.PositiveIntegerField(
        "Minutos para expirar pedido pendente", default=30,
    )

    class Meta:
        verbose_name = "Configuração da plataforma"
        verbose_name_plural = "Configuração da plataforma"

    def __str__(self):
        return "Configuração da plataforma"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Produtor(models.Model):
    """Pessoa/empresa que organiza o evento e recebe o repasse."""

    usuario = models.OneToOneField(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="produtor",
        help_text="Conta CNPJ do produtor no site — dá acesso à área do produtor.",
    )
    nome = models.CharField(max_length=200)
    email = models.EmailField()
    telefone = models.CharField(max_length=30, blank=True)
    documento = models.CharField("CPF/CNPJ", max_length=20, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Produtor"
        verbose_name_plural = "Produtores"

    def __str__(self):
        return self.nome


class Evento(models.Model):
    CATEGORIAS = [
        ("show", "Shows"),
        ("festa", "Festas"),
        ("teatro", "Teatros e Espetáculos"),
        ("esporte", "Esportes"),
        ("standup", "Stand Up Comedy"),
        ("congresso", "Congressos e Palestras"),
        ("passeio", "Passeios e Tours"),
        ("infantil", "Infantil"),
        ("curso", "Cursos e Workshops"),
        ("gastronomia", "Gastronomia"),
        ("religiao", "Religião e Espiritualidade"),
        ("festival", "Festivais"),
        ("online", "Eventos Online"),
        ("outros", "Outros"),
    ]

    CATEGORIA_ICONES = {
        "show": "mic", "festa": "music", "teatro": "teatro", "esporte": "trofeu",
        "standup": "megafone", "congresso": "users", "passeio": "montanha", "infantil": "smile",
        "curso": "livro", "gastronomia": "talheres", "religiao": "igreja", "festival": "tenda",
        "online": "monitor", "outros": "ticket",
    }

    produtor = models.ForeignKey(Produtor, on_delete=models.PROTECT, related_name="eventos")
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    descricao = models.TextField()
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default="show")
    data_inicio = models.DateTimeField("Data e hora de início")
    data_fim = models.DateTimeField("Data e hora de término", null=True, blank=True)
    local = models.CharField(max_length=300)
    cidade = models.CharField(max_length=100)
    imagem = models.ImageField(upload_to="eventos/", blank=True, null=True,
                               help_text="Banner MENOR — aparece nos cards de eventos (proporção 16:9, ex.: 800x450).")
    banner = models.ImageField(upload_to="banners/", blank=True, null=True,
                               help_text="Banner MAIOR — aparece no carrossel da página inicial (ex.: 1600x820). Se vazio, usa o banner menor.")
    destaque = models.BooleanField("Evento em destaque na home", default=False)
    publicado = models.BooleanField(default=False, help_text="Só eventos publicados aparecem na loja.")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data_inicio"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.titulo)
            slug, i = base, 2
            while Evento.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo

    @property
    def imagem_carrossel(self):
        """Banner do carrossel: usa o banner grande; se não tiver, o menor."""
        return self.banner or self.imagem

    @property
    def tipos_disponiveis(self):
        """Tipos à venda agora: ativos, com estoque, e (se for lote) com os
        lotes anteriores já esgotados (ou desativados)."""
        ativos = list(self.tipos_ingresso.filter(ativo=True))
        todos = list(self.tipos_ingresso.all())
        vendaveis = []
        for t in ativos:
            if t.disponivel <= 0:
                continue
            if t.eh_lote:
                anteriores_fechados = all(
                    a.disponivel == 0 or not a.ativo
                    for a in todos if a.eh_lote and a.ordem < t.ordem
                )
                if not anteriores_fechados:
                    continue
            vendaveis.append(t)
        return vendaveis

    @property
    def lotes_em_espera(self):
        """Lotes ativos com estoque, aguardando o lote anterior esgotar."""
        todos = list(self.tipos_ingresso.all())
        espera = []
        for t in todos:
            if not (t.ativo and t.eh_lote and t.disponivel > 0):
                continue
            anteriores_fechados = all(
                a.disponivel == 0 or not a.ativo
                for a in todos if a.eh_lote and a.ordem < t.ordem
            )
            if not anteriores_fechados:
                espera.append(t)
        return espera

    @property
    def preco_minimo(self):
        """Menor preço de ingresso já com a taxa da plataforma ('a partir de')."""
        precos = [t.preco for t in self.tipos_disponiveis]
        if not precos:
            return None
        config = Configuracao.get_solo()
        menor = min(precos)
        return menor + (menor * config.taxa_plataforma / 100)


class RequerimentoEvento(Evento):
    """Visão de admin: eventos enviados por produtores aguardando aprovação."""

    class Meta:
        proxy = True
        verbose_name = "Requerimento de evento"
        verbose_name_plural = "📥 Requerimentos de eventos"


class Repasse(models.Model):
    """Controle financeiro do admin: o que já foi pago ao produtor por evento."""

    evento = models.OneToOneField(Evento, on_delete=models.CASCADE, related_name="repasse_controle")
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pago_em = models.DateTimeField(null=True, blank=True)
    observacao = models.CharField(max_length=200, blank=True,
                                  help_text="Ex.: PIX enviado, comprovante nº, acordo especial")
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Repasse ao produtor"
        verbose_name_plural = "Repasses aos produtores"

    def __str__(self):
        return f"Repasse {self.evento.titulo} — R$ {self.valor_pago}"


class TipoIngresso(models.Model):
    """Lote/tipo de ingresso: Pista, VIP, Meia, 1º lote etc.

    ordem = 0  -> sempre à venda (sem lógica de lote)
    ordem >= 1 -> lote: só abre quando todos os lotes anteriores esgotarem
    """

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="tipos_ingresso")
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2,
                                help_text="Preço que o PRODUTOR recebe exatamente. A taxa da plataforma é somada no checkout.")
    quantidade_total = models.PositiveIntegerField()
    quantidade_vendida = models.PositiveIntegerField(default=0)
    max_por_pedido = models.PositiveIntegerField("Máximo por pedido", default=10)
    ordem = models.PositiveIntegerField("Ordem do lote", default=0,
                                        help_text="0 = sempre à venda. 1, 2, 3... = abre quando o lote anterior esgotar.")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de ingresso"
        verbose_name_plural = "Tipos de ingresso"
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.nome} — {self.evento.titulo}"

    @property
    def disponivel(self):
        return max(self.quantidade_total - self.quantidade_vendida, 0)

    @property
    def repasse(self):
        """Quanto o produtor recebe por este tipo até agora."""
        return self.preco * self.quantidade_vendida

    @property
    def eh_lote(self):
        return self.ordem > 0


class ListaVIP(models.Model):
    """Lista VIP de um evento: página de captura própria, gratuita ou paga.

    O produtor gera a lista na área dele e divulga o link. Quem entra na
    lista recebe um ingresso com QR Code como qualquer compra — bipa na
    portaria normalmente. O estoque da lista é separado dos ingressos
    normais (usa um TipoIngresso oculto, criado automaticamente).
    """

    TIPOS = [
        ("free", "Gratuita — cadastro direto"),
        ("paga", "Paga — checkout Mercado Pago"),
    ]

    evento = models.OneToOneField(Evento, on_delete=models.CASCADE, related_name="lista_vip")
    tipo = models.CharField(max_length=5, choices=TIPOS, default="free")
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Só para lista PAGA: valor que o PRODUTOR recebe. A taxa da plataforma é somada no checkout.",
    )
    quantidade_limite = models.PositiveIntegerField("Quantidade de vagas da lista")
    ativa = models.BooleanField(default=True)
    tipo_ingresso = models.OneToOneField(
        TipoIngresso, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="lista_vip_origem",
        help_text="Tipo de ingresso oculto que guarda o estoque da lista.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lista VIP"
        verbose_name_plural = "Listas VIP"

    def __str__(self):
        return f"Lista VIP ({self.get_tipo_display()}) — {self.evento.titulo}"

    @property
    def vagas_usadas(self):
        return self.tipo_ingresso.quantidade_vendida if self.tipo_ingresso else 0

    @property
    def vagas_restantes(self):
        return max(self.quantidade_limite - self.vagas_usadas, 0)

    @property
    def esgotada(self):
        return self.vagas_restantes <= 0
