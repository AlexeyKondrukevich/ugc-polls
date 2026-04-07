from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from ugc.models import AnswerOption, Poll, PollSession, Question, UserAnswer

User = get_user_model()


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser", password="pass123", email="test@example.com"
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("pass123"))

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            username="admin", password="adminpass", email="admin@example.com"
        )
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)


class PollModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", password="pass"
        )

    def test_poll_creation(self):
        poll = Poll.objects.create(title="Test Poll", author=self.user)
        self.assertEqual(str(poll), "Test Poll")
        self.assertEqual(poll.author, self.user)
        self.assertIsNotNone(poll.created_at)
        self.assertIsNotNone(poll.updated_at)


class QuestionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", password="pass"
        )
        self.poll = Poll.objects.create(title="Test Poll", author=self.user)

    def test_question_creation(self):
        q = Question.objects.create(
            poll=self.poll,
            text="What is your favorite color?",
            weight=1,
            allow_custom_answer=True,
        )
        self.assertEqual(str(q), "Test Poll - What is your favorite color?")
        self.assertEqual(q.weight, 1)
        self.assertTrue(q.allow_custom_answer)

    def test_unique_constraint_on_weight(self):
        Question.objects.create(poll=self.poll, text="Q1", weight=1)
        with self.assertRaises(IntegrityError):
            Question.objects.create(poll=self.poll, text="Q2", weight=1)

    def test_ordering_by_weight(self):
        Question.objects.create(poll=self.poll, text="Q2", weight=2)
        Question.objects.create(poll=self.poll, text="Q1", weight=1)
        questions = list(Question.objects.filter(poll=self.poll))
        self.assertEqual(questions[0].weight, 1)
        self.assertEqual(questions[1].weight, 2)

    def test_str_truncates_long_text(self):
        long_text = "A" * 100
        q = Question.objects.create(poll=self.poll, text=long_text, weight=1)
        expected = f"Test Poll - {long_text[:50]}"
        self.assertEqual(str(q), expected)


class AnswerOptionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", password="pass"
        )
        self.poll = Poll.objects.create(title="Test Poll", author=self.user)
        self.question = Question.objects.create(
            poll=self.poll, text="Q", weight=1
        )

    def test_answer_option_creation(self):
        opt = AnswerOption.objects.create(
            question=self.question, text="Red", weight=1
        )
        self.assertEqual(str(opt), "Red")
        self.assertEqual(opt.weight, 1)

    def test_unique_constraint_on_weight(self):
        AnswerOption.objects.create(question=self.question, text="A", weight=1)
        with self.assertRaises(IntegrityError):
            AnswerOption.objects.create(
                question=self.question, text="B", weight=1
            )


class PollSessionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.poll = Poll.objects.create(title="Test Poll", author=self.user)
        self.q1 = Question.objects.create(poll=self.poll, text="Q1", weight=1)

    def test_create_session(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        self.assertIsNone(session.end_time)
        self.assertFalse(session.is_completed())
        self.assertEqual(session.current_question, self.q1)

    def test_complete_session(self):
        session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.q1
        )
        session.complete()
        self.assertTrue(session.is_completed())
        self.assertIsNotNone(session.end_time)
        self.assertIsNone(session.current_question)

    def test_session_str(self):
        session = PollSession.objects.create(user=self.user, poll=self.poll)
        expected = f"{self.user.username} - {self.poll.title}"
        self.assertEqual(str(session), expected)


class UserAnswerModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.question = Question.objects.create(
            poll=self.poll, text="Q", weight=1
        )
        self.option = AnswerOption.objects.create(
            question=self.question, text="A", weight=1
        )
        self.other_question = Question.objects.create(
            poll=self.poll, text="Other", weight=2
        )
        self.other_option = AnswerOption.objects.create(
            question=self.other_question, text="B", weight=1
        )
        self.session = PollSession.objects.create(
            user=self.user, poll=self.poll, current_question=self.question
        )

    def test_create_answer_with_option(self):
        answer = UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            selected_option=self.option,
        )
        self.assertEqual(answer.selected_option, self.option)
        self.assertIsNone(answer.custom_text)
        self.assertIsNotNone(answer.answered_at)

    def test_create_answer_with_custom_text(self):
        answer = UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            custom_text="My own answer",
        )
        self.assertEqual(answer.custom_text, "My own answer")
        self.assertIsNone(answer.selected_option)

    def test_clean_raises_when_both_fields_missing(self):
        answer = UserAnswer(session=self.session, question=self.question)
        with self.assertRaises(ValidationError) as cm:
            answer.clean()
        self.assertIn(
            "Требуется либо вариант ответа, либо свой ответ", str(cm.exception)
        )

    def test_clean_raises_when_both_fields_provided(self):
        answer = UserAnswer(
            session=self.session,
            question=self.question,
            selected_option=self.option,
            custom_text="text",
        )
        with self.assertRaises(ValidationError) as cm:
            answer.clean()
        self.assertIn(
            "Невозможно одновременно указать вариант ответа и свой ответ",
            str(cm.exception),
        )

    def test_clean_raises_when_option_belongs_to_other_question(self):
        answer = UserAnswer(
            session=self.session,
            question=self.question,
            selected_option=self.other_option,
        )
        with self.assertRaises(ValidationError) as cm:
            answer.clean()
        self.assertIn(
            "Выбранный вариант ответа не относится к указанному вопросу",
            str(cm.exception),
        )

    def test_clean_passes_with_valid_option(self):
        answer = UserAnswer(
            session=self.session,
            question=self.question,
            selected_option=self.option,
        )
        try:
            answer.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly")

    def test_clean_passes_with_valid_custom_text(self):
        answer = UserAnswer(
            session=self.session,
            question=self.question,
            custom_text="Valid answer",
        )
        try:
            answer.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly")

    def test_unique_session_question_constraint(self):
        UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            selected_option=self.option,
        )
        with self.assertRaises(IntegrityError):
            UserAnswer.objects.create(
                session=self.session,
                question=self.question,
                custom_text="another",
            )

    def test_str_with_valid_user_and_question(self):
        answer = UserAnswer.objects.create(
            session=self.session,
            question=self.question,
            selected_option=self.option,
        )
        expected = f"Ответ пользователя {self.user.username} на вопрос {self.question.text[:30]}"
        self.assertEqual(str(answer), expected)
