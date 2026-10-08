from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pedidos.models import Pedido


class Command(BaseCommand):
    help = "Expira pedidos pendentes vencidos e devolve os ingressos ao estoque."

    @transaction.atomic
    def handle(self, *args, **options):
        vencidos = Pedido.objects.filter(status="pendente", expira_em__lt=timezone.now())
        total = 0
        for pedido in vencidos.select_for_update():
            for item in pedido.itens.select_related("tipo_ingresso"):
                tipo = item.tipo_ingresso
                tipo.quantidade_vendida = max(tipo.quantidade_vendida - item.quantidade, 0)
                tipo.save(update_fields=["quantidade_vendida"])
            pedido.status = "expirado"
            pedido.save(update_fields=["status"])
            total += 1
        self.stdout.write(self.style.SUCCESS(f"{total} pedido(s) expirado(s)."))
