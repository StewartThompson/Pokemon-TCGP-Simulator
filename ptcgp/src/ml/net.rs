//! Tiny three-head value network implemented with [`candle-nn`].
//!
//! # Architecture
//!
//! ```text
//!   input [B, FEATURE_DIM]
//!     → Linear(FEATURE_DIM → 192) → ReLU
//!     → Linear(192 → 192)         → ReLU
//!     → three heads:
//!       win_head   : Linear(192 → 1) → tanh    — predicts game outcome, [-1, +1]
//!       prize_head : Linear(192 → 1)           — predicts (my_prizes − opp_prizes) end-of-game
//!       hp_head    : Linear(192 → 1)           — predicts normalized HP differential
//! ```
//!
//! Total params ≈ 78k. Trains in milliseconds per batch on CPU.
//!
//! # Why three heads?
//!
//! The "win" target is the canonical ±1 outcome — sparse (one label per full
//! game). "prize" and "hp" heads are auxiliary: they're dense intermediate
//! signals that give the shared trunk something to learn on during every
//! move, not just at game end. AlphaZero-family papers consistently show
//! ~3× faster convergence with aux regression heads. Zero extra MCTS cost.

use candle_core::{Device, Error as CandleError, Module, Result, Tensor};
use candle_nn::{linear, AdamW, Linear, Optimizer, ParamsAdamW, VarBuilder, VarMap};
use std::path::Path;

use super::features::FEATURE_DIM;

/// Hidden dimension for both shared linear layers.
pub const HIDDEN_DIM: usize = 192;

/// The full value-network module.
pub struct ValueNet {
    fc1: Linear,
    fc2: Linear,
    win_head: Linear,
    prize_head: Linear,
    hp_head: Linear,
    /// Underlying parameter storage. We hold a `VarMap` here so that `save`
    /// / `load` can round-trip all weights without the caller tracking them
    /// separately. Cloneable because `VarMap` is internally `Arc<Mutex<…>>`.
    varmap: VarMap,
    device: Device,
}

/// Outputs of a forward pass. Each is shape `[B, 1]`.
pub struct ValueOutputs {
    pub win: Tensor,
    pub prize: Tensor,
    pub hp: Tensor,
}

impl ValueNet {
    /// Create a randomly initialized network on the given device (CPU).
    pub fn new(device: Device) -> Result<Self> {
        let varmap = VarMap::new();
        let vs = VarBuilder::from_varmap(&varmap, candle_core::DType::F32, &device);
        let net = Self::build(vs, varmap, device)?;
        Ok(net)
    }

    /// Build the layers given a `VarBuilder`. Used by both `new` and `load`.
    fn build(vs: VarBuilder, varmap: VarMap, device: Device) -> Result<Self> {
        let fc1 = linear(FEATURE_DIM, HIDDEN_DIM, vs.pp("fc1"))?;
        let fc2 = linear(HIDDEN_DIM, HIDDEN_DIM, vs.pp("fc2"))?;
        let win_head = linear(HIDDEN_DIM, 1, vs.pp("win_head"))?;
        let prize_head = linear(HIDDEN_DIM, 1, vs.pp("prize_head"))?;
        let hp_head = linear(HIDDEN_DIM, 1, vs.pp("hp_head"))?;
        Ok(Self {
            fc1,
            fc2,
            win_head,
            prize_head,
            hp_head,
            varmap,
            device,
        })
    }

    /// Forward pass. `x` shape `[B, FEATURE_DIM]`.
    pub fn forward(&self, x: &Tensor) -> Result<ValueOutputs> {
        let h = self.fc1.forward(x)?.relu()?;
        let h = self.fc2.forward(&h)?.relu()?;
        let win = self.win_head.forward(&h)?.tanh()?;
        let prize = self.prize_head.forward(&h)?;
        let hp = self.hp_head.forward(&h)?;
        Ok(ValueOutputs { win, prize, hp })
    }

    /// Evaluate the win head on a single feature vector. Returns a scalar in
    /// [-1, +1] from the acting player's POV — the natural MCTS leaf value.
    ///
    /// Hot path: called once per MCTS leaf expansion during self-play. We
    /// don't batch here (batched inference is a Wave 5 optimisation).
    pub fn win_value(&self, features: &[f32]) -> Result<f32> {
        debug_assert_eq!(features.len(), FEATURE_DIM);
        let x = Tensor::from_slice(features, (1, FEATURE_DIM), &self.device)?;
        let outputs = self.forward(&x)?;
        let v = outputs.win.to_vec2::<f32>()?;
        Ok(v[0][0])
    }

    /// Save weights to a `safetensors` file.
    pub fn save(&self, path: &Path) -> Result<()> {
        self.varmap.save(path)?;
        Ok(())
    }

