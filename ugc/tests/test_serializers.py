from django.contrib.auth import get_user_model
from django.db.models import Count
from django.test import TestCase

from ugc.models import AnswerOption, Poll, PollSession, Question
from ugc.serializers import (
    AnswerOptionSerializer,
    PollDetailSerializer,
    PollSerializer,
    QuestionSerializer,
    RegisterSerializer,
    SubmitAnswerInputSerializer,
    UserAnswerSerializer,
)

User = get_user_model()


class AnswerOptionSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", password="pass"
        )
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.question = Question.objects.create(
            poll=self.poll, text="Q", weight=1
        )

    def test_serializer_fields(self):
        opt = AnswerOption.objects.create(
            question=self.question, text="Red", weight=1
        )
        serializer = AnswerOptionSerializer(opt)
        self.assertEqual(serializer.data["id"], opt.id)
        self.assertEqual(serializer.data["text"], "Red")
        self.assertEqual(serializer.data["weight"], 1)


class QuestionSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", password="pass"
        )
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.question = Question.objects.create(
            poll=self.poll, text="Q", weight=1, allow_custom_answer=True
        )
        self.opt1 = AnswerOption.objects.create(
            question=self.question, text="A", weight=1
        )
        self.opt2 = AnswerOption.objects.create(
            question=self.question, text="B", weight=2
        )

    def test_serializer_includes_options(self):
        serializer = QuestionSerializer(self.question)
        data = serializer.data
        self.assertEqual(data["id"], self.question.id)
        self.assertEqual(data["text"], "Q")
        self.assertEqual(data["weight"], 1)
        self.assertTrue(data["allow_custom_answer"])
        self.assertEqual(len(data["options"]), 2)
        self.assertEqual(data["options"][0]["text"], "A")
        self.assertEqual(data["options"][1]["text"], "B")


class PollSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", password="pass"
        )
        self.poll = Poll.objects.create(title="Test Poll", author=self.user)

    def test_serializer_contains_questions_count(self):
        Question.objects.create(poll=self.poll, text="Q1", weight=1)
        Question.objects.create(poll=self.poll, text="Q2", weight=2)

        qs = Poll.objects.annotate(questions_count=Count("questions"))
        poll_annotated = qs.get(id=self.poll.id)
        serializer = PollSerializer(poll_annotated)
        self.assertEqual(serializer.data["questions_count"], 2)
        self.assertEqual(serializer.data["title"], "Test Poll")
        self.assertEqual(serializer.data["author"], self.user.id)


class PollDetailSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", password="pass"
        )
        self.poll = Poll.objects.create(title="Poll", author=self.user)
        self.q1 = Question.objects.create(poll=self.poll, text="Q1", weight=1)
        self.q2 = Question.objects.create(poll=self.poll, text="Q2", weight=2)
        AnswerOption.objects.create(question=self.q1, text="A1", weight=1)
        AnswerOption.objects.create(question=self.q2, text="A2", weight=1)

    def test_serializer_includes_questions(self):
        serializer = PollDetailSerializer(self.poll)
        data = serializer.data
        self.assertEqual(data["title"], "Poll")
        self.assertEqual(len(data["questions"]), 2)
        self.assertEqual(data["questions"][0]["text"], "Q1")
        self.assertEqual(data["questions"][1]["text"], "Q2")
        self.assertTrue("options" in data["questions"][0])


class UserAnswerSerializerTest(TestCase):
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

    def test_valid_option_answer(self):
        data = {
            "session": self.session.id,
            "question": self.question.id,
            "selected_option": self.option.id,
        }
        serializer = UserAnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        answer = serializer.save()
        self.assertEqual(answer.selected_option, self.option)

    def test_valid_custom_answer(self):
        data = {
            "session": self.session.id,
            "question": self.question.id,
            "custom_text": "my answer",
        }
        serializer = UserAnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        answer = serializer.save()
        self.assertEqual(answer.custom_text, "my answer")

    def test_invalid_both_fields(self):
        data = {
            "session": self.session.id,
            "question": self.question.id,
            "selected_option": self.option.id,
            "custom_text": "text",
        }
        serializer = UserAnswerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Невозможно одновременно указать вариант ответа и свой ответ",
            str(serializer.errors),
        )

    def test_invalid_neither_field(self):
        data = {
            "session": self.session.id,
            "question": self.question.id,
        }
        serializer = UserAnswerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Требуется либо вариант ответа, либо свой ответ",
            str(serializer.errors),
        )

    def test_invalid_option_belongs_to_other_question(self):
        data = {
            "session": self.session.id,
            "question": self.question.id,
            "selected_option": self.other_option.id,
        }
        serializer = UserAnswerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Выбранный вариант ответа не относится к указанному вопросу",
            str(serializer.errors),
        )


class RegisterSerializerTest(TestCase):
    def test_valid_registration(self):
        data = {
            "username": "newuser",
            "password": "strongpass123",
            "password2": "strongpass123",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.check_password("strongpass123"))

    def test_passwords_mismatch(self):
        data = {
            "username": "newuser",
            "password": "StrongPass123",
            "password2": "WrongPass123",
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)
        self.assertIn(
            "Пароли не совпадают", str(serializer.errors["password"])
        )

    def test_missing_required_fields(self):
        data = {"username": "onlyuser"}
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)
        self.assertIn("password2", serializer.errors)


class SubmitAnswerInputSerializerTest(TestCase):
    def test_valid_selected_option(self):
        data = {"question_id": 1, "selected_option": 5}
        serializer = SubmitAnswerInputSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_valid_custom_text(self):
        data = {"question_id": 1, "custom_text": "Hello"}
        serializer = SubmitAnswerInputSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_both_fields(self):
        data = {"question_id": 1, "selected_option": 5, "custom_text": "Hello"}
        serializer = SubmitAnswerInputSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Невозможно одновременно указать вариант ответа и свой ответ",
            str(serializer.errors),
        )

    def test_invalid_neither_field(self):
        data = {"question_id": 1}
        serializer = SubmitAnswerInputSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Требуется либо вариант ответа, либо свой ответ",
            str(serializer.errors),
        )
