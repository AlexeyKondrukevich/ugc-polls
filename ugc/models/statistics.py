from django.db import models
from django.utils.translation import gettext_lazy as _

from .answer_option import AnswerOption
from .poll import Poll
from .question import Question


class PollStatistics(models.Model):
    poll = models.OneToOneField(
        Poll,
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    total_completed_sessions = models.IntegerField(
        default=0,
        help_text=_("Количество завершённых прохождений опроса"),
    )
    total_answers = models.IntegerField(
        default=0,
        help_text=_("Общее количество ответов на все вопросы"),
    )
    average_completion_time_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text=_("Среднее время прохождения (сек)"),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "poll_statistics"
        indexes = [
            models.Index(fields=["total_answers"]),
        ]


class QuestionStatistics(models.Model):
    question = models.OneToOneField(
        Question,
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    total_answers = models.IntegerField(
        default=0,
        help_text=_("Количество ответов на данный вопрос"),
    )
    custom_answers_count = models.IntegerField(
        default=0,
        help_text=_("Количество собственных ответов (не из вариантов)"),
    )

    class Meta:
        db_table = "question_statistics"


class AnswerOptionStatistics(models.Model):
    option = models.OneToOneField(
        AnswerOption,
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    times_selected = models.IntegerField(
        default=0,
        help_text=_("Сколько раз выбран этот вариант"),
    )

    class Meta:
        db_table = "answer_option_statistics"
        indexes = [
            models.Index(fields=["times_selected"]),
        ]
