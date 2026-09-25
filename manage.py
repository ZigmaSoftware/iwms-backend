#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _check_venv_active():
    """Fail fast, with a clear message, when this project's own .venv isn't
    the active interpreter — running with a system/other Python still finds
    *a* Django on site-packages (so the ImportError below never fires) but
    it's the wrong version with the wrong pinned dependencies, which instead
    surfaces later as a confusing crash deep in some unrelated import (e.g.
    "No module named 'dateutil'") the first time a view module happens to
    need a package this project's pyproject.toml pins but the system Python
    never had installed.
    """
    project_venv = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
    if os.path.commonpath([sys.prefix, project_venv]) != project_venv:
        sys.stderr.write(
            "\n"
            "This project's virtualenv isn't active — you're running:\n"
            f"  {sys.executable}\n"
            "which is not under this project's .venv, so it will import the "
            "wrong versions of Django and this project's other pinned "
            "dependencies (or be missing some of them entirely).\n\n"
            "Run this first, then retry your command:\n"
            "  source .venv/bin/activate\n\n"
        )
        sys.exit(1)


def main():
    """Run administrative tasks."""
    _check_venv_active()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
