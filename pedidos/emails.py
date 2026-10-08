"""Envio de e-mails transacionais do Ingressou.

Configuração via .env (ver .env.example). Sem configuração SMTP,
usa o backend 'console': o e-mail aparece no terminal do servidor
(perfeito para testar sem mandar e-mail de verdade).
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def enviar_ingressos(pedido):
    """Envia os ingressos (QR codes anexados) após a confirmação do pagamento.

    Falha de e-mail NUNCA pode quebrar a confirmação de pagamento —
    por isso qualquer erro é apenas registrado no log.
    """
    try:
        assunto = f"🎟️ Seus ingressos — {pedido.evento.titulo}"
        link = f"{settings.SITE_URL.rstrip('/')}/pedido/{pedido.uuid}/confirmado/"
        html = render_to_string("emails/ingressos.html", {"pedido": pedido, "link": link})
        texto = (
            f"Compra confirmada! {pedido.evento.titulo} — "
            f"{pedido.evento.data_inicio:%d/%m/%Y %H:%M}. "
            f"Acesse seus ingressos: {link}"
        )

        email = EmailMultiAlternatives(
            assunto, texto,
            settings.DEFAULT_FROM_EMAIL,
            [pedido.comprador_email],
        )
        email.attach_alternative(html, "text/html")

        # QR codes como anexos — o comprador pode salvar/abrir direto do e-mail
        for item in pedido.itens.all():
            for ingresso in item.ingressos.all():
                if ingresso.qrcode:
                    ingresso.qrcode.open("rb")
                    email.attach(
                        f"ingresso-{str(ingresso.codigo)[:8]}.png",
                        ingresso.qrcode.read(),
                        "image/png",
                    )
        email.send()
        logger.info("Ingressos enviados para %s (pedido %s)", pedido.comprador_email, pedido.uuid)
        return True
    except Exception:
        logger.exception("Falha ao enviar ingressos do pedido %s", pedido.uuid)
        return False
