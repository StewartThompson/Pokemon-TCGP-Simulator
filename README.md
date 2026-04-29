# Pokémon TCG Pocket Battle Simulator

A full Pokémon TCG Pocket simulator with a self-learning AI bot. The bot trains itself by playing millions of games and gets progressively stronger — no human strategy was hardcoded.

---

## Requirements

- Rust (stable) — [install](https://rustup.rs)
- macOS with Apple Silicon recommended (uses Metal GPU for training)

```bash
git clone https://github.com/StewartThompson/Pokemon-TCGP-Simulator.git
cd Pokemon-TCGP-Simulator/ptcgp
cargo build --release
```

---

## Play against the bot

```bash
# From the ptcgp/ directory:
PTCGP_CHECKPOINTS=../checkpoints_v8 \
  ./target/release/ptcgp play --deck charizard --opponent mcts:latest
```

Available decks: `charizard`, `pikachu`, `mewtwo`, `rampardos`

To play against the pure rule-based bot instead:
```bash
./target/release/ptcgp play --deck charizard --opponent heuristic
```

---

## Resume training from a saved checkpoint

Weights are committed in `saved_checkpoints/`. Copy the latest one and continue:

```bash
mkdir -p checkpoints_v8/gen_111
cp saved_checkpoints/v8_gen111/weights.safetensors checkpoints_v8/gen_111/
cp saved_checkpoints/v8_gen111/meta.json checkpoints_v8/gen_111/

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

Logs are written to `logs/training.log` automatically.

---

## Start training from scratch

```bash
./target/release/ptcgp-train \
  --checkpoint-dir ../checkpoints_new \
  --games-per-gen 400 \
  --mcts-sims 480 \
  --generations 50
```

---

## Evaluate two bots head-to-head

```bash
PTCGP_CHECKPOINTS=../checkpoints_v8 \
  ./target/release/ptcgp eval \
  --a mcts:gen_105 --b mcts-raw:720 \
  --games 500 --paired
```

---

## Bot strength

The bot is evaluated against a pure Monte Carlo tree search opponent using 720 simulated lookaheads per move.

| Checkpoint | Win rate vs MCTS-720 | Gens trained |
|---|---|---|
| v7 gen_446 | 68.1% | 446 |
| **v8 gen_105** (best) | **66.4%** | 105 |
| v8 gen_111 (latest) | 65.2% | 111 |

v8 reached comparable strength in ~¼ the training time due to warm-started weights and improved strategic features.

---

## Project layout

```
ptcgp/
  src/
    engine/       Game rules and state machine
    agents/       Random, Heuristic, Human, MctsAgent
    ml/           Neural net, MCTS, self-play, training, checkpoints
    bin/
      ptcgp.rs          play / eval CLI
      train_mcts.rs     training loop

saved_checkpoints/  Best weights (committed to git, ~640KB each)
assets/cards/       Card data (JSON)
logs/               Training logs
docs/               Architecture notes
RULES.md            Complete game rules reference
```

---

## How the bot works

The bot uses **AlphaZero-style self-play**:

1. **Play** — run Monte Carlo tree search (MCTS) guided by a small neural net (~178K params) that predicts win probability from any board state
2. **Learn** — after each game, train the net on the outcomes
3. **Repeat** — each generation the bot plays stronger opponents (itself from the previous generation)

Hidden information (opponent's hand) is handled by sampling multiple plausible opponent hands and averaging over them.

Everything runs in Rust on-device. No Python, no cloud.
