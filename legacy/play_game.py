#!/usr/bin/env python3
"""
Simple script to play Pokemon TCG Pocket Battle Simulator from the terminal.
"""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from v3.importers.json_card_importer import JsonCardImporter
from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.match.game_rules import GameRules
from v3.models.agents.random_agent import RandomAgent
from v3.models.agents.human_agent import HumanAgent
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.decks.basic_grass_deck import BasicGrassDeck
from v3.decks.intermediate_grass_deck import BasicGrassDeck as IntermediateGrassDeck
from v3.decks.basic_fire_deck import BasicFireDeck

# Map deck names to deck classes
DECK_MAP = {
    'basic_grass_deck': BasicGrassDeck,
    'intermediate_grass_deck': IntermediateGrassDeck,
    'basic_fire_deck': BasicFireDeck,
    # Also support without _deck suffix
    'basic_grass': BasicGrassDeck,
    'intermediate_grass': IntermediateGrassDeck,
    'basic_fire': BasicFireDeck,
}


def create_basic_deck(importer: JsonCardImporter, energy_type: Energy.Type, deck_size: int = 20):
    """Create a basic deck from available Pokemon cards (max 2 copies per card)
    Note: energy_type is used for Energy Zone generation, not for filtering Pokemon"""
    from copy import deepcopy
    from collections import Counter
    
    deck = []
    
    # Get all available Pokemon
    available_pokemon = list(importer.pokemon.values())
    
    if not available_pokemon:
        print("Error: No Pokemon cards found in JSON file!")
        return None
    
    # Get all Basic Pokemon (don't filter by energy type - use all available)
    basic_pokemon = [p for p in available_pokemon if p.subtype == Card.Subtype.BASIC]
    
    if not basic_pokemon:
        print("Error: No Basic Pokemon found!")
        return None
    
    # Sort by energy type preference (prefer Pokemon matching the chosen energy type)
    def sort_key(p):
        if p.element == energy_type:
            return 0  # Prefer matching energy type
        return 1
    
    basic_pokemon.sort(key=sort_key)
    
    # Create deck with max 2 copies of each card
    # Track how many of each card ID we've added
    card_counts = Counter()
    max_copies = 2
    
    # First pass: add up to 2 copies of each unique card
    for pokemon in basic_pokemon:
        card_id = pokemon.id
        if card_counts[card_id] < max_copies:
            copies_to_add = min(max_copies - card_counts[card_id], deck_size - len(deck))
            for _ in range(copies_to_add):
                deck.append(deepcopy(pokemon))
                card_counts[card_id] += 1
                if len(deck) >= deck_size:
                    break
        if len(deck) >= deck_size:
            break
    
    # If we still need more cards, add more copies (but still max 2 per card)
    # Cycle through available cards
    while len(deck) < deck_size:
        added_any = False
        for pokemon in basic_pokemon:
            card_id = pokemon.id
            if card_counts[card_id] < max_copies and len(deck) < deck_size:
                deck.append(deepcopy(pokemon))
                card_counts[card_id] += 1
                added_any = True
                if len(deck) >= deck_size:
                    break
        if not added_any or len(deck) >= deck_size:
            break
    
    # If still not enough cards, we need to allow more copies (but warn)
    if len(deck) < deck_size:
        print(f"Warning: Only {len(basic_pokemon)} unique Basic Pokemon available.")
        print(f"Adding extra copies to reach {deck_size} cards (exceeding 2-copy limit).")
        while len(deck) < deck_size:
            for pokemon in basic_pokemon:
                if len(deck) >= deck_size:
                    break
                deck.append(deepcopy(pokemon))
    
    return deck[:deck_size]


