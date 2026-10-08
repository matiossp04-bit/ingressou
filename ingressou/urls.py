from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve


def servir_media(request, caminho):
    """Serve arquivos de mídia (QR codes, capas) quando DEBUG=False.

    Os nomes são UUIDs imprevisíveis, então não há risco de enumeração.
    Para escala real, migrar para S3/Cloudinary (ver DEPLOY.md).
    """
    return serve(request, caminho, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("eventos.urls")),
    path("", include("pedidos.urls")),
    path("", include("contas.urls")),
    path("painel/", include("painel.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [path("media/<path:caminho>", servir_media)]
