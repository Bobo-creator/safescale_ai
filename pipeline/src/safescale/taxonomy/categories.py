"""The hazard categories (v1). The migration seed in 004_hazard_taxonomy.sql must match this."""

from dataclasses import dataclass
from typing import Literal, get_args

Category = Literal[
    "fire_overheating",
    "burn",
    "electrical_shock",
    "choking",
    "suffocation_strangulation",
    "laceration",
    "fall",
    "entrapment",
    "poisoning",
    "crash_loss_of_control",
    "drowning",
    "other",
]


@dataclass(frozen=True)
class CategoryInfo:
    code: Category
    label: str
    description: str


CATEGORIES: tuple[CategoryInfo, ...] = (
    CategoryInfo(
        "fire_overheating",
        "Fire / overheating",
        "Fire, flames, ignition, explosion, overheating, melting or smoking.",
    ),
    CategoryInfo(
        "burn", "Burn", "Burns or scalds from hot surfaces, liquids, flames or chemicals."
    ),
    CategoryInfo("electrical_shock", "Electrical shock", "Electric shock or electrocution."),
    CategoryInfo(
        "choking",
        "Choking",
        "Choking or aspiration: small parts, or objects lodged in the throat or airway.",
    ),
    CategoryInfo(
        "suffocation_strangulation",
        "Suffocation / strangulation",
        "Suffocation, asphyxia, strangulation or entanglement (e.g. cords, bedding).",
    ),
    CategoryInfo("laceration", "Laceration", "Cuts or punctures from sharp edges or points."),
    CategoryInfo(
        "fall",
        "Fall / tip-over",
        "A person falls, or a product tips over or collapses onto or under someone.",
    ),
    CategoryInfo(
        "entrapment",
        "Entrapment / crush",
        "Entrapment, pinching, crushing or amputation (e.g. fingers, head, body).",
    ),
    CategoryInfo(
        "poisoning",
        "Poisoning / toxic exposure",
        "Poisoning, lead, harmful chemicals, ingestion, carbon monoxide or illness.",
    ),
    CategoryInfo(
        "crash_loss_of_control",
        "Crash / loss of control",
        "Vehicle or ride-on crash or loss of control (e.g. brakes, steering, throttle).",
    ),
    CategoryInfo("drowning", "Drowning", "Drowning."),
    CategoryInfo(
        "other",
        "Other / unspecified injury",
        "A hazard none of the other categories describes, or only a generic injury risk.",
    ),
)

CATEGORY_CODES: tuple[Category, ...] = get_args(Category)

assert tuple(c.code for c in CATEGORIES) == CATEGORY_CODES, "CATEGORIES out of sync with Category"
