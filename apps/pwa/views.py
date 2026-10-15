from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control


@cache_control(max_age=3600)
def manifest(request):
    return JsonResponse({
        "name": "givlah",
        "short_name": "givlah",
        "description": "Give usable household items a new home with help from neighbours.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#FDFCFD",
        "theme_color": "#10C766",
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, content_type="application/manifest+json")


@cache_control(no_cache=True)
def service_worker(request):
    response = render(request, "pwa/sw.js", {
        "precache": [static("css/givlah.css"), static("js/givlah.js"), static("icons/icon-192.png"), "/offline/"],
    }, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    return render(request, "pwa/offline.html")
