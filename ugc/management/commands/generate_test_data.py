# ugc/management/commands/generate_test_data.py

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from ugc.models import AnswerOption, Poll, Question

User = get_user_model()


class Command(BaseCommand):
    help = "Generate test data: polls, questions, answer options"

    def add_arguments(self, parser):
        parser.add_argument(
            "--polls", type=int, default=1000, help="Number of polls"
        )
        parser.add_argument(
            "--questions", type=int, default=5, help="Questions per poll"
        )
        parser.add_argument(
            "--answers", type=int, default=3, help="Answers per question"
        )
        parser.add_argument(
            "--batch-size", type=int, default=500, help="Batch size for polls"
        )

    def handle(self, *args, **options):
        total_polls = options["polls"]
        q_per_poll = options["questions"]
        a_per_q = options["answers"]
        batch_size = options["batch_size"]

        # Создаём автора
        user, created = User.objects.get_or_create(
            username="test_author",
            defaults={"email": "author@example.com"},
        )
        if created:
            user.set_password("testpass123")
            user.save()
            self.stdout.write(self.style.SUCCESS("Test author created."))

        self.stdout.write(
            f"Generating {total_polls:,} polls with {q_per_poll} questions each..."
        )

        poll_batch = []
        poll_counter = 0

        for poll_num in range(1, total_polls + 1):
            title = f"Опрос #{poll_num}: Мнение о технологиях"
            poll_batch.append(Poll(title=title, author=user))

            if len(poll_batch) >= batch_size or poll_num == total_polls:
                # Вставляем батч опросов
                Poll.objects.bulk_create(poll_batch)
                # Получаем ID только что созданных опросов (последние len(poll_batch) записей)
                last_ids = Poll.objects.order_by("-id")[
                    : len(poll_batch)
                ].values_list("id", flat=True)
                # Переворачиваем, чтобы ID шли в порядке возрастания
                new_poll_ids = list(reversed(last_ids))
                poll_counter += len(new_poll_ids)

                # Генерируем вопросы и ответы для этих опросов
                self._generate_questions_and_answers(
                    new_poll_ids, q_per_poll, a_per_q, batch_size
                )

                self.stdout.write(f"Processed {poll_counter:,} polls...")
                poll_batch = []

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {total_polls:,} polls, {total_polls * q_per_poll:,} questions, "
                f"{total_polls * q_per_poll * a_per_q:,} answer options."
            )
        )

    def _generate_questions_and_answers(
        self, poll_ids, q_per_poll, a_per_q, batch_size
    ):
        """Генерирует вопросы и ответы для заданных ID опросов."""
        question_batch = []
        answer_batch = []

        for poll_id in poll_ids:
            for q_order in range(1, q_per_poll + 1):
                question_text = f"Вопрос {q_order} для опроса {poll_id}"
                question_batch.append(
                    Question(
                        poll_id=poll_id,
                        text=question_text,
                        weight=q_order,
                        allow_custom_answer=random.choice([True, False]),
                    )
                )
                if len(question_batch) >= batch_size:
                    Question.objects.bulk_create(question_batch)
                    question_batch = []

        if question_batch:
            Question.objects.bulk_create(question_batch)

        # Получаем все созданные вопросы для этих опросов (только что вставленные)
        # Чтобы не загружать все вопросы из базы, можно сгенерировать ответы сразу после вставки каждого батча вопросов,
        # но проще сначала получить ID всех вопросов, связанных с этими опросами.
        all_questions = Question.objects.filter(poll_id__in=poll_ids).order_by(
            "id"
        )
        for question in all_questions:
            for a_order in range(1, a_per_q + 1):
                answer_text = f"Вариант {a_order} для вопроса {question.id}"
                answer_batch.append(
                    AnswerOption(
                        question_id=question.id,
                        text=answer_text,
                        weight=a_order,
                    )
                )
                if len(answer_batch) >= batch_size:
                    AnswerOption.objects.bulk_create(answer_batch)
                    answer_batch = []

        if answer_batch:
            AnswerOption.objects.bulk_create(answer_batch)
        if answer_batch:
            AnswerOption.objects.bulk_create(answer_batch)
