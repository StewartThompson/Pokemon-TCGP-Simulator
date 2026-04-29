#!/usr/bin/env python3
"""
Warm-start v8 from v7 gen_446 weights.

v7: FEATURE_DIM=331, HIDDEN_DIM=256
v8: FEATURE_DIM=340, HIDDEN_DIM=256  (9 new strategic features appended)

fc1 weight shape: [HIDDEN_DIM, FEATURE_DIM]
  v7: [256, 331]  →  v8: [256, 340]  (pad 9 columns of zeros on the right)
fc1 bias shape: [HIDDEN_DIM]  — identical, copy directly

All other tensors (fc2, win_head, prize_head, hp_head, policy_head) are
identical in shape — copy directly.
"""

import json
import shutil
import sys
from pathlib import Path

try:
    from safetensors import safe_open
    from safetensors.numpy import save_file
    import numpy as np
except ImportError:
    print("Installing safetensors and numpy...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "safetensors", "numpy"])
    from safetensors import safe_open
    from safetensors.numpy import save_file
    import numpy as np

SRC = Path("/Users/stewart/Documents/projects/PokemonTCGP-BattleSimulator/checkpoints_v7/gen_446")
DST = Path("/Users/stewart/Documents/projects/PokemonTCGP-BattleSimulator/checkpoints_v8/gen_000")

DST.mkdir(parents=True, exist_ok=True)

src_weights = SRC / "weights.safetensors"
dst_weights = DST / "weights.safetensors"

print(f"Loading v7 weights from {src_weights}")

tensors = {}
with safe_open(str(src_weights), framework="numpy") as f:
    for key in f.keys():
        tensors[key] = f.get_tensor(key)
        print(f"  {key}: {tensors[key].shape} dtype={tensors[key].dtype}")

print()

# Check fc1 weight
fc1_w_key = "fc1.weight"
if fc1_w_key not in tensors:
    # Try alternate naming
    for k in tensors:
        print(f"  key: {k}")
    raise ValueError("Could not find fc1.weight — check key names above")

fc1_w = tensors[fc1_w_key]
print(f"fc1.weight original shape: {fc1_w.shape}")
assert fc1_w.shape == (256, 331), f"Expected (256, 331), got {fc1_w.shape}"

# Pad 9 new feature columns with zeros
pad = np.zeros((256, 9), dtype=fc1_w.dtype)
fc1_w_new = np.concatenate([fc1_w, pad], axis=1)
print(f"fc1.weight padded shape:   {fc1_w_new.shape}")
assert fc1_w_new.shape == (256, 340)

tensors[fc1_w_key] = fc1_w_new

print(f"\nSaving warm-started v8 weights to {dst_weights}")
save_file(tensors, str(dst_weights))
print("Done!")

# Write meta.json for v8 gen_000
meta = {
    "generation": 0,
    "feature_version": 4,
    "games_played": 0,
    "wall_time_s": 0.0,
    "notes": "warm-started from v7 gen_446 (331->340 features, 9 new strategic features zero-padded)",
    "eval_spec": "720:0.25:25"
}
meta_path = DST / "meta.json"
with open(meta_path, "w") as f:
    json.dump(meta, f, indent=2)
print(f"Wrote {meta_path}")

# Copy replay buffer from v7 gen_446 to bootstrap with good training data
src_replay = SRC / "replay.bin"
dst_replay = DST / "replay.bin"
if src_replay.exists():
    # Note: replay was built with feature_version=3 (331 features)
    # The training code checks feature_version in meta, but replay samples have
    # raw f32 arrays. v8 uses 340 features so we can't reuse the v7 replay.
    # Just skip it — training will build a fresh buffer.
    print(f"\nSkipping replay.bin (feature dimensions differ v7=331 vs v8=340)")
else:
    print(f"\nNo replay.bin found in v7 source")

print("\nWarm-start complete!")
print(f"  Source:  v7 gen_446 (331 features, HIDDEN_DIM=256)")
print(f"  Dest:    v8 gen_000 (340 features, HIDDEN_DIM=256)")
print(f"  fc1 weight: padded 9 zero columns for new strategic features")
print(f"  All other layers: copied directly (same shape)")
print()
print("Next: cd ptcgp && ./target/release/ptcgp-train --checkpoint-dir ../checkpoints_v8 --resume ...")
