"""Cria usuário admin e eventos de demonstração com capas geradas."""
import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from eventos.models import Evento, Produtor, TipoIngresso

GRADIENTES = [
    ((91, 46, 229), (229, 46, 138)),
    ((20, 120, 220), (91, 46, 229)),
    ((229, 110, 30), (229, 46, 138)),
    ((16, 163, 74), (20, 120, 220)),
    ((200, 30, 60), (120, 20, 160)),
]


def gerar_capa(titulo, caminho: Path, cores):
    """Gera uma capa 1200x675 em gradiente com o título do evento."""
    from PIL import Image, ImageDraw

    w, h = 1200, 675
    (r1, g1, b1), (r2, g2, b2) = cores
    img = Image.new("RGB", (w, h))
    for x in range(w):
        t = x / w
        cor = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
        ImageDraw.Draw(img).line([(x, 0), (x, h)], fill=cor)

    draw = ImageDraw.Draw(img)
    # círculos decorativos translúcidos
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for _ in range(6):
        cx, cy = random.randint(0, w), random.randint(0, h)
        raio = random.randint(60, 200)
        od.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=(255, 255, 255, 22))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont
        fonte = ImageFont.truetype("arial.ttf", 64)
        fonte_menor = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        from PIL import ImageFont
        fonte = ImageFont.load_default()
        fonte_menor = fonte
    draw.rectangle([60, h - 220, w - 60, h - 60], fill=(0, 0, 0))
    draw.text((85, h - 200), titulo[:40], fill=(255, 255, 255), font=fonte)
    draw.text((85, h - 115), "INGRESSOU", fill=(255, 209, 102), font=fonte_menor)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    img.save(caminho, "JPEG", quality=85)


class Command(BaseCommand):
    help = "Cria usuário admin e eventos de demonstração."

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@ingressou.com", "ingressou123")
            self.stdout.write("Admin criado: usuário 'admin', senha 'ingressou123' (troque depois!)")

        produtor, _ = Produtor.objects.get_or_create(
            nome="Produtora ForFun Eventos",
            defaults={"email": "contato@forfun.com", "telefone": "(11) 99999-0000"},
        )

        if Evento.objects.exists():
            self.stdout.write("Eventos já existem — nada a fazer.")
            return

        demos = [
            {
                "titulo": "Show Nacional — Noite de Sucessos", "categoria": "show",
                "descricao": "Uma noite inesquecível com os maiores sucessos do momento.\nAbertura dos portões às 19h.\n\nClassificação: 16 anos (menores acompanhados).",
                "local": "Arena Central", "cidade": "São Paulo", "dias": 30, "destaque": True,
                "tipos": [("Pista", "100.00", 500), ("VIP Camarote", "250.00", 100)],
            },
            {
                "titulo": "Festa Sunset — Edição Verão", "categoria": "festa",
                "descricao": "Open air à beira-mar com DJs convidados e pôr do sol lendário.",
                "local": "Beach Club", "cidade": "Florianópolis", "dias": 45, "destaque": True,
                "tipos": [("1º Lote", "80.00", 300), ("Camarote Open Bar", "320.00", 80)],
            },
            {
                "titulo": "Peça: O Fantasma do Teatro", "categoria": "teatro",
                "descricao": "O clássico musical em versão brasileira, com orquestra ao vivo.",
                "local": "Teatro Municipal", "cidade": "Rio de Janeiro", "dias": 20, "destaque": False,
                "tipos": [("Plateia", "120.00", 200), ("Balcão", "70.00", 150)],
            },
            {
                "titulo": "Workshop: Finanças para Produtores de Eventos", "categoria": "curso",
                "descricao": "Aprenda a precificar eventos e controlar repasses como um profissional.",
                "local": "Centro de Convenções", "cidade": "Belo Horizonte", "dias": 15, "destaque": False,
                "tipos": [("Ingresso único", "150.00", 80)],
            },
            {
                "titulo": "Final do Campeonato Regional", "categoria": "esporte",
                "descricao": "A grande decisão ao vivo. Traga sua torcida!",
                "local": "Estádio Municipal", "cidade": "Curitiba", "dias": 10, "destaque": False,
                "tipos": [("Arquibancada", "50.00", 2000), ("Cadeira numerada", "110.00", 400)],
            },
        ]

        for i, d in enumerate(demos):
            evento = Evento.objects.create(
                produtor=produtor, titulo=d["titulo"], categoria=d["categoria"],
                descricao=d["descricao"], data_inicio=timezone.now() + timedelta(days=d["dias"]),
                local=d["local"], cidade=d["cidade"], publicado=True, destaque=d["destaque"],
            )
            for nome, preco, qtd in d["tipos"]:
                TipoIngresso.objects.create(
                    evento=evento, nome=nome, preco=Decimal(preco), quantidade_total=qtd
                )
            capa = Path(settings.MEDIA_ROOT) / "eventos" / f"{evento.slug}.jpg"
            gerar_capa(d["titulo"], capa, GRADIENTES[i % len(GRADIENTES)])
            evento.imagem = f"eventos/{evento.slug}.jpg"
            evento.save(update_fields=["imagem"])
            self.stdout.write(f"Evento criado: {evento.titulo}")

        self.stdout.write(self.style.SUCCESS("Pronto! Acesse /, /admin/ e /painel/"))
