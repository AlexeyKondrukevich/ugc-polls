from unittest.mock import patch

from django.contrib.auth import get_user_model
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
from ugc.signals import invalidate_poll_cache

User = get_user_model()


class PollCacheInvalidationTest(TransactionTestCase):
    def setUp(self):
        # Мокаем django_redis.get_redis_connection, чтобы избежать ошибок Redis
        patcher = patch("django_redis.get_redis_connection")
        self.mock_get_redis = patcher.start()
        self.addCleanup(patcher.stop)
        # Возвращаем мок-соединение
        self.mock_conn = self.mock_get_redis.return_value
        self.mock_conn.scan_iter.return_value = []

        # Создаём пользователя и опрос (это вызовет сигнал и invalidate_poll_cache)
        self.user = User.objects.create_user(username="user", password="pass")
        self.poll = Poll.objects.create(title="Test Poll", author=self.user)

    @patch("ugc.signals.invalidate_poll_cache")
    def test_poll_cache_invalidator_called_on_save(self, mock_invalidate):
        # Мок уже сработал при создании опроса в setUp, сбрасываем
        mock_invalidate.reset_mock()
        new_poll = Poll.objects.create(title="New Poll", author=self.user)
        mock_invalidate.assert_called_once()
        mock_invalidate.reset_mock()

        new_poll.title = "Updated"
        new_poll.save()
        mock_invalidate.assert_called_once()
        mock_invalidate.reset_mock()

        new_poll.delete()
        mock_invalidate.assert_called_once()

    def test_invalidate_poll_cache_with_redis(self):
        # Сбрасываем мок-соединение, чтобы очистить вызовы из setUp
        self.mock_conn.reset_mock()
        self.mock_conn.scan_iter.return_value = ["key1", "key2"]

        invalidate_poll_cache()

        self.mock_conn.scan_iter.assert_called_once_with(match="*cache_page*")
        self.assertEqual(self.mock_conn.delete.call_count, 2)

    def test_invalidate_poll_cache_fallback_to_cache_clear(self):
        # Переопределяем мок, чтобы вызвать ImportError
        with patch(
            "django_redis.get_redis_connection", side_effect=ImportError
        ):
            with patch("ugc.signals.cache.clear") as mock_clear:
                invalidate_poll_cache()
                mock_clear.assert_called_once()


class UpdateStatsSignalTest(TransactionTestCase):
    def setUp(self):
        # Мокаем invalidate_poll_cache, чтобы при создании Poll не было проблем
        self.invalidate_patcher = patch("ugc.signals.invalidate_poll_cache")
        self.mock_invalidate = self.invalidate_patcher.start()
        self.addCleanup(self.invalidate_patcher.stop)

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

    def test_update_stats_on_answer_creation(self):
        UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            selected_option=self.option,
        )
        poll_stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(poll_stats.total_answers, 1)

        q_stats = QuestionStatistics.objects.get(question=self.question)
        self.assertEqual(q_stats.total_answers, 1)
        self.assertEqual(q_stats.custom_answers_count, 0)

        opt_stats = AnswerOptionStatistics.objects.get(option=self.option)
        self.assertEqual(opt_stats.times_selected, 1)

    def test_update_stats_custom_answer(self):
        UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            custom_text="my answer",
        )
        q_stats = QuestionStatistics.objects.get(question=self.question)
        self.assertEqual(q_stats.total_answers, 1)
        self.assertEqual(q_stats.custom_answers_count, 1)

    def test_update_stats_runs_on_update(self):
        answer = UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            selected_option=self.option,
        )
        PollStatistics.objects.filter(poll=self.poll).update(total_answers=0)
        answer.custom_text = "changed"
        answer.save()
        poll_stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(poll_stats.total_answers, 1)


class PollSessionCompletionSignalTest(TransactionTestCase):
    def setUp(self):
        # Мокаем invalidate_poll_cache
        self.invalidate_patcher = patch("ugc.signals.invalidate_poll_cache")
        self.mock_invalidate = self.invalidate_patcher.start()
        self.addCleanup(self.invalidate_patcher.stop)

        self.user = User.objects.create_user(username="user", password="pass")
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.question = Question.objects.create(
            poll=self.poll, text="Q", weight=1
        )
        self.session = PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=120),
        )

    def test_completion_updates_poll_statistics(self):
        self.session.end_time = timezone.now()
        self.session.save()
        stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(stats.total_completed_sessions, 1)
        self.assertIsNotNone(stats.average_completion_time_seconds)
        self.assertAlmostEqual(
            stats.average_completion_time_seconds, 120.0, delta=0.1
        )

    def test_unfinished_session_does_not_update(self):
        self.session.save()
        with self.assertRaises(PollStatistics.DoesNotExist):
            PollStatistics.objects.get(poll=self.poll)

    def test_multiple_completions_incremental_average(self):
        self.session.end_time = self.session.start_time + timezone.timedelta(
            seconds=100
        )
        self.session.save()
        PollSession.objects.create(
            user=self.user,
            poll=self.poll,
            start_time=timezone.now() - timezone.timedelta(seconds=200),
            end_time=timezone.now(),
        )
        stats = PollStatistics.objects.get(poll=self.poll)
        self.assertEqual(stats.total_completed_sessions, 2)
        self.assertAlmostEqual(
            stats.average_completion_time_seconds, 150.0, delta=0.1
        )


class SignalIntegrationTest(TransactionTestCase):
    """Проверка, что сигналы действительно вызывают нужные функции через on_commit."""

    def setUp(self):
        # Мокаем invalidate_poll_cache
        self.invalidate_patcher = patch("ugc.signals.invalidate_poll_cache")
        self.mock_invalidate = self.invalidate_patcher.start()
        self.addCleanup(self.invalidate_patcher.stop)

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

    @patch("ugc.signals.update_stats")
    def test_user_answer_signal_calls_update_stats(self, mock_update_stats):
        UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            selected_option=self.option,
        )
        mock_update_stats.assert_called_once()

    @patch("ugc.signals.update_poll_statistics_on_completion")
    def test_poll_session_signal_calls_update_on_completion(self, mock_update):
        self.session.end_time = timezone.now()
        self.session.save()
        mock_update.assert_called_once_with(self.session)

    @patch("ugc.signals.invalidate_poll_cache")
    def test_poll_signal_calls_invalidate(self, mock_invalidate):
        # Сбросим мок, так как в setUp уже был вызов при создании опроса
        mock_invalidate.reset_mock()
        Poll.objects.create(title="New", author=self.user)
        mock_invalidate.assert_called_once()
