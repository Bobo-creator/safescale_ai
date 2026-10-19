# Spec: hazard-taxonomy

Module id: `hazard-taxonomy` (see [CAPABILITY_MAP.md](CAPABILITY_MAP.md)). Depends on: `data-ingest`.
Consumed by: `hazard-analysis` (hazard profile over the top-k), `app` (labels on evidence cards),
`evaluation` (hazard-label precision / recall / F1).

## Objective

Give every recall one or more **normalized hazard categories** (multi-label), each with the
phrase that justified it, so `hazard-analysis` can say things like "47% of similar recalls
involved fire/overheating" and the app can show *why* a recall carries a label.

The brief's design rule (§6): normalize the hazard labels the records already describe, rather than
having clustering invent categories. CPSC's structured `HazardType` field is empty on every
record, so we classify from the free text, which is very regular. A typical example: "The adapters can
overheat, posing a fire hazard to consumers."

**Done looks like:** `safescale classify` labels all 10,039 recalls in a few seconds, and
`safescale hazards 166` (Tumi lithium-ion power packs) prints
`fire_overheating ← "can ignite or explode while charging, posing a fire hazard"` (source: hazard).

## Key facts (measured on the local copy, 2026-10-19)

- `hazard_text` exists on 9,870 of 10,039 recalls (169 have none). Its average length is 138
  characters, and it usually contains "posing a ___ hazard". Old records are often a single word
  ("Strangulation", "Laceration", "Choking"). Recent titles also name the hazard ("… Due to Fire Hazard").
- A 12-category regex prototype over `hazard_text + title` (falling back to `description`) gave ≥ 1
  label to 90% of recalls. 56% got exactly one label and 33% got two or more, so multi-label matters.
- The brief's example list misses two large groups in the data, which the prototype counted:
  **crash / loss of control** (≈ 520 recalls: ATVs, off-road vehicles, bikes, go-karts) and
  **suffocation / strangulation** (≈ 600: cords, blinds, cribs, sleep products).
- About 1,260 recalls cite a violated standard ("fails to meet the federal …"). About 1,470 say
  only "injury hazard" or "risk of injury", and these should end up as `other`.
- Known false-positive traps: "lead to" is not lead poisoning. "the drop side can fall out of
  position" is a part falling, not a person falling (it's still often correct, since such recalls
  usually do pose a fall hazard). Generic "injury" must never trigger a specific category.

## The taxonomy (v1)

| Code | Display label | Covers (examples) |
|---|---|---|
| `fire_overheating` | Fire / overheating | fire, flames, ignition, explosion, overheating, melting, smoking |
| `burn` | Burn | burns, scalding, hot surfaces / liquids |
| `electrical_shock` | Electrical shock | shock, electrocution |
| `choking` | Choking | choking, small parts, aspiration, objects lodged in the throat |
| `suffocation_strangulation` | Suffocation / strangulation | suffocation, asphyxia, strangulation, entanglement, cords |
| `laceration` | Laceration | cuts, sharp edges or points, puncture |
| `fall` | Fall / tip-over | falls, tip-over, collapse of something supporting a person |
| `entrapment` | Entrapment / crush | entrapment, pinching, crushing, amputation, fingertip injuries |
| `poisoning` | Poisoning / toxic exposure | poisoning, lead, chemicals, ingestion, carbon monoxide, illness |
| `crash_loss_of_control` | Crash / loss of control | crash, loss of control, brakes or steering failing |
| `drowning` | Drowning | drowning |
| `other` | Other / unspecified injury | the record has a hazard but none of the above matched |

The first 8 rows come from the brief; I added `suffocation_strangulation`, `crash_loss_of_control`
and `drowning` because the data shows them as big, distinct groups. `other` is assigned only when
nothing else matches, so every recall has at least one label. Changing this list bumps
`TAXONOMY_VERSION`.

## Design

### Classifier: rules first (deterministic, free, explainable)

- Each category has a list of **include** patterns (regex, case-insensitive, word-boundary aware)
  and optional **exclude** patterns. Examples: `lead\b(?!\s+to)` for poisoning; `fall` excludes
  "fall(s) out of position" unless a person falls.
- **Text used, in order:** `hazard_text` and `title` together. If neither yields a label (or both are
  empty), `description` is used. The description is never used otherwise, because it mentions
  things that aren't the hazard (such as "No injuries reported" or usage instructions).
- **Evidence:** for each label we keep the matched sentence fragment (≤ 160 characters) and which
  field it came from. The app shows this, and it makes rule errors easy to debug.
