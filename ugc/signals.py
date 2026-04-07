from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import (
    AnswerOptionStatistics,
    Poll,
    PollSession,
    PollStatistics,
    QuestionStatistics,
    UserAnswer,
)


def invalidate_poll_cache() -> None:
    """Удаляет все ключи кеша, созданные cache_page для опросов."""
    try:
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
        for key in conn.scan_iter(match="*cache_page*"):
            conn.delete(key)
    except ImportError:
        cache.clear()


@transaction.atomic
def update_stats(answer: UserAnswer) -> None:
    """
    Обновляет агрегированную статистику для опроса, вопроса и варианта ответа
    на основе только что сохранённого ответа пользователя.

    Все операции выполняются в атомарной транзакции с блокировкой строк
    (`select_for_update`), чтобы избежать гонок при параллельных ответах.

    :param answer: Экземпляр модели `UserAnswer`, для которого нужно обновить статистику.
    """

    poll = answer.session.poll
    question = answer.question

    poll_stats, _ = PollStatistics.objects.select_for_update().get_or_create(
        poll=poll
    )
    poll_stats.total_answers += 1
    poll_stats.save()

    (
        q_stats,
        _,
    ) = QuestionStatistics.objects.select_for_update().get_or_create(
        question=question
    )
    q_stats.total_answers += 1
    if answer.custom_text:
        q_stats.custom_answers_count += 1
    q_stats.save()

    if answer.selected_option:
        (
            opt_stats,
            _,
        ) = AnswerOptionStatistics.objects.select_for_update().get_or_create(
            option=answer.selected_option
        )
        opt_stats.times_selected += 1
        opt_stats.save()


@transaction.atomic
def update_poll_statistics_on_completion(session: PollSession) -> None:
    """
    Обновляет статистику опроса на основе завершённой сессии.

    Вычисляет длительность сессии и инкрементально обновляет:
    - total_completed_sessions
    - average_completion_time_seconds

    :param session: Завершённая сессия (end_time не None)
    """
    duration = (session.end_time - session.start_time).total_seconds()

    poll_stats, _ = PollStatistics.objects.select_for_update().get_or_create(
        poll=session.poll
    )
    old_count = poll_stats.total_completed_sessions
    old_avg = poll_stats.average_completion_time_seconds

    poll_stats.total_completed_sessions += 1

    if old_avg is None:
        poll_stats.average_completion_time_seconds = duration
    else:
        new_avg = (old_avg * old_count + duration) / (old_count + 1)
        poll_stats.average_completion_time_seconds = new_avg

    poll_stats.save()


@receiver(
    [post_save, post_delete],
    sender=Poll,
    dispatch_uid="invalidate_poll_cache",
    weak=False,
)
def poll_cache_invalidator(sender: type[Poll], **kwargs) -> None:
    """
    Сигнал, который срабатывает после сохранения или удаления опроса.
    Инвалидирует кеш списка опросов (вызывая `invalidate_poll_cache`).
    """
    return transaction.on_commit(lambda: invalidate_poll_cache())


@receiver(
    post_save,
    sender=UserAnswer,
    dispatch_uid="update_statistics_on_answer",
    weak=False,
)
def update_statistics_on_answer(
    sender: type[UserAnswer], instance: UserAnswer, created: bool, **kwargs
) -> None:
    """
    Сигнал, срабатывающий при создании нового ответа пользователя.
    Запускает обновление статистики (`update_stats`) после фиксации транзакции.
    """
    return transaction.on_commit(lambda: update_stats(instance))


@receiver(
    post_save,
    sender=PollSession,
    dispatch_uid="update_poll_statistics_on_completion",
    weak=False,
)
def poll_session_post_save(
    sender: type[PollSession], instance: PollSession, created: bool, **kwargs
) -> None:
    """
    Когда сессия завершается (end_time проставлено), обновляем статистику опроса:
    - увеличиваем total_completed_sessions
    - инкрементально пересчитываем среднее время прохождения
    """
    if instance.end_time is None:
        return

    return transaction.on_commit(
        lambda: update_poll_statistics_on_completion(instance)
    )
