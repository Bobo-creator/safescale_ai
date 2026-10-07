"""Download the CPSC recall dataset and keep each response as a reproducible snapshot."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CPSC_RECALLS_URL = "https://www.saferproducts.gov/RestWebServices/Recall"


def fetch_snapshot(client: httpx.Client, out_dir: Path) -> Path:
    """Fetch every recall in one request and write the raw response body to ``out_dir``."""
    response = client.get(CPSC_RECALLS_URL, params={"format": "json"}, timeout=120)
    response.raise_for_status()
    if not isinstance(response.json(), list):
        raise ValueError("CPSC API returned JSON that is not a list of recalls")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"recalls_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    path.write_bytes(response.content)
    log.info("saved snapshot %s (%d bytes)", path, len(response.content))
    return path


def read_snapshot(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Return the records in a snapshot file and the SHA-256 of its exact bytes."""
    data = path.read_bytes()
    records = json.loads(data)
    if not isinstance(records, list):
        raise ValueError(f"{path} does not contain a JSON list of recalls")
    return records, hashlib.sha256(data).hexdigest()
