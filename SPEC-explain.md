# Spec: explain

Module id: `explain` (see [CAPABILITY_MAP.md](CAPABILITY_MAP.md)).
Depends on: `retrieval`, `hazard-analysis`. Consumed by: `app`, `evaluation`.

## Objective

Turn a `HazardReport` into a **plain-language explanation an engineer can trust**. It covers the
brief's *Explain* step (§4): "show why each historical case is relevant: battery type, charging
system, intended user, enclosure material, indoor use, detachable part, etc." The brief's rule
(§3): "an LLM may explain the retrieved evidence in plain language, but it should not invent
unsupported safety conclusions."

The explanation has four parts, and **every sentence cites recall ids**:

1. **Summary** (2–4 sentences): what the similar recalls have in common and which hazards dominate.
2. **Hazards:** one short paragraph for each category the report rates MODERATE or HIGH, saying
   which failure modes recur and in what kinds of products.
3. **Why these matches:** for the top matches, one line each on what they share with the new
   product (e.g. "same: lithium-ion battery, USB charging; different: a portable lamp, not a
   night light").
4. **Investigation notes:** one sentence per investigation area in the report, tying the area
   to what actually failed in the supporting recalls.

The disclaimer and the statistical caveat (recalls only contain products that failed) are fixed
text added by code, never written by the model.

**Done looks like:** `safescale explain "Rechargeable children's night light, 2000 mAh lithium-ion
battery, USB-C charging, ABS plastic housing, LED"` prints the signal, the explanation with
citations like `[#11013]`, a numbered reference list (title, date, CPSC link) and the disclaimer.
Every sentence shown has passed automatic grounding checks.

## Key facts (checked 2026-10-19)

- **Models on this account** (from the OpenAI models list, with prices from OpenAI's pricing page,
  per 1M tokens):

  | Model | Input | Output | Notes |
  |---|---|---|---|
  | `gpt-6-luna` | $0.10 | $0.50 | "Most efficient model for focused, high-volume tasks"; reasoning model; structured outputs |
  | `gpt-6.1-sol` | $2.00 | $10.00 | "Near-Astra performance at a lower cost" |
  | `gpt-6-astra` | $10.00 | $50.00 | flagship; overkill here |

- **Size of one request:** about 15 relevant matches × ~250 tokens of evidence plus the report
  summary is ~6–8k input tokens; the output is ~1–2k tokens including reasoning. That is **≈ $0.002 per
  explanation with luna**, ≈ $0.03 with 6.1-sol.
- **SDK:** `openai` 3.26 (already a dependency) supports `client.responses.parse(...,
  text_format=PydanticModel)`, which returns a schema-validated object (structured outputs). So the
  output is always well-formed JSON, and we only need to check its *content*.
- **Data sent to OpenAI:** the user's product description (already sent for embeddings) and public
  CPSC recall text. Nothing else.

## Design

### Flow

```
HazardReport ──► evidence packet (deterministic) ──► LLM (structured output) ──► draft
                                                                                   │
                       validated Explanation ◄── drop / retry / fallback ◄── validator
```

- **No LLM call when evidence is insufficient** (`insufficient_evidence` in the report). The
  explanation is then a fixed, deterministic message. That's cheaper, and there's nothing to make up.

### Evidence packet

Built only from the report, plus each relevant match's product names and description excerpt (one
extra query):

- The query, the overall signal and its drivers, and the profile rows (count, share, lift).
- Shared and failure terms, investigation areas (id, title, recall ids), cited standards.
- The **top 15 relevant matches** by rank: recall id, date, title, product names, hazard text
  (≤ 400 chars), description (≤ 300 chars), hazard labels. Weak matches are never included.

Recall text is passed as JSON data. The instructions say it is data to summarize, never
instructions to follow.

### Output schema (structured outputs, Pydantic)

```python
class Sentence(BaseModel):
    text: str
    citations: list[int] = Field(min_length=1)       # recall ids

class HazardParagraph(BaseModel):
    category: CategoryCode                            # enum of the 12 codes
    sentences: list[Sentence] = Field(min_length=1, max_length=3)

class MatchReason(BaseModel):
    recall_id: int
    shared: list[str]                                 # e.g. ["lithium-ion battery", "USB charging"]
    different: list[str]                              # e.g. ["portable lamp, not a night light"]

class InvestigationNote(BaseModel):
    area_id: str
    sentence: Sentence

class ExplanationDraft(BaseModel):
    summary: list[Sentence] = Field(min_length=1, max_length=4)
    hazards: list[HazardParagraph]
    match_reasons: list[MatchReason] = Field(max_length=8)
    investigation_notes: list[InvestigationNote]
```

### Grounding validator (deterministic, the heart of this module)

Each sentence and item is checked against the packet:

