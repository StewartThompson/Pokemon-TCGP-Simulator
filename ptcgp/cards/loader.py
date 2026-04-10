"""Load card JSON files into Card objects."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional

from ptcgp.cards.attack import Ability, Attack
from ptcgp.cards.card import Card
from ptcgp.cards.types import CardKind, CostSymbol, Element, Stage


def _parse_damage(raw: str | int | None) -> int:
    """Parse a damage value like '40', '40+', '20x', or integer."""
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    # strip trailing +, x, × symbols
    s = re.sub(r"[+×x]$", "", s).strip()
    return int(s) if s.isdigit() else 0


def _parse_cost(cost_list: list[str]) -> tuple[CostSymbol, ...]:
    symbols = []
    for token in (cost_list or []):
        try:
            symbols.append(CostSymbol.from_str(token))
        except ValueError:
            pass  # skip unknown cost tokens
    return tuple(symbols)


def _parse_element(value: str | None) -> Optional[Element]:
    if not value:
        return None
    try:
        return Element.from_str(value)
    except ValueError:
        return None


def _parse_stage(subtype: str | None) -> Optional[Stage]:
    if not subtype:
        return None
    try:
        return Stage.from_str(subtype)
    except ValueError:
        return None


def _parse_attacks(raw_attacks: list[dict]) -> tuple[Attack, ...]:
    """Parse the raw attack list and dedupe variants that differ only in targeting.

    Some cards in the dataset (e.g. Lilligant's Leaf Supply) list one entry per
    legal bench slot the attack's side-effect could target. The engine resolves
    the target itself, so we only want ONE logical attack per (name, cost,
    damage) triple — otherwise the UI shows three identical "Leaf Supply" rows.
    """
    from ptcgp.effects.apply import parse_handler_string
    attacks: list[Attack] = []
    seen: set[tuple[str, tuple, int]] = set()
    for a in raw_attacks or []:
        name = a.get("name", "")
        damage = _parse_damage(a.get("damage"))
        cost = _parse_cost(a.get("cost", []))
        key = (name, cost, damage)
        if key in seen:
            continue
        seen.add(key)
        handler = a.get("handler", "")
        attacks.append(Attack(
            name=name,
            damage=damage,
            cost=cost,
            effect_text=a.get("effect", ""),
            handler=handler,
            cached_effects=tuple(parse_handler_string(handler)),
        ))
    return tuple(attacks)


def _parse_ability(raw_abilities: list[dict]) -> Optional[Ability]:
    """Return the first ability that is a true Pokemon ability (not a trainer handler)."""
    from ptcgp.effects.apply import parse_handler_string
    for ab in (raw_abilities or []):
        # Skip abilities that are really just trainer card handler metadata
        name = ab.get("name", "")
        effect = ab.get("effect", "")
        if name and effect:
            handler = ab.get("handler", "")
            return Ability(
                name=name,
                effect_text=effect,
                is_passive=False,  # refined later per card if needed
                handler=handler,
                cached_effects=tuple(parse_handler_string(handler)),
            )
    return None


def _detect_ex(name: str) -> bool:
    stripped = name.strip()
    return stripped.endswith(" ex") or stripped.endswith("-ex")


def _detect_mega_ex(name: str) -> bool:
    low = name.lower()
    return "mega" in low and "ex" in low


def _detect_is_ex_rarity(rarity: str | None) -> bool:
    if not rarity:
        return False
    return "ex" in rarity.lower()


def load_card_from_dict(data: dict) -> Card:
    """Convert a raw JSON card dict to a Card object."""
    card_type = data.get("type", "Pokemon")
    subtype = data.get("subtype", "")
    name = data.get("name", "")
    rarity = data.get("rarity")

    is_pokemon = card_type.lower() == "pokemon"

    if is_pokemon:
        kind = CardKind.POKEMON
        stage = _parse_stage(subtype)
        element = _parse_element(data.get("element"))
        weakness = _parse_element(data.get("weakness"))
        hp = data.get("health", 0)
        retreat_cost = data.get("retreatCost", 0)
        is_ex = _detect_ex(name) or _detect_is_ex_rarity(rarity)
        is_mega_ex = _detect_mega_ex(name)
        if is_mega_ex:
            is_ex = True
        attacks = _parse_attacks(data.get("attacks", []))
        ability = _parse_ability(data.get("abilities", []))
        evolves_from = data.get("evolvesFrom") or None
        trainer_effect_text = ""
        trainer_handler = ""
    else:
        # Trainer card
        subtype_low = subtype.lower()
        if subtype_low == "supporter":
            kind = CardKind.SUPPORTER
        elif subtype_low == "tool":
            kind = CardKind.TOOL
        else:
            kind = CardKind.ITEM

        stage = None
        element = None
        weakness = None
        hp = 0
        retreat_cost = 0
        is_ex = False
        is_mega_ex = False
        evolves_from = None
        attacks = ()
        ability = None

        # Extract trainer effect text and handler from the abilities list
        from ptcgp.effects.apply import parse_handler_string
        raw_abs = data.get("abilities", [])
        if raw_abs:
            trainer_effect_text = raw_abs[0].get("effect", "")
            trainer_handler = raw_abs[0].get("handler", "")
        else:
            trainer_effect_text = ""
            trainer_handler = ""

    if is_pokemon:
        cached_trainer_effects: tuple = ()
    else:
        from ptcgp.effects.apply import parse_handler_string
        cached_trainer_effects = tuple(parse_handler_string(trainer_handler))

    return Card(
        id=data["id"],
        name=name,
        kind=kind,
        stage=stage,
        element=element,
        hp=hp,
        weakness=weakness,
        retreat_cost=retreat_cost,
        is_ex=is_ex,
        is_mega_ex=is_mega_ex,
        evolves_from=evolves_from,
        attacks=attacks,
        ability=ability,
        trainer_effect_text=trainer_effect_text,
        trainer_handler=trainer_handler if not is_pokemon else "",
        cached_trainer_effects=cached_trainer_effects,
    )


def load_cards_from_json(path: str | Path) -> list[Card]:
    """Load all cards from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [load_card_from_dict(d) for d in data]


def load_all_sets(directory: str | Path) -> list[Card]:
    """Load cards from all *.json files in a directory."""
    directory = Path(directory)
    cards = []
    for json_file in sorted(directory.glob("*.json")):
        cards.extend(load_cards_from_json(json_file))
    return cards
