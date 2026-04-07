from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TransactionTestCase
from django.utils import timezone

from ugc.models import (
    AnswerOption,
    AnswerOptionStatistics,
    Poll,
    PollSession,
    PollStatistics,
    Question,
    QuestionStatistics,
    UserAnswer,
)

User = get_user_model()


class StatisticsFunctionTest(TransactionTestCase):
    """
    Тесты для статистики: проверяем, что сигналы корректно обновляют счётчики.
    Сигналы уже вызываются автоматически при сохранении объектов.
    """

    def setUp(self):
        # Мокаем invalidate_poll_cache, чтобы при создании опроса не было проблем с Redis
        patcher = patch("ugc.signals.invalidate_poll_cache")
        self.mock_invalidate = patcher.start()
        self.addCleanup(patcher.stop)

        self.user = User.objects.create_user(username="user", password="pass")
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.q1 = Question.objects.create(poll=self.poll, text="Q1", weight=1)
        self.q2 = Question.objects.create(poll=self.poll, text="Q2", weight=2)
        self.opt1 = AnswerOption.objects.create(
            question=self.q1, text="A1", weight=1
        )
        self.opt2 = AnswerOption.objects.create(
            question=self.q2, text="A2", weight=1
        )

    # ---- Тесты обновления статистики при ответе (сигнал post_save UserAnswer) ----

    def test_stats_on_answer_with_option(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        UserAnswer.objects.create(
            session=session, question=self.q1, selected_option=self.opt1
        )

        poll_stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(poll_stats.total_answers, 1)
        self.assertEqual(poll_stats.total_completed_sessions, 0)

        q_stats = QuestionStatistics.objects.get(question=self.q1)
        self.assertEqual(q_stats.total_answers, 1)
        self.assertEqual(q_stats.custom_answers_count, 0)

        opt_stats = AnswerOptionStatistics.objects.get(option=self.opt1)
        self.assertEqual(opt_stats.times_selected, 1)

    def test_stats_on_answer_with_custom_text(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        UserAnswer.objects.create(
            session=session, question=self.q1, custom_text="My answer"
        )

        q_stats = QuestionStatistics.objects.get(question=self.q1)
        self.assertEqual(q_stats.total_answers, 1)
        self.assertEqual(q_stats.custom_answers_count, 1)

        # Вариант не выбран – статистика для opt1 не создаётся
        self.assertFalse(
            AnswerOptionStatistics.objects.filter(option=self.opt1).exists()
        )

    def test_stats_multiple_answers_different_questions(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        UserAnswer.objects.create(
            session=session, question=self.q1, selected_option=self.opt1
        )
        # Переключаем текущий вопрос (имитируем прохождение)
        session.current_question = self.q2
        session.save()
        UserAnswer.objects.create(
            session=session, question=self.q2, selected_option=self.opt2
        )

        poll_stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(poll_stats.total_answers, 2)

        q1_stats = QuestionStatistics.objects.get(question=self.q1)
        self.assertEqual(q1_stats.total_answers, 1)
        q2_stats = QuestionStatistics.objects.get(question=self.q2)
        self.assertEqual(q2_stats.total_answers, 1)

        opt1_stats = AnswerOptionStatistics.objects.get(option=self.opt1)
        self.assertEqual(opt1_stats.times_selected, 1)
        opt2_stats = AnswerOptionStatistics.objects.get(option=self.opt2)
        self.assertEqual(opt2_stats.times_selected, 1)

    def test_cannot_answer_same_question_twice_in_one_session(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        UserAnswer.objects.create(
            session=session, question=self.q1, selected_option=self.opt1
        )
        with self.assertRaises(IntegrityError):
            UserAnswer.objects.create(
                session=session, question=self.q1, custom_text="Again"
            )

    # ---- Тесты обновления статистики при завершении сессии (сигнал post_save PollSession) ----

    def test_stats_on_session_completion(self):
        PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=120),
            end_time=timezone.now(),
        )
        # Сигнал post_save сам вызовет update_poll_statistics_on_completion

        stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(stats.total_completed_sessions, 1)
        self.assertAlmostEqual(
            stats.average_completion_time_seconds, 120.0, delta=0.1
        )

    def test_stats_multiple_completions(self):
        PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=100),
            end_time=timezone.now(),
        )
        PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=200),
            end_time=timezone.now(),
        )
        stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(stats.total_completed_sessions, 2)
        expected_avg = (100.0 + 200.0) / 2
        self.assertAlmostEqual(
            stats.average_completion_time_seconds, expected_avg, delta=0.1
        )

    def test_stats_with_existing_none_avg(self):
        # Создаём статистику с пустым средним (например, нет завершённых)
        poll_stats, _ = PollStatistics.objects.get_or_create(poll=self.poll)
        poll_stats.total_completed_sessions = 0
        poll_stats.average_completion_time_seconds = None
        poll_stats.save()

        PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=90),
            end_time=timezone.now(),
        )
        stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(stats.total_completed_sessions, 1)
        self.assertAlmostEqual(
            stats.average_completion_time_seconds, 90.0, delta=0.1
        )

    def test_unfinished_session_does_not_create_stats(self):
        PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=50),
            end_time=None,
        )
        self.assertFalse(
            PollStatistics.objects.filter(poll=self.poll).exists()
        )

    # ---- Комбинированный тест (полный цикл) ----

    def test_full_poll_flow(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )

        # Ответ на первый вопрос
        UserAnswer.objects.create(
            session=session, question=self.q1, selected_option=self.opt1
        )
        session.current_question = self.q2
        session.save()

        UserAnswer.objects.create(
            session=session, question=self.q2, custom_text="Done"
        )

        session.end_time = timezone.now()
        session.save()

        poll_stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(poll_stats.total_answers, 2)
        self.assertEqual(poll_stats.total_completed_sessions, 1)
        self.assertIsNotNone(poll_stats.average_completion_time_seconds)

        q1_stats = QuestionStatistics.objects.get(question=self.q1)
        self.assertEqual(q1_stats.total_answers, 1)
        self.assertEqual(q1_stats.custom_answers_count, 0)

        q2_stats = QuestionStatistics.objects.get(question=self.q2)
        self.assertEqual(q2_stats.total_answers, 1)
        self.assertEqual(q2_stats.custom_answers_count, 1)

        opt1_stats = AnswerOptionStatistics.objects.get(option=self.opt1)
        self.assertEqual(opt1_stats.times_selected, 1)

    # ---- Тест на идемпотентность: повторный вызов complete не увеличивает счётчик ----
    def test_completion_idempotent(self):
        PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=60),
            end_time=timezone.now(),
        )
        stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(stats.total_completed_sessions, 1)
