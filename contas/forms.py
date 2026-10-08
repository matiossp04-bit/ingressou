from django import forms
from django.contrib.auth import get_user_model

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
