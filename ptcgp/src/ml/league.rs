//! Opponent selection for self-play training.
//!
//! Pure self-play (bot vs. mirror of itself) has a well-known failure mode:
//! the bot can cycle — new generation beats the old by exploiting one quirk,
//! then the next generation exploits a quirk of THAT one, and on it goes,
//! with overall strength oscillating instead of climbing. AlphaStar fixed
//! this with a "league" — play against a distribution of opponents instead.
//!
//! This module implements a small 3-way league:
//!   * 60% vs current-gen mirror (standard self-play)
//!   * 30% vs a uniformly-random past generation
//!   * 10% vs `HeuristicAgent` (anchors to a fixed external baseline)
//!
//! Past-generation selection is *decided* here but the actual loading
//! happens in the training binary — this module returns a descriptor.

use rand::Rng;

/// What kind of opponent to face for one training game.
#[derive(Clone, Debug)]
pub enum Opponent {
    /// Mirror of the current (still-training) network.
    SelfMirror,
    /// A past generation's checkpoint (specified by gen number).
    PastGen(u32),
    /// Fixed hand-coded baseline.
    Heuristic,
}

/// Pick an opponent at random, according to the league distribution.
///
/// `past_gens` is the sorted list of available past-generation checkpoints.
/// If empty (e.g., gen 0), past-gen slots fall through to self-mirror.
pub fn pick_opponent<R: Rng>(rng: &mut R, past_gens: &[u32]) -> Opponent {
    let r: f32 = rng.gen::<f32>();
    if r < 0.60 {
        Opponent::SelfMirror
    } else if r < 0.90 {
        if past_gens.is_empty() {
            // No past checkpoints yet — fall back to self-mirror.
            Opponent::SelfMirror
        } else {
            let idx = rng.gen_range(0..past_gens.len());
            Opponent::PastGen(past_gens[idx])
        }
    } else {
        Opponent::Heuristic
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand::rngs::SmallRng;

    #[test]
    fn distribution_is_roughly_correct() {
        let mut rng = SmallRng::seed_from_u64(0);
        let past = vec![0u32, 1, 2, 3];
        let n = 10_000usize;
        let mut counts = [0usize; 3];
        for _ in 0..n {
            match pick_opponent(&mut rng, &past) {
                Opponent::SelfMirror => counts[0] += 1,
                Opponent::PastGen(_) => counts[1] += 1,
                Opponent::Heuristic => counts[2] += 1,
            }
        }
        let frac0 = counts[0] as f32 / n as f32;
        let frac1 = counts[1] as f32 / n as f32;
        let frac2 = counts[2] as f32 / n as f32;
        // Loose bounds — law of large numbers, 10k samples.
        assert!((frac0 - 0.60).abs() < 0.03, "self mirror frac = {}", frac0);
        assert!((frac1 - 0.30).abs() < 0.03, "past-gen frac = {}", frac1);
        assert!((frac2 - 0.10).abs() < 0.03, "heuristic frac = {}", frac2);
    }

    #[test]
    fn empty_past_falls_back_to_self_mirror() {
        let mut rng = SmallRng::seed_from_u64(0);
        // With no past gens available, any non-heuristic roll should land
        // on SelfMirror. Run 1000× and check we never see PastGen.
        for _ in 0..1000 {
            match pick_opponent(&mut rng, &[]) {
                Opponent::PastGen(_) => panic!("should have no past gens"),
                _ => {}
            }
        }
    }
}
