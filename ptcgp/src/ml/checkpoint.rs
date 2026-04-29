//! Generation checkpoints — save and resume training.
//!
//! Disk layout:
//! ```text
//! <root>/
//!   gen_000/
//!     weights.safetensors      value net params
//!     replay.bin              (optional) replay buffer snapshot
//!     meta.json               { generation, feature_version, games_played,
//!                               wall_time_s, notes }
//!   gen_001/
//!     ...
//! ```
//!
//! A `feature_version` mismatch on load is a hard error — the net's layer
//! shapes depend on `FEATURE_DIM`, so loading a checkpoint from a different
//! feature layout would silently corrupt predictions.

use candle_core::Device;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

use super::features::FEATURE_VERSION;
use super::net::ValueNet;
use super::replay::ReplayBuffer;

/// Metadata stored alongside the weights. Small JSON for human inspection.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Meta {
    pub generation: u32,
    pub feature_version: u32,
    pub games_played: u64,
    pub wall_time_s: f64,
    pub notes: String,
    /// Recommended eval spec fragment: "sims:hybrid_weight:rollout_depth"
    /// e.g. "240:0.5:25". Written by the trainer so `--agent ai` can
    /// reconstruct the exact eval parameters the model was trained with.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub eval_spec: Option<String>,
}

impl Meta {
    pub fn new(generation: u32) -> Self {
        Self {
            generation,
            feature_version: FEATURE_VERSION,
            games_played: 0,
            wall_time_s: 0.0,
            notes: String::new(),
            eval_spec: None,
        }
    }
}

/// Save a full generation. Creates `<root>/gen_{NNN}/` if it doesn't exist.
pub fn save_generation(
    root: &Path,
    gen: u32,
    net: &ValueNet,
    buffer: Option<&ReplayBuffer>,
    meta: &Meta,
) -> std::io::Result<()> {
    let dir = root.join(format!("gen_{:03}", gen));
    fs::create_dir_all(&dir)?;

    let weights_path = dir.join("weights.safetensors");
    net.save(&weights_path)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, format!("weights save: {e}")))?;

    if let Some(buf) = buffer {
        let replay_path = dir.join("replay.bin");
        buf.save(&replay_path)?;
    }

    let meta_path = dir.join("meta.json");
    let meta_json = serde_json::to_string_pretty(meta).map_err(|e| {
        std::io::Error::new(std::io::ErrorKind::Other, format!("meta serialise: {e}"))
    })?;
    fs::write(&meta_path, meta_json)?;

    Ok(())
}

/// Load a generation. Returns (net, meta, optional replay buffer).
///
/// A replay buffer with capacity `replay_cap` is loaded if the file exists;
/// otherwise an empty buffer of that capacity is returned.
pub fn load_generation(
    root: &Path,
    gen: u32,
    device: Device,
    replay_cap: usize,
) -> std::io::Result<(ValueNet, Meta, ReplayBuffer)> {
    let dir = root.join(format!("gen_{:03}", gen));
    if !dir.is_dir() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("no generation {} at {}", gen, dir.display()),
        ));
    }

    let meta_path = dir.join("meta.json");
    let meta_str = fs::read_to_string(&meta_path)?;
    let meta: Meta = serde_json::from_str(&meta_str).map_err(|e| {
        std::io::Error::new(std::io::ErrorKind::InvalidData, format!("meta parse: {e}"))
    })?;
    if meta.feature_version != FEATURE_VERSION {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            format!(
                "checkpoint feature_version {} differs from current {} — cannot load",
                meta.feature_version, FEATURE_VERSION
            ),
        ));
    }

    let weights_path = dir.join("weights.safetensors");
    let net = ValueNet::load(&weights_path, device).map_err(|e| {
        std::io::Error::new(std::io::ErrorKind::Other, format!("weights load: {e}"))
    })?;

    let replay_path = dir.join("replay.bin");
    let buffer = if replay_path.exists() {
        ReplayBuffer::load(&replay_path, replay_cap)?
    } else {
        ReplayBuffer::new(replay_cap)
    };

    Ok((net, meta, buffer))
}

/// Find the highest-numbered generation under `root`, or None if empty.
pub fn latest_generation(root: &Path) -> Option<u32> {
    let mut best: Option<u32> = None;
    let rd = fs::read_dir(root).ok()?;
    for entry in rd.flatten() {
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        if let Some(stripped) = name_str.strip_prefix("gen_") {
            if let Ok(n) = stripped.parse::<u32>() {
                best = Some(best.map_or(n, |b| b.max(n)));
            }
        }
    }
    best
}

/// List all generation numbers under `root`, sorted ascending.
pub fn list_generations(root: &Path) -> Vec<u32> {
    let mut out = Vec::new();
    if let Ok(rd) = fs::read_dir(root) {
        for entry in rd.flatten() {
            let name = entry.file_name();
            if let Some(stripped) = name.to_string_lossy().strip_prefix("gen_") {
                if let Ok(n) = stripped.parse::<u32>() {
                    out.push(n);
                }
            }
        }
    }
    out.sort_unstable();
    out
}

/// Helper: canonical generation directory path.
pub fn gen_dir(root: &Path, gen: u32) -> PathBuf {
    root.join(format!("gen_{:03}", gen))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn save_and_load_round_trip() {
        let tmp = std::env::temp_dir().join("ptcgp_checkpoint_roundtrip");
        let _ = fs::remove_dir_all(&tmp);

        let net = ValueNet::new(Device::Cpu).expect("create net");
        let meta = Meta::new(0);

        save_generation(&tmp, 0, &net, None, &meta).expect("save");
        let (_net2, meta2, buf2) =
            load_generation(&tmp, 0, Device::Cpu, 100).expect("load");
        assert_eq!(meta.generation, meta2.generation);
        assert_eq!(meta.feature_version, meta2.feature_version);
        assert_eq!(buf2.len(), 0);

        assert_eq!(latest_generation(&tmp), Some(0));
        assert_eq!(list_generations(&tmp), vec![0]);

        let _ = fs::remove_dir_all(&tmp);
    }
}
