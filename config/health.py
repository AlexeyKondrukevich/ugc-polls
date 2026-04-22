from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def health_live(request):
    return JsonResponse({"status": "ok"})


def health_ready(request):
    checks = {"database": False, "cache": False}

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except OperationalError:
        checks["database"] = False

    try:
        cache_key = "health:ready"
        cache.set(cache_key, "ok", timeout=10)
        checks["cache"] = cache.get(cache_key) == "ok"
    except Exception:  # noqa: BLE001
        checks["cache"] = False

    status_code = 200 if all(checks.values()) else 503
    return JsonResponse({"status": "ok" if status_code == 200 else "degraded", "checks": checks}, status=status_code)
