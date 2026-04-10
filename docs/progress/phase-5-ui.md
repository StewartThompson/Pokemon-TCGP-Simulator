# Phase 5: Terminal UI + Human Agent + CLI

## Status: Complete

All 277 prior tests continue to pass. Five new files were created.

---

## Files Created

### `ptcgp/ui/theme.py`
Defines constants for terminal rendering:
- `ELEMENT_COLORS` — maps `Element` to rich color name
- `ELEMENT_SYMBOLS` — maps `Element` to emoji symbol (🌿🔥💧⚡🔮👊🌑⚙️)
- `STATUS_SYMBOLS` — maps status effect name strings to display labels
- `element_str(element)` — helper returning the emoji for an element

### `ptcgp/ui/renderer.py`
Read-only renderer using the `rich` library:
- `render_state(state, human_player)` — clears the terminal and draws the full board
- Opponent panel at top (hand contents hidden), player panel at bottom (hand shown)
- Displays active Pokemon, HP, attacks with energy cost symbols, bench slots, and available energy
- Status effects, EX tags, and per-turn energy availability are all surfaced
- Never mutates `GameState`

### `ptcgp/ui/prompts.py`
Interactive action selection:
- `choose_action_prompt(state, legal_actions, human_player)` — numbered menu with descriptive labels; defaults to last option (End Turn) on Enter
- `_describe_action(state, action, human_player)` — human-readable label for every `ActionKind`
- `choose_promotion_prompt(state, player_index, legal_promotions)` — shown when the active Pokemon is KO'd; lists bench candidates with HP

### `ptcgp/agents/human.py`
`HumanAgent(Agent)` implementation:
- `on_game_start` — announces player number
- `choose_action` — calls `render_state` then `choose_action_prompt`
- `choose_promotion` — calls `render_state` then `choose_promotion_prompt`

### `ptcgp/cli.py`
`click` CLI with two subcommands, registered as `ptcgp` entry point:

**`ptcgp play`**
- Options: `--deck`, `--opponent` (grass/fire), `--seed`
- Runs `HumanAgent` vs `HeuristicAgent`
- Renders final board and prints WIN/LOSE/DRAW

**`ptcgp simulate`**
- Options: `--games`, `--deck1`, `--deck2`, `--agent1`, `--agent2` (random/heuristic)
- Runs N bot-vs-bot games with a `rich` progress bar
- Prints win/loss/tie counts and percentages

---

## Verification

```
277 passed in 1.71s
```

```
ptcgp simulate --games 5
# Simulating 5 games... 100%
# Results after 5 games:
#   Player 1 (grass/random): 1 wins (20.0%)
#   Player 2 (fire/random): 2 wins (40.0%)
#   Ties: 2 (40.0%)
```

Renderer output (seed=42, grass vs fire, player 0 perspective):
```
─────────────────────── Pokemon TCG Pocket ────────────────────────
╭──────────────────────────── OPPONENT ────────────────────────────╮
│ Points: 0/3  |  Deck: 15  |  Hand: 3                             │
│ ACTIVE: Weedle 50/50 🌿                                          │
│   ATK1: Sting (20) 🌿                                            │
│ BENCH:  [Charmander 60/60🔥]  ---  ---                           │
╰──────────────────────────────────────────────────────────────────╯
                     >>> OPPONENT'S TURN <<<
╭──────────────────────────────── YOU ─────────────────────────────╮
│ Points: 0/3  |  Deck: 15  |  Hand: 4                             │
│ ACTIVE: Caterpie 50/50 🌿                                        │
│   ATK1: Find a Friend (0) ⚪                                     │
│ BENCH:  ---  ---  ---                                            │
│ HAND:   Ivysaur, Venusaur ex, Butterfree, Potion                 │
╰──────────────────────────────────────────────────────────────────╯
```