| Check | Rule |
|---|---|
| **Citations exist** | every cited id is a relevant match in the packet |
| **Citations fit the claim** | a hazard paragraph cites only recalls carrying that category; an investigation note cites only that area's supporting recalls |
| **Numbers are real** | every number in the text (counts, percentages, multipliers like "1.9×", years) appears in the packet |
| **Known references** | categories and area ids exist in the report; match reasons refer to packet recalls |
| **Advisory wording** | no "safe", "unsafe", "compliant", "certified", "guarantee", "will fail", "probability", "likely to fail", "required" |

A failing item is **dropped**, never shown. If more than a quarter of the items fail, or the summary
loses all its sentences, the model gets **one retry** with the list of problems. If the retry still
fails, the summary falls back to a **deterministic template** built from the report ("14 of 25
similar recalls involved fire/overheating, 1.9× its share of all recalls [#…]"). Every explanation
records `retries`, `dropped` (with reasons) and `fallback_used`, so `evaluation` can measure
faithfulness.

### Provider interface

```python
class Explainer(Protocol):
    model: str
    def draft(self, packet: dict, feedback: list[str] | None = None) -> tuple[ExplanationDraft, Usage]: ...

class OpenAIExplainer:          # client.responses.parse(model=..., instructions=..., input=...,
    ...                         #   text_format=ExplanationDraft, reasoning={"effort": ...})

def explain(report: HazardReport, conn, *, explainer: Explainer) -> Explanation: ...
```

- `EXPLAIN_MODEL` env var, default **`gpt-6-luna`** (see Decisions). Reasoning effort is configurable
  (default `low`). The SDK's built-in retries handle rate limits.
- `FakeExplainer` (tests only) returns scripted drafts, valid and deliberately invalid, so the
  validator, retry and fallback paths are tested offline.
- `PROMPT_VERSION` is bumped whenever the instructions change and is stored on every explanation.

### Result

```python
@dataclass(frozen=True)
class Explanation:
    summary: list[Sentence]
    hazards: list[HazardParagraph]
    match_reasons: list[MatchReason]
    investigation_notes: list[InvestigationNote]
    caveat: str                  # fixed: recall data only contains products that had problems
    disclaimer: str              # fixed, from the brief
    generated: bool              # False = deterministic text only (insufficient evidence / fallback)
    model: str | None
    prompt_version: int
    usage: Usage                 # input / output / reasoning tokens, estimated cost in USD
    validation: Validation       # retries, dropped items with reasons, fallback_used
    def to_dict(self) -> dict: ...
```

No caching or storage in v1: an explanation costs a fraction of a cent. The app can add a cache
later if demos repeat the same queries.

## Commands

```bash
uv run safescale explain "rechargeable night light, lithium-ion battery, USB-C" [--k 25]
uv run safescale explain "..." --json                   # report + explanation as one JSON object
uv run safescale explain "..." --model gpt-6.1-sol      # compare models
uv run pytest                                           # offline (FakeExplainer)
uv run pytest -m live                                   # one real explanation
```

## Project structure

```
pipeline/src/safescale/explain/
  packet.py        # HazardReport (+ descriptions) -> evidence packet
  schema.py        # Pydantic output schema (ExplanationDraft and parts)
  prompt.py        # instructions, PROMPT_VERSION
  explainer.py     # Explainer protocol, OpenAIExplainer, Usage + cost estimate
  validate.py      # grounding validator
  explain.py       # explain(): packet -> draft -> validate -> retry / fallback -> Explanation
  text.py          # terminal rendering with [#id] citations and a reference list
pipeline/tests/explain/
  fake_explainer.py
  test_packet.py   test_validate.py   test_explain.py   test_live.py (marked live)
evaluation/explain_review/        # your manual review sheet (see Testing)
```

## Testing strategy

- **Validator unit tests (most of the effort):** a made-up recall id, a real id cited for the wrong
  hazard, an invented percentage, "1.9×" when the packet says 1.9 (allowed) vs "3×" (not), a banned
  word, an unknown area id, an empty summary after drops. Each must be caught with a readable reason.
- **Flow tests (FakeExplainer):** valid on the first try; one retry, then valid; still invalid, so the
  fallback is used; insufficient evidence makes no model call at all.
- **Packet tests:** weak matches are never included, at most 15 matches, text truncation, and every
  id in the packet comes from the report.
- **Live (opt-in):** one real explanation of the night-light report passes validation.
- **Faithfulness benchmark (once built, on Supabase):** 10 product descriptions (the 4 prototypes
  plus 6 more I'll draft for you to check) × 2 models (`gpt-6-luna`, `gpt-6.1-sol`). Recorded per
  run: first-try validation pass rate, dropped items, retries, latency and cost.
- **Human review:** you read 5 luna explanations in a generated Markdown sheet and mark any sentence
  its cited recalls don't support (about 15 minutes). This catches what automatic checks can't,
  such as a real citation attached to a slightly wrong claim.

## Boundaries

- **Always:** cite recall ids in every sentence. Run every draft through the validator before
  showing it. Add the fixed caveat and disclaimer in code. Log tokens and cost per call.
- **Ask first:** changing the default model. Raising the per-explanation cost above $0.01. Sending
  OpenAI anything beyond the packet. Adding storage or caching of explanations.
- **Never:** show text that failed validation. Let the model write the disclaimer or a safety or
  compliance verdict. Call the LLM when evidence is insufficient. Make live API calls in default tests.

## Success criteria

1. **Night light:** the explanation passes validation. The summary names fire/overheating and/or
   burn with citations, and at least 3 match reasons name concrete shared features (battery,
   charging, LED, night light).
2. **Unrelated query:** no model call; deterministic "not enough similar recalls" text; `generated = false`.
3. Validator tests cover every check in the table, plus the retry and fallback paths.
4. **Benchmark (10 queries, default model):** 100% of *shown* sentences pass validation (by
   construction), first-try pass rate and drops are reported, and fallback is used in at most 1 of 10.
5. **Human review:** at least 95% of sentences in your 5 reviewed explanations are judged supported
   by their citations.
6. **Default model:** ≤ $0.01 per explanation; median latency < 8 s for the LLM step.
7. Tests and lint pass offline; `-m live` passes.

## Decisions (approved 2026-10-19)

1. **Default model `gpt-6-luna`**, with `gpt-6.1-sol` benchmarked alongside. Luna is about 20× cheaper,
   and the task is focused (summarize given evidence, with citations), which is what luna is built
   for. If sol is clearly more faithful on the benchmark, I'll show you the numbers before switching.
2. **The validator drops, retries and falls back; it never shows unchecked text.** This is
   stricter than "the LLM is told to cite", and it's the part the seminar can measure.
3. **No explanation caching in v1** (≈ $0.002 each); revisit in `app` if needed.
4. **Human review of 5 explanations** (about 15 minutes of your time), as a Markdown sheet.

## Results (2026-10-19, Supabase)

Benchmark: `evaluation/explain_benchmark/run.py`, 10 product descriptions (all rated HIGH, 25 of 25
relevant matches). Raw rows are in `results_v1.json`, `results_v2_low.json` and `results.json`.

| Run | First try clean | Items dropped | Retries | Fallback | Median (max) | Mean cost |
|---|---|---|---|---|---|---|
| luna, prompt v1, effort low | 5/10 | 46 | 4 | 0 | 12.7 s (25.1) | $0.0014 |
| sol 6.1, prompt v1, effort low | 10/10 | 0 | 0 | 0 | 38.9 s (57.5) | $0.0193 |
| luna, prompt v2, effort low | 9/10 | 2 | 0 | 0 | 9.7 s (12.3) | $0.0010 |
| sol 6.1, prompt v2, effort low | 10/10 | 0 | 0 | 0 | 20.1 s (21.9) | $0.0194 |
| luna, prompt v2, effort none (two runs) | 10/10, 9/10 | 0, 1 | 0 | 0 | 8.3 s, 9.3 s | $0.0009 |

**What changed between runs.**
- Prompt v1 → v2: 45 of luna's 46 drops were one formatting habit. It repeated its citations as
  a trailing "[10158, 755]" in the sentence, and the number check read those ids as invented
  statistics. Prompt v2 says to keep ids out of the text. The validator also strips a trailing id
  list, but only when it exactly repeats the sentence's citations; any other id list is still caught.
- Effort low → none: just as clean, faster and cheaper, so `none` is the default.
- The remaining drops are real catches: a recall cited for a hazard it isn't labeled with.

**Default: `gpt-6-luna`, effort `none`.** sol is fully clean but costs about 20× more and takes
about 2× longer. With prompt v2, luna is nearly as clean, so the spec's "switch only if clearly more
faithful" condition isn't met. The human review below is the deciding check.

| # | Criterion | Result |
|---|---|---|
| 1 | Night light: validated summary with fire/burn citations; ≥ 3 concrete match reasons | ✅ e.g. "shared: rechargeable lamp; lithium-ion battery · different: portable sleep lamp" |
| 2 | Unrelated query: no model call, deterministic notice | ✅ 0 calls to the Responses API |
| 3 | Validator, retry and fallback tests | ✅ (an unsupported `effort` value also showed the error path working: each failed call fell back cleanly) |
| 4 | Benchmark: shown text 100% validated; fallback ≤ 1 / 10 | ✅ fallback 0 / 10 |
| 5 | Human review ≥ 95% supported | ⏳ waiting for the owner: `evaluation/explain_review/review.md` (77 items) |
| 6 | ≤ $0.01 and median < 8 s for the LLM step | ⚠️ $0.0009 ✅; median 8.3–9.3 s ❌ (generation time; the app should stream) |
| 7 | Tests offline; live test | ✅ 331 tests; `-m live` passes |

Fixed along the way: the chemical-content investigation area no longer fires on battery "chemical
burns" (which concern ingestion, not material content).
