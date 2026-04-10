# Phase 4 Group E — Bot Agents

## Summary

Implemented the agent layer for the battle simulator, providing an abstract Agent base class plus two concrete implementations: RandomAgent and HeuristicAgent. 15 new tests were added, bringing the total from 254 to 269 passing.

## New Files

| File | Description |
|------|-------------|
| `ptcgp/agents/base.py` | `Agent` ABC — defines `choose_action`, `choose_promotion`, `on_game_start`, `on_game_end` |
| `ptcgp/agents/random_agent.py` | `RandomAgent` — uniform random selection with optional seeding |
| `ptcgp/agents/heuristic.py` | `HeuristicAgent` — priority-scored hand-crafted heuristics |
| `tests/agents/test_random.py` | 15 tests covering both agents |

## Modified Files

| File | Change |
|------|--------|
| `ptcgp/agents/__init__.py` | Exports `Agent`, `RandomAgent`, `HeuristicAgent` |

## Agent Design

### Agent (ABC)
- `choose_action(state, legal_actions) -> Action` — abstract, must be implemented
- `choose_promotion(state, player_index, legal_promotions) -> Action` — default random
- `on_game_start` / `on_game_end` — optional lifecycle hooks (no-op defaults)

### RandomAgent
- Uses `random.Random` with optional seed for reproducibility
- All choices are uniform random from the provided legal action list

### HeuristicAgent
Scores each legal action by priority (higher = preferred):

| Priority | Action |
|----------|--------|
| 100 | ATTACK that KOs the opponent |
| 50 + damage | ATTACK (highest damage preferred) |
| 37–39 | EVOLVE (Stage 2 active > Stage 2 bench > Stage 1) |
| 30 | PLAY_CARD (Basic Pokemon to bench) |
| 28 | ATTACH_ENERGY to active |
| 25 | PLAY_CARD (Item/Supporter) |
| 24 | ATTACH_ENERGY to bench (prefers high attack cost) |
| 22 | PLAY_CARD (Tool) |
| 20 | USE_ABILITY |
| 15 | RETREAT (when active has bad status and bench has more HP) |
| 10 | RETREAT (normal) |
| 5 | RETREAT (low priority) |
| 0 | END_TURN |

Tie-breaking uses `self._rng.random()` so behavior is deterministic when seeded.

`choose_promotion` picks the bench slot with the highest current HP.

## Test Coverage

| Test | What it checks |
|------|----------------|
| `test_random_agent_chooses_from_legal` | Always returns from legal list |
| `test_random_agent_seeded` | Same seed → same sequence |
| `test_random_agent_never_returns_none` | Never returns None |
| `test_random_agent_single_action` | Single-item list always returns that item |
| `test_random_agent_choose_promotion` | Promotion from legal list |
| `test_random_agent_on_game_start_end_noop` | Lifecycle hooks don't raise |
| `test_heuristic_agent_chooses_from_legal` | Always returns from legal list |
| `test_heuristic_prefers_attack_over_end_turn` | Prefers ATTACK |
| `test_heuristic_prefers_ko_attack` | Prefers KO-dealing attack |
| `test_heuristic_never_returns_none` | Never returns None |
| `test_heuristic_end_turn_only` | Handles single END_TURN |
| `test_heuristic_prefers_evolve_over_end_turn` | Prefers EVOLVE |
| `test_heuristic_prefers_bench_fill_over_end_turn` | Prefers PLAY_CARD (basic) |
| `test_heuristic_choose_promotion_picks_highest_hp` | Promotes highest-HP bench Pokemon |
| `test_heuristic_on_game_start_end_noop` | Lifecycle hooks don't raise |

## What Was NOT Implemented

- `ptcgp/agents/human.py` — reserved for Phase 5 (UI layer)
- Runner/game loop integration — reserved for Phase 4 Group F
