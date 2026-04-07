from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from ugc.models import AnswerOption, Poll, PollSession, Question, UserAnswer
from ugc.services import AnswerService, PollSessionService

User = get_user_model()


class PollSessionServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.q1 = Question.objects.create(poll=self.poll, text="Q1", weight=1)
        self.q2 = Question.objects.create(poll=self.poll, text="Q2", weight=2)

    def test_get_or_start_session_creates_new(self):
        session = PollSessionService.get_or_start_session(self.user, self.poll)
        self.assertIsNotNone(session)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.poll, self.poll)
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_question, self.q1)

    def test_get_or_start_session_returns_none_if_completed_exists(self):
        PollSession.objects.create(
            user=self.user, poll=self.poll, end_time=timezone.now()
        )
        session = PollSessionService.get_or_start_session(self.user, self.poll)
        self.assertIsNone(session)

    def test_get_active_session_returns_active(self):
        active_session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        session = PollSessionService.get_active_session(self.user, self.poll)
        self.assertEqual(session, active_session)

    def test_get_active_session_raises_permission_denied_if_completed(self):
        PollSession.objects.create(
            user=self.user, poll=self.poll, end_time=timezone.now()
        )
        with self.assertRaises(PermissionDenied) as cm:
            PollSessionService.get_active_session(self.user, self.poll)
        self.assertIn("Вы уже завершили этот опрос", str(cm.exception))

    def test_get_active_session_raises_validation_error_if_no_session(self):
        with self.assertRaises(ValidationError) as cm:
            PollSessionService.get_active_session(self.user, self.poll)
        self.assertIn("Нет активной сессии", str(cm.exception))

    def test_advance_to_next_question_updates_current_question(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        PollSessionService.advance_to_next_question(
            session, self.poll, self.q1
        )
        session.refresh_from_db()
        self.assertEqual(session.current_question, self.q2)
        self.assertIsNone(session.end_time)

    def test_advance_to_next_question_completes_if_last(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q2
        )
        PollSessionService.advance_to_next_question(
            session, self.poll, self.q2
        )
        session.refresh_from_db()
        self.assertTrue(session.is_completed())
        self.assertIsNotNone(session.end_time)
        self.assertIsNone(session.current_question)


class AnswerServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.question = Question.objects.create(
            poll=self.poll, text="Q", weight=1
        )
        self.option = AnswerOption.objects.create(
            question=self.question, text="A", weight=1
        )
        self.session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.question
        )

    def test_save_answer_with_option(self):
        result = AnswerService.save_answer(
            session=self.session,
            question=self.question,
            selected_option=self.option.id,
            custom_text=None,
        )
        self.assertIsNotNone(result)
        answer = UserAnswer.objects.first()
        self.assertEqual(answer.selected_option, self.option)
        self.assertEqual(result["selected_option"], self.option.id)

    def test_save_answer_with_custom_text(self):
        result = AnswerService.save_answer(
            session=self.session,
            question=self.question,
            selected_option=None,
            custom_text="my answer",
        )
        answer = UserAnswer.objects.first()
        self.assertEqual(answer.custom_text, "my answer")
        self.assertEqual(result["custom_text"], "my answer")

    def test_save_answer_invalid_both_fields(self):
        with self.assertRaises(ValidationError) as cm:
            AnswerService.save_answer(
                session=self.session,
                question=self.question,
                selected_option=self.option.id,
                custom_text="text",
            )
        self.assertIn(
            "Невозможно одновременно указать вариант ответа и свой ответ",
            str(cm.exception),
        )

    def test_save_answer_invalid_neither_field(self):
        with self.assertRaises(ValidationError) as cm:
            AnswerService.save_answer(
                session=self.session,
                question=self.question,
                selected_option=None,
                custom_text=None,
            )
        self.assertIn(
            "Требуется либо вариант ответа, либо свой ответ", str(cm.exception)
        )

    def test_save_answer_option_belongs_to_other_question(self):
        other_question = Question.objects.create(
            poll=self.poll, text="Other", weight=2
        )
        other_option = AnswerOption.objects.create(
            question=other_question, text="B", weight=1
        )
        with self.assertRaises(ValidationError) as cm:
            AnswerService.save_answer(
                session=self.session,
                question=self.question,
                selected_option=other_option.id,
                custom_text=None,
            )
        self.assertIn("не относится к указанному вопросу", str(cm.exception))
