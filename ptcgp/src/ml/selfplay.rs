//! Self-play trajectory collection.
//!
//! Plays one game between two agents while capturing, for every decision
//! point, the encoded state from that player's POV. At game end, those
//! captured states are labelled with the game's outcome (win +1 / loss -1 /
//! draw 0) plus the auxiliary targets (prize differential, HP differential).
//!
//! Works with any [`Agent`] pair — used both for self-play (bot vs same bot)
//! and for league training (bot vs past generation / heuristic). **Both**
//! players' decisions are recorded, each from their own POV, so the value
//! net learns a symmetric representation: "given the board from my POV,
//! predict whether I win."
//!
//! ## Why symmetric matters
//!
//! MCTS calls `net_value(state)` for leaf states where EITHER player may be
//! the current mover.  If training only ever sees player-0 features, the net
//! is completely out-of-distribution when asked to evaluate player-1-to-move
//! states.  Recording both players with their own POV features fixes this:
//! the net learns one consistent rule — "high output ⟹ the player whose
//! features I was given is likely to win" — and MCTS inference can safely
//! encode from `current_player`'s POV and negate when needed.
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
use super::mcts::RootQSource;
use super::replay::Sample;

// ------------------------------------------------------------------ //
// Recording agent
// ------------------------------------------------------------------ //

/// An [`Agent`] wrapper that records every main-phase decision it makes for
/// later training. Delegates action selection to an inner agent.
///
/// Each logged entry is `(feature_vector, player_idx, Option<root_q>)` so that
/// `play_training_game` can assign the correct per-player win target after
/// the game ends, optionally blending in the MCTS root Q-value.
///
/// We call the inner agent first, then capture the Q-value (if a
/// [`RootQSource`] was provided), then push to the log. This ordering is
/// important: the inner agent must run its MCTS before we read the Q.
pub struct RecordingAgent<'a> {
    inner: &'a (dyn Agent + Send + Sync),
    /// Optional Q-value source — typically the same [`MctsAgent`] object as
    /// `inner`. When `Some`, each logged entry includes the root Q-value that
    /// the MCTS search computed for that decision.
    q_source: Option<&'a (dyn RootQSource + Send + Sync)>,
    /// Per-decision interior mutability so we can push states from inside
    /// `select_action(&self, ...)` (the trait's immutable receiver).
    /// Each entry: (feature_vector, player_idx_that_acted, optional_root_q).
    log: std::sync::Mutex<Vec<(Vec<f32>, usize, Option<f32>)>>,
    /// Reference to a card-embed cache — avoids rebuilding it per-call.
    embed_cache: &'a [[f32; CARD_EMBED_DIM]],
}

impl<'a> RecordingAgent<'a> {
    pub fn new(
        inner: &'a (dyn Agent + Send + Sync),
        embed_cache: &'a [[f32; CARD_EMBED_DIM]],
    ) -> Self {
        Self {
            inner,
            q_source: None,
            log: std::sync::Mutex::new(Vec::new()),
            embed_cache,
        }
    }

    /// Attach a [`RootQSource`] (typically the same `MctsAgent` as `inner`)
    /// so that MCTS root Q-values are captured alongside each decision.
    pub fn with_q_source(mut self, qs: &'a (dyn RootQSource + Send + Sync)) -> Self {
        self.q_source = Some(qs);
        self
    }

    /// Consume the recorder and return the captured `(features, player_idx, root_q)` triples.
    pub fn into_log(self) -> Vec<(Vec<f32>, usize, Option<f32>)> {
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
        // Record every main-phase decision from this player's own POV.
        // We skip Setup and AwaitingBenchPromotion because (a) they're
        // handled by HeuristicAgent (and so carry no search information),
        // (b) their value is always trivial/ambiguous. We want training
        // samples from the meaty Main-phase decisions only.
        if state.phase == crate::types::GamePhase::Main {
            // Encode from the acting player's perspective — symmetric training.
            // We must encode BEFORE calling inner (state is not mutated by select_action,
            // so order doesn't matter for features), but we call inner BEFORE reading Q
            // so that MCTS has finished its sims when we sample last_root_q().
            let feats = encode_with_cache(state, db, player_idx, self.embed_cache);
            debug_assert_eq!(feats.len(), FEATURE_DIM);
            let action = self.inner.select_action(state, db, player_idx);
            // Read Q after the inner search completes. None for fast-path moves
            // (setup phase delegated to heuristic, trivial single-action turns).
            let maybe_q = self.q_source.and_then(|qs| qs.last_root_q());
            if let Ok(mut log) = self.log.lock() {
                log.push((feats, player_idx, maybe_q));
            }
            return action;
        }
        self.inner.select_action(state, db, player_idx)
    }
}

