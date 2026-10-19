"""The gold file: a fixed random sample of recalls plus the human labels for each.

The file is self-contained (it stores each recall's text), so labeling and scoring don't depend on
which database is connected, and the gold set stays stable even if a recall is updated later.
"""

import json
import os
import random
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from safescale.taxonomy.categories import CATEGORY_CODES

FORMAT_VERSION = 1
DEFAULT_SAMPLE_SIZE = 50
DEFAULT_SEED = 2026


@dataclass
class GoldItem:
    recall_id: int
    title: str
    hazard_text: str | None
    description: str | None
    url: str
    recall_date: str | None
    labels: list[str] = field(default_factory=list)
    violates_standard: bool = False
    notes: str = ""
    labeled_at: str | None = None  # set once the item has at least one category

    @property
    def is_labeled(self) -> bool:
        return bool(self.labels)


@dataclass
class GoldSet:
    seed: int
    items: list[GoldItem]
    created_at: str
    format_version: int = FORMAT_VERSION

    def item(self, recall_id: int) -> GoldItem:
        for item in self.items:
            if item.recall_id == recall_id:
                return item
        raise KeyError(recall_id)


def sample_ids(all_ids: list[int], n: int, seed: int) -> list[int]:
    """The same ids for the same corpus and seed, whatever order the ids come in."""
    population = sorted(set(all_ids))
    if n > len(population):
        raise ValueError(f"sample size {n} exceeds the {len(population)} recalls available")
    return sorted(random.Random(seed).sample(population, n))


def create_gold_set(conn, *, n: int = DEFAULT_SAMPLE_SIZE, seed: int = DEFAULT_SEED) -> GoldSet:
    all_ids = [row[0] for row in conn.execute("select recall_id from recalls")]
    ids = sample_ids(all_ids, n, seed)
    rows = conn.execute(
        """
        select recall_id, title, hazard_text, description, url, recall_date::text
        from recalls where recall_id = any(%s) order by recall_id
        """,
        (ids,),
    ).fetchall()
    items = [GoldItem(*row) for row in rows]
    return GoldSet(seed=seed, items=items, created_at=_now())


def apply_label(
    gold: GoldSet, recall_id: int, *, labels: list[str], violates_standard: bool, notes: str
) -> GoldItem:
    unknown = sorted(set(labels) - set(CATEGORY_CODES))
    if unknown:
        raise ValueError(f"unknown categories: {', '.join(unknown)}")
    if "other" in labels and len(set(labels)) > 1:
        raise ValueError("'other' means no other category applies; don't combine it")
    item = gold.item(recall_id)
    item.labels = [code for code in CATEGORY_CODES if code in set(labels)]  # canonical order
    item.violates_standard = bool(violates_standard)
    item.notes = notes.strip()
    item.labeled_at = _now() if item.labels else None
    return item


def load_gold(path: Path) -> GoldSet:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"{path}: unsupported gold format {data.get('format_version')!r}")
    items = [GoldItem(**item) for item in data["items"]]
    return GoldSet(
        seed=data["seed"],
        items=items,
        created_at=data["created_at"],
        format_version=data["format_version"],
    )


def save_gold(gold: GoldSet, path: Path) -> None:
    """Write atomically, so a crash mid-save never leaves a half-written gold file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(gold), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
