"""Pure cleaning functions: raw CPSC record -> CleanRecall."""

import html
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from safescale.ingest.models import RawRecall

_TAGS = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_PLACEHOLDERS = {"none", "n/a", "na", "null"}


@dataclass(frozen=True)
class CleanRecall:
    recall_id: int
    recall_number: str | None
    recall_date: date
    last_publish_date: date | None
    title: str
    description: str | None
    url: str
    product_names: list[str]
    product_types: list[str]
    hazard_text: str | None
    injuries_text: str | None
    remedy_text: str | None
    units_text: str | None
    manufacturer_countries: list[str]
    raw: dict[str, Any]


def clean_text(value: str | None) -> str | None:
    """Strip tags, unescape entities, collapse whitespace; empty or placeholder -> None.

    Tags are stripped before unescaping so escaped markup (``&lt;b&gt;``) survives as text.
    """
    if value is None:
        return None
    text = _WHITESPACE.sub(" ", html.unescape(_TAGS.sub(" ", value))).strip()
    return None if not text or text.lower() in _PLACEHOLDERS else text


def clean_list(values: Iterable[str | None]) -> list[str]:
    """Clean each value, drop empties, dedupe preserving first-seen order."""
    cleaned = (clean_text(value) for value in values)
    return list(dict.fromkeys(value for value in cleaned if value))


def _join(values: Iterable[str | None]) -> str | None:
    return "; ".join(clean_list(values)) or None


def to_clean_recall(record: dict[str, Any]) -> CleanRecall:
    """Validate and clean one raw API record; the unmodified dict is kept as ``raw``.

    Raises pydantic.ValidationError or ValueError for records that cannot be used.
    """
    raw = RawRecall.model_validate(record)
    title = clean_text(raw.Title)
    url = clean_text(raw.URL)
    if title is None or url is None:  # e.g. Title made only of tags or a placeholder
        raise ValueError(f"recall {raw.RecallID}: title or url is empty after cleaning")
    return CleanRecall(
        recall_id=raw.RecallID,
        recall_number=clean_text(raw.RecallNumber),
        recall_date=raw.RecallDate.date(),
        last_publish_date=raw.LastPublishDate.date() if raw.LastPublishDate else None,
        title=title,
        description=clean_text(raw.Description),
        url=url,
        product_names=clean_list(p.Name for p in raw.Products),
        product_types=clean_list(p.Type for p in raw.Products),
        hazard_text=_join(h.Name for h in raw.Hazards),
        injuries_text=_join(i.Name for i in raw.Injuries),
        remedy_text=_join(r.Name for r in raw.Remedies),
        units_text=_join(p.NumberOfUnits for p in raw.Products),
        manufacturer_countries=clean_list(c.Country for c in raw.ManufacturerCountries),
        raw=record,
    )
