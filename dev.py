"""Servidor de desenvolvimento que entende --host e --port (padrão dos previews)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ingressou.settings")

from django.core.management import execute_from_command_line

host, port = "127.0.0.1", "8000"
args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == "--host" and i + 1 < len(args):
        host = args[i + 1]
    elif arg == "--port" and i + 1 < len(args):
        port = args[i + 1]

execute_from_command_line(["manage.py", "runserver", f"{host}:{port}", "--noreload"])
