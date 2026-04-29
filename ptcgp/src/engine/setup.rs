//! Game setup functions — create and initialize a GameState for play.
//!
//! Ported from `ptcgp/engine/setup.py`.

use rand::seq::SliceRandom;
use crate::card::CardDb;
use crate::constants::{BENCH_SIZE, INITIAL_HAND_SIZE};
use crate::state::{GameState, PokemonSlot};
use crate::types::{CardKind, GamePhase, Stage, Element};
use crate::engine::turn::start_turn;

/// Initialize a new game with the given decks and energy pools.
///
/// Does NOT shuffle decks or draw hands; call `draw_opening_hands` and
/// `finalize_setup` for that.
pub fn create_game(
    db: &CardDb,
    deck1: Vec<u16>,
    deck2: Vec<u16>,
    energy_types1: Vec<Element>,
    energy_types2: Vec<Element>,
    seed: u64,
) -> GameState {
    let _ = db; // db not needed at creation, but kept for API symmetry
    let mut state = GameState::new(seed);

    state.players[0].deck = deck1.into();
    state.players[0].energy_types = energy_types1.into();

    state.players[1].deck = deck2.into();
    state.players[1].energy_types = energy_types2.into();

    state.phase = GamePhase::Setup;
    state
}

/// Shuffle decks and draw opening hands for both players (with mulligan).
///
/// If no Basic Pokemon is in a player's hand, the hand is shuffled back
/// and redrawn until at least one Basic is found.
pub fn draw_opening_hands(state: &mut GameState, db: &CardDb) {
    draw_opening_hand_for_player(state, db, 0);
    draw_opening_hand_for_player(state, db, 1);
}

fn draw_opening_hand_for_player(state: &mut GameState, db: &CardDb, player_idx: usize) {
    loop {
        state.players[player_idx].deck.shuffle(&mut state.rng);

        let hand: smallvec::SmallVec<[u16; 12]> = state.players[player_idx].deck
            .drain(..INITIAL_HAND_SIZE.min(state.players[player_idx].deck.len()))
            .collect();

        // Check for at least one Basic Pokemon.
        let has_basic = hand.iter().any(|&idx| is_basic_pokemon(db, idx));

        if has_basic {
            state.players[player_idx].hand = hand;
            break;
        }

        // No basic — return hand to front of deck and retry.
        let mut deck: smallvec::SmallVec<[u16; 20]> = hand.into_iter().collect();
        deck.extend(state.players[player_idx].deck.drain(..));
        state.players[player_idx].deck = deck;
        state.players[player_idx].hand.clear();
    }

    // Reverse so "top" of deck is at the back — allows O(1) pop() draws.
    state.players[player_idx].deck.reverse();
}

/// Place setup choices: set active from hand (by hand index), optionally bench some basics.
///
/// Removes the placed cards from the player's hand.
pub fn apply_setup_placement(
    state: &mut GameState,
    db: &CardDb,
    player_idx: usize,
    active_hand_idx: usize,
    bench_hand_idxs: &[usize],
) {
    let card_idx = state.players[player_idx].hand[active_hand_idx];
    let card = db.get_by_idx(card_idx);
    let slot = PokemonSlot::new(card_idx, card.hp);
    state.players[player_idx].active = Some(slot);
    state.players[player_idx].hand.remove(active_hand_idx);

    // Place bench Pokemon (adjust indices after removal of active).
    // Sort descending so earlier removes don't shift later indices.
    let mut adjusted: Vec<usize> = bench_hand_idxs.iter()
        .take(BENCH_SIZE)
        .map(|&i| if i > active_hand_idx { i - 1 } else { i })
        .collect();
    adjusted.sort_unstable_by(|a, b| b.cmp(a));
    // Collect (bench_position, card_idx) pairs before removing from hand.
    let mut to_place: Vec<(usize, u16)> = Vec::new();
    for (bench_pos, hand_idx) in adjusted.iter().enumerate() {
        let ci = state.players[player_idx].hand[*hand_idx];
        to_place.push((bench_pos, ci));
    }
    // Now remove from hand (descending index order).
    for &hand_idx in &adjusted {
        state.players[player_idx].hand.remove(hand_idx);
    }
    // Place into bench slots.
    for (bench_pos, ci) in to_place {
        let card = db.get_by_idx(ci);
        state.players[player_idx].bench[bench_pos] = Some(PokemonSlot::new(ci, card.hp));
    }
}

