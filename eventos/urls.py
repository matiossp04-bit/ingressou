from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("evento/<slug:slug>/", views.evento_detalhe, name="evento_detalhe"),
]
