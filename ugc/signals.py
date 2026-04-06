from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Poll


def invalidate_poll_cache():
    """Удаляет все ключи кеша, созданные cache_page для опросов."""
    try:
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
        for key in conn.scan_iter(match="*cache_page*"):
            conn.delete(key)
    except ImportError:
        cache.clear()


@receiver(
    [post_save, post_delete],
    sender=Poll,
    dispatch_uid="invalidate_poll_cache",
    weak=False,
)
def poll_cache_invalidator(sender, **kwargs):
    return transaction.on_commit(lambda: invalidate_poll_cache())
