"""Project-level views that sit outside DRF."""

import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


@never_cache
@require_safe
def health(request):
    """Liveness and database check for container health checks.

    A plain Django view, so DRF's authentication and throttles don't apply.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check: database query failed")
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})
