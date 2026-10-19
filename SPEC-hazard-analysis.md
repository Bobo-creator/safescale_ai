# Spec: hazard-analysis

Module id: `hazard-analysis` (see [CAPABILITY_MAP.md](CAPABILITY_MAP.md)).
Depends on: `retrieval`, `hazard-taxonomy`. Consumed by: `explain`, `app`, `evaluation`.

## Objective

Turn "the 25 most similar historical recalls" into an **evidence-backed hazard report** for a new
product description. This is the brief's *Analyze* and *Recommend investigation* steps (§4):

1. **Similar recalls:** the matches, each with score, date, link, hazard labels and evidence phrase.
2. **Hazard profile:** how often each hazard category appears among the *relevant* matches, and
   how that compares with all recalls (e.g. "fire/overheating: 14 of 25 similar recalls, 56%,
   1.9× its share of all recalls").
3. **Historical signal per hazard and overall:** LOW / MODERATE / HIGH, a ranked signal and not
   a probability (§5).
4. **Shared terms:** components and phrases from the description that recur in the matches
   ("lithium-ion", "charging"), plus recurring failure terms the user didn't mention ("overheat",
   "short circuit").
5. **Investigation areas:** review or test areas justified by the matches (e.g. "battery thermal
   behavior", "battery compartment security"), plus standards that similar recalls failed. Each
   lists the recalls that support it, and all are labeled as recommendations for review.
6. The fixed **disclaimer** from the brief, on every report.

Everything is deterministic (no LLM) and every statement points to recall ids. `explain` (next
module) puts the report into plain language with an LLM, and may only use what is in it.

**Done looks like:** `safescale analyze "Rechargeable children's night light, 2000 mAh lithium-ion
battery, USB-C charging, ABS plastic housing, LED"` prints an overall HIGH signal led by
fire/overheating and burn, the shared terms, investigation areas such as battery thermal behavior and
battery compartment security (Reese's Law), and the disclaimer. `--json` gives the same report as
JSON for the app.

## Key facts (measured on Supabase, 2026-10-19)

- **Cosine scores separate relevant from irrelevant well.** Real product queries score 0.48–0.57
  at rank 1 and still 0.34–0.46 at rank 100. An unrelated query ("cloud accounting software")
  scores 0.18 at rank 1 and 0.14 at rank 100. A **relevance floor of 0.30** therefore keeps
  matches out of the profile when there is nothing similar, without trimming real ones.
- **Prototype profiles over the top 25** (share; multiple of the share among all recalls):

  | Query | Top hazards | Standards cited by matches |
  |---|---|---|
  | Night light (brief's example) | fire 56% (1.9×), burn 56% (3.2×), shock 28% (4.2×), poisoning 28% (2.5×) | Reese's Law ×7 |
  | Baby crib with drop side | fall 80% (4.6×), entrapment 76% (11.7×), suffocation 64% (9.9×) | crib standard ×2 |
  | 6-drawer child's dresser | fall 100% (5.7×), entrapment 96% (14.8×) | STURDY Act ×18, ASTM F2057 ×2 |
  | Folding e-bike, 48 V battery | crash 44% (7.5×), fall 40% (2.3×), fire 28% (0.9×) | none |

- **Why the comparison with all recalls matters:** fire/overheating is on 30% of *all* recalls, so
  "28% of matches involve fire" alone says little. Showing the share next to its overall rate is
  how we stay honest about §5: recalls only contain products that failed. The e-bike row is a good
  seminar example. Battery fires are a known e-bike issue, but CPSC's bicycle recalls are mostly
  mechanical, so fire shows up at below its overall rate.
- **Fixed alongside this spec:** vector search used to cap `k` at 40 (HNSW `ef_search`); it now
  returns up to 100 (migration 005).

## Design

### Pipeline

```
description ──► retrieval.search(k, method) ──► hits (recall_id, rank, score)
                    │
                    ├─► taxonomy.labels_for(hits) ──► hazard profile ──► signals
                    ├─► term stats (SQL) ──────────► shared terms, failure terms
                    └─► investigation catalog ─────► investigation areas (+ cited standards)
                                                         │
                                                         ▼
                                             HazardReport (+ disclaimer)
```

### Relevant matches

A hit counts toward the profile, signals and investigation areas only if its cosine score is
≥ `RELEVANCE_FLOOR = 0.30`. Hits below it are still listed (marked "weak match") so nothing is
hidden. For `keyword` and `hybrid`, scores aren't cosine, so the report fetches each hit's cosine
from the stored embeddings and applies the floor to that. The profile always means the same thing.

### Hazard profile

For each category: `count` (relevant hits carrying it), `share = count / relevant hits`,
`base_rate` (share of all recalls carrying it) and `lift = share / base_rate`, plus the supporting
recall ids. Counts are plain, not similarity-weighted, so "14 of 25" is easy to read and check.
Categories with count 0 are omitted. `other` is shown but never drives the overall signal.

### Signal (v1 rule)

Per category, using relevant hits only:

| Signal | Rule |
|---|---|
| **HIGH** | share ≥ 40% **and** count ≥ 5 **and** lift ≥ 1.5 |
| **MODERATE** | share ≥ 20% **and** count ≥ 3 (and not HIGH) |
| **LOW** | anything else |

**Overall signal** = the highest per-category signal (excluding `other`), reported together with the
categories that produced it. If there are **fewer than 5 relevant matches**, the overall signal is
`LOW` with `insufficient_evidence = true`, and the report says that few similar recalls exist.
That's not the same as "safe". All thresholds are named constants. Applied to the prototype
rows above: night light HIGH (fire, burn); crib HIGH (fall, entrapment, suffocation); dresser HIGH
(fall, entrapment); e-bike HIGH (crash, fall) with fire MODERATE.

### Shared terms and failure terms

Both come from Postgres full-text lexemes (same English stemming as keyword search), with
document frequencies precomputed over the corpus:

- **Shared terms:** words from the description that appear in ≥ 2 relevant matches, ranked by
  `(matches containing it / relevant matches) × idf`. Shown with the user's own wording
  ("lithium-ion", "charging", "housing"), each with its matching recall ids.
- **Failure terms:** words that recur in the matches' **hazard text** (≥ 3 matches), are not in the
  description, and are distinctive (ranked by share × idf over hazard text). Examples: "overheat",
  "short circuit", "ingest". They are shown with the most common surface word, not the stem.
- A short stoplist removes recall boilerplate ("recall", "consumer", "posing", "hazard", "risk").

Storage: migration `006_term_stats.sql` adds two small materialized views,
`recall_term_df (lexeme, ndoc)` over `recalls.search_tsv` and `recall_hazard_term_df (lexeme,
ndoc)` over `to_tsvector('english', hazard_text)`. Materialized views can't use row-level
security, so the migration revokes access from Supabase's Data API roles (`anon`, `authenticated`)
instead. A test checks this, alongside the existing check that every table has RLS. Both are refreshed
at the end of `safescale classify`, so pipeline order is unchanged: `ingest → classify → embed`.

### Investigation areas

A small curated **catalog** in code (about 20 entries, versioned like the taxonomy). Each entry has
an id, a title, the checks to consider, and a trigger: one or more hazard categories plus optional
terms that must appear in the supporting matches. Representative entries:

| Area | Trigger (in relevant matches) | Suggested checks (examples) |
|---|---|---|
| Battery thermal behavior & cell quality | fire_overheating/burn + battery, lithium, cell | cell sourcing and certification, thermal runaway, abuse testing |
| Charging circuit & overcharge protection | fire_overheating + charg, charger, adapter | overcharge/over-current protection, charger compatibility |
| Enclosure & material flammability | fire_overheating + housing, plastic, enclosure, melt | material flame rating, heat sources near plastics |
| Battery compartment security | poisoning/choking + button, coin, battery | secured compartment, Reese's Law applicability |
| Small and detachable parts | choking + detach, small part, button, cap | small-parts cylinder, pull/torque retention |
| Electrical insulation, cords & plugs | electrical_shock + cord, wire, plug, insulation | insulation, strain relief, water ingress |
| Stability & tip-over | fall + tip | stability testing, anchoring hardware |
| Gaps, hinges & pinch points | entrapment | gap dimensions, folding/hinge mechanisms |
| Cords, straps & loops | suffocation_strangulation + cord, strap, loop, drawstring | cord length, breakaway features |
| Chemical & heavy-metal content | poisoning + lead, chemical, phthalate | material content testing |
| Structural integrity & fasteners | fall/crash + break, crack, weld, bolt, frame | load and fatigue testing, fastener retention |
| Brakes, steering & control | crash_loss_of_control | brake, steering and throttle failure modes |

- An area is shown when **≥ 2 relevant matches** support it. Areas are ranked by support count, and
  each shows its supporting recall ids and the trigger terms found.
- **Standards:** every standard named by ≥ 2 relevant matches becomes an item such as "Review whether
  the STURDY Act (furniture tip-over) applies: cited by 18 of 25 similar recalls." Unnamed
  violations are counted but not listed.
- The wording is always "consider reviewing" or "similar recalls involved". Never "required",
  "non-compliant" or "safe".

### Python interface

```python
@dataclass(frozen=True)
class HazardReport:
    query: str
    method: Method
    k: int
    matches: list[Match]                  # hit + cosine + labels + violations + weak flag
    relevant: int                         # matches with cosine >= RELEVANCE_FLOOR
    profile: list[CategoryStat]           # code, label, count, share, base_rate, lift, signal, recall_ids
    overall_signal: Literal["LOW", "MODERATE", "HIGH"]
    signal_drivers: list[str]             # categories that set the overall signal
    insufficient_evidence: bool
    shared_terms: list[Term]              # term, matches, recall_ids
    failure_terms: list[Term]
    investigation_areas: list[Area]       # id, title, checks, support, recall_ids, terms
    standards: list[StandardStat]         # standard, count, recall_ids
    disclaimer: str                       # fixed text from the brief
    taxonomy_version: int
    analysis_version: int

def analyze(conn, query: str, *, k: int = 25, method: Method = "vector",
            embedder: Embedder | None = None) -> HazardReport: ...
def build_report(...)                     # pure: hits + labels + term stats -> report (unit-tested)
HazardReport.to_dict() -> dict            # JSON-ready, for the app and explain
```

## Commands

```bash
uv run safescale migrate                                  # applies 006_term_stats.sql
uv run safescale classify                                 # now also refreshes term stats
uv run safescale analyze "rechargeable night light, lithium-ion battery, USB-C" --k 25
uv run safescale analyze "..." --k 50 --method hybrid --json
uv run pytest
```

## Project structure

```
db/migrations/006_term_stats.sql
pipeline/src/safescale/analysis/
  report.py          # dataclasses, to_dict, disclaimer, constants (floor, thresholds)
  profile.py         # hazard profile, lift, signals (pure)
  terms.py           # shared and failure terms (SQL + ranking)
  investigate.py     # investigation catalog and matching (pure)
  analyze.py         # analyze(): retrieval + labels + terms -> build_report
pipeline/tests/analysis/
  test_profile.py    # signal rules at the thresholds, insufficient evidence, 'other' excluded
  test_investigate.py
  test_terms.py      # fixtures in local Postgres
  test_analyze.py    # end to end with FakeEmbedder; JSON shape; disclaimer always present
```

## Testing strategy

- **Unit (pure):** the profile and signal logic on hand-built hits, including every threshold edge
  (39% vs 40%, 4 vs 5 matches, lift 1.49 vs 1.5), `other` never driving the signal, fewer than
  5 relevant matches giving `insufficient_evidence`, and below-floor matches being listed but not counted.
  Plus catalog matching (≥ 2 supporters, trigger terms) and wording checks (no "safe", "compliant" or
  "certified" in any generated text except the disclaimer).
- **Integration (local Postgres, fixtures, FakeEmbedder):** `analyze()` end to end. The report
  serializes to JSON and every recall id in it is one of the matches.
- **Live sanity (Supabase, manual, recorded in the spec):** the 4 prototype queries plus the
  unrelated one. The expected results are the success criteria below.
- Whether the signals are *right* belongs to `evaluation` (for example, held-out recalls used as
  queries: does the profile predict their real hazard?).

## Boundaries

- **Always:** attach the disclaimer. Show the comparison with all recalls next to every share.
  Back every statement with recall ids. Keep weak matches visible but out of the counts.
- **Ask first:** changing the relevance floor or the signal thresholds (they shape the seminar's
  claims). Adding similarity weighting. Adding clustering (HDBSCAN is out of scope for v1).
- **Never:** call an LLM in this module. Phrase anything as a probability of failure, as a
  compliance determination, or as "safe".

## Success criteria

1. `safescale analyze` returns a full report (matches, profile, signal, shared and failure terms,
   investigation areas, standards, disclaimer) for k = 25, 50 and 100 and all three methods.
2. **Night light (brief's example):** overall HIGH, driven by fire/overheating and/or burn;
   investigation areas include battery thermal behavior and charging/overcharge protection;
   "lithium-ion" and "charging" are among the shared terms.
3. **Dresser:** HIGH, driven by fall and entrapment; the STURDY Act appears among the standards.
4. **Unrelated query** ("cloud accounting software"): 0 relevant matches,
   `insufficient_evidence = true`, overall LOW, and no investigation areas.
5. Every recall id in the profile, terms, areas and standards is one of the report's relevant
   matches; the JSON round-trips.
6. Warm on Supabase: the database work for one report (search, labels, terms) is < 300 ms; the
   `analyze` CLI end to end (including the OpenAI embedding call) is < 2 s.
7. Tests and lint pass offline; Supabase advisors show no new warnings.

## Decisions (approved 2026-10-19)

- **Default k = 25**; 50 and 100 remain options (the app offers them later). Relevance falls with
  depth, and 25 is what the prototypes measured.
- **Signal rule v1 ships as written and is frozen before `evaluation`.** Tuning thresholds on the
  prototype queries would fit them to examples already seen; changes after evaluation need approval.
- **Investigation catalog:** I draft about 20 entries; the project owner reviews them in real
  reports. Tests guard the wording (no "safe", "compliant", "certified").
- Overheating stays inside `fire_overheating` (hazard-taxonomy decision, reconfirmed).

## Results (2026-10-19, Supabase)

| # | Criterion | Result |
|---|---|---|
| 1 | Full report for k = 25 / 50 / 100 × vector / keyword / hybrid | ✅ all 9 combinations; JSON round-trips |
| 2 | Night light: HIGH via fire/burn; battery thermal + charging areas; shared "lithium-ion", "charging" | ✅ HIGH (fire 14/25 at 1.9×, burn 14/25 at 3.2×); 6 areas led by battery thermal behavior (13), battery compartment security (7), charging protection (3); Reese's Law cited by 7 |
| 3 | Dresser: HIGH via fall + entrapment; STURDY Act listed | ✅ fall 25/25 (5.7×), entrapment 24/25 (14.8×); STURDY Act 18, ASTM F2057 2 |
| 4 | Unrelated query: 0 relevant, insufficient evidence, LOW, no areas | ✅ best match 0.183; nothing counted, every match marked weak |
| 5 | Every recall id in the report is a relevant match | ✅ checked for all 9 combinations |
| 6 | DB work < 300 ms warm; CLI < 2 s | ⚠️ see below |
| 7 | Tests and lint offline; advisors | ✅ 289 tests; advisors INFO only; API roles cannot read the term views |

**Latency (criterion 6), measured honestly.** One report runs 8 queries. From the laptop each is a
~44 ms network round trip, so a warm report takes ~410 ms, of which only **~58 ms is database and
Python work**. The CLI end to end takes 2.1–2.6 s (Python start-up ~0.4 s, TLS connect ~0.4 s,
OpenAI embedding ~0.65 s, the 8 round trips ~0.35 s). The database work itself meets the target.
The 2 s end-to-end target should be re-measured from the deployed API (Vercel in us-east-1, the same
region as Supabase, so round trips are a few ms and the connection stays open) as an `app` criterion.

Other observations:

- **Keyword search shows why the relevance floor matters:** only 17 of its top 25 night-light hits
  are actually similar (cosine ≥ 0.30), against 25 of 25 for vector search.
- **Failure terms** needed a regulatory stoplist ("violates", "mandatory", "Reese's", "easily
  accessed", "warnings"). Template recall texts repeat these words, but they don't describe how
  a product failed. The night light now shows coin, cell, chemical, internal, button, swallowed,
  overheat.
- **Cold cache:** the first queries after the project was restored took 200–300 ms each inside the
  database (HNSW pages read from disk) and then dropped to 1–14 ms. Warm the project before a demo.
- `classify` now also refreshes the term views: 9.0 s on Supabase in total.
- Postgres 17 builds materialized views with a restricted `search_path`, so the views name
  `public.recalls` explicitly.
