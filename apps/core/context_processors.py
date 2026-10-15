from django.conf import settings


def givlah(request):
    return {"demo_mode": settings.DEMO_MODE}
