# Saved Checkpoints

These are the best trained bot weights. No replay buffer is included (too large for git) — training will rebuild it from scratch within ~5 generations.

| Checkpoint | Eval vs pure MCTS (720 sims) | Notes |
|---|---|---|
| `v7_gen446` | 68.1% | 331 features, trained for 446 gens |
| `v8_gen105` | 66.4% | 340 features (+9 strategic) — best eval score |
| `v8_gen111` | 65.2% | 340 features — **latest, use this to resume training** |

## Resuming training on a new machine

```bash
# 1. Clone the repo
git clone https://github.com/StewartThompson/Pokemon-TCGP-Simulator.git
cd Pokemon-TCGP-Simulator

# 2. Copy the latest checkpoint into a checkpoints dir
mkdir -p checkpoints_v8/gen_111
cp saved_checkpoints/v8_gen111/weights.safetensors checkpoints_v8/gen_111/
cp saved_checkpoints/v8_gen111/meta.json checkpoints_v8/gen_111/

# 3. Build
cd ptcgp && cargo build --release

# 4. Resume training (replay buffer will be empty and rebuild over first ~5 gens)
./target/release/ptcgp-train \
  --checkpoint-dir ../checkpoints_v8 \
  --games-per-gen 400 \
  --mcts-sims 720 \
  --eval-games 250 \
  --eval-opponent mcts-raw:720 \
  --generations 10 \
  --resume \
  --lr 5e-5 \
  --lr-end 2e-5 \
  --train-steps 400 \
  --policy-target-tau 0.25
```

## Playing against the bot

```bash
cd ptcgp
PTCGP_CHECKPOINTS=../checkpoints_v8 \
  ./target/release/ptcgp play --deck charizard --opponent mcts:latest
```
