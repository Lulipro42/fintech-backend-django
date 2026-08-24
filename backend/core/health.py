from django.http import JsonResponse
from django.views import View
from django.db import connection
from django.db.utils import OperationalError
import time


class HealthCheckView(View):  # ← Hereda de View, no clase suelta
    def get(self, request):
        start = time.time()
        
        db_status = "up"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except OperationalError:
            db_status = "down"
        
        duration_ms = round((time.time() - start) * 1000, 2)
        status_code = 200 if db_status == "up" else 503
        status = "ok" if db_status == "up" else "error"
        
        return JsonResponse(
            {
                "status": status,
                "db": db_status,
                "response_time_ms": duration_ms,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            status=status_code,
        )