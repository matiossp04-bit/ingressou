from django import forms
from django.contrib.auth import get_user_model

from eventos.models import Evento, ListaVIP, TipoIngresso
from .models import Perfil


def _digitos(valor):
    return "".join(c for c in valor if c.isdigit())


def validar_cpf(cpf):
    cpf = _digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for pos in (9, 10):
        soma = sum(int(cpf[i]) * (pos + 1 - i) for i in range(pos))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[pos]):
            return False
    return True


def validar_cnpj(cnpj):
    cnpj = _digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    for pos, pesos in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
                       (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(pos))
        digito = 11 - soma % 11
        digito = 0 if digito >= 10 else digito
        if digito != int(cnpj[pos]):
            return False
    return True


class CriarContaForm(forms.Form):
    nome = forms.CharField(label="Nome completo / Razão social", max_length=200)
    email = forms.EmailField(label="E-mail")
    tipo_documento = forms.ChoiceField(
        label="Você quer…",
        choices=[("comprador", "Comprar ingressos (CPF)"), ("produtor", "Criar eventos (CNPJ)")],
        widget=forms.RadioSelect,
    )
    documento = forms.CharField(label="CPF ou CNPJ", max_length=18,
                                help_text="Somente números.")
    data_nascimento = forms.DateField(
        label="Data de nascimento",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput, min_length=8)
    confirmar_senha = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(username=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean_documento(self):
        doc = _digitos(self.cleaned_data["documento"])
        tipo = self.data.get("tipo_documento")
        if tipo == "comprador":
            if not validar_cpf(doc):
                raise forms.ValidationError("CPF inválido. Confira os números digitados.")
        else:
            if not validar_cnpj(doc):
                raise forms.ValidationError("CNPJ inválido. Confira os números digitados.")
        if Perfil.objects.filter(documento=doc).exists():
            raise forms.ValidationError("Este documento já está cadastrado.")
        return doc

    def clean(self):
        dados = super().clean()
        if dados.get("senha") and dados["senha"] != dados.get("confirmar_senha"):
            self.add_error("confirmar_senha", "As senhas não coincidem.")
        return dados

    def salvar(self):
        dados = self.cleaned_data
        usuario = get_user_model().objects.create_user(
            username=dados["email"], email=dados["email"],
            first_name=dados["nome"], password=dados["senha"],
        )
        Perfil.objects.create(
            usuario=usuario, tipo=dados["tipo_documento"],
            documento=dados["documento"], data_nascimento=dados["data_nascimento"],
        )
        return usuario


class _EventosPortariaMixin:
    """Queryset de eventos limitado aos eventos do produtor logado."""

    def _preparar_eventos(self, produtor):
        campo = self.fields["eventos"]
        campo.queryset = produtor.eventos.order_by("data_inicio")
        campo.label_from_instance = (
            lambda e: f"{e.titulo} — {e.data_inicio:%d/%m/%Y %H:%M} · {e.cidade}"
        )


class ContaPortariaForm(_EventosPortariaMixin, forms.Form):
    """Produtor cria uma conta de portaria (recepção) para bipar seus eventos."""

    nome = forms.CharField(label="Nome da equipe / responsável", max_length=200,
                           help_text="Ex.: Portaria Principal, Equipe João…")
    email = forms.EmailField(label="E-mail de acesso",
                             help_text="Será o login da equipe na entrada do evento.")
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput, min_length=8,
                            help_text="Mínimo 8 caracteres. Entregue pessoalmente à equipe.")
    eventos = forms.ModelMultipleChoiceField(
        label="Eventos que essa conta pode bipar",
        queryset=Evento.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Selecione pelo menos um evento."},
    )

    def __init__(self, produtor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._preparar_eventos(produtor)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(username=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def salvar(self, produtor):
        dados = self.cleaned_data
        usuario = get_user_model().objects.create_user(
            username=dados["email"], email=dados["email"],
            first_name=dados["nome"], password=dados["senha"],
        )
        perfil = Perfil.objects.create(usuario=usuario, tipo="recepcao", produtor=produtor)
        perfil.eventos_liberados.set(dados["eventos"])
        return perfil


class EditarPortariaForm(_EventosPortariaMixin, forms.Form):
    """Edita os eventos liberados de uma conta de portaria e, opcionalmente, a senha."""

    eventos = forms.ModelMultipleChoiceField(
        label="Eventos que essa conta pode bipar",
        queryset=Evento.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Selecione pelo menos um evento."},
    )
    nova_senha = forms.CharField(
        label="Nova senha (opcional)", widget=forms.PasswordInput, min_length=8,
        required=False, help_text="Preencha só se quiser trocar a senha da equipe.",
    )

    def __init__(self, produtor, perfil, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._preparar_eventos(produtor)
        if not self.is_bound:
            self.fields["eventos"].initial = perfil.eventos_liberados.all()

    def salvar(self, perfil):
        perfil.eventos_liberados.set(self.cleaned_data["eventos"])
        nova = self.cleaned_data.get("nova_senha")
        if nova:
            perfil.usuario.set_password(nova)
            perfil.usuario.save(update_fields=["password"])
        return perfil


class GerarListaVIPForm(forms.Form):
    """Produtor gera a lista VIP de um evento: gratuita ou paga, com limite de vagas."""

    evento = forms.ModelChoiceField(
        label="Para qual evento?",
        queryset=Evento.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        error_messages={"required": "Escolha o evento da lista VIP."},
    )
    tipo = forms.ChoiceField(
        label="Tipo da lista",
        choices=ListaVIP.TIPOS,
        widget=forms.RadioSelect,
        initial="free",
    )
    preco = forms.DecimalField(
        label="Valor da vaga (só lista paga)", required=False, min_value=1,
        max_digits=10, decimal_places=2,
        help_text="Você recebe exatamente esse valor por vaga. A taxa do Ingressou é somada no checkout.",
    )
    quantidade_limite = forms.IntegerField(
        label="Quantidade de vagas da lista", min_value=1,
        help_text="Quem define é você. Esgotou, a página de captura avisa que a lista encerrou.",
    )

    def __init__(self, produtor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["evento"]
        campo.queryset = (
            produtor.eventos.filter(lista_vip__isnull=True)
            .order_by("data_inicio")
        )
        campo.label_from_instance = (
            lambda e: f"{e.titulo} — {e.data_inicio:%d/%m/%Y %H:%M} · {e.cidade}"
        )

    def clean(self):
        dados = super().clean()
        if dados.get("tipo") == "paga" and not dados.get("preco"):
            self.add_error("preco", "Lista paga precisa de um valor (mín. R$ 1,00).")
        return dados

    def salvar(self):
        dados = self.cleaned_data
        evento = dados["evento"]
        preco = dados["preco"] if dados["tipo"] == "paga" else 0
        tipo_oculto = TipoIngresso.objects.create(
            evento=evento,
            nome="🎟️ Lista VIP",
            preco=preco,
            quantidade_total=dados["quantidade_limite"],
            max_por_pedido=1,
            ordem=0,
            ativo=False,  # oculto: não aparece à venda na página do evento
        )
        return ListaVIP.objects.create(
            evento=evento,
            tipo=dados["tipo"],
            preco=preco,
            quantidade_limite=dados["quantidade_limite"],
            tipo_ingresso=tipo_oculto,
        )
