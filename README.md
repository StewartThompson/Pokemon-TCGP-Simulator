# Pokémon TCG Pocket — Self-Learning Battle Bot

A Pokémon Trading Card Game Pocket simulator with a bot that teaches itself to play by competing against itself millions of times. No human strategy was programmed — it figures out card combos, type matchups, and tempo on its own.

---

## What it does

The bot uses a technique called **AlphaZero-style self-play**: it starts knowing nothing, plays games against itself, and uses the results to get smarter each "generation." After enough generations, it consistently beats a hand-coded rule-based player and holds its own against a brute-force search bot.

```
Random noise → Self-play → Learn from results → Stronger bot → Better self-play → ...
```

Each generation takes about 60 seconds on a MacBook (400 games, then a training step, then an evaluation match).

---

## Current strength

The bot is evaluated by playing 250 games against a **pure Monte Carlo tree search** opponent running 720 simulated lookaheads per move — no learned strategy, just brute-force search. Beating it consistently means the bot has learned something real.

### Training progress (v8, from gen 1 → 111)

```
Win % vs pure MCTS (720 sims)
70% │                                              ▄  ▄▄
    │                                           ▄▄█▄▄██
65% │                                        ▄▄█████████
    │                              ▄      ▄▄█████████████
60% │                          ▄▄▄█▄▄▄▄▄██████████████████
    │                    ▄▄▄▄▄██████████████████████████████▄
55% │▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄███████████████████████████████████████
50% │─────────────────────────────────────────────────────────
    └──────────────────────────────────────────────────────────
    Gen 1                  Gen 50                    Gen 111

  Best: 66.4% (gen 105)   v7 all-time best: 68.1% (gen 446)
```

| Metric | Value |
|---|---|
| Best win rate vs pure MCTS 720 | **66.4%** (gen 105) |
| Gens trained (v8) | 111 |
| Previous best (v7, 446 gens) | 68.1% |
| Speed | ~9–10 games/sec on Apple Silicon |
| Model size | ~178K parameters |

v8 matched v7's level in roughly **¼ the training time** due to warm-started weights and 9 new strategic features (type weaknesses, bench damage, next-turn KO threats).

---

## How to run

### Play against the bot

```bash
cd ptcgp
cargo build --release

PTCGP_CHECKPOINTS=../checkpoints_v8 \
  ./target/release/ptcgp play --deck charizard --opponent mcts:latest
```

Deck options: `charizard`, `pikachu`, `mewtwo`, `rampardos`

### Run training yourself

```bash
cd ptcgp
./target/release/ptcgp-train \
  --checkpoint-dir ../checkpoints_v8 \
  --games-per-gen 400 \
  --mcts-sims 720 \
  --eval-games 250 \
  --eval-opponent mcts-raw:720 \
  --generations 10 \
  --resume \
  --lr 5e-5 --lr-end 2e-5 \
  --train-steps 400 \
  --policy-target-tau 0.25
```

### Evaluate two bots head to head

```bash
PTCGP_CHECKPOINTS=../checkpoints_v8 \
  ./target/release/ptcgp eval \
  --a mcts:gen_105 --b mcts-raw:720 \
  --games 500 --paired
```

---

## Resume from a saved checkpoint

Pre-trained weights are in `saved_checkpoints/`. See [`saved_checkpoints/README.md`](saved_checkpoints/README.md) for instructions to resume training on a new machine.

---

## How it works (brief)

- **MCTS + neural net:** The bot runs a tree search for each move, guided by a small neural network (~178K params) that predicts who's likely to win from any position.
- **Self-play loop:** Each generation: play 400 games → store results → train the net → evaluate strength → repeat.
- **Hidden information:** Opponent's hand is unknown. The bot handles this by sampling several plausible opponent hands and averaging over them (called PIMC).
- **All Rust, runs on-device.** Training uses the Metal GPU for the net, CPU threads for the game simulation. No Python, no cloud.

---

## Project layout

```
ptcgp/src/
  ml/          — neural net, MCTS, self-play, training, checkpoints
  engine/      — game rules and state machine
  agents/      — Random, Heuristic, Human, MctsAgent
  bin/
    ptcgp.rs          — play / eval CLI
    train_mcts.rs     — training loop

saved_checkpoints/   — best weights for v7 and v8 (committed to git)
checkpoints_v8/      — full training checkpoints (local only, not in git)
```
