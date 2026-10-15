import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control


@cache_control(max_age=3600)
def manifest(request):
    return JsonResponse({
        "name": "Givlah",
        "short_name": "Givlah",
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


SHELL_FILES = ["css/givlah.css", "js/givlah.js", "icons/icon-192.png",
               "fonts/givlah/Givlah-Bold.woff2", "fonts/caveat/Caveat-latin.woff2"]


def shell_version():
    """Hash of the cached shell files and offline page, so any change installs a fresh cache."""
    digest = hashlib.sha256()
    for name in SHELL_FILES:
        path = finders.find(name)
        digest.update(Path(path).read_bytes() if path else name.encode())
    digest.update(Path(settings.BASE_DIR / "templates" / "pwa" / "offline.html").read_bytes())
    return digest.hexdigest()[:12]


@cache_control(no_cache=True)
def service_worker(request):
    response = render(request, "pwa/sw.js", {
        "precache": [static(name) for name in SHELL_FILES] + ["/offline/"],
        "version": shell_version(),
    }, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    return render(request, "pwa/offline.html")