// ------------------------------------------------------------------ //
// Public entrypoint
// ------------------------------------------------------------------ //

/// Play one game, returning labeled training samples from **both** players.
///
/// Each sample carries:
/// - `features`: board state from the acting player's POV at that decision.
/// - `win_target`:  +1 if *that player* won, −1 if they lost (optionally
///   blended with the MCTS root Q-value — see `focal_q_source` / `q_blend`).
/// - `prize_target`: (my_prizes − opp_prizes) / 3 from that player's POV.
///
/// Both agents are wrapped in recorders, so mirror-match self-play
/// naturally doubles the training data without any extra games.
///
/// # Q-value blending
///
/// When `focal_q_source` is `Some(qs)` and `q_blend > 0`, the win target for
/// focal-agent decisions is blended:
///
/// ```text
/// win_target = (1 - q_blend) * game_outcome  +  q_blend * mcts_root_q
/// ```
///
/// `mcts_root_q` is the mean backed-up value over all MCTS simulations — its
/// variance is ~1/N vs 1/1 for the single game outcome, which substantially
/// reduces label noise. Passing `focal_q_source: None` or `q_blend: 0.0` is
/// equivalent to the pure game-outcome baseline.
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
    focal_q_source: Option<&(dyn RootQSource + Send + Sync)>,
    q_blend: f32,
) -> Vec<Sample> {
    let recorder0 = if let Some(qs) = focal_q_source {
        RecordingAgent::new(focal_agent, embed_cache).with_q_source(qs)
    } else {
        RecordingAgent::new(focal_agent, embed_cache)
    };
    let recorder1 = RecordingAgent::new(opp_agent, embed_cache);

    let result = run_game(
        db,
        deck0,
        deck1,
        energy0,
        energy1,
        &recorder0,
        &recorder1,
        seed,
        None,
    );

    let log0 = recorder0.into_log();
    let log1 = recorder1.into_log();

    log0.into_iter()
        .chain(log1)
        .map(|(feats, player_idx, maybe_q)| {
            // Game outcome from this player's POV: +1 win, -1 loss, 0 draw.
            let game_outcome: f32 = match result.winner {
                Some(w) if w as usize == player_idx => 1.0,
                Some(_) => -1.0,
                _ => 0.0,
            };
            // Blend MCTS root Q into the win target when available.
            // Root Q = mean backed-up value over all sims — variance ~1/N.
            // Game outcome variance = 1. Blending reduces label noise by ~sqrt(N).
            // Q is already from the acting player's POV (MctsAgent encodes from
            // player_idx's perspective and stores Q in that same frame).
            let win_target: f32 = if q_blend > 0.0 {
                if let Some(q) = maybe_q {
                    (1.0 - q_blend) * game_outcome + q_blend * q
                } else {
                    game_outcome
                }
            } else {
                game_outcome
            };
            // Prize differential from this player's POV: (my_prizes - opp_prizes) / 3.
            let prize_sign: f32 = if player_idx == 0 { 1.0 } else { -1.0 };
            let prize_target: f32 =
                prize_sign * (result.player0_points as f32 - result.player1_points as f32) / 3.0;
            // HP-proxy target: game tempo signal — did this player win *quickly*?
            // Shorter games = more lopsided outcomes = higher magnitude.
            // Normalized so a 10-turn win ≈ +0.8, a 40-turn win ≈ +0.2, loss = negative.
            // This is distinct from the prize differential (which only depends on
            // final point counts, not how long the game lasted) and gives the shared
            // trunk a complementary training signal.
            let max_turns = 50.0f32;
            let tempo = 1.0 - (result.turns as f32 / max_turns).min(1.0);
            let hp_target: f32 = win_target * tempo;

            Sample::new(feats, win_target, prize_target, hp_target)
        })
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
        let (ids, energy) = get_sample_deck("charizard").expect("charizard deck");
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
            None,  // no Q source (HeuristicAgent has no MCTS Q)
            0.0,   // no blending
        );

        // Both players are recorded, so we get ~2x the samples of the old design.
        assert!(
            samples.len() > 2,
            "expected at least a few training samples, got {}",
            samples.len()
        );
        // Samples are from both players — win targets are NOT all the same.
        // Each sample's win_target should be in {-1, 0, +1}.
        for s in &samples {
            assert!(
                (s.win_target + 1.0).abs() < 1e-6
                    || s.win_target.abs() < 1e-6
                    || (s.win_target - 1.0).abs() < 1e-6,
                "win_target {} is not in {{-1, 0, +1}}",
                s.win_target
            );
            assert_eq!(s.features.len(), FEATURE_DIM);
        }
    }
}
