from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied, ValidationError

from ugc.models import PollSession, Question
from ugc.serializers import UserAnswerSerializer


class PollSessionService:
    """Сервис для управления сессией прохождения опроса."""

    @staticmethod
    def get_or_start_session(user, poll):
        """
        Возвращает активную сессию или создаёт новую,
        если нет завершённой.
        """

        if PollSession.objects.filter(
            user=user, poll=poll, end_time__isnull=False
        ).exists():
            return None

        session, _ = PollSession.objects.get_or_create(
            user=user,
            poll=poll,
            end_time__isnull=True,
            defaults={"current_question": poll.questions.first()},
        )

        return session

    @staticmethod
    def get_active_session(user, poll):
        """Возвращает активную сессию или None с информативным исключением."""

        try:
            return PollSession.objects.select_related("current_question").get(
                user=user, poll=poll, end_time__isnull=True
            )
        except PollSession.DoesNotExist:

            if PollSession.objects.filter(
                user=user, poll=poll, end_time__isnull=False
            ).exists():
                raise PermissionDenied(_("Вы уже завершили этот опрос."))

            raise ValidationError(
                _("Нет активной сессии. Начните опрос с /next-question/.")
            )

    @staticmethod
    def advance_to_next_question(session, poll, current_question):
        """Переводит сессию на следующий вопрос или завершает."""

        next_q = (
            Question.objects.filter(
                poll=poll, weight__gt=current_question.weight
            )
            .order_by("weight")
            .prefetch_related("options")
            .first()
        )

        if next_q:
            session.current_question = next_q
            session.save(update_fields=["current_question"])
        else:
            session.complete()


class AnswerService:
    """Сервис для сохранения ответов."""

    @staticmethod
    def save_answer(session, question, selected_option, custom_text):
        """Сохраняет ответ пользователя, проверяет корректность."""

        data = {
            "session": session.id,
            "question": question.id,
            "selected_option": selected_option,
            "custom_text": custom_text,
        }
        serializer = UserAnswerSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return serializer.data
