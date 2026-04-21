import random

from locust import HttpUser, between, task


class PollUser(HttpUser):
    wait_time = between(1, 3)
    token = None
    poll_id = None

    def on_start(self):
        """Регистрация и получение токена, выбор опроса"""
        # Уникальное имя пользователя, чтобы избежать конфликтов
        username = f"locust_{random.randint(1, 1000000)}"
        password = "TestPass123"

        # Регистрация
        reg_resp = self.client.post(
            "/api/register/",
            json={
                "username": username,
                "password": password,
                "password2": password,
                "email": f"{username}@example.com",
            },
        )
        if reg_resp.status_code == 201:
            self.token = reg_resp.json()["token"]
        else:
            # Если регистрация не удалась (например, пользователь уже есть), пробуем логин
            login_resp = self.client.post(
                "/api/login/",
                json={"username": username, "password": password},
            )
            if login_resp.status_code != 200:
                raise Exception("Не удалось авторизоваться")
            self.token = login_resp.json()["token"]

        # Устанавливаем заголовок авторизации для всех последующих запросов
        self.client.headers.update({"Authorization": f"Token {self.token}"})

        # Получаем список опросов и выбираем первый попавшийся
        polls_resp = self.client.get("/api/polls/")
        if polls_resp.status_code != 200:
            raise Exception("Не удалось получить список опросов")
        results = polls_resp.json().get("results", [])
        if not results:
            raise Exception(
                "Нет ни одного опроса. Сначала создайте опрос через админку или скрипт."
            )
        self.poll_id = results[0]["id"]

    @task(3)  # будет выполняться в 3 раза чаще, чем full_poll_flow
    def get_polls_list(self):
        self.client.get("/api/polls/")

    @task
    def full_poll_flow(self):
        """Полное прохождение опроса"""
        if not self.poll_id:
            return

        # Последовательно отвечаем на вопросы, пока не получим 204 (опрос завершён)
        while True:
            resp = self.client.get(f"/api/polls/{self.poll_id}/next-question/")
            if resp.status_code == 204:
                # Опрос завершён
                break
            if resp.status_code != 200:
                # Логируем ошибку и прерываем прохождение для этого пользователя
                print(
                    f"Ошибка получения вопроса: {resp.status_code} {resp.text}"
                )
                break

            question = resp.json()
            question_id = question["id"]
            options = question.get("options", [])

            # Выбираем случайный вариант ответа, если есть; иначе пишем свой текст
            if options and random.choice([True, False]):
                selected_option = random.choice(options)["id"]
                answer_data = {
                    "question_id": question_id,
                    "selected_option": selected_option,
                }
            else:
                answer_data = {
                    "question_id": question_id,
                    "custom_text": "Мой ответ",
                }

            submit_resp = self.client.post(
                f"/api/polls/{self.poll_id}/submit-answer/", json=answer_data
            )
            if submit_resp.status_code != 200:
                print(
                    f"Ошибка отправки ответа: {submit_resp.status_code} {submit_resp.text}"
                )
                break
