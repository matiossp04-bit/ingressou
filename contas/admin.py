from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Perfil


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False


class UsuarioComPerfil(UserAdmin):
    inlines = [PerfilInline]


admin.site.unregister(User)
admin.site.register(User, UsuarioComPerfil)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "documento", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("usuario__email", "usuario__first_name", "documento")
