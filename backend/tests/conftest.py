"""Test environment, fixed BEFORE ``app`` is imported by any test module.

* ``backend/.env`` (local dev) points ``PERCEPCION_DATABASE_URL`` at a copy of the REAL
  database. The suite must never touch it: ``services/percepcion/db.py`` creates its
  engines (and runs idempotent DDL) at import time, so the URL is forced to a throwaway
  SQLite file here. ``load_dotenv`` does not override variables already in the
  environment, so these assignments win over ``.env``.
* ``BOVEDA_DATABASE_URL`` is cleared and APP_ENV is ``dev``; the auth tests set what they need.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="boveda_tests_")
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)

os.environ["APP_ENV"] = "dev"
os.environ["APP_SESSION_SECRET"] = "test-secret-not-the-dev-default"
os.environ["PERCEPCION_DATABASE_URL"] = f"sqlite:///{_TMP}/percepcion_test.db"
os.environ["OPERATIONAL_DATABASE_URL"] = f"sqlite:///{_TMP}/operational_test.db"
# The access database is never the one in backend/.env: tests swap the access adapter for
# an in-memory fake (accesos.configure) or, in the opt-in integration module, use
# BOVEDA_TEST_DATABASE_URL inside a rolled-back transaction.
os.environ["BOVEDA_DATABASE_URL"] = ""
os.environ["TASKS_TRIGGER_TOKEN"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
