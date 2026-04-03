from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    class Meta:
        db_table = "users"
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")
        indexes = (
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
        )

    def __str__(self):
        return self.username
