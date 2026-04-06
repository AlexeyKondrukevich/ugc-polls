from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .poll_session import PollSession
from .question import Question
from .answer_option import AnswerOption


class UserAnswer(models.Model):
    session = models.ForeignKey(
        PollSession,
        verbose_name=_("Сессия опроса"),
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        verbose_name=_("Вопрос"),
        on_delete=models.CASCADE,
    )
    selected_option = models.ForeignKey(
        AnswerOption,
        verbose_name=_("Выбранный вариант ответа"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    custom_text = models.TextField(
        verbose_name=_("Текст пользовательского ответа"),
        blank=True,
        null=True
    )
    answered_at = models.DateTimeField(
        verbose_name=_("Время ответа"),
        default=timezone.now,
    )

    class Meta:
        db_table = "user_answers"
        verbose_name = _("Ответ пользователя")
        verbose_name_plural = _("Ответы пользователей")
        constraints = (
            models.UniqueConstraint(
                fields=["session", "question"],
                name="unique_session_question"
            ),
        )
        indexes = (
            models.Index(fields=["question"]),
            models.Index(fields=["selected_option"]),
        )

    def clean(self):
        errors = {}

        if not self.selected_option and not self.custom_text:
            msg = _("Требуется либо вариант ответа, либо свой ответ")
            errors.update(
                {
                    "selected_option": msg,
                    "custom_text": msg,
                }
            )
            raise ValidationError(msg)

        if self.selected_option and self.custom_text:
            msg = _(
                "Невозможно одновременно указать вариант ответа и свой ответ"
            )
            errors.update(
                {
                    "selected_option": msg,
                    "custom_text": msg,
                }
            )

        selected_option = self.selected_option
        question = self.question
        if selected_option and question and selected_option.question_id != question.id:
            msg = _(
                "Выбранный вариант ответа не относится к указанному вопросу."
            )
            errors.update(
                {
                    "question": msg,
                    "selected_option": msg,
                }
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        username = self.session.user.username if self.session and self.session.user else "Unknown"
        question_text = self.question.text[:30] if self.question else "Deleted question"
        return f"Ответ пользователя {username} на вопрос {question_text}"
