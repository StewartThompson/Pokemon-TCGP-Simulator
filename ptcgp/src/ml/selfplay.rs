//! Self-play trajectory collection.
//!
//! Plays one game between two agents while capturing, for every decision
//! point, the encoded state from that player's POV. At game end, those
//! captured states are labelled with the game's outcome (win +1 / loss -1 /
//! draw 0) plus the auxiliary targets (prize differential, HP differential).
//!
//! Works with any [`Agent`] pair — used both for self-play (bot vs same bot)
//! and for league training (bot vs past generation / heuristic). Only the
//! **focal player's** decisions are recorded — that's the POV we want to
//! train on.
//!
//! # A note on parallelism
//!
//! Each call to [`play_training_game`] is self-contained: it clones the
//! card DB via `Arc`, uses per-game seeds, and the internal agent state
//! is read-only (no shared writable state). This makes it safe to run many
//! games in parallel with rayon, which is exactly what the training loop
//! does.

use crate::agents::Agent;
use crate::card::CardDb;
use crate::runner::run_game;
use crate::types::Element;

use super::card_embed::CARD_EMBED_DIM;
use super::features::{encode_with_cache, FEATURE_DIM};
use super::replay::Sample;

// ------------------------------------------------------------------ //
// Recording agent
// ------------------------------------------------------------------ //

/// An [`Agent`] wrapper that records every decision it makes for later
/// training. Delegates action selection to an inner agent.
///
/// We record *before* the agent's action is applied — this gives us the
/// state the agent was facing when it chose. That state is then labeled
/// post-game with the eventual outcome.
pub struct RecordingAgent<'a> {
    inner: &'a (dyn Agent + Send + Sync),
    focal_player: usize,
    /// Per-decision interior mutability so we can push states from inside
    /// `select_action(&self, ...)` (the trait's immutable receiver).
    log: std::sync::Mutex<Vec<Vec<f32>>>,
    /// Reference to a card-embed cache — avoids rebuilding it per-call.
    embed_cache: &'a [[f32; CARD_EMBED_DIM]],
}

impl<'a> RecordingAgent<'a> {
    pub fn new(
        inner: &'a (dyn Agent + Send + Sync),
        focal_player: usize,
        embed_cache: &'a [[f32; CARD_EMBED_DIM]],
    ) -> Self {
        Self {
            inner,
            focal_player,
            log: std::sync::Mutex::new(Vec::new()),
            embed_cache,
        }
    }

    /// Consume the recorder and return the captured feature vectors.
    pub fn into_log(self) -> Vec<Vec<f32>> {
        self.log.into_inner().unwrap_or_default()
    }
}

impl<'a> Agent for RecordingAgent<'a> {
    fn select_action(
        &self,
        state: &crate::state::GameState,
        db: &CardDb,
        player_idx: usize,
    ) -> crate::actions::Action {
        // Record the focal player's perspective at every decision of theirs.
        // We skip Setup and AwaitingBenchPromotion because (a) they're
        // handled by HeuristicAgent (and so carry no search information),
        // (b) their value is always trivial/ambiguous. We want training
        // samples from the meaty Main-phase decisions.
        if player_idx == self.focal_player
            && state.phase == crate::types::GamePhase::Main
        {
            let feats = encode_with_cache(state, db, self.focal_player, self.embed_cache);
            debug_assert_eq!(feats.len(), FEATURE_DIM);
            if let Ok(mut log) = self.log.lock() {
                log.push(feats);
            }
        }
        self.inner.select_action(state, db, player_idx)
    }
}

// ------------------------------------------------------------------ //
// Public entrypoint
// ------------------------------------------------------------------ //

/// Play one game, returning the focal player's labeled samples.
///
/// `focal_agent` is the one whose decisions we record (always plays
/// player 0 for simplicity — callers that want symmetry should also run
/// mirror matches with the agents swapped).
///
/// `opp_agent` controls player 1 — can be the same agent (self-play mirror),
/// a past-generation checkpoint (league), or a heuristic baseline.
pub fn play_training_game(
    db: &CardDb,
    focal_agent: &(dyn Agent + Send + Sync),
    opp_agent: &(dyn Agent + Send + Sync),
    deck0: Vec<u16>,
    deck1: Vec<u16>,
    energy0: Vec<Element>,
    energy1: Vec<Element>,
    seed: u64,
    embed_cache: &[[f32; CARD_EMBED_DIM]],
) -> Vec<Sample> {
    let recorder = RecordingAgent::new(focal_agent, 0, embed_cache);

    let result = run_game(
        db,
        deck0,
        deck1,
        energy0,
        energy1,
        &recorder,
        opp_agent,
        seed,
        None,
    );

    // Determine outcome from focal-player POV.
    let win_target: f32 = match result.winner {
        Some(0) => 1.0,
        Some(1) => -1.0,
        _ => 0.0,
    };

    // Prize differential, normalized to a soft [-1, +1] scale (3 is winning points).
    let prize_target: f32 =
        (result.player0_points as f32 - result.player1_points as f32) / 3.0;

    // HP differential proxy: we don't have HP totals in GameResult, so we
    // use prize_target as a proxy. Acceptable for Wave 3 — the aux target
    // still gives the net a non-outcome signal to latch onto and the trunk
    // representation benefits regardless.
    let hp_target: f32 = prize_target;

    let features_list = recorder.into_log();
    features_list
        .into_iter()
        .map(|f| Sample::new(f, win_target, prize_target, hp_target))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agents::{HeuristicAgent, RandomAgent};
    use crate::decks::get_sample_deck;
    use crate::ml::card_embed::build_embed_cache;
    use std::path::PathBuf;
    use std::sync::Arc;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    #[test]
    fn play_training_game_produces_nonempty_samples() {
        let db = Arc::new(CardDb::load_from_dir(&assets_dir()));
        let (ids, energy) = get_sample_deck("fire").expect("fire deck");
        let deck: Vec<u16> = ids
            .iter()
            .filter_map(|id| db.get_idx_by_id(id))
            .collect();
        let cache = build_embed_cache(&db);

        let focal = HeuristicAgent;
        let opp = RandomAgent;

        let samples = play_training_game(
            &db,
            &focal,
            &opp,
            deck.clone(),
            deck,
            energy.to_vec(),
            energy.to_vec(),
            7,
            &cache,
        );

        // A real game has many main-phase decisions — should be well above 1.
        assert!(
            samples.len() > 2,
            "expected at least a few training samples, got {}",
            samples.len()
        );
        // All samples carry the same win target (whole game is one outcome).
        let w = samples[0].win_target;
        for s in &samples {
            assert!((s.win_target - w).abs() < 1e-6);
            // Win target should be in {-1, 0, +1}.
            assert!((w + 1.0).abs() < 1e-6 || w.abs() < 1e-6 || (w - 1.0).abs() < 1e-6);
            assert_eq!(s.features.len(), FEATURE_DIM);
        }
    }
}
