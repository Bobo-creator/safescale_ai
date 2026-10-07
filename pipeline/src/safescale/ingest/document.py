"""Canonical retrieval text for a recall, shared by embeddings and BM25."""

import hashlib
import re

from safescale.ingest.clean import CleanRecall

# Injury fields that only say nothing happened ("None reported.", "No injuries have been
# reported") appear in thousands of records and would dominate similarity, so they are left out.
_NO_INJURIES = re.compile(r"^(there (were|have been) )?(none|no)\b", re.IGNORECASE)


def build_document(recall: CleanRecall) -> str:
    injuries = recall.injuries_text
    if injuries and _NO_INJURIES.match(injuries):
        injuries = None

    sections = [
        ("Title", recall.title),
        ("Products", "; ".join(recall.product_names)),
        ("Product types", "; ".join(recall.product_types)),
        ("Hazard", recall.hazard_text),
        ("Description", recall.description),
        ("Injuries", injuries),
    ]
    return "\n".join(f"{label}: {value}" for label, value in sections if value)


def content_hash(document: str) -> str:
    return hashlib.sha256(document.encode("utf-8")).hexdigest()
