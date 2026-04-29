//! One training epoch: draw minibatches from the replay buffer, compute
//! multi-head Huber loss, backprop with AdamW.
//!
//! Scale is tiny — a generation is a few hundred minibatches of 256 on a
//! tiny net. This takes seconds on CPU.

use candle_core::{DType, Device, Result, Tensor};
use candle_nn::{ops, AdamW, Optimizer};
use rand::Rng;

use super::features::FEATURE_DIM;
use super::net::{huber_loss, ValueNet, MAX_POLICY_SIZE};
use super::replay::ReplayBuffer;

/// Summary statistics from one epoch.
#[derive(Clone, Debug, Default)]
pub struct TrainStats {
    pub loss_win: f32,
    pub loss_prize: f32,
    pub loss_hp: f32,
    /// Cross-entropy policy head loss (average over batches that had policy data).
    /// Zero when no samples in the buffer have policy targets yet.
    pub loss_policy: f32,
    pub total_loss: f32,
    pub batches: u32,
    pub samples: u64,
}

impl TrainStats {
    fn accumulate(&mut self, win: f32, prize: f32, hp: f32, policy: f32, total: f32, samples: usize) {
        // Running averages (equal weight per batch; if batches all same size this
        // is the true per-sample mean).
        let n = self.batches as f32;
        self.loss_win    = (self.loss_win    * n + win)    / (n + 1.0);
        self.loss_prize  = (self.loss_prize  * n + prize)  / (n + 1.0);
        self.loss_hp     = (self.loss_hp     * n + hp)     / (n + 1.0);
        self.loss_policy = (self.loss_policy * n + policy) / (n + 1.0);
        self.total_loss  = (self.total_loss  * n + total)  / (n + 1.0);
        self.batches += 1;
        self.samples += samples as u64;
    }
}

/// Run one training epoch.
///
/// Pulls `batches` random minibatches of size `batch_size` from `buffer`
/// and applies one AdamW step per batch.
///
/// Loss = L_win + aux_weight*(L_prize + L_hp) + policy_weight*L_policy.
/// `aux_weight=0.3` is the original conservative default; `aux_weight=0.5`
/// gives more gradient signal to the tempo/prize heads.
/// `policy_weight=1.0` gives equal weight to the cross-entropy policy head.
pub fn train_epoch<R: Rng>(
    net: &ValueNet,
    opt: &mut AdamW,
    buffer: &ReplayBuffer,
    batch_size: usize,
    batches: usize,
    rng: &mut R,
) -> Result<TrainStats> {
    train_epoch_weighted(net, opt, buffer, batch_size, batches, rng, 0.3, 1.0)
}

