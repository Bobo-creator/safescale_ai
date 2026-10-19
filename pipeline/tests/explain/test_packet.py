import json

from safescale.explain.packet import MAX_MATCHES, build_packet, truncate


def test_truncate_at_a_word_boundary():
    assert truncate("short", 10) == "short" and truncate(None, 10) is None
    assert (
        truncate("The battery can overheat, posing a fire hazard.", 26)
        == "The battery can overheat…"
    )


def test_packet_holds_only_relevant_matches_in_rank_order(analyzed):
    conn, report = analyzed
    packet = build_packet(conn, report)
    relevant = [m for m in sorted(report.matches, key=lambda m: m.rank) if m.relevant]
    ids = [r["recall_id"] for r in packet.data["recalls"]]
    assert ids == [m.recall_id for m in relevant][:MAX_MATCHES]
    assert packet.grounding.match_ids == set(ids)
    assert len(ids) <= MAX_MATCHES < len(report.matches)


def test_every_id_in_the_packet_is_a_packet_recall(analyzed):
    conn, report = analyzed
    packet = build_packet(conn, report)
    allowed = packet.grounding.match_ids
    for section in ("hazard_profile", "investigation_areas"):
        for item in packet.data[section]:
            assert set(item["recall_ids"]) <= allowed
    for ids in [*packet.grounding.category_ids.values(), *packet.grounding.area_ids.values()]:
        assert ids <= allowed


def test_recall_text_is_truncated_and_has_products(analyzed):
    conn, report = analyzed
    recalls = build_packet(conn, report).data["recalls"]
    assert all(
        len(r["hazard"] or "") <= 401 and len(r["description"] or "") <= 301 for r in recalls
    )
    assert any(r["products"] for r in recalls)


def test_numbers_come_from_the_packet_but_not_from_recall_ids(analyzed):
    conn, report = analyzed
    packet = build_packet(conn, report)
    profile = packet.data["hazard_profile"][0]
    assert str(profile["similar_recalls"]) in packet.grounding.numbers
    assert str(profile["share_percent"]) in packet.grounding.numbers
    long_ids = {str(i) for i in packet.grounding.match_ids if i > 1000}
    text_without_ids = json.dumps({k: v for k, v in packet.data.items() if k != "recalls"})
    for rid in long_ids:
        if rid not in text_without_ids:  # ids only appear as ids
            assert rid not in packet.grounding.numbers


def test_packet_is_json_serializable(analyzed):
    conn, report = analyzed
    json.dumps(build_packet(conn, report).data)
