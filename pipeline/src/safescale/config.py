"""Runtime configuration: environment variables, optionally loaded from the repo's .env file."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_DATABASE_URL = "postgresql://localhost/safescale"


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Set variables from a KEY=VALUE file without overriding ones already in the environment."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
