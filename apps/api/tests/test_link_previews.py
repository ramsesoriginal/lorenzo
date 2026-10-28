"""The registry of preview templates (ADR 0264), as pure functions."""

from lorenzo_api.link_previews import FALLBACK, TEMPLATES, excerpt_of, pick_stats, template_for


def test_the_most_specific_kind_chooses_the_template() -> None:
    assert template_for(["being", "character"]).name == "character"
    assert template_for(["being"]).name == "being"
    assert template_for(["item", "item_instance"]).name == "item_instance"
    assert template_for(["item"]).name == "item"
    assert template_for(["location"]).name == "location"
    assert template_for(["map"]).name == "map"
    # A being's numbers come first; a place that is also a map is a place.
    assert template_for(["being", "location"]).name == "being"
    assert template_for(["item", "location"]).name == "item"
    assert template_for(["location", "map"]).name == "location"


def test_a_bare_entry_gets_the_fallback_which_shows_no_stats() -> None:
    assert template_for([]) is FALLBACK
    assert pick_stats(FALLBACK, {"weight": 3}) == []


def test_stats_come_in_the_templates_order_matched_without_case_and_capped() -> None:
    values = {"Price": 15, "Weight": 3, "rarity": "rare", "Damage": "1d8", "colour": "red"}
    picked = pick_stats(TEMPLATES["item"], values)
    assert picked == [("Damage", "1d8"), ("Weight", 3), ("Price", 15), ("rarity", "rare")]
    assert len(pick_stats(TEMPLATES["being"], {"hp": 1, "armor": 2, "height": 3, "rarity": 4})) == 3


def test_tags_and_unset_stats_are_left_out() -> None:
    assert pick_stats(TEMPLATES["item"], {"weight": True, "price": 2}) == [("price", 2)]


def test_every_template_names_its_own_kind() -> None:
    assert {name: t.name for name, t in TEMPLATES.items()} == {n: n for n in TEMPLATES}


def test_an_excerpt_is_plain_words_without_markup() -> None:
    text = "# Title\n\nA **sharp** [[Longsword]] with ![pic](x) a [link](other).\n\n- one\n- two"
    assert excerpt_of(text, 200) == "Title A sharp Longsword with a link. one two"


def test_a_long_excerpt_is_cut_at_a_word_with_an_ellipsis() -> None:
    cut = excerpt_of("word " * 100, 23)
    assert cut == "word word word word…"
    assert excerpt_of("short", 23) == "short"
    assert excerpt_of("", 23) == ""
