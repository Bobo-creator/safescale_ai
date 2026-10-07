# Test fixtures

`recalls_sample.json` holds real, unmodified CPSC recall records (from the full API
response fetched 2026-10-06), one per edge case below. Tests must not call the live API.

| RecallID | Edge case |
|---|---|
| 3722 | no Hazards entries |
| 2574 | no Description |
| 205 | HTML tags in text |
| 9237 | HTML entity (&amp;) |
| 3724 | multiple Products |
| 3760 | multiple Hazards |
| 4670 | duplicate product names |
| 3725 | 1970s record |
| 9491 | recent record, empty Products.Type |
| 2 | Injuries 'None reported' |
| 9294 | non-breaking space / repeated whitespace |
| 3730 | empty product name |
| 50 | short hazard label (e.g. 'Choking') |
| 1245 | very long description (>4000 chars) |
| 166 | lithium-ion battery / fire hazard |
| 1 | 1990s record |
| 4 | 2000s record with Products.Type |
| 20 | children's product / injuries reported |
