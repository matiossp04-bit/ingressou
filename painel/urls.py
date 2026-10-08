from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="painel_dashboard"),
    path("evento/<int:evento_id>/", views.pedidos_evento, name="painel_evento"),
]
