"""Pytest plugin loaded before pytest-django sets up Django.

The IWMS AppConfig.ready() starts a background daily-trip scheduler thread
(app/services/daily_trip_scheduler.py). Inside pytest that thread queries the
shared in-memory SQLite test database and raises "database schema is locked".
This hook runs before Django is configured, so the scheduler refuses to start.
"""
import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    os.environ.setdefault("ENABLE_DAILY_TRIP_JOB_SCHEDULER", "false")
