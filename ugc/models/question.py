from django.db import models
from django.utils.translation import gettext_lazy as _

from .poll import Poll


class Question(models.Model):
    poll = models.ForeignKey(
        Poll,
        verbose_name=_("Опрос"),
        on_delete=models.CASCADE,
        related_name="questions"
    )
    text = models.TextField(
        verbose_name=_("Текст вопроса"),
    )
    weight = models.PositiveIntegerField(
        verbose_name=_("Вес вопроса"),
        default=1,
        blank=False,
    )
    allow_custom_answer = models.BooleanField(
        default=True,
        verbose_name=_("Разрешить пользователю ввести свой ответ"),
    )

    class Meta:
        db_table = "questions"
        ordering = ("weight",)
        verbose_name = _("Вопрос")
        verbose_name_plural = _("Вопросы")
        constraints = (
            models.UniqueConstraint(
                fields=["poll", "weight"],
                name="unique_poll_question_weight"
            ),
        )

    def __str__(self):
        return f"{self.poll.title} - {self.text[:50]}"
