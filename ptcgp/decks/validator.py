"""Deck validation — checks legality and implementation status of a deck."""
from __future__ import annotations

from ptcgp.cards.database import get_card_or_none
from ptcgp.cards.types import CardKind, Stage
from ptcgp.effects.parser import parse_effect_text, is_effect_text_known
from ptcgp.effects.registry import is_effect_implemented
from ptcgp.effects.base import UnknownEffect


def is_card_fully_implemented(card_id: str) -> bool:
    """Return True if every effect on the card has a registered handler."""
    card = get_card_or_none(card_id)
    if card is None:
        return False

    effect_texts: list[str] = []

    if card.is_pokemon:
        # Check attack effect texts
        for attack in card.attacks:
            if attack.effect_text:
                effect_texts.append(attack.effect_text)
        # Check ability effect text (non-passive abilities have active handlers)
        if card.ability and not card.ability.is_passive and card.ability.effect_text:
            effect_texts.append(card.ability.effect_text)
    else:
        # Trainer card
        if card.trainer_effect_text:
            effect_texts.append(card.trainer_effect_text)

    for text in effect_texts:
        effects = parse_effect_text(text)
        for effect in effects:
            if isinstance(effect, UnknownEffect):
                return False
            if not is_effect_implemented(effect.name):
                return False

    return True


def validate_deck(card_ids: list[str]) -> list[str]:
    """Validate a deck, returning a list of error strings (empty = valid).

    Checks:
    1. Exactly 20 cards
    2. At least 1 Basic Pokemon
    3. No more than 2 copies of any card with the same name
    4. All cards exist in the database
    5. All cards are fully implemented (no unimplemented effects)
    """
    errors: list[str] = []

    # 1. Exactly 20 cards
    if len(card_ids) != 20:
        errors.append(f"Deck must contain exactly 20 cards (got {len(card_ids)})")

    # Track name counts and basic pokemon presence
    name_counts: dict[str, int] = {}
    has_basic_pokemon = False

    for card_id in card_ids:
        card = get_card_or_none(card_id)

        # 4. Card must exist
        if card is None:
            errors.append(f"Card ID {card_id!r} not found in database")
            continue

        # Track name counts for duplicate check
        name_counts[card.name] = name_counts.get(card.name, 0) + 1

        # Check for basic pokemon
        if card.is_pokemon and card.stage == Stage.BASIC:
            has_basic_pokemon = True

    # 2. At least 1 Basic Pokemon
    if not has_basic_pokemon:
        errors.append("Deck must contain at least 1 Basic Pokemon")

    # 3. No more than 2 copies of any card with the same name
    for name, count in name_counts.items():
        if count > 2:
            errors.append(f"Card {name!r} appears {count} times (max 2)")

    # 5. All cards are fully implemented
    for card_id in card_ids:
        card = get_card_or_none(card_id)
        if card is None:
            continue  # already reported above
        if not is_card_fully_implemented(card_id):
            errors.append(
                f"Card {card.name!r} has unimplemented effects and cannot be used"
            )

    return errors


def get_unimplemented_cards(card_ids: list[str]) -> list[str]:
    """Return card IDs that have unimplemented effects."""
    result = []
    seen: set[str] = set()
    for card_id in card_ids:
        if card_id in seen:
            continue
        seen.add(card_id)
        if not is_card_fully_implemented(card_id):
            result.append(card_id)
    return result