def create_evolution_deck(importer: JsonCardImporter, base_pokemon_name: str, deck_size: int = 20):
    """Create a deck focused on an evolution chain (e.g., Bulbasaur -> Ivysaur -> Venusaur)"""
    from copy import deepcopy
    from collections import Counter
    
    deck = []
    available_pokemon = list(importer.pokemon.values())
    
    if not available_pokemon:
        return None
    
    # Find the evolution chain
    base = None
    stage1 = []
    stage2 = []
    
    for pokemon in available_pokemon:
        if pokemon.name == base_pokemon_name and pokemon.subtype == Card.Subtype.BASIC:
            base = pokemon
        elif pokemon.evolves_from == base_pokemon_name:
            if pokemon.subtype == Card.Subtype.STAGE_1:
                stage1.append(pokemon)
            elif pokemon.subtype == Card.Subtype.STAGE_2:
                stage2.append(pokemon)
    
    if not base:
        print(f"Error: Base Pokemon '{base_pokemon_name}' not found!")
        return None
    
    # Build deck: 8-10 base, 4-6 stage1, 2-4 stage2, fill rest with base
    card_counts = Counter()
    max_copies = 2
    
    # Add base Pokemon (8-10 copies)
    base_count = min(10, deck_size - 6)  # Leave room for evolutions
    for _ in range(base_count):
        if card_counts[base.id] < max_copies * 5:  # Allow more base Pokemon
            deck.append(deepcopy(base))
            card_counts[base.id] += 1
    
    # Add Stage 1 (4-6 copies)
    if stage1:
        stage1_pokemon = stage1[0]
        stage1_count = min(6, deck_size - len(deck) - 2)
        for _ in range(stage1_count):
            if card_counts[stage1_pokemon.id] < max_copies * 3:
                deck.append(deepcopy(stage1_pokemon))
                card_counts[stage1_pokemon.id] += 1
    
    # Add Stage 2 (2-4 copies)
    if stage2:
        stage2_pokemon = stage2[0]
        stage2_count = min(4, deck_size - len(deck))
        for _ in range(stage2_count):
            if card_counts[stage2_pokemon.id] < max_copies * 2:
                deck.append(deepcopy(stage2_pokemon))
                card_counts[stage2_pokemon.id] += 1
    
    # Fill remaining with base Pokemon
    while len(deck) < deck_size:
        deck.append(deepcopy(base))
    
    return deck[:deck_size]


def create_mixed_type_deck(importer: JsonCardImporter, energy_types: list[Energy.Type], deck_size: int = 20):
    """Create a deck with multiple energy types"""
    from copy import deepcopy
    from collections import Counter
    
    deck = []
    available_pokemon = list(importer.pokemon.values())
    
    if not available_pokemon:
        return None
    
    # Get Basic Pokemon of any specified type
    basic_pokemon = []
    for energy_type in energy_types:
        matching = [p for p in available_pokemon 
                   if p.subtype == Card.Subtype.BASIC and p.element == energy_type]
        basic_pokemon.extend(matching)
    
    if not basic_pokemon:
        basic_pokemon = [p for p in available_pokemon if p.subtype == Card.Subtype.BASIC]
    
    if not basic_pokemon:
        return None
    
    # Create deck with max 2 copies per card
    card_counts = Counter()
    max_copies = 2
    
    # Distribute cards across types
    cards_per_type = deck_size // len(energy_types) if energy_types else deck_size
    
    for energy_type in energy_types:
        type_pokemon = [p for p in basic_pokemon if p.element == energy_type]
        for pokemon in type_pokemon:
            if len(deck) >= deck_size:
                break
            if card_counts[pokemon.id] < max_copies:
                copies = min(max_copies - card_counts[pokemon.id], deck_size - len(deck))
                for _ in range(copies):
                    deck.append(deepcopy(pokemon))
                    card_counts[pokemon.id] += 1
    
    # Fill remaining slots
    while len(deck) < deck_size:
        for pokemon in basic_pokemon:
            if len(deck) >= deck_size:
                break
            if card_counts[pokemon.id] < max_copies:
                deck.append(deepcopy(pokemon))
                card_counts[pokemon.id] += 1
    
    return deck[:deck_size]


