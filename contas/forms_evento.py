from django import forms

from eventos.models import Evento, TipoIngresso

UFS = [
    ("", "Selecione…"),
    ("AC", "AC"), ("AL", "AL"), ("AP", "AP"), ("AM", "AM"), ("BA", "BA"),
    ("CE", "CE"), ("DF", "DF"), ("ES", "ES"), ("GO", "GO"), ("MA", "MA"),
    ("MT", "MT"), ("MS", "MS"), ("MG", "MG"), ("PA", "PA"), ("PB", "PB"),
    ("PR", "PR"), ("PE", "PE"), ("PI", "PI"), ("RJ", "RJ"), ("RN", "RN"),
    ("RS", "RS"), ("RO", "RO"), ("RR", "RR"), ("SC", "SC"), ("SP", "SP"),
    ("SE", "SE"), ("TO", "TO"),
]


class CriarEventoForm(forms.ModelForm):
    """Formulário do produtor para criar seu evento (fica aguardando aprovação do admin)."""

    cep = forms.CharField(
        label="CEP", max_length=9,
        widget=forms.TextInput(attrs={"placeholder": "00000-000", "pattern": "[0-9]{5}-?[0-9]{3}", "inputmode": "numeric"}),
    )
    logradouro = forms.CharField(label="Rua / Avenida", max_length=200,
                                 widget=forms.TextInput(attrs={"placeholder": "Ex.: Av. Paulista"}))
    numero = forms.CharField(label="Número", max_length=20,
                             widget=forms.TextInput(attrs={"placeholder": "Ex.: 1000 ou S/N"}))
    complemento = forms.CharField(label="Complemento (opcional)", max_length=100, required=False,
                                  widget=forms.TextInput(attrs={"placeholder": "Ex.: Sala 2, Bloco B"}))
    bairro = forms.CharField(label="Bairro", max_length=100)
    uf = forms.ChoiceField(label="UF (estado)", choices=UFS)

    field_order = ["titulo", "categoria", "descricao", "data_inicio", "data_fim",
                   "local", "cidade", "cep", "logradouro", "numero",
                   "complemento", "bairro", "uf", "imagem", "banner"]

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
            "local": "Nome do local (ex.: Ginásio Municipal)",
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

    def local_completo(self):
        """Monta o endereço discriminado em uma linha para exibição no evento."""
        c = self.cleaned_data
        complemento = f", {c['complemento']}" if c.get("complemento") else ""
        cep = c["cep"].replace("-", "")
        cep = f"{cep[:5]}-{cep[5:]}"
        return (f"{c['local']} — {c['logradouro']}, {c['numero']}{complemento} "
                f"- {c['bairro']} · CEP {cep}")


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
