"""Investigation areas: review and test areas that the similar recalls justify.

A curated catalog (v1). An area applies to a relevant match when the match carries one of the
area's hazard categories and, if the area lists trigger terms, its text mentions one of them. An
area is shown when at least MIN_SUPPORT matches support it. Wording is deliberately advisory:
these are areas to consider reviewing, never compliance determinations.
"""

import re
from collections import defaultdict
from dataclasses import dataclass

from safescale.analysis.report import Area, Match, StandardStat

CATALOG_VERSION = 1
MIN_SUPPORT = 2


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    title: str
    categories: frozenset[str]
    terms: dict[str, str]  # display term -> regex; empty = the categories alone trigger it
    checks: tuple[str, ...]

    def found_terms(self, text: str) -> list[str]:
        return [name for name, pattern in self.terms.items() if re.search(pattern, text, re.I)]

    def supports(self, match: Match) -> list[str] | None:
        """The trigger terms found, or None when this match doesn't support the area."""
        if not self.categories & {lbl.category for lbl in match.labels}:
            return None
        if not self.terms:
            return []
        found = self.found_terms(match.text)
        return found or None


def _entry(id, title, categories, terms, *checks) -> CatalogEntry:
    return CatalogEntry(id, title, frozenset(categories), terms, tuple(checks))


FIRE, BURN, SHOCK = "fire_overheating", "burn", "electrical_shock"

