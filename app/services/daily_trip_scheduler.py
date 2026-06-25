import logging
import os
import sys
import threading
import time
from datetime import datetime, time as datetime_time, timedelta

from django.db import connection
from django.utils import timezone

from app.services.daily_trip_generation import generate_daily_trips_for_date

logger = logging.getLogger(__name__)

JOB_NAME = "daily_trip_generation"
DEFAULT_RUN_TIME = "04:00"
_scheduler_thread = None
_scheduler_lock = threading.Lock()
_status = {
    "job_name": JOB_NAME,
    "enabled": False,
    "run_time": DEFAULT_RUN_TIME,
    "last_run_at": None,
    "last_result": None,
    "last_error": None,
    "next_run_at": None,
    "is_running": False,
}


def _parse_run_time(value):
    try:
        hour, minute = str(value or DEFAULT_RUN_TIME).split(":", 1)
        return datetime_time(hour=int(hour), minute=int(minute))
    except (TypeError, ValueError):
        return datetime_time(hour=4, minute=0)


def _next_run_after(now, run_time):
    candidate = datetime.combine(now.date(), run_time, tzinfo=now.tzinfo)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _try_database_lock(lock_name):
    if connection.vendor != "mysql":
        return True
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 0)", [lock_name])
        row = cursor.fetchone()
    return bool(row and row[0] == 1)


def _release_database_lock(lock_name):
    if connection.vendor != "mysql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT RELEASE_LOCK(%s)", [lock_name])


def run_daily_trip_job(target_date=None, force: bool = False):
    target_date = target_date or timezone.localdate()
    mode = "manual" if force else "auto"
    lock_name = f"iwms:{JOB_NAME}:{target_date.isoformat()}:{mode}"
    if not _try_database_lock(lock_name):
        return {
            "skipped": True,
            "reason": "Another scheduler worker is already generating daily trips.",
        }

    _status["is_running"] = True
    _status["last_error"] = None
    try:
        result = generate_daily_trips_for_date(target_date, force=force)
        _status["last_run_at"] = timezone.localtime().isoformat()
        _status["last_result"] = result
        return result
    except Exception as exc:
        logger.exception("Daily trip scheduler failed")
        _status["last_error"] = str(exc)
        raise
    finally:
        _status["is_running"] = False
        _release_database_lock(lock_name)


def scheduler_status():
    return dict(_status)


def _scheduler_loop(run_time):
    while True:
        now = timezone.localtime()
        next_run = _next_run_after(now, run_time)
        _status["next_run_at"] = next_run.isoformat()
        seconds = max((next_run - now).total_seconds(), 1)
        time.sleep(seconds)
        run_daily_trip_job()


def _should_start_scheduler():
    if os.getenv("ENABLE_DAILY_TRIP_JOB_SCHEDULER", "true").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return False

    management_commands = {
        "makemigrations",
        "migrate",
        "collectstatic",
        "shell",
        "test",
        "check",
        "seed",
        "generate_daily_trips",
    }
    if len(sys.argv) > 1 and sys.argv[1] in management_commands:
        return False

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        return os.environ.get("RUN_MAIN") == "true"

    return True


def start_daily_trip_scheduler():
    global _scheduler_thread
    if not _should_start_scheduler():
        return False

    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return True
        run_time_value = os.getenv("DAILY_TRIP_SCHEDULER_TIME", DEFAULT_RUN_TIME)
        run_time = _parse_run_time(run_time_value)
        _status["enabled"] = True
        _status["run_time"] = run_time.strftime("%H:%M")
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(run_time,),
            name="iwms-daily-trip-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()
        return True
