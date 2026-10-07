"""Shared test settings (importable from tests, unlike conftest.py)."""

import os

from safescale import config

config.load_dotenv()
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost/safescale_test")
