"""Table-driven: hazard phrase -> expected categories (phrases taken from real recalls)."""

import pytest

from safescale.taxonomy.classify import classify

CASES = [
    # fire / overheating / burn
    ("The adapters can overheat, posing a fire hazard to consumers.", {"fire_overheating"}),
    ("The bulbs can overheat and catch fire, posing a fire hazard.", {"fire_overheating"}),
    ("Fire & Fire-Related Burn", {"fire_overheating", "burn"}),
    (
        "The engine exhaust can emit flames, posing fire and burn hazards to consumers.",
        {"fire_overheating", "burn"},
    ),
    (
        "The lithium-ion cells can ignite or explode while charging, posing a fire hazard.",
        {"fire_overheating"},
    ),
    ("Sustained contact with the door during self-cleaning mode could cause burns.", {"burn"}),
    (
        "The glass mugs can break when filled with hot liquids, posing burn and laceration risks.",
        {"burn", "laceration"},
    ),
    (
        "The recalled candles can burn with a high flame and melt the plastic holders.",
        {"fire_overheating"},
    ),
    ("The fire extinguishers can fail to discharge.", {"other"}),
    ("The smoke alarms can fail to alert consumers.", {"other"}),
    ("The gas burner valve can leak.", {"other"}),
    # electrical shock
    ("Electrocution/Electric Shock", {"electrical_shock"}),
    (
        "A defect in the line cord insulation poses a risk of electrical shock.",
        {"electrical_shock"},
    ),
    ("The shock absorber can break, posing an injury hazard.", {"other"}),
    # choking / suffocation / strangulation
    ("Choking", {"choking"}),
    (
        "The toy's sliding yellow knob can detach, posing a choking hazard to young children.",
        {"choking"},
    ),
    ("The peg dolls' spherical ends can block the child's airway.", {"choking"}),
    ("The mallets can get stuck in the throats of young children.", {"choking"}),
    ("The mallets can become lodged in the child's throat, blocking the airway.", {"choking"}),
    ("Suffocation", {"suffocation_strangulation"}),
    ("Strangulation", {"suffocation_strangulation"}),
    (
        "The hoodies have drawstrings which pose a strangulation hazard to young children.",
        {"suffocation_strangulation"},
    ),
    ("A child's neck becomes entangled in the free-standing loop.", {"suffocation_strangulation"}),
    (
        "An infant can become entrapped in the space, which can lead to strangulation.",
        {"entrapment", "suffocation_strangulation"},
    ),
    # laceration
    ("Laceration", {"laceration"}),
    (
        "The undersides of the foot platforms can have sharp edges, posing a laceration hazard.",
        {"laceration"},
    ),
    ("The handles can separate from the body, causing the operator to be cut.", {"laceration"}),
    (
        "The front floor cover can be punctured by a foreign object, posing an injury hazard.",
        {"other"},
    ),
    (
        "A plug designed to cut off electrical current in case of contact with water is missing.",
        {"electrical_shock"},
    ),
    # fall
    ("Chair legs can break unexpectedly, posing a fall hazard.", {"fall"}),
    ("The heel of the recalled shoes can detach, posing a fall hazard to consumers.", {"fall"}),
    (
        "The dressers are unstable if not anchored to the wall, posing tip-over and entrapment "
        "hazards.",
        {"fall", "entrapment"},
    ),
    ("A child can slide downward in the seat and could fall out of the carrier.", {"fall"}),
    (
        "The plastic fittings can break, causing the mirror to fall, posing a laceration hazard.",
        {"laceration"},
    ),
    ("The chains can break, causing the swing seats to fall to the ground.", {"other"}),
    ("The chains can break, causing children to fall to the ground.", {"fall"}),
    ("The drop side can detach and fall out of position.", {"other"}),
    (
        "The hair dryers are not equipped to prevent electrocution if the hair dryer falls into "
        "water.",
        {"electrical_shock"},
    ),
    # entrapment
    ("Entrapment", {"entrapment"}),
    (
        "The stroller's hinge poses a fingertip amputation and laceration hazard to the child.",
        {"entrapment", "laceration"},
    ),
    ("Fingers can become caught in the folding mechanism, posing a pinch hazard.", {"entrapment"}),
    # poisoning
    (
        "The necklaces contain high levels of lead, posing a risk of lead poisoning to children.",
        {"poisoning"},
    ),
    (
        "Surface paints contain excessive levels of lead, violating the federal lead paint "
        "standard.",
        {"poisoning"},
    ),
    ("This can lead to the bracket breaking, posing a fall hazard.", {"fall"}),
    ("The bottles can contain a bacteria.", {"poisoning"}),
    ("Like all charcoal grills, this grill emits carbon monoxide gas.", {"poisoning"}),
    ("A chemical in the rubber can cause skin or eye irritation.", {"poisoning"}),
    (
        "The batteries can be accessed easily by children, posing an ingestion hazard.",
        {"poisoning"},
    ),
    (
        "The toy violates the small parts ban under the Federal Hazardous Substances Act.",
        {"choking"},
    ),
    # crash / loss of control
    (
        "The front lower control arms can separate, posing a crash hazard.",
        {"crash_loss_of_control"},
    ),
    (
        "The forks can break, causing the rider to lose control and fall.",
        {"crash_loss_of_control", "fall"},
    ),
    (
        "The ROPS can loosen and fail to protect the operator in a rollover accident.",
        {"crash_loss_of_control"},
    ),
    ("Vehicle Accident", {"crash_loss_of_control"}),
    # drowning
    (
        "The leg holes can tear, causing children to fall into the water and, possibly, drown.",
        {"fall", "drowning"},
    ),
    # generic injury words never trigger a specific category
    (
        "The blades can detach from the fan while in use, posing an injury hazard to consumers.",
        {"other"},
    ),
    (
        "The seatbelts can unintentionally unlatch, posing a risk of serious injury or death.",
        {"other"},
    ),
    ("The valve cap can pop off and strike a bystander, posing an impact hazard.", {"other"}),
]


@pytest.mark.parametrize(("hazard_text", "expected"), CASES)
def test_hazard_phrase(hazard_text, expected):
    result = classify(title="", hazard_text=hazard_text, description=None)
    assert set(result.categories) == expected
