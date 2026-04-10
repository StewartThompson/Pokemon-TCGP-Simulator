# Architecture Overview

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      CLI (ptcgp.cli)                    │
│              click commands: play, simulate             │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                 Runner (ptcgp.runner)                   │
│         game_runner.py · batch_runner.py                │
└────┬─────────────────┬──────────────────┬───────────────┘
     │                 │                  │
┌────▼────┐    ┌───────▼──────┐   ┌───────▼───────┐
│ Agents  │    │   Terminal   │   │   Decks       │
│ base    │    │   UI (rich)  │   │   validator   │
│ random  │    │   renderer   │   │   sample_decks│
│ heurist.│    │   prompts    │   └───────────────┘
│ human   │    └──────────────┘
└────┬────┘
     │
┌────▼────────────────────────────────────────────────────┐
│                  Engine (ptcgp.engine)                  │
│                                                         │
│  GameState ──► get_legal_actions() ──► list[Action]     │
│       │                                                 │
│       └──► apply_action(state, action) ──► GameState    │
│                                                         │
│  Modules: setup · turn · play_card · energy · evolve    │
│           retreat · attack · abilities · status         │
│           checkup · ko · legal_actions · mutations      │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│               Effects (ptcgp.effects)                   │
│   registry · parser · heal · draw · energy_effects      │
│   status_effects · movement · coin_flip · tool_effects  │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                Cards (ptcgp.cards)                      │
│     types · card · attack · loader · database           │
└─────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. Pure State Machine Engine
The engine is completely side-effect-free:
```python
apply_action(state: GameState, action: Action) -> GameState
get_legal_actions(state: GameState) -> list[Action]
check_winner(state: GameState) -> int | None
```
`GameState` is a dataclass with `copy()` helpers. This enables MCTS search and RL rollouts.

### 2. Energy Type System
- `Element` enum: 8 real types (Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness, Metal)
- `CostSymbol` enum: same 8 + COLORLESS (used only in `Attack.cost`)
- Colorless is **only** a cost specifier — it never appears in the Energy Zone or on a Pokemon
- `PokemonSlot.attached_energy: dict[Element, int]` — can never contain Colorless

### 3. Effect Handler Registry
Card effects are parsed from JSON effect text into Effect tokens, dispatched via:
```python
@register_effect("heal_self")
def heal_self(ctx: EffectContext, amount: int) -> GameState: ...
```
Cards with unimplemented effects are blocked from deck building by the validator.

### 4. Typed Action Dataclass
```python
@dataclass(frozen=True)
class Action:
    kind: ActionKind
    hand_index: int | None = None
    target: SlotRef | None = None
    attack_index: int | None = None
    discard_energy: tuple[Element, ...] | None = None
```

### 5. Seeded RNG
All randomness (coin flips, energy discard, shuffle) flows through `state.rng: random.Random`.
Seed the RNG at game start for reproducible games.

### 6. ML Separation
`ml/encoder.py` is the single conversion point: `GameState → np.ndarray`, `Action ↔ int`.
The engine is completely unaware of ML — it only speaks GameState and Action.

## Data Flow: A Single Turn

```
1. start_turn(state) → draws card, generates energy
2. agent.choose_action(state, get_legal_actions(state)) → Action
3. apply_action(state, action) → new GameState
   └─ (repeat 2-3 until ActionKind.END_TURN or ATTACK)
4. resolve_between_turns(state) → apply status damage, cure effects
5. next player's turn begins
```

## File Size Targets
- Most files: ≤ 200 lines
- None over 300 lines
- Engine modules stay focused on a single responsibility
