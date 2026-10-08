from django.contrib import admin, messages

from .models import Configuracao, Evento, Produtor, Repasse, RequerimentoEvento, TipoIngresso


@admin.register(Repasse)
class RepasseAdmin(admin.ModelAdmin):
    list_display = ("evento", "valor_pago", "pago_em", "atualizado_em")
    search_fields = ("evento__titulo",)


class TipoIngressoInline(admin.TabularInline):
    model = TipoIngresso
    extra = 1


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "produtor", "data_inicio", "cidade", "publicado")
    list_filter = ("publicado", "cidade")
    search_fields = ("titulo", "produtor__nome")
    prepopulated_fields = {"slug": ("titulo",)}
    inlines = [TipoIngressoInline]


@admin.register(RequerimentoEvento)
class RequerimentoEventoAdmin(admin.ModelAdmin):
    """Fila de aprovação: eventos enviados por produtores (ainda não publicados)."""

    list_display = ("titulo", "produtor", "categoria", "cidade", "data_inicio", "criado_em", "tem_banners")
    list_filter = ("categoria", "cidade")
    search_fields = ("titulo", "produtor__nome")
    prepopulated_fields = {"slug": ("titulo",)}
    inlines = [TipoIngressoInline]
    actions = ["aprovar", "aprovar_e_destacar"]
    ordering = ("-criado_em",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(publicado=False)

    def tem_banners(self, obj):
        partes = []
        if obj.imagem:
            partes.append("🖼️ menor")
        if obj.banner:
            partes.append("🎠 maior")
        return " + ".join(partes) if partes else "—"
    tem_banners.short_description = "Banners"

    @admin.action(description="✅ Aprovar e publicar os eventos selecionados")
    def aprovar(self, request, queryset):
        total = queryset.update(publicado=True)
        self.message_user(request, f"{total} evento(s) aprovado(s) e publicado(s)! 🎉", messages.SUCCESS)

    @admin.action(description="⭐ Aprovar, publicar e destacar no carrossel da home")
    def aprovar_e_destacar(self, request, queryset):
        total = queryset.update(publicado=True, destaque=True)
        self.message_user(request, f"{total} evento(s) publicado(s) e em destaque no carrossel! ⭐", messages.SUCCESS)

    def has_add_permission(self, request):
        return False  # requerimentos só chegam pela área do produtor


@admin.register(Produtor)
class ProdutorAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "telefone", "usuario")
    search_fields = ("nome", "email")
    autocomplete_fields = ["usuario"]


@admin.register(Configuracao)
class ConfiguracaoAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not Configuracao.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