/// Like [`train_epoch`] but with configurable head weights.
///
/// `aux_weight`: multiplier for prize and HP auxiliary heads.
/// `policy_weight`: multiplier for the masked cross-entropy policy head.
///    0.0 disables policy training entirely (value-only mode).
///    1.0 gives the policy head equal weight to the win head.
pub fn train_epoch_weighted<R: Rng>(
    net: &ValueNet,
    opt: &mut AdamW,
    buffer: &ReplayBuffer,
    batch_size: usize,
    batches: usize,
    rng: &mut R,
    aux_weight: f32,
    policy_weight: f32,
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
        let mut feat_flat       = Vec::with_capacity(b * FEATURE_DIM);
        let mut win_tgt         = Vec::with_capacity(b);
        let mut prize_tgt       = Vec::with_capacity(b);
        let mut hp_tgt          = Vec::with_capacity(b);
        // Policy data — we build this for all samples; non-policy samples get
        // all-ones legal mask (prevents NaN in log_softmax) and zero target
        // (CE = 0 ⇒ no gradient signal).
        let mut policy_tgt_flat  = Vec::with_capacity(b * MAX_POLICY_SIZE);
        let mut policy_legal_flat = Vec::with_capacity(b * MAX_POLICY_SIZE);
        let mut has_policy_flat  = Vec::with_capacity(b);

        for s in &samples {
            feat_flat.extend_from_slice(&s.features);
            win_tgt.push(s.win_target);
            prize_tgt.push(s.prize_target);
            hp_tgt.push(s.hp_target);

            if s.has_policy() {
                policy_tgt_flat.extend_from_slice(&s.policy_target);
                policy_legal_flat.extend_from_slice(&s.policy_legal);
                has_policy_flat.push(1.0f32);
            } else {
                // Zero target, uniform legal mask — CE loss = 0 for this sample.
                for _ in 0..MAX_POLICY_SIZE {
                    policy_tgt_flat.push(0.0f32);
                    policy_legal_flat.push(1.0f32);
                }
                has_policy_flat.push(0.0f32);
            }
        }

        let x      = Tensor::from_vec(feat_flat,  (b, FEATURE_DIM), &device)?;
        let win_t  = Tensor::from_vec(win_tgt,    (b, 1), &device)?;
        let prize_t = Tensor::from_vec(prize_tgt, (b, 1), &device)?;
        let hp_t   = Tensor::from_vec(hp_tgt,     (b, 1), &device)?;

        let out = net.forward(&x)?;

        // Huber losses (delta=1.0) on value heads.
        let l_win   = huber_loss(&out.win,   &win_t,   1.0)?;
        let l_prize = huber_loss(&out.prize, &prize_t, 1.0)?;
        let l_hp    = huber_loss(&out.hp,    &hp_t,    1.0)?;

        // Weighted sum: win head primary; aux heads with aux_weight.
        let weight_aux   = Tensor::new(aux_weight, &device)?;
        let weight_aux_p = weight_aux.broadcast_as(l_prize.shape())?;
        let weight_aux_h = weight_aux.broadcast_as(l_hp.shape())?;
        let loss_value = ((&l_win + (weight_aux_p * &l_prize)?)? + (weight_aux_h * &l_hp)?)?;

        // Policy head: masked cross-entropy.
        // Only adds gradient signal when there are samples with policy targets.
        let n_policy: f32 = has_policy_flat.iter().sum();
        let (loss, lpo) = if policy_weight > 0.0 && n_policy > 0.0 {
            let policy_t = Tensor::from_vec(
                policy_tgt_flat, (b, MAX_POLICY_SIZE), &device)?;
            let legal_t = Tensor::from_vec(
                policy_legal_flat, (b, MAX_POLICY_SIZE), &device)?;
            let has_pol_t = Tensor::from_vec(has_policy_flat, b, &device)?;

            // Mask illegal slots with a large negative value before log_softmax.
            // illegal_mask = (1 - legal_mask): 1 for illegal, 0 for legal.
            let ones       = Tensor::ones((b, MAX_POLICY_SIZE), DType::F32, &device)?;
            let illegal    = (&ones - &legal_t)?;
            let neg_inf    = Tensor::new(-1e9f32, &device)?
                .broadcast_as((b, MAX_POLICY_SIZE))?;
            let masked_logits = (&out.policy + (&illegal * &neg_inf)?)?;

            // log P(a|s) for legal actions; very negative for illegal ones.
            let log_probs = ops::log_softmax(&masked_logits, 1)?;

            // CE per sample: -sum_a(π(a) * log P(a)).
            // For samples without policy, π(a)=0 everywhere → CE=0.
            let ce_per_sample = (&policy_t * &log_probs)?
                .neg()?.sum(1)?;  // [B]

            // Mean over policy-having samples only.
            let n_policy_t = Tensor::new(n_policy, &device)?;
            let l_policy = (&ce_per_sample * &has_pol_t)?
                .sum_all()?
                .div(&n_policy_t)?;

            let lpo_scalar = l_policy.to_scalar::<f32>().unwrap_or(0.0);
            let pw = Tensor::new(policy_weight, &device)?;
            let total = (&loss_value + &(pw * &l_policy)?)?;
            (total, lpo_scalar)
        } else {
            (loss_value, 0.0)
        };

        opt.backward_step(&loss)?;

        // Collect scalars for reporting.
        let lw = l_win.to_scalar::<f32>().unwrap_or(0.0);
        let lp = l_prize.to_scalar::<f32>().unwrap_or(0.0);
        let lh = l_hp.to_scalar::<f32>().unwrap_or(0.0);
        let lt = loss.to_scalar::<f32>().unwrap_or(0.0);
        stats.accumulate(lw, lp, lh, lpo, lt, b);

        // Quiet unused-import warnings.
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
