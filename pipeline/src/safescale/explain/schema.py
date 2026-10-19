"""What the model must return (OpenAI structured outputs). Sizes are enforced by the validator,
not the schema, so the schema stays within what strict structured outputs accept."""

from pydantic import BaseModel, ConfigDict

from safescale.taxonomy.categories import Category


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Sentence(_Strict):
    text: str
    citations: list[int]  # recall ids; at least one (checked by the validator)


class HazardParagraph(_Strict):
    category: Category
    sentences: list[Sentence]  # 1-3


class MatchReason(_Strict):
    recall_id: int
    shared: list[str]  # what the recall has in common with the new product
    different: list[str]  # how it differs


class InvestigationNote(_Strict):
    area_id: str
    sentence: Sentence


class ExplanationDraft(_Strict):
    summary: list[Sentence]  # 1-4
    hazards: list[HazardParagraph]
    match_reasons: list[MatchReason]  # up to 8
    investigation_notes: list[InvestigationNote]
