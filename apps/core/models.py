import uuid

from django.conf import settings
from django.db import models


class ActionToken(models.Model):
    """One submitted form. A repeated submission returns the first result instead of acting twice."""

    token = models.UUIDField(unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    result_url = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def new():
        return uuid.uuid4()
