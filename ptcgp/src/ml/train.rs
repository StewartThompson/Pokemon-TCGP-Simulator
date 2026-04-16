//! One training epoch: draw minibatches from the replay buffer, compute
//! multi-head Huber loss, backprop with AdamW.
//!
//! Scale is tiny — a generation is a few hundred minibatches of 256 on a
//! tiny net. This takes seconds on CPU.

use candle_core::{DType, Device, Result, Tensor};
use candle_nn::{AdamW, Optimizer};
use rand::Rng;

use super::features::FEATURE_DIM;
use super::net::{huber_loss, ValueNet};
use super::replay::ReplayBuffer;

/// Summary statistics from one epoch.
#[derive(Clone, Debug, Default)]
pub struct TrainStats {
    pub loss_win: f32,
    pub loss_prize: f32,
    pub loss_hp: f32,
    pub total_loss: f32,
    pub batches: u32,
    pub samples: u64,
}

impl TrainStats {
    fn accumulate(&mut self, win: f32, prize: f32, hp: f32, total: f32, samples: usize) {
        // Running averages (equal weight per batch; if batches all same size this
        // is the true per-sample mean).
        let n = self.batches as f32;
        self.loss_win = (self.loss_win * n + win) / (n + 1.0);
        self.loss_prize = (self.loss_prize * n + prize) / (n + 1.0);
        self.loss_hp = (self.loss_hp * n + hp) / (n + 1.0);
        self.total_loss = (self.total_loss * n + total) / (n + 1.0);
        self.batches += 1;
        self.samples += samples as u64;
    }
}

/// Run one training epoch.
///
/// Pulls `batches` random minibatches of size `batch_size` from `buffer`
/// and applies one AdamW step per batch. Loss weights: win=1.0,
/// prize=0.3, hp=0.3 (auxiliary heads intentionally down-weighted so
/// the win head stays the primary signal).
pub fn train_epoch<R: Rng>(
    net: &ValueNet,
    opt: &mut AdamW,
    buffer: &ReplayBuffer,
    batch_size: usize,
    batches: usize,
    rng: &mut R,
) -> Result<TrainStats> {
    let mut stats = TrainStats::default();
    if buffer.is_empty() {
        return Ok(stats);
    }

    let device = net.device().clone();

    for _ in 0..batches {
        let samples = buffer.sample_batch(batch_size, rng);
        if samples.is_empty() {
            break;
        }

        // Stack features [B, FEATURE_DIM] and targets [B, 1] each.
        let b = samples.len();
        let mut feat_flat = Vec::with_capacity(b * FEATURE_DIM);
        let mut win_tgt = Vec::with_capacity(b);
        let mut prize_tgt = Vec::with_capacity(b);
        let mut hp_tgt = Vec::with_capacity(b);
        for s in &samples {
            feat_flat.extend_from_slice(&s.features);
            win_tgt.push(s.win_target);
            prize_tgt.push(s.prize_target);
            hp_tgt.push(s.hp_target);
        }
        let x = Tensor::from_vec(feat_flat, (b, FEATURE_DIM), &device)?;
        let win_t = Tensor::from_vec(win_tgt, (b, 1), &device)?;
        let prize_t = Tensor::from_vec(prize_tgt, (b, 1), &device)?;
        let hp_t = Tensor::from_vec(hp_tgt, (b, 1), &device)?;

        let out = net.forward(&x)?;

        // Huber losses (delta=1.0) on each head.
        let l_win = huber_loss(&out.win, &win_t, 1.0)?;
        let l_prize = huber_loss(&out.prize, &prize_t, 1.0)?;
        let l_hp = huber_loss(&out.hp, &hp_t, 1.0)?;

        // Weighted sum. Aux heads contribute 30 % each — enough to shape
        // the trunk's intermediate representation without overwhelming the
        // primary win signal.
        let weight_aux = Tensor::new(0.3f32, &device)?;
        let weight_aux_p = weight_aux.broadcast_as(l_prize.shape())?;
        let weight_aux_h = weight_aux.broadcast_as(l_hp.shape())?;
        let loss = ((&l_win + (weight_aux_p * &l_prize)?)? + (weight_aux_h * &l_hp)?)?;

        opt.backward_step(&loss)?;

        // Collect scalars for reporting.
        let lw = l_win.to_scalar::<f32>().unwrap_or(0.0);
        let lp = l_prize.to_scalar::<f32>().unwrap_or(0.0);
        let lh = l_hp.to_scalar::<f32>().unwrap_or(0.0);
        let lt = loss.to_scalar::<f32>().unwrap_or(0.0);
        stats.accumulate(lw, lp, lh, lt, b);

        // Quiet unused-import warning if Device constructor isn't referenced.
        let _ = DType::F32;
    }

    let _ = Device::Cpu;
    Ok(stats)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ml::net::make_optimizer;
    use crate::ml::replay::Sample;
    use rand::SeedableRng;
    use rand::rngs::SmallRng;

    #[test]
    fn training_reduces_loss_on_synthetic_data() {
        // Sanity check: net should learn to predict a simple target function
        // on a tiny fixed dataset. Start high-loss, train, verify it drops.
        let net = ValueNet::new(Device::Cpu).expect("create net");
        let mut opt = make_optimizer(&net, 1e-3).expect("opt");

        let mut buf = ReplayBuffer::new(128);
        for i in 0..64 {
            let mut feat = vec![0.0f32; FEATURE_DIM];
            feat[0] = i as f32 / 64.0;
            // Target: win = 2 * feat[0] - 1 (linear, -1 to +1).
            let t = 2.0 * feat[0] - 1.0;
            buf.push(Sample::new(feat, t, t * 0.5, t * 0.3));
        }

        let mut rng = SmallRng::seed_from_u64(42);
        let before = train_epoch(&net, &mut opt, &buf, 16, 1, &mut rng)
            .expect("epoch 1")
            .loss_win;

        // Run many more epochs.
        let mut after = 0.0;
        for _ in 0..15 {
            after = train_epoch(&net, &mut opt, &buf, 16, 10, &mut rng)
                .expect("epoch N")
                .loss_win;
        }

        // Loss should strictly decrease.
        assert!(
            after < before * 0.8,
            "training did not meaningfully reduce loss: before={}, after={}",
            before,
            after
        );
    }
}
