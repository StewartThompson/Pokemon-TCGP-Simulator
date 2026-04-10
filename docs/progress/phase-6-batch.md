# Phase 6: Batch Simulation

## Summary

Phase 6 adds parallel batch simulation, allowing multiple bot-vs-bot games to be
run concurrently using Python's `multiprocessing` module, with aggregated
statistics returned as a `BatchResult` dataclass.

## Files Created / Modified

| File | Change |
|------|--------|
| `ptcgp/runner/batch_runner.py` | New — core batch runner |
| `tests/runner/test_batch_runner.py` | New — 8 tests |
| `ptcgp/cli.py` | Enhanced `simulate` command |

## New Public API

### `ptcgp/runner/batch_runner.py`

**`BatchResult`** dataclass:
- `total_games`, `wins` (list[int]), `ties`, `errors`
- `.win_rate` property → `(p1_rate, p2_rate)` as 0.0–1.0 fractions
- `.tie_rate` property → fraction of completed games ending in a tie

**`run_batch(...)`** — low-level parallel runner:
- Accepts agent factories (callables), deck card IDs, energy types
- Each game gets `seed = base_seed + game_index` for reproducibility
- Agents that accept a `seed` keyword argument are seeded per-game to ensure
  fully reproducible results across repeated calls with the same `base_seed`
- `n_workers=None` defaults to `cpu_count()`

**`run_batch_simple(...)`** — high-level convenience wrapper:
- Accepts named decks (`"grass"`, `"fire"`) and agent types (`"random"`, `"heuristic"`)
- `n_workers=1` default makes it safe to call from pytest (avoids forking issues)

### Enhanced `simulate` CLI command

```
ptcgp simulate --games 100 --deck1 grass --deck2 fire \
               --agent1 heuristic --agent2 random \
               --seed 0 --workers 4
```

New options: `--seed` (base seed, default 0) and `--workers` (parallelism,
default auto / CPU count). Now backed by `run_batch_simple` internally.

## Design Decisions

- **Picklable factories**: Worker processes receive factory callables (class
  objects) rather than agent instances, satisfying Python's `spawn`-based
  multiprocessing on macOS/Windows.
- **Per-game agent seeding**: `_run_single_game` inspects the factory signature
  and passes `seed=game_seed` if supported. This makes `RandomAgent` results
  deterministic across batch runs with the same `base_seed`.
- **`imap_unordered`**: Used for efficient streaming of results as games
  complete, regardless of order.
- **Error isolation**: Any exception in a worker returns `"error"` rather than
  crashing the whole batch. Errors are counted in `BatchResult.errors`.

## Test Results

```
tests/runner/test_batch_runner.py   8 passed
tests/ (full suite)               285 passed
```

Previous passing count: 277. Phase 6 adds 8 new tests.