CATALOG: tuple[CatalogEntry, ...] = (
    _entry(
        "battery_thermal",
        "Battery thermal behavior and cell quality",
        {FIRE, BURN},
        {
            "battery": r"\bbatter",
            "lithium": r"\blithium",
            "cell": r"\bcells?\b",
            "power bank": r"power (bank|pack)",
        },
        "Review cell sourcing and the battery's protection circuitry",
        "Consider thermal-runaway and abuse testing (overcharge, short circuit, crush, drop)",
        "Check temperatures of the cells and nearby materials in worst-case use",
    ),
    _entry(
        "charging_protection",
        "Charging circuit and overcharge protection",
        {FIRE, BURN, SHOCK},
        {
            "charging": r"\bcharg",
            "adapter": r"\badapter",
            "USB": r"\busb\b",
            "power supply": r"power suppl",
        },
        "Review overcharge, over-current and over-temperature protection",
        "Test with third-party and faulty chargers and cables",
    ),
    _entry(
        "enclosure_flammability",
        "Enclosure and material flammability",
        {FIRE},
        {
            "housing": r"\bhousing",
            "enclosure": r"\benclos",
            "plastic": r"\bplastic",
            "melting": r"\bmelt",
            "casing": r"\bcas(e|ing)\b",
        },
        "Review the flame rating of housing and internal materials",
        "Check clearances between heat sources and plastics",
    ),
    _entry(
        "heating_control",
        "Heating elements and temperature control",
        {FIRE, BURN},
        {
            "heating element": r"heating element",
            "heater": r"\bheater",
            "thermostat": r"thermost",
            "hot surface": r"\bhot\b",
            "temperature": r"temperatur",
        },
        "Review thermostat and thermal cut-off behavior, including failure modes",
        "Measure accessible surface temperatures in normal and abnormal use",
    ),
    _entry(
        "internal_wiring",
        "Internal wiring, connections and short circuits",
        {FIRE, SHOCK},
        {
            "wiring": r"\bwir(e|es|ing)\b",
            "short circuit": r"short[- ]circuit",
            "circuit board": r"circuit board|\bpcb\b",
            "solder": r"\bsolder",
            "connection": r"connect",
        },
        "Review wire routing, strain points and solder joints",
        "Consider fault testing for short circuits and loose connections",
    ),
    _entry(
        "cords_plugs",
        "Power cords, plugs and insulation",
        {SHOCK, FIRE},
        {
            "cord": r"\bcords?\b",
            "plug": r"\bplugs?\b",
            "insulation": r"insulat",
            "outlet": r"\boutlet",
        },
        "Review cord insulation, strain relief and plug construction",
        "Test cords and plugs under flexing, pulling and heat",
    ),
    _entry(
        "water_ingress",
        "Water ingress and leakage current",
        {SHOCK},
        {"water": r"\bwater", "moisture": r"moisture|\bwet\b", "immersion": r"immers"},
        "Review sealing and the product's behavior when wet",
        "Consider leakage-current and immersion protection",
    ),
    _entry(
        "battery_compartment",
        "Battery compartment security (button and coin cells)",
        {"poisoning", "choking", BURN},
        {
            "button battery": r"button(-| )?cell|button batter",
            "coin battery": r"\bcoin",
            "battery compartment": r"battery (compartment|cover|door)",
        },
        "Review how the battery compartment is secured against child access",
        "Test that batteries stay enclosed after drops and abuse",
        "Check warnings and packaging for button and coin batteries",
    ),
    _entry(
        "magnets",
        "Magnet size, strength and containment",
        {"poisoning", "choking"},
        {"magnet": r"\bmagnet"},
        "Review magnet size and strength, and how magnets are contained",
        "Test that magnets cannot come loose with use and abuse",
    ),
    _entry(
        "small_parts",
        "Small and detachable parts",
        {"choking"},
        {
            "detach": r"\bdetach",
            "small part": r"small parts?",
            "break off": r"break(s)? off",
            "come off": r"come(s)? (off|loose)",
            "button": r"\bbuttons?\b",
            "cap": r"\bcaps?\b",
        },
        "Review which parts could detach and fit a small-parts cylinder",
        "Consider pull, torque and drop testing of attachments",
    ),
    _entry(
        "chemical_content",
        "Chemical and heavy-metal content",
        {"poisoning"},
        {
            "lead": r"\blead\b(?!\s+to)",
            "chemical": r"chemical(?!s?\s+burn)",  # not battery "chemical burns"
            "phthalate": r"phthalat",
            "paint": r"\bpaint",
            "toxic": r"\btoxic",
        },
        "Review materials, paints and coatings for restricted substances",
        "Consider third-party content testing of accessible parts",
    ),
    _entry(
        "child_resistant_packaging",
        "Child-resistant packaging",
        {"poisoning"},
        {
            "child-resistant": r"child[- ]resistant",
            "packaging": r"packag",
            "poison prevention": r"poison prevention",
        },
        "Review whether the contents call for child-resistant packaging",
        "Check closures and labeling for household chemicals",
    ),
    _entry(
        "combustion_venting",
        "Combustion, venting and carbon monoxide",
        {"poisoning", FIRE},
        {
            "carbon monoxide": r"carbon monoxide",
            "exhaust": r"\bexhaust",
            "venting": r"\bvent",
            "gas": r"\bgas\b",
        },
        "Review venting and combustion behavior, including indoor misuse",
        "Check carbon monoxide emissions and warnings",
    ),
    _entry(
        "stability_tipover",
        "Stability and tip-over",
        {"fall", "entrapment"},
        {"tip-over": r"\btip", "unstable": r"unstable|instab", "anchor": r"\banchor"},
        "Consider stability testing with loads, open drawers and climbing children",
        "Review anchoring hardware and how it is supplied",
    ),
    _entry(
        "structural_integrity",
        "Structural integrity and fasteners",
        {"fall", "crash_loss_of_control", "laceration"},
        {
            "break": r"\bbreak|\bbroke",
            "crack": r"\bcrack",
            "weld": r"\bweld",
            "bolt": r"\bbolts?\b|\bscrews?\b",
            "frame": r"\bframe",
            "separate": r"separat",
            "collapse": r"collaps",
        },
        "Consider load, fatigue and drop testing of load-bearing parts",
        "Review fasteners, welds and joints for loosening and fracture",
    ),
    _entry(
        "pinch_points",
        "Gaps, hinges and pinch points",
        {"entrapment"},
        {
            "hinge": r"\bhinge",
            "folding": r"\bfold",
            "gap": r"\bgaps?\b|\bspac(e|es|ing)\b",
            "pinch": r"\bpinch",
            "fingers": r"\bfinger",
            "lid": r"\blids?\b",
        },
        "Review gaps and openings against head, limb and finger entrapment",
        "Check folding, hinged and closing mechanisms for pinch points",
    ),
    _entry(
        "cords_straps_loops",
        "Cords, straps and loops",
        {"suffocation_strangulation"},
        {
            "cord": r"\bcords?\b",
            "strap": r"\bstraps?\b",
            "loop": r"\bloops?\b",
            "drawstring": r"drawstring",
            "string": r"\bstrings?\b",
            "chain": r"\bchains?\b",
        },
        "Review cord and strap lengths, loops and breakaway features",
    ),
    _entry(
        "infant_sleep",
        "Infant sleep environment",
        {"suffocation_strangulation", "entrapment"},
        {
            "mattress": r"mattress",
            "crib": r"\bcribs?\b",
            "bassinet": r"bassinet",
            "sleep": r"\bsleep",
            "bedding": r"bedding|blanket|pillow",
            "infant": r"\binfant",
        },
        "Review mattress fit, firmness and gaps around sleeping surfaces",
        "Check incline, soft bedding and positions an infant can reach",
    ),
    _entry(
        "brakes_steering",
        "Brakes, steering and throttle",
        {"crash_loss_of_control"},
        {},
        "Review brake, steering and throttle failure modes",
        "Consider durability testing of control components under real use",
    ),
    _entry(
        "sharp_edges",
        "Sharp edges, blades and glass",
        {"laceration"},
        {
            "sharp": r"\bsharp",
            "edge": r"\bedges?\b",
            "blade": r"\bblades?\b",
            "glass": r"\bglass",
            "shatter": r"shatter",
        },
        "Review accessible edges, points and guards",
        "Consider breakage testing of glass and brittle parts",
    ),
    _entry(
        "water_use",
        "Water use and flotation",
        {"drowning"},
        {},
        "Review how the product behaves in and around water",
        "Check flotation, buoyancy and warnings for water use",
    ),
)


def investigation_areas(matches: list[Match]) -> list[Area]:
    relevant = [m for m in matches if m.relevant]
    areas = []
    for entry in CATALOG:
        ids, terms = [], []
        for match in relevant:
            found = entry.supports(match)
            if found is None:
                continue
            ids.append(match.recall_id)
            terms += [t for t in found if t not in terms]
        if len(ids) >= MIN_SUPPORT:
            areas.append(Area(entry.id, entry.title, list(entry.checks), len(ids), ids, terms))
    order = {entry.id: i for i, entry in enumerate(CATALOG)}
    return sorted(areas, key=lambda a: (-a.support, order[a.id]))


def cited_standards(matches: list[Match]) -> list[StandardStat]:
    """Standards named by at least MIN_SUPPORT relevant matches, most cited first."""
    by_standard: dict[str, list[int]] = defaultdict(list)
    for match in matches:
        if not match.relevant:
            continue
        for name in {v.standard for v in match.violations if v.standard}:
            by_standard[name].append(match.recall_id)
    stats = [
        StandardStat(name, len(ids), ids)
        for name, ids in by_standard.items()
        if len(ids) >= MIN_SUPPORT
    ]
    return sorted(stats, key=lambda s: (-s.count, s.standard))