def create_aggressive_deck(importer: JsonCardImporter, energy_type: Energy.Type, deck_size: int = 20):
    """Create an aggressive deck focused on high-damage Pokemon"""
    from copy import deepcopy
    from collections import Counter
    
    deck = []
    available_pokemon = list(importer.pokemon.values())
    
    if not available_pokemon:
        return None
    
    # Filter for Basic Pokemon with attacks that do damage
    basic_pokemon = [
        p for p in available_pokemon 
        if p.subtype == Card.Subtype.BASIC and p.element == energy_type
    ]
    
    if not basic_pokemon:
        basic_pokemon = [p for p in available_pokemon if p.subtype == Card.Subtype.BASIC]
    
    # Sort by attack damage (highest first)
    def get_max_damage(pokemon):
        if pokemon.attacks:
            return max((a.damage for a in pokemon.attacks), default=0)
        return 0
    
    basic_pokemon.sort(key=get_max_damage, reverse=True)
    
    # Create deck prioritizing high-damage Pokemon
    card_counts = Counter()
    max_copies = 2
    
    for pokemon in basic_pokemon:
        if len(deck) >= deck_size:
            break
        if card_counts[pokemon.id] < max_copies:
            copies = min(max_copies - card_counts[pokemon.id], deck_size - len(deck))
            for _ in range(copies):
                deck.append(deepcopy(pokemon))
                card_counts[pokemon.id] += 1
    
    # Fill remaining
    while len(deck) < deck_size:
        for pokemon in basic_pokemon:
            if len(deck) >= deck_size:
                break
            deck.append(deepcopy(pokemon))
    
    return deck[:deck_size]


