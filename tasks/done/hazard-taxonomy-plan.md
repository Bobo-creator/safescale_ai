# Implementation Plan: hazard-taxonomy

Implements [SPEC-hazard-taxonomy.md](../../SPEC-hazard-taxonomy.md). Tasks: [hazard-taxonomy-todo.md](hazard-taxonomy-todo.md).
Previous modules: [data-ingest](data-ingest-plan.md), [retrieval](retrieval-plan.md).

## Overview

Rule-based, multi-label hazard classifier with evidence fragments, plus a standards-violation flag,
stored by migration 004 and recomputed in full by `safescale classify`. A local labeling page
produces a blind 50-recall gold set, and `safescale score-hazards` reports P / R / F1 against it.

## Approved decisions (2026-10-19)

- 12 categories (brief's 8 + suffocation/strangulation, crash/loss of control, drowning + `other`).
- `violates_standard` flag with the standard's name, built now.
- Gold set: 50 recalls, blind, local labeling page (stdlib HTTP server on 127.0.0.1, no new deps).
- Rules ship; an OpenAI labeler is a challenger in `evaluation`.

## Order and why

1. **Labeling page first.** You can label while I build the classifier, and fixing the 50 gold
   ids up front lets me exclude them from everything I look at while tuning rules.
2. Pure `classify()` with table-driven tests (no DB) is the core.
3. Migration + store + CLI, then a Supabase run, then scoring once your labels are in.

## Dependency graph

```
sample + labeling page (1) ─────────────────────────────────────┐
categories + rules + classify() (2) ──► standards rules (3) ──┐  │
migration 004 (4) ──────────────────► store + CLI (5) ────────┴─►│─► Supabase run (6) ─► score (7)
                                                                 └──────────────────────────┘
```

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| I unconsciously tune rules on the gold set | High | Gold ids fixed first (seeded sample); dev inspection queries exclude them; never print gold recalls during tuning |
| 50 recalls is a small gold set; rare categories (drowning) may appear 0–1 times | Med | Report raw counts next to every score; `evaluation` can extend the set |
| Regex false positives ("lead to", parts that "fall") | Med | Exclude patterns + trap cases in table-driven tests |
| Labeling server reachable from the network | Low | Bind to 127.0.0.1 only; test asserts it |
| Recompute in one transaction locks readers on Supabase | Low | 10k small rows, ~1 s; delete+insert in one transaction keeps reads consistent |
