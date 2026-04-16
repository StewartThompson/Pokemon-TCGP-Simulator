//! Fixed-size replay buffer for self-play training.
//!
//! Each [`Sample`] captures one decision point:
//!   * features — the encoded state the bot was looking at
//!   * win_target — the eventual outcome, ±1 from that player's POV
//!   * prize_target — end-of-game (my_prizes − opp_prizes) / 3
//!   * hp_target — end-of-game HP differential (me − opp) / MAX_HP_SUM
//!
//! The buffer is FIFO (oldest evicted when full) and stored entirely in
//! memory. Size 50k × (FEATURE_DIM=273 floats + 3 targets) ≈ ~55 MB —
//! fine for a laptop and plenty of variance across generations.
//!
//! Serialization is manual (no serde derives for f32 arrays) — we write
//! a flat binary format: magic header + FEATURE_VERSION + count, then
//! packed (features..., win, prize, hp) for each sample.

use std::fs::File;
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::Path;

use rand::seq::SliceRandom;
use rand::Rng;

use super::features::{FEATURE_DIM, FEATURE_VERSION};

const MAGIC: &[u8; 8] = b"PTCGPRB\x01";

/// One training datum from a single game-state decision.
#[derive(Clone, Debug)]
pub struct Sample {
    pub features: Vec<f32>, // length FEATURE_DIM
    pub win_target: f32,    // [-1, +1]
    pub prize_target: f32,  // normalized prize differential
    pub hp_target: f32,     // normalized HP differential
}

impl Sample {
    pub fn new(features: Vec<f32>, win: f32, prize: f32, hp: f32) -> Self {
        debug_assert_eq!(features.len(), FEATURE_DIM);
        Self {
            features,
            win_target: win,
            prize_target: prize,
            hp_target: hp,
        }
    }
}

/// Bounded FIFO replay buffer.
pub struct ReplayBuffer {
    cap: usize,
    samples: std::collections::VecDeque<Sample>,
}

impl ReplayBuffer {
    pub fn new(cap: usize) -> Self {
        Self {
            cap,
            samples: std::collections::VecDeque::with_capacity(cap),
        }
    }