    /// Load weights from a `safetensors` file into a fresh network.
    ///
    /// The architecture (layer shapes) is determined by the constants in
    /// this file — `FEATURE_DIM`, `HIDDEN_DIM`. A file saved under a
    /// different layout will fail here with a shape-mismatch error.
    pub fn load(path: &Path, device: Device) -> Result<Self> {
        // Candle's VarMap::load only overwrites *already-registered* tensors.
        // Loading into an empty VarMap is a no-op — variables are registered
        // during layer construction, not during load.
        //
        // Correct pattern:
        //   1. Build the network (registers all vars in the VarMap with random init).
        //   2. Overwrite those registered vars by loading from file.
        let varmap = VarMap::new();
        let vs = VarBuilder::from_varmap(&varmap, candle_core::DType::F32, &device);
        let mut net = Self::build(vs, varmap, device)?;
        net.varmap.load(path)?; // overwrite registered vars with saved values
        Ok(net)
    }

    pub fn varmap(&self) -> &VarMap {
        &self.varmap
    }

    pub fn device(&self) -> &Device {
        &self.device
    }
}

/// Pure-Rust inference copy of the value network.
///
/// Extracted from a trained [`ValueNet`] via [`ValueNet::to_inference_net`].
/// Runs the forward pass as plain f32 arithmetic with stack-allocated scratch
/// buffers — **zero heap allocation per call**.
///
/// Use this during MCTS self-play (the hot path). Use [`ValueNet`] for training.
///
/// # Layout
///
/// Weights are row-major:
/// - `fc1_w[i * FEATURE_DIM .. (i+1) * FEATURE_DIM]` → row `i` of the first linear layer
/// - `fc2_w[i * HIDDEN_DIM .. (i+1) * HIDDEN_DIM]` → row `i` of the second linear layer
/// - `win_w[0..HIDDEN_DIM]` → the single output row of the win head
pub struct InferenceNet {
    fc1_w: Vec<f32>,   // [HIDDEN_DIM × FEATURE_DIM]
    fc1_b: Vec<f32>,   // [HIDDEN_DIM]
    fc2_w: Vec<f32>,   // [HIDDEN_DIM × HIDDEN_DIM]
    fc2_b: Vec<f32>,   // [HIDDEN_DIM]
    win_w: Vec<f32>,   // [HIDDEN_DIM]
    win_b: f32,
}

impl InferenceNet {
    /// Evaluate the win head. Returns a tanh-activated value in `[-1, +1]`.
    ///
    /// `x` must be exactly [`FEATURE_DIM`] elements. Uses `[f32; HIDDEN_DIM]`
    /// stack buffers for the two hidden layers — no heap allocation.
    pub fn win_value(&self, x: &[f32; FEATURE_DIM]) -> f32 {
        // h1 = relu(fc1_w @ x + fc1_b)
        let mut h1 = [0.0f32; HIDDEN_DIM];
        for (i, (b, row)) in self
            .fc1_b
            .iter()
            .zip(self.fc1_w.chunks_exact(FEATURE_DIM))
            .enumerate()
        {
            let mut s = *b;
            for (w, xv) in row.iter().zip(x.iter()) {
                s += w * xv;
            }
            h1[i] = s.max(0.0); // ReLU
        }

        // h2 = relu(fc2_w @ h1 + fc2_b)
        let mut h2 = [0.0f32; HIDDEN_DIM];
        for (i, (b, row)) in self
            .fc2_b
            .iter()
            .zip(self.fc2_w.chunks_exact(HIDDEN_DIM))
            .enumerate()
        {
            let mut s = *b;
            for (w, hv) in row.iter().zip(h1.iter()) {
                s += w * hv;
            }
            h2[i] = s.max(0.0); // ReLU
        }

        // win = tanh(win_w @ h2 + win_b)
        let mut win = self.win_b;
        for (w, hv) in self.win_w.iter().zip(h2.iter()) {
            win += w * hv;
        }
        win.tanh()
    }
}

impl ValueNet {
    /// Extract weights into an [`InferenceNet`] for allocation-free MCTS leaf
    /// evaluation. Call once after training; share the result via `Arc`.
    ///
    /// The conversion reads current weight tensors from Candle (one `to_vec1`
    /// each) and copies them into plain `Vec<f32>`. Typically < 1 ms.
    pub fn to_inference_net(&self) -> Result<InferenceNet> {
        fn flat(t: &Tensor) -> Result<Vec<f32>> {
            t.flatten_all()?.to_vec1::<f32>()
        }
        Ok(InferenceNet {
            fc1_w: flat(self.fc1.weight())?,
            fc1_b: flat(self.fc1.bias().expect("fc1 has bias"))?,
            fc2_w: flat(self.fc2.weight())?,
            fc2_b: flat(self.fc2.bias().expect("fc2 has bias"))?,
            win_w: flat(self.win_head.weight())?,
            win_b: flat(self.win_head.bias().expect("win_head has bias"))?[0],
        })
    }
}

/// Construct an AdamW optimizer over a net's parameters with sensible
/// defaults for this task (small net, supervised regression).
pub fn make_optimizer(net: &ValueNet, lr: f64) -> Result<AdamW> {
    let params = ParamsAdamW {
        lr,
        beta1: 0.9,
        beta2: 0.999,
        eps: 1e-8,
        weight_decay: 1e-4,
    };
    AdamW::new(net.varmap.all_vars(), params)
}

