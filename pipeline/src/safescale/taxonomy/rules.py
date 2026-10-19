"""Hazard rules (v1): regex include patterns per category, plus exclude patterns.

An include match is ignored when it falls inside an exclude match, so "Recalls Fire Pits Due to
Burn Hazard" does not count "Fire Pits" as fire, while "Fire Pits Due to Fire Hazard" still does.
Patterns are case-insensitive. Generic words ("injury", "death", "hazard") never trigger a
category: a recall with only those gets `other`.
"""

import re
from dataclasses import dataclass, field

from safescale.taxonomy.categories import Category

TAXONOMY_VERSION = 1


@dataclass(frozen=True)
class Rule:
    include: list[str]
    exclude: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_include", [re.compile(p, re.IGNORECASE) for p in self.include])
        object.__setattr__(self, "_exclude", [re.compile(p, re.IGNORECASE) for p in self.exclude])

    def first_match(self, text: str) -> re.Match[str] | None:
        """The earliest include match that isn't inside an exclude match."""
        excluded = [m.span() for pattern in self._exclude for m in pattern.finditer(text)]
        best: re.Match[str] | None = None
        for pattern in self._include:
            for m in pattern.finditer(text):
                if any(start <= m.start() and m.end() <= end for start, end in excluded):
                    continue
                if best is None or m.start() < best.start():
                    best = m
                break  # later matches of this pattern start further right
        return best


# Product names that contain a hazard word but say nothing about the hazard.
_PRODUCT_NAMES_FIRE = [
    r"\bfire[- ]?(pits?|places?|extinguishers?|starters?|trucks?|tables?|logs?|bowls?|"
    r"alarms?|escape ladders?|resistant|retardant|works?)\b",
    r"\bfire\s+and\s+(carbon monoxide|co)\s+(alarms?|detectors?)\b",
    r"\bsmoke\s+(and\s+\w+\s+)?(alarms?|detectors?)\b",
    r"\bnon-?flammable\b",
]

HAZARD_RULES: dict[Category, Rule] = {
    "fire_overheating": Rule(
        include=[
            r"\bfires?\b",
            r"\bflam(e|es|mable|mability|ing)\b",
            r"\bignit(e|es|ed|ing|ion)\b",
            r"\bcombust",
            r"\bexplo(de|des|ded|ding|sion|sions|sive)\b",
            r"\boverheat",
            r"\bmelt(s|ed|ing)?\b",
            r"\bsmok(e|es|ed|ing)\b",
            r"\bthermal (runaway|event)",
            r"\bexcessive(ly)? heat",
        ],
        exclude=_PRODUCT_NAMES_FIRE,
    ),
    "burn": Rule(
        include=[r"\bburns?\b", r"\bburned\b", r"\bburnt\b", r"\bscald"],
        exclude=[r"\bburns? (off|out|with)\b"],
    ),
    "electrical_shock": Rule(
        include=[r"\b(electric(al)? )?shocks?\b", r"\belectrocut", r"\belectric(al)? current\b"],
        exclude=[r"\bshock (absorb|mount)", r"\btoxic shock\b", r"\bshock[- ]?proof\b"],
    ),
    "choking": Rule(
        include=[
            r"\bchok(e|es|ed|ing)\b",
            r"\baspirat",
            r"\bsmall parts?\b",
            r"\b(lodged|stuck) in (the |a |their |an )?(child's |infant's |young children's )?"
            r"(throat|airway|mouth)",
            r"\bblock(s|ing)? (the |a |their |an )?(child's |infant's )?(throat|airway)",
        ],
    ),
    "suffocation_strangulation": Rule(
        include=[
            r"\bsuffocat",
            r"\basphyx",
            r"\bstrang(le|led|les|ling|ulation|ulate|ulated)\b",
            r"\bentangl",
            r"\bpositional asphyxia",
        ],
    ),
    "laceration": Rule(
        include=[
            r"\blacerat",
            r"\bcuts?\b",
            r"\bsharp\b",
            r"\bpuncture (wounds?|hazards?|injur)",
        ],
        exclude=[r"\bcuts? (off|out)\b", r"\bpower cut\b", r"\bcut-?off\b"],
    ),
    "fall": Rule(
        include=[
            r"\bfall(s|ing)?\b",
            r"\bfell\b",
            r"\btip(s|ping|ped)?[- ]?over\b",
            r"\btip(s|ping|ped)? (over|forward|backward)",
            r"\bcollaps",
        ],
        exclude=[
            r"\bfall(s|ing)? (out of position|apart)\b",
            r"\bfall(s|ing)? (off|out|from) (of )?(its|their|the) (mount|bracket|ceiling|wall|"
            r"installed|housing|frame|base)",
            r"\bfall(s|ing)? onto\b",
            # An object falling ("causing the mirror to fall"), unless the subject is a person.
            r"\b(caus\w*|allow\w*) (the|its|their) (?!(child|children|rider|riders|user|users|"
            r"consumer|consumers|infant|infants|baby|babies|toddler|toddlers|occupant|occupants|"
            r"person|climber|operator|driver|wearer)\b)(\w+[- ]){0,2}\w+ to fall\b",
            r"\b(dryers?|appliances?) (\w+ )?falls? into\b",
        ],
    ),
    "entrapment": Rule(
        include=[
            r"\bentrap",
            r"\bpinch",
            r"\bcrush",
            r"\bamputat",
            r"\bfingertip",
            r"\bfinger (injur|entrap|amput|pinch|crush)",
            r"\b(caught|trapped|wedged) (in|between|under|beneath)\b",
        ],
    ),
    "poisoning": Rule(
        include=[
            r"\bpoison",
            r"\blead[- ](paint|content|levels?|poisoning|limit|standard|ban|based|containing)\b",
            r"\b(levels?|amounts?|concentrations?) of lead\b",
            r"\bcontains? (high |excessive |prohibited )?(levels of )?lead\b",
            r"\btoxic",
            r"\bingest",
            r"\bswallow",
            r"\bcarbon monoxide\b",
            r"\bchemicals?\b",
            r"\bphthalate",
            r"\bcadmium\b",
            r"\bmercury\b",
            r"\basbestos\b",
            r"\bmethanol\b",
            r"\b(diethylene|ethylene) glycol\b",
            r"\bbacteri",
            r"\bmold\b",
            r"\billness",
            r"\binfection",
            r"\bfumes\b",
            r"\b(skin|eye|respiratory) irritation\b",
        ],
        exclude=[r"\bfederal hazardous substances act\b", r"\bchemical burns?\b"],
    ),
    "crash_loss_of_control": Rule(
        include=[
            r"\bcrash",
            r"\bloss of (vehicle )?control\b",
            r"\blos(e|es|ing) control\b",
            r"\bout of control\b",
            r"\bcollision",
            r"\broll ?overs?\b",
            r"\bvehicle accidents?\b",
        ],
    ),
    "drowning": Rule(include=[r"\bdrown"]),
}
