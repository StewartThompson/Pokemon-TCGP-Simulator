# Pokemon TCG Pocket Battle Simulator

A complete Python implementation of the Pokemon TCG Pocket battle system, featuring automated battle simulations, human play, and AI agent support.

## Features

- ✅ **Complete Battle Engine**: Full turn-based gameplay with all phases (Draw, Main, Attack, End)
- ✅ **Card System**: JSON-powered card database with support for Pokemon, Items, Supporters, and Tools
- ✅ **Effect System**: Comprehensive effect parser supporting healing, energy, search, coin flips, and more
- ✅ **Evolution System**: Complete evolution mechanics (Basic → Stage 1 → Stage 2)
- ✅ **Status Effects**: Asleep, Poisoned, Burned, Paralyzed, Confused
- ✅ **Energy Zone**: Automatic energy generation system
- ✅ **Multiple Agents**: Random AI, Human player, and extensible bot framework
- ✅ **Pre-built Decks**: Ready-to-use deck configurations
- ✅ **Comprehensive Testing**: 40+ tests covering all game mechanics

## Quick Start

### Play from Terminal

```bash
# Quick simulation (two random AI players)
python3 play_game.py

# Play as human (interactive)
python3 play_game.py --player1 human

# Watch with debug output
python3 play_game.py --debug

# Use pre-built decks
python3 play_game.py --deck1_type grass --deck2_type fire

# Run multiple simulations
python3 play_game.py --simulations 10
```

### Command Line Options

- `--player1 {human,random}` - Player 1 type (default: random)
- `--player2 {human,random}` - Player 2 type (default: random)
- `--simulations N` - Number of games to simulate (default: 1)
- `--debug` - Show detailed game actions and board state
- `--deck1_type {grass,fire,intermediate_grass}` - Pre-built deck for Player 1
- `--deck2_type {grass,fire,intermediate_grass}` - Pre-built deck for Player 2
- `deck1 deck2` - Specify deck names as positional arguments

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd PokemonTCGP-BattleSimulator
   ```

2. **Python 3.7+ required** (no external dependencies needed for basic functionality)

3. **Run the game:**
   ```bash
   python3 play_game.py
   ```

## Project Structure

```
PokemonTCGP-BattleSimulator/
├── v3/                          # Current version (v3)
│   ├── models/
│   │   ├── cards/               # Card models (Pokemon, Trainer, etc.)
│   │   ├── agents/              # AI agents (Random, Human, Bot)
│   │   └── match/               # Battle engine and game logic
│   │       ├── actions/         # Game actions (Attack, Evolve, etc.)
│   │       ├── effects/          # Card effects (Heal, Energy, etc.)
│   │       └── status_effects/   # Status conditions
│   ├── importers/               # Card data loaders
│   ├── assets/                  # JSON card database
│   └── decks/                   # Pre-built deck configurations
├── play_game.py                 # Main entry point
└── tests/                       # Comprehensive test suite
```

## Game Rules Summary

### Deck Construction
- **Deck Size**: Exactly 20 cards
- **Card Limits**: Maximum 2 copies of the same card
- **Basic Pokemon**: Deck must contain at least 1 Basic Pokemon

### Turn Structure
1. **Draw Phase**: Draw 1 card
2. **Main Phase**: Play Pokemon, attach energy, use trainers, evolve, retreat
3. **Attack Phase**: Attack with active Pokemon
4. **End Phase**: Apply status effects, reset flags, generate energy

### Energy System
- **Automatic Generation**: 1 energy per turn from Energy Zone
- **Attachment Limit**: 1 energy per turn
- **Energy Persistence**: Energy is NOT discarded after attacks
- **Colorless Energy**: Can be satisfied by any energy type

### Evolution
- **Requirement**: Pokemon must be in play 1 turn before evolving
- **Limit**: 1 evolution per Pokemon per turn (multiple Pokemon can evolve)
- **Restriction**: Neither player can evolve on Turn 1

### Victory Conditions
- **Prize Victory**: Collect 3 prize points (by knocking out Pokemon)
- **No Active Pokemon**: Opponent has no Pokemon to promote
- **Turn Limit**: Game ends in draw after 100 turns

For complete rules, see the [Game Rules](#game-rules) section below.

## Usage Examples

### Basic Simulation

```python
from v3.models.match.match import Match
from v3.decks.basic_grass_deck import BasicGrassDeck
from v3.models.agents.random_agent import RandomAgent

# Create decks
deck1 = BasicGrassDeck().get_deck()
deck2 = BasicGrassDeck().get_deck()

# Create players
player1 = Player("Player 1", deck1, ["Grass"], RandomAgent)
player2 = Player("Player 2", deck2, ["Grass"], RandomAgent)

# Run match
match = Match(player1, player2)
winner = match.start_battle()
print(f"Winner: {winner.name}")
```

### Human Play

```python
from v3.models.agents.human_agent import HumanAgent

player1 = Player("You", deck1, ["Grass"], HumanAgent)
player2 = Player("AI", deck2, ["Grass"], RandomAgent)

