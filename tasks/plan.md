# Implementation Plan: explain

Implements [SPEC-explain.md](../SPEC-explain.md). Tasks: [todo.md](todo.md).
Previous modules: [data-ingest](done/data-ingest-plan.md), [retrieval](done/retrieval-plan.md),
[hazard-taxonomy](done/hazard-taxonomy-plan.md), [hazard-analysis](done/hazard-analysis-plan.md).

## Overview

HazardReport → deterministic evidence packet → OpenAI structured output (`gpt-6-luna` default) →
grounding validator (drop / one retry / deterministic fallback) → `Explanation` with fixed caveat
and disclaimer; `safescale explain [--json] [--model]`.

## Approved decisions (2026-10-19)

- Default `gpt-6-luna`; benchmark against `gpt-6.1-sol` on 10 queries before finalizing.
- Never show unvalidated text; no LLM call on insufficient evidence; no caching in v1.
- Owner reviews 5 explanations (Markdown sheet), target ≥ 95% supported sentences.

## Order and why

The validator is the core and the riskiest logic, and it needs no network, so it comes first
together with the schema. Then the packet, the flow with a fake explainer, then the real OpenAI
explainer (first paid calls, tiny), then the CLI, the benchmark and the review sheet.

## Dependency graph

```
schema + validator (1) ──┐
evidence packet (2) ─────┼─► explain() flow with FakeExplainer (3) ─► OpenAIExplainer + live test (4)
                         │                                                  │
                         └──────────────────────────────► CLI (5) ─► benchmark + review sheet (6)
```

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Model states unsupported claims with real-looking citations | High | Category/area-scoped citation checks, number check, human review of 5 explanations |
| Validator too strict, most text dropped | Med | Report drop reasons; tune the prompt (bump PROMPT_VERSION), not the checks |
| Recall text tries to steer the model (prompt injection) | Low | Recall text passed as JSON data; instructions say so; validator catches the effects |
| Reasoning tokens make cost/latency higher than estimated | Med | Measure per call; effort `low` by default; ask before exceeding $0.01 |
| New model names change or get deprecated | Low | `EXPLAIN_MODEL` env var; model recorded on each explanation |
