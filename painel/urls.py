from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="painel_dashboard"),
    path("evento/<int:evento_id>/", views.pedidos_evento, name="painel_evento"),
    path("evento/<int:evento_id>/repasse/", views.marcar_repasse, name="marcar_repasse"),
    path("evento/<int:evento_id>/participantes.csv", views.exportar_participantes, name="exportar_participantes"),
]