match = Match(player1, player2, debug=True)
match.start_battle()
```

## Card Database

Cards are stored in JSON format in `v3/assets/`. The current implementation includes cards from the Genetic Apex (A1) set.

### Adding New Cards

1. Edit `v3/assets/a1-genetic-apex.json` (or create a new JSON file)
2. Add card data following the existing format
3. Cards are automatically loaded when the game starts

### Card Format Example

```json
{
  "id": "a1-001",
  "name": "Bulbasaur",
  "element": "Grass",
  "type": "Pokemon",
  "subtype": "Basic",
  "health": 70,
  "attacks": [
    {
      "name": "Vine Whip",
      "damage": "40",
      "cost": ["Grass", "Colorless"],
      "effect": "Optional effect text"
    }
  ],
  "retreatCost": 1,
  "weakness": "Fire"
}
```

## Effect System

The simulator supports a comprehensive effect system that parses effect text and executes game actions:

- **Healing**: Heal damage from Pokemon (single or all)
- **Energy**: Attach/discard energy from Energy Zone
- **Search**: Search deck for Pokemon and add to hand
- **Draw**: Draw cards from deck
- **Coin Flips**: Conditional effects based on coin flips
- **Switch**: Switch Pokemon between active and bench
- **Status Effects**: Apply status conditions
- **Evolution**: Rare Candy for Basic → Stage 2 evolution

All effects from `a1-genetic-apex.json` are fully implemented and tested.

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python3 tests/run_all_tests.py

# Run specific test
python3 tests/test_all_effects_integration.py
```

**Test Coverage:**
- ✅ 40+ unit and integration tests
- ✅ All core game mechanics tested
- ✅ Effect system fully tested
- ✅ Edge cases covered

## Game Rules

### Setup Phase
1. Each player draws 5 cards (redraw until at least 1 Basic Pokemon)
2. Players must play at least 1 Basic Pokemon to active spot
3. Players can play any number of Basic Pokemon to bench (up to 3)
4. Coin toss determines first player

### First Turn Restrictions
- **First Player**: Cannot attach energy or evolve on first turn
- **Second Player**: Can perform all normal actions (except evolution - neither player can evolve on Turn 1)

### Main Phase Actions
- **Play Pokemon**: 1 Basic Pokemon per turn (unlimited during setup)
- **Evolve**: 1 evolution per Pokemon per turn
- **Attach Energy**: 1 energy per turn from Energy Zone
- **Trainer Cards**: 
  - Items: Unlimited per turn
  - Supporters: 1 per turn
  - Tools: Unlimited per turn (attach to Pokemon)
- **Use Abilities**: 1 ability per Pokemon per turn
- **Retreat**: Once per turn (discard energy equal to retreat cost)

### Attacks
- **Energy Requirements**: Must have enough energy to pay attack cost
- **Colorless Energy**: Can be paid with any energy type
- **Damage Calculation**: Base damage + weakness bonus (+20) if applicable
- **Weakness Rule**: Only applies if base damage > 0
- **Energy Not Discarded**: Energy remains attached after attacking

### Status Effects
- **Asleep**: Cannot attack. Coin flip at end of turn to wake up (50% chance)
- **Poisoned**: Takes 10 damage at end of each turn
- **Burned**: Coin flip at end of turn: Heads = 20 damage, Tails = remove status
- **Paralyzed**: Cannot attack or retreat. Removed at end of turn
- **Confused**: Coin flip when attacking: Heads = attack normally, Tails = attack self for 30 damage

Status effects are applied at the end of each turn and removed when a Pokemon evolves.

### Evolution
- **Timing**: Pokemon must be in play 1 turn before evolving
- **Chain**: Must follow evolution chain (Basic → Stage 1 → Stage 2)
- **Rare Candy**: Allows Basic → Stage 2 evolution (bypassing Stage 1)
- **Status Removal**: All status effects removed when Pokemon evolves

### Energy Zone
- **Generation**: 1 energy automatically generated per turn
- **Types**: Player specifies which energy types are available (typically matching deck Pokemon types)
- **Attachment Only**: Energy can only be attached from Energy Zone
- **No Hand Size Limit**: Players can have any number of cards in hand

### Victory Conditions
1. **Prize Victory**: Collect 3 prize points (1 point per regular Pokemon KO, 2 points per EX Pokemon KO)
2. **No Active Pokemon**: Opponent has no active Pokemon and no bench to promote
3. **Turn Limit**: Game ends in draw after 100 turns

## Extending the Simulator

### Creating Custom Agents

```python
from v3.models.agents.agent import Agent

class MyAgent(Agent):
    def __init__(self, player):
        super().__init__(player)
        self.is_human = False
    
    def get_action(self, state, valid_action_indices):
        # Your AI logic here
        return chosen_index
```

### Adding New Effects

Effects are automatically parsed from text. To add new effect types:

1. Create a new effect class in `v3/models/match/effects/`
2. Implement `from_text()` class method for parsing
3. Implement `execute()` method for execution
4. Add to `EffectParser.EFFECT_CLASSES`

## Contributing

Contributions are welcome! Areas that could use work:
- Advanced AI agents (RL, MCTS, etc.)
- Additional card sets and expansions
- Performance optimizations
- GUI for interactive play
- Network play functionality

## Acknowledgments

Built as a complete implementation of the Pokemon TCG Pocket battle system for simulation, testing, and AI development.
