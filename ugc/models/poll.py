from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Poll(models.Model):
    title = models.CharField(
        verbose_name=_("Название опроса"),
        max_length=255,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Автор опроса"),
        on_delete=models.CASCADE,
        related_name="polls",
    )
    created_at = models.DateTimeField(
        verbose_name=_("Дата создания опроса"),
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name=_("Дата обновления опроса"),
        auto_now=True,
    )

    class Meta:
        db_table = "polls"
        verbose_name = _("Опрос")
        verbose_name_plural = _("Опросы")
        indexes = (
            models.Index(fields=["author"]),
            models.Index(fields=["created_at"]),
        )

    def __str__(self):
        return self.title