    pub fn len(&self) -> usize {
        self.samples.len()
    }

    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }

    pub fn cap(&self) -> usize {
        self.cap
    }

    /// Append one sample, evicting the oldest if at capacity.
    pub fn push(&mut self, s: Sample) {
        if self.samples.len() == self.cap {
            self.samples.pop_front();
        }
        self.samples.push_back(s);
    }

    /// Append many samples. Implemented on top of `push` for simple FIFO
    /// semantics at the boundary.
    pub fn push_many<I: IntoIterator<Item = Sample>>(&mut self, it: I) {
        for s in it {
            self.push(s);
        }
    }

    /// Sample `n` items uniformly at random (with replacement if n > len).
    /// Returns references so callers can stack into tensors without cloning.
    pub fn sample_batch<R: Rng>(&self, n: usize, rng: &mut R) -> Vec<&Sample> {
        if self.samples.is_empty() {
            return Vec::new();
        }
        let mut out = Vec::with_capacity(n);
        if n <= self.samples.len() {
            // Without replacement: reservoir-style Fisher-Yates on indices.
            let mut indices: Vec<usize> = (0..self.samples.len()).collect();
            indices.shuffle(rng);
            for &i in indices.iter().take(n) {
                out.push(&self.samples[i]);
            }
        } else {
            // Buffer smaller than batch → draw with replacement.
            for _ in 0..n {
                let i = rng.gen_range(0..self.samples.len());
                out.push(&self.samples[i]);
            }
        }
        out
    }

    /// Persist the buffer to disk. See module docs for format.
    pub fn save(&self, path: &Path) -> std::io::Result<()> {
        let f = File::create(path)?;
        let mut w = BufWriter::new(f);
        w.write_all(MAGIC)?;
        w.write_all(&FEATURE_VERSION.to_le_bytes())?;
        w.write_all(&(FEATURE_DIM as u32).to_le_bytes())?;
        w.write_all(&(self.samples.len() as u64).to_le_bytes())?;
        for s in &self.samples {
            // features as f32 little-endian
            for &f in &s.features {
                w.write_all(&f.to_le_bytes())?;
            }
            w.write_all(&s.win_target.to_le_bytes())?;
            w.write_all(&s.prize_target.to_le_bytes())?;
            w.write_all(&s.hp_target.to_le_bytes())?;
        }
        w.flush()?;
        Ok(())
    }

    /// Load from disk. Validates magic + feature version — a mismatch
    /// means the replay buffer was built with a different feature layout
    /// and the samples are no longer meaningful.
    pub fn load(path: &Path, cap: usize) -> std::io::Result<Self> {
        let f = File::open(path)?;
        let mut r = BufReader::new(f);

        let mut magic = [0u8; 8];
        r.read_exact(&mut magic)?;
        if &magic != MAGIC {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "replay-buffer magic mismatch (corrupt or wrong file)",
            ));
        }

        let mut fv = [0u8; 4];
        r.read_exact(&mut fv)?;
        let on_disk_fv = u32::from_le_bytes(fv);
        if on_disk_fv != FEATURE_VERSION {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!(
                    "replay-buffer feature_version {} differs from current {} — discard and regenerate",
                    on_disk_fv, FEATURE_VERSION
                ),
            ));
        }

        let mut dim_buf = [0u8; 4];
        r.read_exact(&mut dim_buf)?;
        let on_disk_dim = u32::from_le_bytes(dim_buf) as usize;
        if on_disk_dim != FEATURE_DIM {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!(
                    "replay-buffer feature dim {} differs from current {}",
                    on_disk_dim, FEATURE_DIM
                ),
            ));
        }

        let mut count_buf = [0u8; 8];
        r.read_exact(&mut count_buf)?;
        let n = u64::from_le_bytes(count_buf) as usize;

        let mut buf = Self::new(cap);
        let mut fbuf = [0u8; 4];
        for _ in 0..n {
            let mut features = Vec::with_capacity(FEATURE_DIM);
            for _ in 0..FEATURE_DIM {
                r.read_exact(&mut fbuf)?;
                features.push(f32::from_le_bytes(fbuf));
            }
            r.read_exact(&mut fbuf)?;
            let win = f32::from_le_bytes(fbuf);
            r.read_exact(&mut fbuf)?;
            let prize = f32::from_le_bytes(fbuf);
            r.read_exact(&mut fbuf)?;
            let hp = f32::from_le_bytes(fbuf);
            buf.push(Sample::new(features, win, prize, hp));
        }
        Ok(buf)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand::rngs::SmallRng;

    fn mk_sample(v: f32) -> Sample {
        Sample::new(vec![v; FEATURE_DIM], v, v * 0.5, v * 0.3)
    }

    #[test]
    fn fifo_eviction() {
        let mut buf = ReplayBuffer::new(3);
        buf.push(mk_sample(0.1));
        buf.push(mk_sample(0.2));
        buf.push(mk_sample(0.3));
        buf.push(mk_sample(0.4)); // evicts 0.1
        assert_eq!(buf.len(), 3);
        // First remaining sample should be 0.2.
        assert!((buf.samples[0].win_target - 0.2).abs() < 1e-6);
        assert!((buf.samples[2].win_target - 0.4).abs() < 1e-6);
    }

    #[test]
    fn sample_batch_basic() {
        let mut buf = ReplayBuffer::new(100);
        for i in 0..50 {
            buf.push(mk_sample(i as f32 * 0.01));
        }
        let mut rng = SmallRng::seed_from_u64(7);
        let batch = buf.sample_batch(8, &mut rng);
        assert_eq!(batch.len(), 8);
        // All samples should come from the buffer (not null/random).
        for s in &batch {
            assert_eq!(s.features.len(), FEATURE_DIM);
        }
    }

    #[test]
    fn save_load_roundtrip() {
        let tmp = std::env::temp_dir().join("ptcgp_replay_roundtrip.bin");
        let _ = std::fs::remove_file(&tmp);

        let mut buf = ReplayBuffer::new(10);
        for i in 0..5 {
            buf.push(mk_sample(i as f32 * 0.1));
        }
        buf.save(&tmp).expect("save");
        let loaded = ReplayBuffer::load(&tmp, 10).expect("load");
        assert_eq!(loaded.len(), 5);
        for i in 0..5 {
            assert!((loaded.samples[i].win_target - (i as f32 * 0.1)).abs() < 1e-6);
        }
        let _ = std::fs::remove_file(&tmp);
    }

    #[test]
    fn sample_batch_from_empty_is_empty() {
        let buf = ReplayBuffer::new(10);
        let mut rng = SmallRng::seed_from_u64(0);
        assert!(buf.sample_batch(5, &mut rng).is_empty());
    }
}
