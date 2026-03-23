# Pokemon TCG Pocket Battle Simulator — Full Rewrite Design Spec

**Date:** 2026-03-23
**Status:** Approved

## Overview

Complete rewrite of the Pokemon TCG Pocket battle simulator with three goals:
1. **Play from terminal** — rich TUI for human vs AI games
2. **Simulate games** — batch-run thousands of games for deck analysis
3. **ML-powered deck optimization** — RL agents learn to play, genetic algorithms find optimal decks

## Architecture

ML-first design: the game engine is a pure state machine that produces observations and accepts actions. Everything else (UI, simulation, training) is built on top.

### Core Engine (`ptcgp/engine/`)

**GameState** — immutable dataclass representing the full game state:
- Per player: active pokemon slot, 3 bench slots, hand, deck, discard pile, points (0-3)
- Per pokemon slot: card_id, current_hp, attached_energy (dict), status_effects, turns_in_play, tool
- Turn state: turn_number, current_player, energy_zone type, action flags
- Game phase: SETUP, DRAW, MAIN, ATTACK, BETWEEN_TURNS, GAME_OVER

**Pure function game transitions:**
- `get_legal_actions(state) -> list[Action]`
- `apply_action(state, action) -> GameState`
- `check_winner(state) -> int | None`
- `resolve_between_turns(state) -> GameState`

**Action space (fixed-size for RL):**
- 0-1: Attack (index 0 or 1)
- 2-4: Retreat to bench slot 0/1/2
- 5-14: Play card from hand position 0-9
- 15-18: Attach energy to active/bench 0/1/2
- 19-22: Use ability on active/bench 0/1/2
- 23: End turn
- Multi-step actions use sub-state (target selection)

### PTCGP Rules (encoded correctly)

- Deck: 20 cards, max 2 copies per name, ≥1 Basic Pokemon
- Bench: 3 slots
- Hand limit: 10 cards (skip draw at 10)
- Energy: 1 per turn from Energy Zone (up to 3 selected types, random if multiple)
- First player turn 1: no energy, no attack, no evolution
- Win: 3 points (1 per KO, 2 per EX KO) or opponent has no Pokemon left
- No deck-out loss (skip draw)
- Weakness: +20 damage, no resistance
- Guaranteed Basic in opening hand
- Status effects: Poison (10), Burn (20 + flip), Paralyze (1 turn), Sleep (flip), Confuse (flip, 30 self)
- Paralyzed/Asleep/Confused mutually exclusive; Poison/Burn stack with anything
- Evolution: must wait 1 turn, can't skip stages (except Rare Candy), clears status
- Retreat: once per turn, discard energy = retreat cost, clears status
- Supporters: 1 per turn
- Items: unlimited per turn
- Tools: 1 per Pokemon, unlimited attachments per turn

### Card Database (`ptcgp/data/`)

JSON files per set. Schema:
```json
{
  "id": "a1-001",
  "name": "Bulbasaur",
  "type": "pokemon",
  "stage": "basic",
  "element": "grass",
  "hp": 70,
  "weakness": "fire",
  "retreat_cost": 1,
  "is_ex": false,
  "evolves_from": null,
  "attacks": [{"name": "Vine Whip", "damage": 40, "cost": {"grass": 1, "colorless": 1}, "effect": null}],
  "ability": null
}
```

### Agents (`ptcgp/agents/`)

- **RandomAgent** — uniform random from legal actions
- **HeuristicAgent** — rule-based priorities (attack if possible, evolve, attach energy, etc.)
- **HumanAgent** — rich terminal UI using `rich` library
- **RLAgent** — PPO via stable-baselines3, loads trained model

### Gymnasium Environment (`ptcgp/training/env.py`)

Standard Gym interface:
- Observation: ~400-float vector (pokemon slots, hand info, game state)
- Action: discrete(24) with action masking
- Reward: +1 win, -1 loss, +0.33 per KO, -0.33 per own KO
- Hidden information: opponent's hand size only (not contents)

### Training Pipeline (`ptcgp/training/`)

1. **PPO training** with self-play and curriculum learning
2. **Deck optimizer** — genetic algorithm (population 100, fitness = win rate)
3. **Co-evolution** — train agents → evaluate decks → evolve decks → retrain

### Simulation (`ptcgp/simulation/`)

Batch game runner with multiprocessing. Produces win rates, matchup charts, card usage stats.

### CLI (`ptcgp/cli.py`)

```
python -m ptcgp play              # Human vs AI
python -m ptcgp simulate          # Run simulations
python -m ptcgp train             # Train RL agent
python -m ptcgp optimize-deck     # Run deck optimizer
```

## Dependencies

- gymnasium, stable-baselines3, torch — ML
- rich, click — UI/CLI
- numpy — numerics
- pytest — testing

## Build Order

1. Types/enums → Card database → Game state → Actions → Effects
2. Engine tests
3. Random + Heuristic agents
4. Terminal UI (human agent)
5. Gymnasium env → PPO training
6. Simulation framework
7. Deck optimizer
8. Integration tests