/// Finalize setup: coin flip for first player, set phase to Main, call start_turn.
pub fn finalize_setup(state: &mut GameState, db: &CardDb) {
    use rand::Rng;
    state.first_player = if state.rng.gen::<f64>() < 0.5 { 0 } else { 1 };
    state.current_player = state.first_player;
    state.phase = GamePhase::Main;
    state.turn_number = -1;
    start_turn(state, db);
}

fn is_basic_pokemon(db: &CardDb, card_idx: u16) -> bool {
    let card = db.get_by_idx(card_idx);
    card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic)
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    fn load_db() -> CardDb {
        CardDb::load_from_dir(&assets_dir())
    }

    fn make_grass_deck(db: &CardDb) -> Vec<u16> {
        // Build a 20-card deck from basic Grass Pokemon (Bulbasaur a1-001 repeated).
        let bulbasaur = db.get_by_id("a1-001").expect("a1-001 not found");
        vec![bulbasaur.idx; 20]
    }

    #[test]
    fn create_game_correct_player_count() {
        let db = load_db();
        let deck = make_grass_deck(&db);
        let state = create_game(
            &db,
            deck.clone(),
            deck.clone(),
            vec![Element::Grass],
            vec![Element::Grass],
            42,
        );
        assert_eq!(state.players.len(), 2);
        assert_eq!(state.players[0].deck.len(), 20);
        assert_eq!(state.players[1].deck.len(), 20);
        assert_eq!(state.phase, GamePhase::Setup);
    }

    #[test]
    fn draw_opening_hands_gives_each_player_five_cards() {
        let db = load_db();
        let deck = make_grass_deck(&db);
        let mut state = create_game(
            &db,
            deck.clone(),
            deck.clone(),
            vec![Element::Grass],
            vec![Element::Grass],
            7,
        );
        draw_opening_hands(&mut state, &db);
        assert_eq!(state.players[0].hand.len(), INITIAL_HAND_SIZE);
        assert_eq!(state.players[1].hand.len(), INITIAL_HAND_SIZE);
        // Deck should have shrunk by INITIAL_HAND_SIZE each.
        assert_eq!(state.players[0].deck.len(), 20 - INITIAL_HAND_SIZE);
        assert_eq!(state.players[1].deck.len(), 20 - INITIAL_HAND_SIZE);
    }

    #[test]
    fn draw_opening_hands_contain_basic() {
        let db = load_db();
        let deck = make_grass_deck(&db);
        let mut state = create_game(
            &db,
            deck.clone(),
            deck.clone(),
            vec![Element::Grass],
            vec![Element::Grass],
            99,
        );
        draw_opening_hands(&mut state, &db);
        for pi in 0..2 {
            let has_basic = state.players[pi].hand.iter()
                .any(|&idx| is_basic_pokemon(&db, idx));
            assert!(has_basic, "Player {} hand has no basic Pokemon", pi);
        }
    }

    #[test]
    fn apply_setup_placement_removes_from_hand() {
        let db = load_db();
        let deck = make_grass_deck(&db);
        let mut state = create_game(
            &db,
            deck.clone(),
            deck.clone(),
            vec![Element::Grass],
            vec![Element::Grass],
            1,
        );
        draw_opening_hands(&mut state, &db);
        let initial_hand_size = state.players[0].hand.len();

        // Place first card as active (all are Bulbasaur basics here).
        apply_setup_placement(&mut state, &db, 0, 0, &[]);
        assert_eq!(state.players[0].hand.len(), initial_hand_size - 1);
        assert!(state.players[0].active.is_some());
    }
}