- **Why not an LLM labeler as the primary?** Rules are reproducible, free, instant, and every label
  points to a phrase in the record. That is the same evidence-first stance as the rest of the product.
  An OpenAI labeler is a natural **challenger** that `evaluation` can score on the same gold set
  (about 10k short texts cost well under $1 with a small model). If it clearly wins, we promote it
  then (see Open questions).

```python
# pipeline/src/safescale/taxonomy/rules.py — style of the rule table
TAXONOMY_VERSION = 1

RULES: dict[Category, Rule] = {
    "fire_overheating": Rule(
        include=[r"\bfires?\b", r"\bflam(e|es|mable|mability)\b", r"\bignit", r"overheat", r"\bmelt"],
    ),
    "poisoning": Rule(
        include=[r"poison", r"\blead\b(?!\s+to)", r"carbon monoxide", r"\btoxic", r"ingest"],
    ),
    ...
}
```

### Python interface

```python
Category = Literal["fire_overheating", "burn", ..., "other"]

@dataclass(frozen=True)
class HazardLabel:
    category: Category
    evidence: str                      # matched fragment, <= 160 chars
    source: Literal["hazard", "title", "description"]

@dataclass(frozen=True)
class StandardViolation:
    standard: str | None               # e.g. "ASTM F2057", "16 CFR 1303"; None if only "federal standard"
    evidence: str
    source: Literal["hazard", "title", "description"]

@dataclass(frozen=True)
class Classification:
    labels: list[HazardLabel]          # always >= 1 (falls back to 'other')
    violations: list[StandardViolation]

def classify(*, title: str, hazard_text: str | None, description: str | None) -> Classification:
    """Pure function; no I/O."""

def classify_all(conn) -> ClassifyResult: ...          # recompute every recall, one transaction
def labels_for(conn, recall_ids: list[int]) -> dict[int, Classification]: ...
```

### Standards violations (a flag, not a hazard category)

About 1,260 recalls say the product failed a federal or voluntary standard. We record each
mention, plus the standard's name when the text gives one, so `hazard-analysis` can turn it into
investigation areas (e.g. "3 of your 10 matches failed ASTM F2057 (tip-over)"). Extraction uses
the same rule approach: trigger phrases ("violates", "fails to meet / comply with", "does not
meet") followed by a standard reference (`ASTM F\d+(-\d+)?`, `16 CFR (part )?\d+`, named federal
standards such as the lead paint ban or the Federal Hazardous Substances Act). A recall with a
trigger but no recognizable name gets `standard = null`.

### Storage (migration `db/migrations/004_hazard_taxonomy.sql`)

```sql
create table hazard_categories (           -- seeded by the migration; the app reads labels here
  code        text primary key,
  label       text not null,
  description text not null,
  sort_order  int  not null
);

create table recall_hazards (
  recall_id        bigint not null references recalls (recall_id) on delete cascade,
  category         text   not null references hazard_categories (code),
  evidence         text   not null,
  source           text   not null check (source in ('hazard', 'title', 'description')),
  taxonomy_version int    not null,
  primary key (recall_id, category)
);
create index recall_hazards_category on recall_hazards (category);

create table recall_standard_violations (
  id               bigint generated always as identity primary key,
  recall_id        bigint not null references recalls (recall_id) on delete cascade,
  standard         text,                     -- null = unnamed "federal safety standard"
  evidence         text   not null,
  source           text   not null check (source in ('hazard', 'title', 'description')),
  taxonomy_version int    not null
);
create index recall_standard_violations_recall on recall_standard_violations (recall_id);

alter table hazard_categories          enable row level security;
alter table recall_hazards             enable row level security;
alter table recall_standard_violations enable row level security;
```

Classifying all 10k recalls with regex takes about a second. So `classify` simply **recomputes
everything** in one transaction (delete, then insert), with no staleness tracking. Readers never
see a half-written state, and re-running is idempotent.

### Labeling page (gold set)

`safescale label` draws a fixed random sample of **50 recalls** (seeded, so the same 50 every
time), starts a small local web server (Python standard library only, bound to `127.0.0.1`) and
opens a page in your browser:

- One recall per screen: title, hazard text, description, link to the CPSC page.
- A checkbox for each of the 12 categories, a "violates a standard" checkbox, and a notes field.
- **Blind:** the page never shows the classifier's labels.
- Every click saves to `evaluation/hazard_gold/gold.json`, so you can stop and resume. Progress
  (e.g. 17 / 50) and back / next / jump-to-unlabeled are shown.

