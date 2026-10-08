from django import forms

from eventos.models import Evento, TipoIngresso


class CriarEventoForm(forms.ModelForm):
    """Formulário do produtor para criar seu evento (fica aguardando aprovação do admin)."""

    class Meta:
        model = Evento
        fields = ["titulo", "categoria", "descricao", "data_inicio", "data_fim",
                  "local", "cidade", "imagem", "banner"]
        labels = {
            "titulo": "Nome do evento",
            "categoria": "Categoria",
            "descricao": "Descrição completa",
            "data_inicio": "Data e hora de início",
            "data_fim": "Data e hora de término (opcional)",
            "local": "Local",
            "cidade": "Cidade",
            "imagem": "Banner menor (aparece nos cards de eventos)",
            "banner": "Banner maior (aparece no carrossel da página inicial)",
        }
        widgets = {
            "data_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "data_fim": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "descricao": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_inicio"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["data_fim"].input_formats = ["%Y-%m-%dT%H:%M"]


class PrimeiroIngressoForm(forms.Form):
    """Tipo de ingresso do evento — usado em formset para vários tipos."""

    nome = forms.CharField(label="Nome do ingresso", max_length=100,
                           widget=forms.TextInput(attrs={"placeholder": "Ex.: Pista, VIP, 1º Lote, Meia-entrada"}))
    preco = forms.DecimalField(label="Seu preço (valor exato que você recebe)",
                               min_value=1, max_digits=10, decimal_places=2)
    quantidade_total = forms.IntegerField(label="Quantidade disponível", min_value=1)
    lote = forms.BooleanField(
        label="Abrir só quando o lote anterior esgotar",
        required=False,
        help_text="Opcional: crie 1º, 2º, 3º lote — cada um abre automaticamente quando o anterior acabar.",
    )

    def salvar(self, evento, ordem=0):
        dados = dict(self.cleaned_data)
        dados.pop("lote", None)
        dados["ordem"] = ordem
        return TipoIngresso.objects.create(evento=evento, **dados)


class GerenciarIngressoForm(forms.Form):
    """Adicionar/editar tipo de ingresso depois do evento criado."""

    nome = forms.CharField(label="Nome do ingresso", max_length=100,
                           widget=forms.TextInput(attrs={"placeholder": "Ex.: 2º Lote, Camarote"}))
    preco = forms.DecimalField(label="Preço (valor do seu repasse)",
                               min_value=1, max_digits=10, decimal_places=2)
    quantidade_total = forms.IntegerField(label="Quantidade", min_value=1)
    lote = forms.BooleanField(label="Abrir só quando o lote anterior esgotar", required=False)
