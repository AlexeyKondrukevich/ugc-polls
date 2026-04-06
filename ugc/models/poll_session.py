from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .poll import Poll
from .question import Question


class PollSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Пользователь"),
        on_delete=models.CASCADE,
        related_name="poll_sessions",
    )
    poll = models.ForeignKey(
        Poll,
        verbose_name=_("Опрос"),
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    start_time = models.DateTimeField(
        verbose_name=_("Время начала опроса"), default=timezone.now
    )
    end_time = models.DateTimeField(
        verbose_name=_("Время окончания опроса"),
        null=True,
        blank=True,
    )
    current_question = models.ForeignKey(
        Question,
        on_delete=models.SET_NULL,
        verbose_name=_("Текущий вопрос"),
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "poll_sessions"
        verbose_name = _("Сессия опроса")
        verbose_name_plural = _("Сессии опросов")
        indexes = (
            models.Index(fields=["user", "poll"]),
            models.Index(fields=["poll", "current_question"]),
        )

    def is_completed(self):
        return self.end_time is not None

    def complete(self):
        self.end_time = timezone.now()
        self.current_question = None
        self.save()
