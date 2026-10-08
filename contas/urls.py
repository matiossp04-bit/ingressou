from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("conta/", views.minha_conta, name="minha_conta"),
    path("conta/criar/", views.criar_conta, name="criar_conta"),
    path("produtor/", views.area_produtor, name="area_produtor"),
    path("produtor/criar-evento/", views.criar_evento, name="criar_evento"),
    path("produtor/evento/<int:evento_id>/ingressos/", views.gerenciar_ingressos, name="gerenciar_ingressos"),
    path("produtor/evento/<int:evento_id>/participantes.csv", views.exportar_participantes_produtor, name="exportar_participantes_produtor"),
    path(
        "conta/entrar/",
        auth_views.LoginView.as_view(template_name="contas/login.html"),
        name="entrar",
    ),
    path("conta/sair/", auth_views.LogoutView.as_view(), name="sair"),
]