`safescale score-hazards` then compares the classifier with `gold.json` and prints per-category and
micro precision / recall / F1. With 50 recalls the scores have wide error bars (one wrong label moves
a rare category a lot), so the report also shows raw counts. `evaluation` can grow the set later.

## Commands

```bash
uv run safescale migrate                 # applies 004_hazard_taxonomy.sql
uv run safescale classify                # (re)label every recall; prints per-category counts
uv run safescale hazards 166             # show one recall's labels, violations, evidence
uv run safescale label                   # open the labeling page (50 recalls, resumable)
uv run safescale score-hazards           # classifier vs your gold labels: P / R / F1
uv run pytest                            # offline
```

Pipeline order becomes: `ingest → classify → embed`. The `classify` step is independent of
`embed` and can run in either order.

## Project structure

```
db/migrations/004_hazard_taxonomy.sql
pipeline/src/safescale/taxonomy/
  categories.py     # Category literal, display labels (must match the migration seed)
  rules.py          # TAXONOMY_VERSION, hazard + standard rule tables
  classify.py       # classify() pure function, evidence extraction
  store.py          # classify_all(), labels_for()
  labeling/         # `safescale label`: sample, tiny HTTP server, page (HTML/JS, no build step)
  score.py          # P / R / F1 against gold.json
pipeline/tests/taxonomy/
  test_rules.py     # table-driven: phrase -> expected labels, incl. false-positive traps
  test_classify.py  # fallback order, 'other', evidence, multi-label, standards
  test_store.py     # fixtures in local Postgres; idempotent; categories match the seed
  test_labeling.py  # sample is deterministic; save/resume round-trip; server binds to localhost
  test_score.py     # P / R / F1 on a tiny hand-made gold file
evaluation/hazard_gold/
  gold.json         # your labels (committed: it's research data)
```

## Testing strategy

- **Unit (table-driven):** about 60 hand-written phrases drawn from real recalls, each with its
  expected labels. They include every trap above: "lead to", "fall out of position", "injury hazard",
  "No injuries", one-word old records, multi-hazard sentences, and standard references with and
  without a name.
- **Integration:** the 18 fixture recalls through `classify_all` on local Postgres. Checks: every
  recall has ≥ 1 label, re-running gives identical rows, the categories table matches
  `categories.py`, and RecallID 166 (lithium-ion power pack) gets exactly `fire_overheating`.
- **Labeling page:** API round-trip tests (load sample, save a label, reload) and one Playwright
  check that the page renders, saves and resumes.
- **Accuracy (the gate for this module):** you label the **blind** 50-recall sample. I tune rules
  only on other recalls and never on the gold set, then report per-category and micro
  precision / recall / F1. `evaluation` later reuses the same gold set and adds the LLM challenger.

## Boundaries

- **Always:** keep an evidence fragment for every label and violation. Keep `categories.py` and the
  migration seed in sync (a test checks this). Bump `TAXONOMY_VERSION` whenever rules or categories
  change.
- **Ask first:** adding, removing or renaming a category. Switching the primary classifier to an LLM.
  Changing which text fields are used.
- **Never:** tune rules on the gold set or look at it before scoring. Let the word "injury" alone
  trigger a specific category. Call an external API from `classify`. Expose the labeling server
  beyond `127.0.0.1`.

## Success criteria

1. `safescale classify` on Supabase labels all 10,039 recalls in < 10 s; every recall has ≥ 1 label;
   an immediate re-run produces identical rows.
2. Every label and violation has non-empty evidence that appears verbatim in the named source field.
3. `other` is the only label for ≤ 10% of recalls (the prototype is at about 10% before adding crash
   rules and fixing "strangulation").
4. At least 1,000 recalls are flagged as violating a standard, and at least half of the flags name
   the standard.
5. You can label 50 recalls in the page, stop and resume without losing anything.
6. On your blind 50-recall gold set: micro-F1 ≥ 0.85. The per-category table (with counts) is
   reported, including the categories that miss.
7. `safescale hazards <id>` prints labels with evidence; `labels_for()` returns labels for 25 ids in
   one query.
8. Tests and lint pass offline. Supabase advisors show no new warnings.

## Decisions (approved 2026-10-19)

- Taxonomy: the brief's 8 categories plus suffocation/strangulation, crash/loss of control and
  drowning, plus `other`; overheating stays inside fire, as in the brief.
- `violates_standard` flag with the standard's name, built now.
- Gold set: 50 recalls, labeled blind in a local labeling page.
- Rules are the shipped classifier; an OpenAI labeler is a challenger in `evaluation`.
