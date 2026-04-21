import logging

from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied, ValidationError

from ugc.models import PollSession, Question, UserAnswer
from ugc.serializers import UserAnswerSerializer

logger = logging.getLogger(__name__)


class PollSessionService:
    """Сервис для управления сессией прохождения опроса."""

    @staticmethod
    def _get_first_question(poll):
        return poll.questions.order_by("weight", "id").first()

    @staticmethod
    def _get_active_sessions_qs(user, poll):
        return (
            PollSession.objects.select_related("current_question")
            .filter(user=user, poll=poll, end_time__isnull=True)
            .order_by("start_time", "id")
        )

    @staticmethod
    def _choose_single_active_session(user, poll):
        sessions = list(
            PollSessionService._get_active_sessions_qs(user, poll)[:2]
        )
        if not sessions:
            return None
        if len(sessions) > 1:
            logger.error(
                "Multiple active poll sessions detected for user_id=%s poll_id=%s",
                getattr(user, "id", None),
                getattr(poll, "id", None),
            )
        return sessions[0]

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

        session = PollSessionService._choose_single_active_session(user, poll)
        if session is not None:
            return session

        with transaction.atomic():
            session = PollSessionService._choose_single_active_session(
                user, poll
            )
            if session is not None:
                return session

            session = PollSession.objects.create(
                user=user,
                poll=poll,
                current_question=PollSessionService._get_first_question(poll),
            )

        return session

    @staticmethod
    def get_active_session(user, poll):
        """Возвращает активную сессию или None с информативным исключением."""

        session = PollSessionService._choose_single_active_session(user, poll)
        if session is not None:
            return session

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

        if session is None or current_question is None:
            raise ValidationError(_("Сессия и текущий вопрос обязательны."))

        if session.poll_id != poll.id or current_question.poll_id != poll.id:
            raise ValidationError(
                _("Сессия или вопрос не относятся к указанному опросу.")
            )

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
    def validate_answer_payload(session, question):
        if session is None or question is None:
            raise ValidationError(_("Сессия и вопрос обязательны."))

        if session.poll_id != question.poll_id:
            raise ValidationError(
                _("Вопрос не относится к опросу этой сессии.")
            )

        if session.is_completed():
            raise PermissionDenied(_("Опрос уже завершён."))

        if session.current_question_id is None:
            raise ValidationError(_("Для сессии не задан текущий вопрос."))

        if session.current_question_id != question.id:
            raise ValidationError(
                _("Можно отвечать только на текущий вопрос сессии.")
            )

        if UserAnswer.objects.filter(
            session=session, question=question
        ).exists():
            raise ValidationError(_("Ответ на этот вопрос уже был сохранён."))

    @staticmethod
    def save_answer(session, question, selected_option, custom_text):
        """Сохраняет ответ пользователя, проверяет корректность."""

        AnswerService.validate_answer_payload(session, question)

        data = {
            "session": session.id,
            "question": question.id,
            "selected_option": selected_option,
            "custom_text": custom_text,
        }
        serializer = UserAnswerSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError as exc:
            raise ValidationError(
                _("Ответ на этот вопрос уже был сохранён.")
            ) from exc
        return serializer.data
