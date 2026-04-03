from django.db import models
from django.utils.translation import gettext_lazy as _

from .question import Question


class AnswerOption(models.Model):
    question = models.ForeignKey(
        Question,
        verbose_name=_("Вопрос"),
        on_delete=models.CASCADE,
        related_name="options"
    )
    text = models.CharField(
        verbose_name=_("Текст ответа"),
        max_length=255
    )
    weight = models.PositiveIntegerField(
        verbose_name=_("Вес ответа"),
        default=1,
        blank=False,
    )

    class Meta:
        db_table = "answer_options"
        ordering = ("weight",)
        verbose_name = _("Вариант ответа")
        verbose_name_plural = _("Варианты ответов")
        constraints = (
            models.UniqueConstraint(
                fields=["question", "weight"],
                name="unique_question_answer_weight"
            ),
        )

    def __str__(self):
        return self.text