def print_game_state(engine: BattleEngine):
    """Print current game state"""
    current = engine._get_current_player()
    opponent = engine._get_opponent()
    
    print("\n" + "="*60)
    print(f"Turn {engine.turn} - {current.name}'s Turn")
    print("="*60)
    
    # Current player
    print(f"\n{current.name}:")
    print(f"  Points: {current.points}/3")
    print(f"  Hand: {len(current.cards_in_hand)} cards")
    print(f"  Deck: {len(current.deck)} cards")
    
    if current.active_pokemon:
        pokemon = current.active_pokemon
        max_hp = pokemon.max_health()
        current_hp = pokemon.current_health()
        print(f"  Active: {pokemon.name} ({current_hp}/{max_hp} HP)")
        if pokemon.status_effects:
            statuses = [s.__class__.__name__ for s in pokemon.status_effects]
            print(f"    Status: {', '.join(statuses)}")
    else:
        print("  Active: None")
    
    bench_count = sum(1 for p in current.bench_pokemons if p is not None)
    print(f"  Bench: {bench_count} Pokemon")
    
    # Opponent
    print(f"\n{opponent.name}:")
    print(f"  Points: {opponent.points}/3")
    if opponent.active_pokemon:
        pokemon = opponent.active_pokemon
        max_hp = pokemon.max_health()
        current_hp = pokemon.current_health()
        print(f"  Active: {pokemon.name} ({current_hp}/{max_hp} HP)")
    else:
        print("  Active: None")
    bench_count = sum(1 for p in opponent.bench_pokemons if p is not None)
    print(f"  Bench: {bench_count} Pokemon")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Play Pokemon TCG Pocket Battle Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Two random AI players
  python3 play_game.py

  # Human vs Random AI
  python3 play_game.py --player1 human

  # Specify deck by name
  python3 play_game.py intermediate_grass_deck --player1 human

  # Two human players with specific decks
  python3 play_game.py intermediate_grass_deck basic_fire_deck --player1 human --player2 human

  # With debug output
  python3 play_game.py --debug

  # Run multiple simulations
  python3 play_game.py --simulations 10
        """
    )
    
    # Add positional arguments for deck names
    parser.add_argument(
        'deck1',
        nargs='?',
        default=None,
        help="Deck name for Player 1 (e.g., 'intermediate_grass_deck', 'basic_fire_deck')"
    )
    parser.add_argument(
        'deck2',
        nargs='?',
        default=None,
        help="Deck name for Player 2 (e.g., 'intermediate_grass_deck', 'basic_fire_deck')"
    )
    
    parser.add_argument(
        "--player1", 
        choices=["human", "random"], 
        default="random",
        help="Player 1 agent type (default: random)"
    )
    parser.add_argument(
        "--player2", 
        choices=["human", "random"], 
        default="random",
        help="Player 2 agent type (default: random)"
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=1,
        help="Number of games to simulate (default: 1)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    parser.add_argument(
        "--energy1",
        choices=["Grass", "Fire", "Water", "Electric", "Lightning", "Psychic", "Rock", "Fighting", "Dark", "Darkness", "Metal", "Normal"],
        default="Grass",
        help="Energy type for Player 1's deck (default: Grass)"
    )
    parser.add_argument(
        "--energy2",
        choices=["Grass", "Fire", "Water", "Electric", "Lightning", "Psychic", "Rock", "Fighting", "Dark", "Darkness", "Metal", "Normal"],
        default="Fire",
        help="Energy type for Player 2's deck (default: Fire)"
    )
    parser.add_argument(
        "--deck1_type",
        choices=["basic", "evolution", "mixed", "aggressive", "grass", "intermediate_grass", "fire"],
        default="basic",
        help="Deck type for Player 1 (default: basic). Options: basic, evolution, mixed, aggressive, grass, intermediate_grass, fire"
    )
    parser.add_argument(
        "--deck2_type",
        choices=["basic", "evolution", "mixed", "aggressive", "grass", "intermediate_grass", "fire"],
        default="basic",
        help="Deck type for Player 2 (default: basic). Options: basic, evolution, mixed, aggressive, grass, intermediate_grass, fire"
    )
    
    args = parser.parse_args()
    
    # Load cards from JSON
    print("Loading cards from JSON...")
    importer = JsonCardImporter()
    try:
        importer.import_from_json()
        print(f"✓ Loaded {len(importer.pokemon)} Pokemon cards")
    except Exception as e:
        print(f"Error loading cards: {e}")
        return 1
    
    # Map energy type strings to enum (matching actual Energy.Type values)
    energy_map = {
        "Grass": Energy.Type.GRASS,
        "Fire": Energy.Type.FIRE,
        "Water": Energy.Type.WATER,
        "Electric": Energy.Type.ELECTRIC,
        "Lightning": Energy.Type.ELECTRIC,  # Alias for Electric
        "Psychic": Energy.Type.PSYCHIC,
        "Rock": Energy.Type.ROCK,
        "Fighting": Energy.Type.ROCK,  # Alias for Rock
        "Dark": Energy.Type.DARK,
        "Darkness": Energy.Type.DARK,  # Alias for Dark
        "Metal": Energy.Type.METAL,
        "Normal": Energy.Type.NORMAL,
    }
    
    energy1_type = energy_map[args.energy1]
    energy2_type = energy_map[args.energy2]
    
    # Check if deck names were provided as positional arguments
    # If so, use them instead of deck_type
    deck1_name = args.deck1
    deck2_name = args.deck2
    
    # Create decks
    print(f"\nCreating decks...")
    
    # Player 1 deck
    if deck1_name and deck1_name.lower() in DECK_MAP:
        # Use named deck from positional argument
        deck_class = DECK_MAP[deck1_name.lower()]
        deck_builder = deck_class()
        deck1 = deck_builder.get_deck()
        energy1_types = [getattr(Energy.Type, et.upper()) for et in deck_builder.get_energy_types()]
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        print(f"  Player 1: Using deck '{deck1_name}' ({deck_builder.get_description()['name']})")
    elif args.deck1_type == "grass":
        # Use pre-built Grass deck
        grass_deck = BasicGrassDeck()
        deck1 = grass_deck.get_deck()
        energy1_types = [getattr(Energy.Type, et.upper()) for et in grass_deck.get_energy_types()]
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        print(f"  Using pre-built Grass deck: {grass_deck.get_description()['name']}")
    elif args.deck1_type == "intermediate_grass":
        # Use intermediate Grass deck
        grass_deck = IntermediateGrassDeck()
        deck1 = grass_deck.get_deck()
        energy1_types = [getattr(Energy.Type, et.upper()) for et in grass_deck.get_energy_types()]
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        print(f"  Using intermediate Grass deck: {grass_deck.get_description()['name']}")
    elif args.deck1_type == "evolution":
        # Try Bulbasaur evolution chain
        deck1 = create_evolution_deck(importer, "Bulbasaur", 20)
        if not deck1:
            print("  Falling back to basic deck")
            deck1 = create_basic_deck(importer, energy1_type)
        energy1_types = None  # Will be determined below
    elif args.deck1_type == "mixed":
        deck1 = create_mixed_type_deck(importer, [energy1_type, Energy.Type.NORMAL], 20)
        if not deck1:
            print("  Falling back to basic deck")
            deck1 = create_basic_deck(importer, energy1_type)
        energy1_types = None  # Will be determined below
    elif args.deck1_type == "aggressive":
        deck1 = create_aggressive_deck(importer, energy1_type, 20)
        if not deck1:
            print("  Falling back to basic deck")
            deck1 = create_basic_deck(importer, energy1_type)
        energy1_types = None  # Will be determined below
    else:
        if deck1_name:
            print(f"  Warning: Unknown deck name '{deck1_name}', falling back to {args.deck1_type} deck")
        deck1 = create_basic_deck(importer, energy1_type)
        energy1_types = None  # Will be determined below
    
    if not deck1:
        return 1
    
    # Determine actual energy types needed for deck1 based on Pokemon in deck
    # (only if not already set by pre-built deck)
    if energy1_types is None:
        deck1_energy_types = set()
        for card in deck1:
            if hasattr(card, 'element'):
                deck1_energy_types.add(card.element)
        # Always include Normal for Colorless costs
        deck1_energy_types.add(Energy.Type.NORMAL)
        # Use the most common type, or fall back to chosen type
        if deck1_energy_types:
            energy1_type = max(deck1_energy_types, key=lambda e: sum(1 for c in deck1 if hasattr(c, 'element') and c.element == e))
            if Energy.Type.NORMAL in deck1_energy_types and len(deck1_energy_types) > 1:
                deck1_energy_types.remove(Energy.Type.NORMAL)
                energy1_type = list(deck1_energy_types)[0] if deck1_energy_types else Energy.Type.NORMAL
            energy1_types = [energy1_type, Energy.Type.NORMAL] if energy1_type != Energy.Type.NORMAL else [Energy.Type.NORMAL]
        else:
            energy1_types = [energy1_type, Energy.Type.NORMAL]
    
    # Player 2 deck
    if deck2_name and deck2_name.lower() in DECK_MAP:
        # Use named deck from positional argument
        deck_class = DECK_MAP[deck2_name.lower()]
        deck_builder = deck_class()
        deck2 = deck_builder.get_deck()
        energy2_types = [getattr(Energy.Type, et.upper()) for et in deck_builder.get_energy_types()]
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        print(f"  Player 2: Using deck '{deck2_name}' ({deck_builder.get_description()['name']})")
    elif args.deck2_type == "grass":
        # Use pre-built Grass deck
        grass_deck = BasicGrassDeck()
        deck2 = grass_deck.get_deck()
        energy2_types = [getattr(Energy.Type, et.upper()) for et in grass_deck.get_energy_types()]
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        print(f"  Using pre-built Grass deck: {grass_deck.get_description()['name']}")
    elif args.deck2_type == "intermediate_grass":
        # Use intermediate Grass deck
        grass_deck = IntermediateGrassDeck()
        deck2 = grass_deck.get_deck()
        energy2_types = [getattr(Energy.Type, et.upper()) for et in grass_deck.get_energy_types()]
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        print(f"  Using intermediate Grass deck: {grass_deck.get_description()['name']}")
    elif args.deck2_type == "fire":
        # Use pre-built Fire deck
        fire_deck = BasicFireDeck()
        deck2 = fire_deck.get_deck()
        energy2_types = [getattr(Energy.Type, et.upper()) for et in fire_deck.get_energy_types()]
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        print(f"  Using pre-built Fire deck: {fire_deck.get_description()['name']}")
    elif args.deck2_type == "evolution":
        # Try Bulbasaur evolution chain
        deck2 = create_evolution_deck(importer, "Bulbasaur", 20)
        if not deck2:
            print("  Falling back to basic deck")
            deck2 = create_basic_deck(importer, energy2_type)
        energy2_types = None  # Will be determined below
    elif args.deck2_type == "mixed":
        deck2 = create_mixed_type_deck(importer, [energy2_type, Energy.Type.NORMAL], 20)
        if not deck2:
            print("  Falling back to basic deck")
            deck2 = create_basic_deck(importer, energy2_type)
        energy2_types = None  # Will be determined below
    elif args.deck2_type == "aggressive":
        deck2 = create_aggressive_deck(importer, energy2_type, 20)
        if not deck2:
            print("  Falling back to basic deck")
            deck2 = create_basic_deck(importer, energy2_type)
        energy2_types = None  # Will be determined below
    else:
        if deck2_name:
            print(f"  Warning: Unknown deck name '{deck2_name}', falling back to {args.deck2_type} deck")
        deck2 = create_basic_deck(importer, energy2_type)
        energy2_types = None  # Will be determined below
    
    if not deck2:
        return 1
    
    # Determine actual energy types needed for deck2 based on Pokemon in deck
    # (only if not already set by pre-built deck)
    if energy2_types is None:
        deck2_energy_types = set()
        for card in deck2:
            if hasattr(card, 'element'):
                deck2_energy_types.add(card.element)
        # Always include Normal for Colorless costs
        deck2_energy_types.add(Energy.Type.NORMAL)
        # Use the most common type, or fall back to chosen type
        if deck2_energy_types:
            energy2_type = max(deck2_energy_types, key=lambda e: sum(1 for c in deck2 if hasattr(c, 'element') and c.element == e))
            if Energy.Type.NORMAL in deck2_energy_types and len(deck2_energy_types) > 1:
                deck2_energy_types.remove(Energy.Type.NORMAL)
                energy2_type = list(deck2_energy_types)[0] if deck2_energy_types else Energy.Type.NORMAL
            energy2_types = [energy2_type, Energy.Type.NORMAL] if energy2_type != Energy.Type.NORMAL else [Energy.Type.NORMAL]
        else:
            energy2_types = [energy2_type, Energy.Type.NORMAL]
    
    print(f"✓ Decks created (20 cards each)")
    print(f"  Player 1 energy types: {[str(e) for e in energy1_types]}")
    print(f"  Player 2 energy types: {[str(e) for e in energy2_types]}\n")
    
    # Create agents
    agent1_class = HumanAgent if args.player1 == "human" else RandomAgent
    agent2_class = HumanAgent if args.player2 == "human" else RandomAgent
    
    # Run simulations
    results = {"Player 1": 0, "Player 2": 0, "Draw": 0}
    
    for sim in range(args.simulations):
        if args.simulations > 1:
            print(f"\n{'='*60}")
            print(f"Simulation {sim + 1}/{args.simulations}")
            print(f"{'='*60}\n")
        
        # Create fresh players for each simulation
        # Use deepcopy to ensure each simulation has independent card instances
        from copy import deepcopy
        player1 = Player("Player 1", deepcopy(deck1), energy1_types, agent=agent1_class)
        player2 = Player("Player 2", deepcopy(deck2), energy2_types, agent=agent2_class)
        
        # Create battle engine
        engine = BattleEngine(player1, player2, debug=args.debug)
        
        # Run battle
        if args.simulations == 1 and (args.player1 == "human" or args.player2 == "human"):
            # Interactive mode - show game state
            print("Starting battle...\n")
            engine._setup_game()
            
            # Display initial board after setup
            current = engine._get_current_player()
            opponent = engine._get_opponent(current)
            board_view = engine.generate_board_view(current, opponent)
            
            # Clear screen for human players
            if args.player1 == "human" or args.player2 == "human":
                import os
                os.system('clear' if os.name != 'nt' else 'cls')
            
            print("\n" + board_view + "\n")
            
            while not engine._is_game_over():
                print_game_state(engine)
                engine._execute_turn()
            
            winner = engine._determine_winner()
        else:
            # Automated mode - just run it
            winner = engine.start_battle()
        
        # Record result
        if winner:
            winner_name = winner.name
            results[winner_name] += 1
            if args.simulations == 1:
                print(f"\n{'='*60}")
                print(f"Winner: {winner_name}!")
                if engine.turn >= GameRules.MAX_TURNS:
                    print(f"(Game reached {GameRules.MAX_TURNS} turn limit)")
                print(f"{'='*60}\n")
        else:
            results["Draw"] += 1
            if args.simulations == 1:
                print(f"\n{'='*60}")
                print("Draw!")
                if engine.turn >= GameRules.MAX_TURNS:
                    print(f"(Game reached {GameRules.MAX_TURNS} turn limit)")
                print(f"{'='*60}\n")
    
    # Print summary
    if args.simulations > 1:
        print(f"\n{'='*60}")
        print("Simulation Results:")
        print(f"{'='*60}")
        print(f"Player 1 wins: {results['Player 1']}")
        print(f"Player 2 wins: {results['Player 2']}")
        print(f"Draws: {results['Draw']}")
        print(f"{'='*60}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

