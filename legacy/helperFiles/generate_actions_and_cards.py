#!/usr/bin/env python3
"""Generate/extend ID mappings for game actions (attacks, abilities, evolution triggers)
   and cards themselves.

This script scans one or more card JSON files and produces two Python files
under `v2/game/ids/`:

1. `actions.py` – contains ACTION_IDS: Dict[str, int]
   • all attack identifiers (cardId_pokemon_attack_position_target)
   • all ability identifiers (cardId_pokemon_ability_position_target)
   • evolution trigger identifiers (cardId_spot_evolve_basePokemon_into_evolvedPokemon)
   • play basic pokemon identifiers (cardId_spot_playBasicPokemon)
   • retreat identifiers (cardId_pokemon_retreat)

2. `cards.py` – contains CARD_IDS: Dict[str, int] mapping every card `id` to a
   sequential integer.

Indices are persistent: if the target file already exists, its mapping is
imported so existing numbers stay fixed and only *new* keys are appended with
next indices.

Run:
    python helperFiles/generate_actions_and_cards.py [--cards CARD_JSON...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List
import re

sys.path.append(str(Path(__file__).parent.parent))
from v2.game.ids.action_id_generation import ActionIdGenerator

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_existing_mapping(py_path: Path, var_name: str) -> Dict[str, int]:
    """Load existing ID mapping from a Python file."""
    if not py_path.exists():
        return {}

    # Create a new module
    spec = importlib.util.spec_from_file_location("temp_module", py_path)
    module = importlib.util.module_from_spec(spec)

    # Create a dictionary to store the mapping
    mapping = {}

    # Read the file line by line
    with open(py_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                # Extract variable name and value
                var_name, value = line.split("=", 1)
                var_name = var_name.strip()
                value = value.strip()
                
                # Skip class definition and docstring
                if var_name.startswith("class") or value.startswith('"""'):
                    continue
                
                # Convert variable name back to original format
                # Example: a1_001_attack_bulbasaur_vineWhip_pActive_oActive -> a1-001_attack_bulbasaur_vineWhip_pActive_oActive
                parts = var_name.split("_")
                if len(parts) > 1 and re.match(r"[a-zA-Z]\d+", parts[0]) and parts[1].isdigit():
                    # This is a card ID, convert back to original format
                    original_key = f"{parts[0]}-{parts[1]}_" + "_".join(parts[2:])
                else:
                    original_key = var_name
                
                try:
                    value = int(value)
                    mapping[original_key] = value
                except ValueError:
                    continue

    return mapping

# ---------------------------------------------------------------------------
# mapping builders
# ---------------------------------------------------------------------------

def convert_to_variable_name(key: str) -> str:
    """Convert a key to a valid Python variable name."""
    # For card IDs like "a1-001", convert to "a1_001"
    parts = key.split("_")
    if len(parts) > 0:
        # Handle card ID part (first part) specially
        card_id = parts[0]
        # Extract the set prefix (e.g. "a1") and number (e.g. "001") separately
        match = re.match(r"([a-zA-Z]\d+)-(\d+)", card_id)
        if match:
            set_prefix, number = match.groups()
            card_id = f"{set_prefix}_{number}"
        else:
            card_id = card_id.replace("-", "_")
        
        # Combine with rest of the parts
        var_name = card_id + "_" + "_".join(parts[1:])
    else:
        var_name = key.replace("-", "_")
        
    # Remove any remaining invalid characters
    var_name = "".join(c for c in var_name if c.isalnum() or c == "_")
    return var_name

def build_actions_mapping(cards: List[dict], existing: Dict[str, int]) -> Dict[str, int]:
    """Build mapping of action IDs to sequential integers."""
    mapping = {
        "end_turn": 0,
        "pactive_attach_energy": 1,
        "pbench1_attach_energy": 2,
        "pbench2_attach_energy": 3,
        "pbench3_attach_energy": 4
    }
    next_id = 5

    # Add existing mappings that aren't default actions
    for key, value in existing.items():
        if key not in mapping:
            mapping[key] = value
            next_id = max(next_id, value + 1)

    def add(key: str):
        nonlocal next_id
        if key not in mapping:
            mapping[key] = next_id
            next_id += 1

    # Process in sorted order for deterministic output
    for card in sorted(cards, key=lambda c: c["id"]):
        try:
            # Add play basic pokemon IDs
            for action_id in ActionIdGenerator.get_all_action_ids_for_card(card):
                add(action_id)
        except Exception as e:
            logging.error(f"⚠️ Error processing card {card.get('name', card.get('id', 'Unknown'))}: {str(e)}")
            # Print the full error for debugging
            import traceback
            logging.debug(traceback.format_exc())

    return mapping

def build_card_mapping(cards: List[dict], existing: Dict[str, int]) -> Dict[str, int]:
    """Build mapping of card IDs to sequential integers."""
    mapping = existing.copy()
    next_id = max(mapping.values()) + 1 if mapping else 0

    for card in sorted(cards, key=lambda c: c["id"]):
        if card["id"] not in mapping:
            mapping[card["id"]] = next_id
            next_id += 1

    return mapping

# ---------------------------------------------------------------------------
# file writers
# ---------------------------------------------------------------------------

def write_mapping(mapping: Dict[str, int], py_path: Path, var_name: str):
    """Write ID mapping to a Python file as a class with class variables."""
    content = [
        "# Auto-generated by helperFiles/generate_actions_and_cards.py",
        "# DO NOT EDIT MANUALLY.",
        "",
        f"class {var_name}:",
        '    """Class containing all action IDs as class variables."""',
        "",
    ]

    # Add default actions first
    if var_name == "ACTION_IDS":
        content.extend([
            "    end_turn = 0",
            "    a_attach_energy = 1",
            "    b1_attach_energy = 2",
            "    b2_attach_energy = 3",
            "    b3_attach_energy = 4",
            ""
        ])

    # Write entries in sorted order for deterministic output
    for key, value in sorted(mapping.items(), key=lambda x: x[1]):  # Sort by value to maintain ID order
        if key in ["end_turn", "a_attach_energy", "b1_attach_energy", "b2_attach_energy", "b3_attach_energy"]:
            continue
            
        # Convert the string key format to a valid Python variable name
        var_name = convert_to_variable_name(key)
        content.append(f"    {var_name} = {value}")

    content.extend(["", ""])

    py_path.write_text("\n".join(content))
    logging.info(f"[OK] Wrote {len(mapping)} entries -> {py_path}")

# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cards",
        type=Path,
        nargs="+",
        default=[Path("v2/assets/cards/a1-genetic-apex.json")],
        help="Card JSON files to process",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format="%(message)s", level=log_level)

    # Load and merge all card JSONs
    cards = []
    for path in args.cards:
        cards.extend(json.loads(path.read_text()))
    logging.info(f"[INFO] Loaded {len(cards)} cards from {len(args.cards)} file(s)")

    # Generate action ID mapping
    actions_py = Path("v2/game/ids/actions.py")
    actions_py.parent.mkdir(parents=True, exist_ok=True)
    existing = load_existing_mapping(actions_py, "ACTION_IDS")
    mapping = build_actions_mapping(cards, existing)
    write_mapping(mapping, actions_py, "ACTION_IDS")

    # Generate card ID mapping
    cards_py = Path("v2/game/ids/cards.py")
    cards_py.parent.mkdir(parents=True, exist_ok=True)
    existing = load_existing_mapping(cards_py, "CARD_IDS")
    mapping = build_card_mapping(cards, existing)
    write_mapping(mapping, cards_py, "CARD_IDS")

if __name__ == "__main__":
    main() 