/// Huber loss (smooth-L1) — less sensitive to outliers than MSE. Used for
/// all three regression heads. `delta` is the quadratic-to-linear cutoff.
pub fn huber_loss(pred: &Tensor, target: &Tensor, delta: f32) -> Result<Tensor> {
    let diff = (pred - target)?;
    let abs_diff = diff.abs()?;
    let delta_t = Tensor::new(delta, diff.device())?;
    // For |d| ≤ δ: 0.5 * d^2.  For |d| > δ: δ * (|d| - 0.5 δ).
    let quadratic = (&abs_diff.minimum(&delta_t.broadcast_as(abs_diff.shape())?)?).clone();
    let quadratic_sq = (&quadratic * &quadratic)?;
    let linear_part = (&abs_diff - &quadratic)?;
    let half = Tensor::new(0.5f32, diff.device())?;
    let loss_per = ((&half.broadcast_as(quadratic_sq.shape())? * &quadratic_sq)?
        + (delta_t.broadcast_as(linear_part.shape())? * linear_part)?)?;
    loss_per.mean_all()
}

/// Returns the best available compute device: Metal (Apple GPU) on macOS,
/// CPU everywhere else. Falls back to CPU silently if Metal init fails.
///
/// Metal is used for the training step (batch gradient computation) where
/// the GPU batching amortises dispatch overhead. Self-play inference keeps
/// its own CPU path so rayon parallelism is unaffected.
pub fn best_device() -> Device {
    match Device::new_metal(0) {
        Ok(d) => d,
        Err(_) => Device::Cpu,
    }
}

/// Returns true if the device is a Metal GPU.
pub fn is_metal(device: &Device) -> bool {
    matches!(device, Device::Metal(_))
}

/// Helper to cast a `CandleError` into a more descriptive message when
/// something goes wrong at model-construction time.
#[allow(dead_code)]
pub(crate) fn wrap_err(e: CandleError, context: &str) -> CandleError {
    CandleError::Msg(format!("{}: {}", context, e))
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forward_shapes_are_correct() {
        let net = ValueNet::new(Device::Cpu).expect("create net");
        // Batch of 3 synthetic inputs.
        let x = Tensor::zeros((3, FEATURE_DIM), candle_core::DType::F32, &Device::Cpu)
            .expect("create input");
        let out = net.forward(&x).expect("forward");
        assert_eq!(out.win.dims(), &[3, 1]);
        assert_eq!(out.prize.dims(), &[3, 1]);
        assert_eq!(out.hp.dims(), &[3, 1]);
    }

    #[test]
    fn win_value_returns_scalar_in_range() {
        let net = ValueNet::new(Device::Cpu).expect("create net");
        let features = vec![0.0f32; FEATURE_DIM];
        let v = net.win_value(&features).expect("win_value");
        assert!(v >= -1.0 && v <= 1.0, "win output {} outside [-1, 1]", v);
    }

    #[test]
    fn save_and_load_round_trip() {
        let tmp = std::env::temp_dir().join("ptcgp_valuenet_roundtrip.safetensors");
        let _ = std::fs::remove_file(&tmp);

        let net = ValueNet::new(Device::Cpu).expect("create net");
        let features = vec![0.1f32; FEATURE_DIM];
        let v_before = net.win_value(&features).expect("win_value before save");

        net.save(&tmp).expect("save");
        let net2 = ValueNet::load(&tmp, Device::Cpu).expect("load");
        let v_after = net2.win_value(&features).expect("win_value after load");

        assert!(
            (v_before - v_after).abs() < 1e-5,
            "predictions differ after reload: {} vs {}",
            v_before,
            v_after
        );
        let _ = std::fs::remove_file(&tmp);
    }

    #[test]
    fn inference_net_matches_candle() {
        // Build a fresh (randomly-initialised) ValueNet and extract an
        // InferenceNet from it. Both should produce identical win values
        // on the same input to within floating-point rounding error.
        let net = ValueNet::new(Device::Cpu).expect("create net");
        let inet = net.to_inference_net().expect("to_inference_net");

        // Use a non-trivial input (all 0.1) so we exercise the weight math.
        let features = vec![0.1f32; FEATURE_DIM];
        let feat_arr: [f32; FEATURE_DIM] = features.clone().try_into().unwrap();

        let v_candle = net.win_value(&features).expect("candle win_value");
        let v_rust = inet.win_value(&feat_arr);

        assert!(
            (v_candle - v_rust).abs() < 1e-4,
            "InferenceNet diverges from ValueNet: candle={} rust={}",
            v_candle,
            v_rust,
        );

        // Sanity: both are in range.
        assert!(v_rust >= -1.0 && v_rust <= 1.0, "v_rust {} out of range", v_rust);
    }

    #[test]
    fn huber_loss_is_nonnegative() {
        let device = Device::Cpu;
        let pred = Tensor::new(&[0.5f32, -0.2, 1.0][..], &device).expect("pred");
        let tgt = Tensor::new(&[0.0f32, 0.0, 0.0][..], &device).expect("tgt");
        let loss = huber_loss(&pred, &tgt, 1.0).expect("huber");
        let v = loss.to_scalar::<f32>().expect("scalar");
        assert!(v >= 0.0);
    }
}
