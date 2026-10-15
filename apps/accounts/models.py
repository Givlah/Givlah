from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    display_name = models.CharField(max_length=40)
    # Server-owned flag for fictional demo accounts; never settable from forms.
    is_synthetic = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name or self.username
