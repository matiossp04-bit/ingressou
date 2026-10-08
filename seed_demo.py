"""Cria eventos demo extras (ate 17 publicados) com banners gerados, todos em destaque."""
import os, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ingressou.settings")

import django
django.setup()

from datetime import timedelta
from django.utils import timezone
from django.core.files import File
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

from eventos.models import Evento, TipoIngresso, Produtor

MEDIA = Path("media")
(MEDIA / "eventos").mkdir(parents=True, exist_ok=True)
(MEDIA / "banners").mkdir(parents=True, exist_ok=True)

F_TIT = "C:/Windows/Fonts/arialbd.ttf"
F_TXT = "C:/Windows/Fonts/arial.ttf"

PALETAS = {
    "show":       ((37, 99, 235), (124, 58, 237)),
    "festa":      ((219, 39, 119), (249, 115, 22)),
    "teatro":     ((153, 27, 27), (220, 38, 38)),
    "esporte":    ((4, 120, 87), (16, 185, 129)),
    "standup":    ((217, 119, 6), (245, 158, 11)),
    "congresso":  ((30, 58, 138), (37, 99, 235)),
    "passeio":    ((15, 118, 110), (45, 212, 191)),
    "infantil":   ((190, 24, 93), (168, 85, 247)),
    "curso":      ((13, 148, 136), (59, 130, 246)),
    "gastronomia":((194, 65, 12), (234, 88, 12)),
    "religiao":   ((161, 98, 7), (250, 204, 21)),
    "festival":   ((109, 40, 217), (249, 115, 22)),
    "online":     ((8, 145, 178), (34, 211, 238)),
    "outros":     ((71, 85, 105), (100, 116, 139)),
}


def gerar_banner(path, titulo, categoria, w=1280, h=720):
    c1, c2 = PALETAS.get(categoria, PALETAS["outros"])
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for x in range(w):
        t = x / w
        c = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        d.line([(x, 0), (x, h)], fill=c)
    random.seed(titulo)
    for _ in range(7):
        r = random.randint(60, 190)
        cx, cy = random.randint(-40, w + 40), random.randint(-40, h + 40)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 22))
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0))
        d = ImageDraw.Draw(img)
    # faixa inferior com titulo
    d.rectangle([40, h - 170, w - 40, h - 46], fill=(10, 10, 16))
    ft = ImageFont.truetype(F_TIT, 52)
    fw = ImageFont.truetype(F_TIT, 22)
    t = titulo if len(titulo) <= 44 else titulo[:44] + "…"
    d.text((70, h - 140), t, fill="#ffffff", font=ft)
    d.text((70, h - 76), "INGRESSOU", fill="#9aa3b2", font=fw)
    img.save(path, quality=88)


NOVOS = [
    ("Gusttavo Lima — Turnê 2026", "show", "Arena Allianz", "São Paulo", 9, 19, 250.00, 150.00),
    ("Réveillon Neon 2027", "festa", "Praia de Copacabana — Palco Principal", "Rio de Janeiro", 84, 22, 180.00, 120.00),
    ("Noite de Comédia com Diogo Almeida", "standup", "Teatro Bradesco", "São Paulo", 12, 20, 80.00, None),
    ("Congresso de Marketing Digital 2026", "congresso", "Centro de Convenções Frei Caneca", "São Paulo", 20, 9, 497.00, 297.00),
    ("Tour Vinícolas da Serra Gaúcha", "passeio", "Saída: Catedral de Pedra", "Canela", 6, 10, 220.00, None),
    ("Mundo Mágico — Espetáculo Infantil", "infantil", "Teatro Alfa", "Curitiba", 8, 15, 60.00, 40.00),
    ("Festival de Food Trucks", "gastronomia", "Parque do Povo", "Belo Horizonte", 10, 12, 35.00, None),
    ("Conferência Fé e Louvor 2026", "religiao", "Ginásio Municipal", "Goiânia", 16, 18, 50.00, None),
    ("Festival Eletrônico Horizonte", "festival", "Haras Larissa", "Campinas", 22, 16, 320.00, 220.00),
    ("Masterclass Online: Vendas na Internet", "online", "Online — link enviado por e-mail", "Online", 7, 19, 97.00, None),
    ("Corrida Noturna 10K — Etapa Verão", "esporte", "Orla de Atalaia", "Aracaju", 14, 5, 89.90, None),
]

produtor = Produtor.objects.first()
hoje = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
criados = 0
for titulo, cat, local, cidade, dias, hora, p1, p2 in NOVOS:
    if Evento.objects.filter(titulo=titulo).exists():
        continue
    ini = hoje + timedelta(days=dias, hours=hora)
    fim = ini + timedelta(hours=4)
    slug_base = slugify(titulo)[:40]
    ev = Evento(
        produtor=produtor, titulo=titulo, slug=f"{slug_base}-{random.randint(1000,9999)}",
        descricao=(f"{titulo}. Garanta já o seu ingresso! Evento imperdível em {cidade}. "
                   "Compre com segurança no Ingressou e receba seu QR code na hora."),
        categoria=cat, data_inicio=ini, data_fim=fim, local=local, cidade=cidade,
        destaque=True, publicado=True,
    )
    nome_arq = f"demo_{slug_base[:24]}.jpg"
    gerar_banner(MEDIA / "eventos" / nome_arq, titulo, cat)
    gerar_banner(MEDIA / "banners" / nome_arq, titulo, cat, h=656)
    ev.imagem.name = f"eventos/{nome_arq}"
    ev.banner.name = f"banners/{nome_arq}"
    ev.save()
    TipoIngresso.objects.create(evento=ev, nome="Inteira", preco=p1, quantidade_total=500)
    if p2:
        TipoIngresso.objects.create(evento=ev, nome="Meia-entrada", preco=p2, quantidade_total=200)
    criados += 1
    print("criado:", titulo)

# marca TODOS os publicados como destaque para rodar no carrossel
n = Evento.objects.filter(publicado=True).update(destaque=True)
print("publicados em destaque:", n, "| novos criados:", criados)
print("total no carrossel:", Evento.objects.filter(publicado=True, destaque=True, data_inicio__gte=timezone.now()).count())
