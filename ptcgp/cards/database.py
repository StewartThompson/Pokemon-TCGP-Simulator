"""Global card database — singleton dict keyed by card ID."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from ptcgp.cards.card import Card

_CARD_DB: dict[str, Card] = {}

# Cached evolution map: basic_name → frozenset of Stage-2 names reachable via
# any Stage-1 bridge. Built once in load_defaults(); never changes at runtime.
_BASIC_TO_STAGE2: dict[str, frozenset] = {}

# Path to default card assets
_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "cards"


def register_card(card: Card) -> None:
    _CARD_DB[card.id] = card


def get_card(card_id: str) -> Card:
    try:
        return _CARD_DB[card_id]
    except KeyError:
        raise KeyError(f"Card not found in database: {card_id!r}")


def get_card_or_none(card_id: str) -> Optional[Card]:
    return _CARD_DB.get(card_id)


def get_all_cards() -> dict[str, Card]:
    return dict(_CARD_DB)


def clear_db() -> None:
    _CARD_DB.clear()


def load_defaults() -> None:
    """Load all card sets from the assets/cards/ directory.

    If the same card ID appears in multiple sets, keep whichever version has the
    most information (abilities / attacks / effect text). This prevents a later
    set with an empty duplicate entry from clobbering a richer earlier one.
    """
    from ptcgp.cards.loader import load_all_sets
    for card in load_all_sets(_ASSETS_DIR):
        existing = _CARD_DB.get(card.id)
        if existing is None or _card_info_score(card) > _card_info_score(existing):
            _CARD_DB[card.id] = card
    _build_evo_cache()


def _card_info_score(card: Card) -> int:
    """Rank cards so richer entries beat stub duplicates from other sets."""
    score = 0
    if card.ability is not None:
        score += 2
    score += sum(1 for a in card.attacks if a.effect_text)
    if card.trainer_effect_text:
        score += 3
    return score


def is_loaded() -> bool:
    return len(_CARD_DB) > 0


def get_basic_to_stage2() -> dict[str, frozenset]:
    """Return the cached basic-name → reachable Stage-2 names map."""
    return _BASIC_TO_STAGE2


def _build_evo_cache() -> None:
    """Populate _BASIC_TO_STAGE2 from the loaded card DB (called once at load)."""
    from ptcgp.cards.types import Stage
    stage1_by_name: dict[str, list] = {}
    for c in _CARD_DB.values():
        if c.stage == Stage.STAGE_1 and c.evolves_from:
            stage1_by_name.setdefault(c.name, []).append(c)
    tmp: dict[str, set] = {}
    for c in _CARD_DB.values():
        if c.stage == Stage.STAGE_2 and c.evolves_from:
            for s1 in stage1_by_name.get(c.evolves_from, []):
                if s1.evolves_from:
                    tmp.setdefault(s1.evolves_from, set()).add(c.name)
    _BASIC_TO_STAGE2.clear()
    _BASIC_TO_STAGE2.update({k: frozenset(v) for k, v in tmp.items()})
