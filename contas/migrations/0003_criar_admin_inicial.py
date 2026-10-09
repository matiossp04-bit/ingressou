"""Cria o superuser inicial automaticamente no deploy, se as variáveis
DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD estiverem definidas.
Idempotente: não faz nada se o usuário já existir ou as variáveis faltarem.
(Necessário porque o plano gratuito do Render não tem Shell.)"""
import os

from django.contrib.auth import get_user_model
from django.db import migrations


def criar_admin(apps, schema_editor):
    username = os.getenv("DJANGO_SUPERUSER_USERNAME")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
    if not username or not password:
        return
    User = get_user_model()
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0002_alter_perfil_tipo"),
    ]

    operations = [
        migrations.RunPython(criar_admin, migrations.RunPython.noop),
    ]
