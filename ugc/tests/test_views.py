from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ugc.models import AnswerOption, Poll, PollSession, Question, UserAnswer

User = get_user_model()


class RegisterViewTest(APITestCase):
    def test_register_success(self):
        url = reverse("register")
        data = {
            "username": "newuser",
            "password": "StrongPass123",
            "password2": "StrongPass123",
            "email": "new@example.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["username"], "newuser")
        self.assertEqual(response.data["user"]["email"], "new@example.com")
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_password_mismatch(self):
        url = reverse("register")
        data = {
            "username": "newuser",
            "password": "StrongPass123",
            "password2": "WrongPass123",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_register_missing_fields(self):
        url = reverse("register")
        data = {"username": "onlyuser"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertIn("password2", response.data)


class LoginViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="StrongPass123"
        )
        self.url = reverse("login")

    def test_login_success(self):
        data = {"username": "testuser", "password": "StrongPass123"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["username"], "testuser")

    def test_login_invalid_credentials(self):
        data = {"username": "testuser", "password": "wrong"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)


class PollViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.client.force_authenticate(user=self.user)
        self.poll1 = Poll.objects.create(title="Poll A", author=self.user)
        self.poll2 = Poll.objects.create(title="Poll B", author=self.user)
        self.question = Question.objects.create(
            poll=self.poll1, text="Q1", weight=1
        )
        self.option = AnswerOption.objects.create(
            question=self.question, text="A1", weight=1
        )

    def test_list_polls(self):
        url = reverse("poll-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["results"][0]["title"], "Poll A")
        self.assertEqual(response.data["results"][0]["questions_count"], 1)

    def test_retrieve_poll_detail(self):
        url = reverse("poll-detail", args=[self.poll1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Poll A")
        self.assertEqual(len(response.data["questions"]), 1)
        self.assertEqual(response.data["questions"][0]["text"], "Q1")
        self.assertEqual(len(response.data["questions"][0]["options"]), 1)

    def test_retrieve_nonexistent_poll(self):
        url = reverse("poll-detail", args=[999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NextQuestionViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.client.force_authenticate(user=self.user)
        self.poll = Poll.objects.create(title="Test Poll", author=self.user)
        self.q1 = Question.objects.create(poll=self.poll, text="Q1", weight=1)
        self.q2 = Question.objects.create(poll=self.poll, text="Q2", weight=2)
        self.opt = AnswerOption.objects.create(
            question=self.q1, text="A1", weight=1
        )
        self.url = reverse("next-question", args=[self.poll.id])

    def test_first_question_creates_session(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.q1.id)
        self.assertTrue(
            PollSession.objects.filter(user=self.user, poll=self.poll).exists()
        )
        session = PollSession.objects.get(user=self.user, poll=self.poll)
        self.assertEqual(session.current_question, self.q1)

    def test_second_question_after_answer(self):
        self.client.get(self.url)
        submit_url = reverse("submit-answer", args=[self.poll.id])
        self.client.post(
            submit_url,
            {"question_id": self.q1.id, "selected_option": self.opt.id},
            format="json",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.q2.id)

    def test_completed_poll_returns_204(self):
        self.client.get(self.url)
        submit_url = reverse("submit-answer", args=[self.poll.id])
        self.client.post(
            submit_url,
            {"question_id": self.q1.id, "selected_option": self.opt.id},
            format="json",
        )
        self.client.post(
            submit_url,
            {"question_id": self.q2.id, "custom_text": "done"},
            format="json",
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_nonexistent_poll(self):
        url = reverse("next-question", args=[999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SubmitAnswerViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.client.force_authenticate(user=self.user)
        self.poll = Poll.objects.create(title="Test Poll", author=self.user)
        self.q1 = Question.objects.create(poll=self.poll, text="Q1", weight=1)
        self.q2 = Question.objects.create(poll=self.poll, text="Q2", weight=2)
        self.opt1 = AnswerOption.objects.create(
            question=self.q1, text="A1", weight=1
        )
        self.opt2 = AnswerOption.objects.create(
            question=self.q2, text="A2", weight=1
        )
        self.url = reverse("submit-answer", args=[self.poll.id])

    def test_submit_answer_with_option(self):
        self.client.get(reverse("next-question", args=[self.poll.id]))
        data = {"question_id": self.q1.id, "selected_option": self.opt1.id}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(UserAnswer.objects.count(), 1)
        answer = UserAnswer.objects.first()
        self.assertEqual(answer.selected_option, self.opt1)
        session = PollSession.objects.get(user=self.user, poll=self.poll)
        self.assertEqual(session.current_question, self.q2)

    def test_submit_answer_with_custom_text(self):
        self.client.get(reverse("next-question", args=[self.poll.id]))
        data = {"question_id": self.q1.id, "custom_text": "My own answer"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        answer = UserAnswer.objects.first()
        self.assertEqual(answer.custom_text, "My own answer")

    def test_submit_answer_without_active_session(self):
        data = {"question_id": self.q1.id, "selected_option": self.opt1.id}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Нет активной сессии", str(response.data))

    def test_submit_answer_with_invalid_question_id(self):
        self.client.get(reverse("next-question", args=[self.poll.id]))
        data = {"question_id": 999, "selected_option": self.opt1.id}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Неверный вопрос", str(response.data))

    def test_submit_answer_with_option_belonging_to_other_question(self):
        self.client.get(reverse("next-question", args=[self.poll.id]))
        data = {"question_id": self.q1.id, "selected_option": self.opt2.id}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("не относится к указанному вопросу", str(response.data))

    def test_submit_answer_after_completion_fails(self):
        self.client.get(reverse("next-question", args=[self.poll.id]))
        self.client.post(
            self.url,
            {"question_id": self.q1.id, "selected_option": self.opt1.id},
            format="json",
        )
        self.client.post(
            self.url,
            {"question_id": self.q2.id, "custom_text": "done"},
            format="json",
        )

        response = self.client.post(
            self.url,
            {"question_id": self.q2.id, "custom_text": "again"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("завершили этот опрос", str(response.data))

    def test_unauthenticated(self):
        self.client.force_authenticate(user=None)
        data = {"question_id": self.q1.id, "selected_option": self.opt1.id}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
