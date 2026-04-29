//! Pure value-net action scorer — no tree search.
//!
//! For each legal action: clone the state, apply the action, encode features,
//! let the NN predict `win_value` for the resulting state, pick the action
//! that leads to the best predicted state.
//!
//! Two orders of magnitude faster than `MctsAgent` because there's no tree
//! search: a call is just `(num_legal_actions) × forward_pass`. On a typical
//! PTCGP state that's ~5-15 forward passes per decision instead of the
//! ~240×depth passes an MCTS agent performs.
//!
//! Correspondingly weaker. Think of it as "what the trained NN thinks is
//! best, no lookahead". Good for fast tournaments where you want an
//! NN-driven baseline without waiting for MCTS.

use std::sync::Arc;

use crate::actions::Action;
use crate::agents::{Agent, HeuristicAgent};
use crate::card::CardDb;
use crate::engine::legal_actions::{
    get_legal_actions, get_legal_promotions, get_legal_setup_bench_placements,
    get_legal_setup_placements,
};
use crate::engine::{ko, mutations, turn};
use crate::state::GameState;
use crate::types::{ActionKind, GamePhase};

use super::card_embed::{build_embed_cache, CARD_EMBED_DIM};
use super::features::encode_with_cache;
use super::net::ValueNet;

/// Greedy NN action scorer. Implements [`Agent`].
pub struct NnGreedyAgent {
    pub net: Arc<ValueNet>,
    pub embed_cache: Arc<Vec<[f32; CARD_EMBED_DIM]>>,
    /// Use the Heuristic agent for trivial phases (setup, promotion).
    /// These aren't interesting for the NN and the heuristic has sensible
    /// priors encoded for them.
    pub delegate_setup: bool,
}

impl NnGreedyAgent {
    pub fn new(net: Arc<ValueNet>, db: &Arc<CardDb>) -> Self {
        Self {
            net,
            embed_cache: Arc::new(build_embed_cache(db)),
            delegate_setup: true,
        }
    }
}

impl Agent for NnGreedyAgent {
    fn select_action(&self, state: &GameState, db: &CardDb, player_idx: usize) -> Action {
        // Delegate trivial phases, same as MctsAgent.
        if self.delegate_setup {
            match state.phase {
                GamePhase::Setup | GamePhase::AwaitingBenchPromotion => {
                    return HeuristicAgent.select_action(state, db, player_idx);
                }
                _ => {}
            }
        }

        let legal = match state.phase {
            GamePhase::Setup => {
                if state.players[player_idx].active.is_some() {
                    get_legal_setup_bench_placements(state, db, player_idx)
                } else {
                    get_legal_setup_placements(state, db, player_idx)
                }
            }
            GamePhase::AwaitingBenchPromotion => get_legal_promotions(state, player_idx),
            GamePhase::GameOver => return Action::end_turn(),
            GamePhase::Main => get_legal_actions(state, db),
        };

        if legal.is_empty() {
            return Action::end_turn();
        }
        if legal.len() == 1 {
            return legal.into_iter().next().unwrap();
        }

        // Score every legal action by applying + evaluating.
        // Higher NN value-from-our-POV = better.
        let mut best_idx = 0usize;
        let mut best_score = f32::NEG_INFINITY;
        for (i, action) in legal.iter().enumerate() {
            let mut sim = state.clone();
            apply_and_settle(&mut sim, db, action);

            // If action ended the game, short-circuit.
            let score: f32 = if let Some(w) = sim.winner {
                if w == player_idx as i8 {
                    1.0
                } else if w >= 0 {
                    -1.0
                } else {
                    0.0
                }
            } else {
                let features = encode_with_cache(&sim, db, player_idx, &self.embed_cache);
                self.net.win_value(&features).unwrap_or(0.0)
            };

            if score > best_score {
                best_score = score;
                best_idx = i;
            }
        }
        legal.into_iter().nth(best_idx).unwrap_or_else(Action::end_turn)
    }
}

/// Mirror of [`crate::ml::mcts`]'s private helper — apply the action and
/// then do the runner's post-action settle (KOs + turn advance on Attack).
fn apply_and_settle(state: &mut GameState, db: &CardDb, action: &Action) {
    let kind = action.kind;
    mutations::apply_action(state, db, action);
    if kind == ActionKind::Attack
        && state.phase == GamePhase::Main
        && state.winner.is_none()
    {
        ko::check_and_handle_kos(state, db);
        if state.winner.is_none() && state.phase == GamePhase::Main {
            turn::advance_turn(state, db);
        }
    }
}
