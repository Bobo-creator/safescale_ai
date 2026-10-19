"""Scripted explainers for offline tests."""

from safescale.explain.explainer import ExplainerError, Usage
from safescale.explain.schema import (
    ExplanationDraft,
    HazardParagraph,
    InvestigationNote,
    MatchReason,
    Sentence,
)


def grounded_draft(packet: dict) -> ExplanationDraft:
    """A draft that follows every rule, built from the packet like a well-behaved model would."""
    recalls = packet["recalls"]
    top = packet["hazard_profile"][0]
    summary = [
        Sentence(
            text=f"{top['similar_recalls']} of {packet['relevant_similar_recalls']} similar "
            f"recalls involved {top['label'].lower()}.",
            citations=top["recall_ids"][:2],
        )
    ]
    hazards = [
        HazardParagraph(
            category=row["category"],
            sentences=[Sentence(text=f"{row['label']} recurs.", citations=row["recall_ids"][:2])],
        )
        for row in packet["hazard_profile"]
        if row["recall_ids"] and row["category"] != "other"
    ]
    reasons = [
        MatchReason(recall_id=r["recall_id"], shared=["similar product"], different=[])
        for r in recalls[:3]
    ]
    notes = [
        InvestigationNote(
            area_id=a["area_id"],
            sentence=Sentence(
                text=f"Consider reviewing {a['title'].lower()}.", citations=a["recall_ids"][:2]
            ),
        )
        for a in packet["investigation_areas"]
        if a["recall_ids"]
    ]
    return ExplanationDraft(
        summary=summary, hazards=hazards, match_reasons=reasons, investigation_notes=notes
    )


def ungrounded_draft(packet: dict) -> ExplanationDraft:
    """Every sentence breaks a rule: verdicts, invented numbers, invented ids."""
    return ExplanationDraft(
        summary=[
            Sentence(text="This product is safe.", citations=[recall["recall_id"]])
            for recall in packet["recalls"][:2]
        ]
        + [Sentence(text="97% of products fail.", citations=[999_999_999])],
        hazards=[],
        match_reasons=[],
        investigation_notes=[],
    )


class ScriptedExplainer:
    """Returns the scripted drafts in order (functions of the packet), or raises."""

    model = "scripted"

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[list[str] | None] = []  # the feedback passed on each call

    def draft(self, packet, feedback=None):
        self.calls.append(feedback)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step(packet), Usage(input_tokens=1000, output_tokens=200, cost_usd=0.0002)


__all__ = ["ExplainerError", "ScriptedExplainer", "grounded_draft", "ungrounded_draft"]
