//! Re-sample the opponent's hidden information so MCTS can't cheat.
//!
//! PTCGP has two kinds of hidden info the acting player cannot see:
//!
//! 1. **Opponent's hand identities.** We only know the count.
//! 2. **Opponent's remaining deck order.** We know the cards but not their
//!    ordering. (Deck *identity* is considered public in our training setup
//!    because we pick from a known pool.)
//!
//! If MCTS works on the raw `GameState` the agent gets from
//! [`crate::agents::Agent::select_action`], it will happily peek at
//! `state.players[opp].hand` during rollouts — turning into a cheating bot
//! that wildly overestimates its win rate. This is called *strategy fusion*.
//!
//! # Wave 1 policy
//!
//! Single determinization per MCTS call (one sample for the whole search):
//!   - Pool opponent's visible hand + remaining deck.
//!   - Shuffle.
//!   - Deal a new hand of the same size; put the rest back as their deck.
//!
//! Wave 3 will upgrade to **per-rollout determinization (PIMC)** which
//! averages over K samples and eliminates the residual bias of a single
//! sample. For now, single-sample is enough to unblock the "MCTS beats
//! Heuristic" strength gate without opening the cheat door wide.

use rand::seq::SliceRandom;
use rand::SeedableRng;
use rand::rngs::SmallRng;

use crate::state::GameState;

/// Return a clone of `state` with the opponent's hand + deck order randomized.
///
/// `acting_player` is the perspective whose MCTS is about to run. Everything
/// visible to that player (both boards, discards, point totals, own hand,
/// own deck, per-slot stats) is preserved verbatim. Only the opponent's
/// hand-card identities and deck ordering change.
///
/// We also re-seed the cloned state's RNG so that many independent
/// simulations starting from this determinization don't all follow the
/// same random path (coin flips, energy generation). Without this, every
/// simulated playout is identical — defeating Monte Carlo sampling.
pub fn determinize_for(state: &GameState, acting_player: usize, rng_seed: u64) -> GameState {
    debug_assert!(acting_player < 2);
    let opp = 1 - acting_player;
    let mut s = state.clone();
    let mut rng = SmallRng::seed_from_u64(rng_seed);

    // Pool everything the opponent has that the acting player can't see
    // (hand + remaining deck), shuffle, then split back.
    let hand_size = s.players[opp].hand.len();
    let mut pool: Vec<u16> = s.players[opp].hand.drain(..).collect();
    pool.extend(s.players[opp].deck.drain(..));
    pool.shuffle(&mut rng);

    if hand_size > pool.len() {
        // Extreme edge case: shouldn't happen in practice. Re-populate what
        // we can and leave the deck empty.
        s.players[opp].hand = pool.into_iter().collect();
        s.players[opp].deck = smallvec::SmallVec::new();
    } else {
        let (new_hand, rest) = pool.split_at(hand_size);
        s.players[opp].hand = new_hand.iter().copied().collect();
        s.players[opp].deck = rest.iter().copied().collect();
    }

    // Re-seed so that cloned sims follow diverse random trajectories.
    s.rng = SmallRng::seed_from_u64(rng_seed ^ 0x9E37_79B9_7F4A_7C15);

    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::GamePhase;

    #[test]
    fn determinize_preserves_hand_size() {
        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.players[1].hand = smallvec::smallvec![1, 2, 3, 4, 5];
        state.players[1].deck = smallvec::smallvec![10, 11, 12, 13, 14, 15];

        let d = determinize_for(&state, 0, 42);
        assert_eq!(d.players[1].hand.len(), 5);
        assert_eq!(d.players[1].deck.len(), 6);

        // All original cards are still somewhere (hand or deck) — no creation/loss.
        let mut all: Vec<u16> = d.players[1].hand.iter().copied().collect();
        all.extend(d.players[1].deck.iter().copied());
        all.sort();
        assert_eq!(all, vec![1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15]);
    }

    #[test]
    fn determinize_different_seeds_produce_different_hands() {
        let mut state = GameState::new(0);
        state.players[1].hand = smallvec::smallvec![1, 2, 3, 4, 5];
        state.players[1].deck = smallvec::smallvec![10, 11, 12, 13, 14, 15, 16, 17];

        let a = determinize_for(&state, 0, 1);
        let b = determinize_for(&state, 0, 2);
        // At least one of hand or deck should differ across seeds.
        assert!(a.players[1].hand != b.players[1].hand || a.players[1].deck != b.players[1].deck);
    }

    #[test]
    fn determinize_leaves_acting_player_untouched() {
        let mut state = GameState::new(0);
        state.players[0].hand = smallvec::smallvec![100, 200, 300];
        state.players[0].deck = smallvec::smallvec![400, 500];

        let d = determinize_for(&state, 0, 42);
        assert_eq!(d.players[0].hand.as_slice(), &[100u16, 200, 300]);
        assert_eq!(d.players[0].deck.as_slice(), &[400u16, 500]);
    }
}
