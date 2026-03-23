"""Card definitions and database for PTCGP."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from .types import EnergyType, PokemonStage, CardType, EffectType, StatusEffect


@dataclass(frozen=True)
class AttackEffect:
    """A single effect component of an attack or ability."""
    effect_type: EffectType
    value: int = 0
    energy_type: Optional[EnergyType] = None
    status: Optional[StatusEffect] = None
    condition: Optional[str] = None  # "heads", "tails", etc.
    target: Optional[str] = None  # "self", "bench", "opponent", etc.
    search_filter: Optional[str] = None  # "basic", "grass", etc.


@dataclass(frozen=True)
class Attack:
    """An attack a Pokemon can use."""
    name: str
    damage: int
    cost: dict[EnergyType, int]  # e.g. {GRASS: 1, COLORLESS: 1}
    effects: tuple[AttackEffect, ...] = ()
    effect_text: str = ""


@dataclass(frozen=True)
class Ability:
    """A Pokemon ability."""
    name: str
    effect_text: str
    effects: tuple[AttackEffect, ...] = ()
    is_passive: bool = False  # True = always active, False = must be activated


@dataclass(frozen=True)
class CardData:
    """Immutable card template. Never mutated during gameplay."""
    id: str
    name: str
    card_type: CardType

    # Pokemon-specific fields
    stage: Optional[PokemonStage] = None
    element: Optional[EnergyType] = None
    hp: int = 0
    weakness: Optional[EnergyType] = None
    retreat_cost: int = 0
    is_ex: bool = False
    evolves_from: Optional[str] = None
    attacks: tuple[Attack, ...] = ()
    ability: Optional[Ability] = None

    # Trainer-specific fields
    trainer_effects: tuple[AttackEffect, ...] = ()
    trainer_effect_text: str = ""

    @property
    def is_pokemon(self) -> bool:
        return self.card_type == CardType.POKEMON

    @property
    def is_basic(self) -> bool:
        return self.stage == PokemonStage.BASIC

    @property
    def ko_points(self) -> int:
        """Points awarded for knocking out this Pokemon."""
        return 2 if self.is_ex else 1


# --- Card Database (global singleton) ---

_CARD_DB: dict[str, CardData] = {}


def get_card(card_id: str) -> CardData:
    """Look up a card by its ID."""
    return _CARD_DB[card_id]


def get_all_cards() -> dict[str, CardData]:
    """Get the full card database."""
    return dict(_CARD_DB)


def get_cards_by_name(name: str) -> list[CardData]:
    """Get all cards matching a name."""
    return [c for c in _CARD_DB.values() if c.name == name]


def _parse_energy_type(s: str) -> EnergyType:
    """Parse an energy type string to enum."""
    mapping = {
        "grass": EnergyType.GRASS,
        "fire": EnergyType.FIRE,
        "water": EnergyType.WATER,
        "lightning": EnergyType.LIGHTNING,
        "electric": EnergyType.LIGHTNING,
        "psychic": EnergyType.PSYCHIC,
        "fighting": EnergyType.FIGHTING,
        "darkness": EnergyType.DARKNESS,
        "dark": EnergyType.DARKNESS,
        "metal": EnergyType.METAL,
        "steel": EnergyType.METAL,
        "colorless": EnergyType.COLORLESS,
        "normal": EnergyType.COLORLESS,
    }
    return mapping.get(s.lower().strip(), EnergyType.COLORLESS)


def _parse_cost(cost_list: list[str]) -> dict[EnergyType, int]:
    """Parse a list of energy type strings into a cost dict."""
    cost: dict[EnergyType, int] = {}
    for c in cost_list:
        etype = _parse_energy_type(c)
        cost[etype] = cost.get(etype, 0) + 1
    return cost


def _parse_attack_effects(effect_text: str) -> tuple[AttackEffect, ...]:
    """Parse effect text into AttackEffect objects. Best-effort parsing."""
    if not effect_text:
        return ()

    effects: list[AttackEffect] = []
    text = effect_text.lower().strip()

    # Heal effects
    if "heal" in text:
        m = re.search(r"heal\s+(\d+)\s+damage", text)
        if m:
            target = "self"
            if "each of your" in text or "all" in text:
                effects.append(AttackEffect(EffectType.HEAL_ALL, value=int(m.group(1))))
            else:
                effects.append(AttackEffect(EffectType.HEAL, value=int(m.group(1)), target=target))

    # Discard energy
    if "discard" in text and "energy" in text:
        m = re.search(r"discard\s+(?:a|(\d+))?\s*(\w+)?\s*energy", text)
        if m:
            count = int(m.group(1)) if m.group(1) else 1
            etype = _parse_energy_type(m.group(2)) if m.group(2) else None
            effects.append(AttackEffect(EffectType.DISCARD_ENERGY, value=count, energy_type=etype, target="self"))

    # Draw cards
    if "draw" in text and "card" in text:
        m = re.search(r"draw\s+(\d+)\s+card", text)
        if m:
            effects.append(AttackEffect(EffectType.DRAW_CARDS, value=int(m.group(1))))

    # Search deck for pokemon
    if "put" in text and ("deck" in text or "hand" in text) and "pokémon" in text.replace("pokemon", "pokémon"):
        m = re.search(r"(\d+)\s+(?:random\s+)?(\w+)?\s*pokémon", text.replace("pokemon", "pokémon"))
        if m:
            count = int(m.group(1)) if m.group(1) else 1
            search_filter = m.group(2) if m.group(2) != "random" else None
            effects.append(AttackEffect(EffectType.SEARCH_DECK, value=count, search_filter=search_filter))

    # Status effects
    for status, keyword in [
        (StatusEffect.POISONED, "poison"),
        (StatusEffect.BURNED, "burn"),
        (StatusEffect.PARALYZED, "paralyz"),
        (StatusEffect.ASLEEP, "asleep"),
        (StatusEffect.CONFUSED, "confus"),
    ]:
        if keyword in text:
            effects.append(AttackEffect(EffectType.APPLY_STATUS, status=status, target="opponent"))

    # Coin flip conditional
    if "flip" in text and "coin" in text:
        if not effects:
            effects.append(AttackEffect(EffectType.COIN_FLIP))

    # Attach energy from energy zone
    if "energy zone" in text and "attach" in text:
        m = re.search(r"(\d+)\s+(\w+)\s+energy", text)
        if m:
            count = int(m.group(1))
            etype = _parse_energy_type(m.group(2))
            effects.append(AttackEffect(EffectType.ATTACH_ENERGY, value=count, energy_type=etype))

    # Switch opponent
    if "switch" in text and "opponent" in text:
        effects.append(AttackEffect(EffectType.SWITCH_OPPONENT))

    # Can't attack
    if "can't attack" in text or "cannot attack" in text:
        effects.append(AttackEffect(EffectType.CANT_ATTACK, target="opponent"))

    # Bench damage
    if "bench" in text and ("damage" in text or re.search(r"\d+.*bench", text)):
        m = re.search(r"(\d+)\s+damage\s+to.*bench", text)
        if m:
            effects.append(AttackEffect(EffectType.BENCH_DAMAGE, value=int(m.group(1)), target="opponent"))

    # HP bonus (tools)
    if "+20 hp" in text or "has +20" in text:
        effects.append(AttackEffect(EffectType.HP_BONUS, value=20))

    return tuple(effects)


def _load_card_json(data: dict) -> Optional[CardData]:
    """Convert a JSON card dict to a CardData object."""
    card_type_str = (data.get("type") or "").lower()
    subtype_str = (data.get("subtype") or "").lower()

    # Determine card type
    if card_type_str == "pokemon":
        card_type = CardType.POKEMON
    elif subtype_str == "item":
        card_type = CardType.ITEM
    elif subtype_str == "supporter":
        card_type = CardType.SUPPORTER
    elif subtype_str == "tool":
        card_type = CardType.TOOL
    elif card_type_str == "trainer":
        # Default trainer to item
        card_type = CardType.ITEM
    else:
        return None

    card_id = data.get("id", "")
    name = data.get("name", "")
    is_ex = "ex" in name.lower().split()[-1:] or "ex" in (data.get("rarity") or "").lower()

    if card_type == CardType.POKEMON:
        # Parse stage
        stage_map = {
            "basic": PokemonStage.BASIC,
            "stage 1": PokemonStage.STAGE1,
            "stage1": PokemonStage.STAGE1,
            "stage 2": PokemonStage.STAGE2,
            "stage2": PokemonStage.STAGE2,
        }
        stage = stage_map.get(subtype_str, PokemonStage.BASIC)

        element = _parse_energy_type(data.get("element") or "colorless")
        if element == EnergyType.COLORLESS and data.get("element"):
            element = _parse_energy_type(data["element"])

        # Parse attacks (deduplicate by name - some cards have duplicated entries for targeting)
        seen_attacks: dict[str, Attack] = {}
        for atk_data in data.get("attacks", []):
            atk_name = atk_data.get("name", "Unknown")
            if atk_name in seen_attacks:
                continue
            damage_str = str(atk_data.get("damage", "0")).strip()
            damage = int(damage_str) if damage_str.isdigit() else 0
            cost = _parse_cost(atk_data.get("cost", []))
            effect_text = atk_data.get("effect", "")
            effects = _parse_attack_effects(effect_text)
            seen_attacks[atk_name] = Attack(
                name=atk_name, damage=damage, cost=cost,
                effects=effects, effect_text=effect_text,
            )
        attacks = tuple(seen_attacks.values())

        # Parse ability
        ability = None
        for ab_data in data.get("abilities", []):
            ab_name = ab_data.get("name", "")
            ab_text = ab_data.get("effect", "")
            ab_effects = _parse_attack_effects(ab_text)
            is_passive = "once during your turn" not in ab_text.lower()
            ability = Ability(name=ab_name, effect_text=ab_text, effects=ab_effects, is_passive=is_passive)
            break  # Only first ability

        weakness = _parse_energy_type(data["weakness"]) if data.get("weakness") else None

        return CardData(
            id=card_id, name=name, card_type=card_type,
            stage=stage, element=element,
            hp=int(data.get("health") or data.get("hp") or 0),
            weakness=weakness,
            retreat_cost=int(data.get("retreatCost") or data.get("retreat_cost") or 0),
            is_ex=is_ex, evolves_from=data.get("evolvesFrom") or data.get("evolves_from"),
            attacks=attacks, ability=ability,
        )
    else:
        # Trainer card
        effect_text = ""
        effects: list[AttackEffect] = []
        for ab_data in data.get("abilities", []):
            effect_text = ab_data.get("effect", "")
            effects.extend(_parse_attack_effects(effect_text))

        return CardData(
            id=card_id, name=name, card_type=card_type,
            trainer_effects=tuple(effects),
            trainer_effect_text=effect_text,
        )


def load_cards_from_json(filepath: str) -> int:
    """Load cards from a JSON file into the global database. Returns count loaded."""
    with open(filepath, "r") as f:
        cards_data = json.load(f)

    count = 0
    for card_json in cards_data:
        card = _load_card_json(card_json)
        if card:
            _CARD_DB[card.id] = card
            count += 1
    return count


def load_all_cards() -> int:
    """Load all card JSON files from the data directory."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cards")
    if not os.path.exists(data_dir):
        # Try v3 assets as fallback
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "v3", "assets")

    count = 0
    if os.path.exists(data_dir):
        for fname in sorted(os.listdir(data_dir)):
            if fname.endswith(".json"):
                count += load_cards_from_json(os.path.join(data_dir, fname))
    return count


def register_card(card: CardData) -> None:
    """Register a card directly (useful for testing)."""
    _CARD_DB[card.id] = card


def clear_card_db() -> None:
    """Clear the card database (useful for testing)."""
    _CARD_DB.clear()
