//! Turn management functions — start and end player turns.
//!
//! Ported from `ptcgp/engine/turn.py`.

use rand::seq::SliceRandom;
use crate::card::CardDb;
use crate::state::{GameState, PokemonSlot};
use crate::types::GamePhase;
use super::checkup::resolve_between_turns;
use super::ko::check_and_handle_kos;

/// Promote a slot's `_incoming` two-phase next-turn flags to their active
/// counterparts.  Called at start_turn for slots belonging to the player
/// whose turn is starting (Bug 1 fix — flags now actually apply to the
/// affected player rather than being cleared at the source player's turn-end).
fn promote_slot_incoming_flags(slot: &mut PokemonSlot) {
    slot.cant_attack_next_turn = slot.cant_attack_next_turn_incoming;
    slot.cant_attack_next_turn_incoming = false;
    slot.cant_retreat_next_turn = slot.cant_retreat_next_turn_incoming;
    slot.cant_retreat_next_turn_incoming = false;
    slot.prevent_damage_next_turn = slot.prevent_damage_next_turn_incoming;
    slot.prevent_damage_next_turn_incoming = false;
    slot.incoming_damage_reduction = slot.incoming_damage_reduction_incoming;
    slot.incoming_damage_reduction_incoming = 0;
    slot.attack_bonus_next_turn_self = slot.attack_bonus_next_turn_self_incoming;
    slot.attack_bonus_next_turn_self_incoming = 0;
}

/// Called at the start of each turn:
/// - Increments `turn_number` (first call takes it from -1 → 0).
/// - Increments `turns_in_play` for all current player's Pokemon.
/// - Resets per-turn player flags and per-slot flags.
/// - Draws a card (skipped on turn 0).
/// - Generates energy (skipped on turn 0).
pub fn start_turn(state: &mut GameState, db: &CardDb) {
    let _ = db; // reserved for future use (e.g. ability triggers on turn start)

    state.turn_number += 1;

    // Collect indices of occupied bench slots to avoid borrow issues.
    let current = state.current_player;

    // Increment turns_in_play and reset per-slot flags.
    // Also promote per-slot two-phase next-turn flags from `_incoming` to
    // active for the player whose turn is starting (Bug 1 fix).
    if let Some(ref mut slot) = state.players[current].active {
        slot.turns_in_play += 1;
        slot.evolved_this_turn = false;
        slot.ability_used_this_turn = false;
        promote_slot_incoming_flags(slot);
    }
    for bench_slot in state.players[current].bench.iter_mut() {
        if let Some(ref mut slot) = bench_slot {
            slot.turns_in_play += 1;
            slot.evolved_this_turn = false;
            slot.ability_used_this_turn = false;
            promote_slot_incoming_flags(slot);
        }
    }

    // Reset per-turn player flags.
    state.players[current].has_attached_energy = false;
    state.players[current].has_played_supporter = false;
    state.players[current].has_retreated = false;

    // Turn-scoped buffs reset each turn.
    state.players[current].attack_damage_bonus = 0;
    state.players[current].attack_damage_bonus_names.clear();
    state.players[current].retreat_cost_modifier = 0;

    // Promote incoming supporter-ban flag to "this turn".
    state.players[current].cant_play_supporter_this_turn =
        state.players[current].cant_play_supporter_incoming;
    state.players[current].cant_play_supporter_incoming = false;

    // Reset cant_heal_this_turn for BOTH players each start_turn.  PassiveNoHealing
    // (e.g. Claydol Heal Block) re-applies the flag whenever the passive
    // dispatch fires; this reset prevents stale blocks from persisting across
    // turns when the source Pokémon is no longer in play.
    state.players[0].cant_heal_this_turn = false;
    state.players[1].cant_heal_this_turn = false;

    // Promote incoming item-ban flag to "this turn".
    state.players[current].cant_play_items_this_turn =
        state.players[current].cant_play_items_incoming;
    state.players[current].cant_play_items_incoming = false;

    // Promote incoming energy-attach-ban flag to "this turn".
    state.players[current].cant_attach_energy_this_turn =
        state.players[current].cant_attach_energy_incoming;
    state.players[current].cant_attach_energy_incoming = false;

    // Turn 0 = first player's very first turn: skip draw and energy.
    if state.turn_number == 0 {
        return;
    }

    // Draw a card if deck is not empty.
    if let Some(card_idx) = state.players[current].deck.pop() {
        state.players[current].hand.push(card_idx);
    }

    // Generate energy: pick randomly from this player's energy pool.
    if !state.players[current].energy_types.is_empty() {
        let chosen = *state.players[current].energy_types
            .choose(&mut state.rng)
            .expect("energy_types non-empty but choose returned None");
        state.players[current].energy_available = Some(chosen);
    }
}

/// Called at the end of each turn: clear end-of-turn slot flags, switch current_player.
pub fn end_turn(state: &mut GameState) {
    let current = state.current_player;

    for bench_slot in state.players[current].bench.iter_mut() {
        if let Some(ref mut slot) = bench_slot {
            slot.cant_attack_next_turn = false;
            slot.cant_retreat_next_turn = false;
            slot.prevent_damage_next_turn = false;
            slot.incoming_damage_reduction = 0;
            slot.attack_bonus_next_turn_self = 0;
        }
    }
    if let Some(ref mut slot) = state.players[current].active {
        slot.cant_attack_next_turn = false;
        slot.cant_retreat_next_turn = false;
        slot.prevent_damage_next_turn = false;
        slot.incoming_damage_reduction = 0;
        slot.attack_bonus_next_turn_self = 0;
    }

    state.players[current].energy_available = None;
    state.players[current].cant_play_supporter_this_turn = false;
    state.players[current].cant_play_items_this_turn = false;
    state.players[current].cant_attach_energy_this_turn = false;

    state.current_player = 1 - state.current_player;
}

/// Full turn transition: checkup status effects → KO check → end_turn → start_turn.
///
/// Called after a player ends their turn with the END_TURN action.
/// If a winner is found or the game is in `AwaitingBenchPromotion` after the
/// between-turns sequence, the function returns early without starting the next turn.
pub fn advance_turn(state: &mut GameState, db: &CardDb) {
    resolve_between_turns(state, db);
    check_and_handle_kos(state, db);

    if state.winner.is_some() {
        return;
    }
    if state.phase == GamePhase::AwaitingBenchPromotion {
        return;
    }

    end_turn(state);

    if state.winner.is_none() && state.phase == GamePhase::Main {
        start_turn(state, db);
    }
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::CardDb;
    use crate::state::PokemonSlot;
    use crate::types::{Element, GamePhase};
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

    fn make_state_with_deck(db: &CardDb) -> GameState {
        let bulbasaur = db.get_by_id("a1-001").expect("a1-001 not found");
        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        state.turn_number = -1;
        let deck: Vec<u16> = vec![bulbasaur.idx; 20];
        state.players[0].deck = deck.clone();
        state.players[1].deck = deck;
        state.players[0].energy_types = vec![Element::Grass];
        state.players[1].energy_types = vec![Element::Grass];
        // Set active Pokemon for both players so the state is valid.
        state.players[0].active = Some(PokemonSlot::new(bulbasaur.idx, bulbasaur.hp));
        state.players[1].active = Some(PokemonSlot::new(bulbasaur.idx, bulbasaur.hp));
        state
    }

    #[test]
    fn start_turn_increments_turn_number() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        assert_eq!(state.turn_number, -1);
        start_turn(&mut state, &db);
        assert_eq!(state.turn_number, 0);
        // Subsequent call (turn 0 → 1 requires end_turn first to switch player, then start_turn).
        end_turn(&mut state);
        start_turn(&mut state, &db);
        assert_eq!(state.turn_number, 1);
    }

    #[test]
    fn start_turn_zero_skips_draw_and_energy() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        let deck_before = state.players[0].deck.len();
        start_turn(&mut state, &db);
        // Turn 0: no draw, no energy.
        assert_eq!(state.players[0].hand.len(), 0);
        assert_eq!(state.players[0].deck.len(), deck_before);
        assert_eq!(state.players[0].energy_available, None);
    }

    #[test]
    fn start_turn_nonzero_draws_card_and_generates_energy() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        // Advance past turn 0.
        start_turn(&mut state, &db); // turn 0 for player 0
        end_turn(&mut state);
        // Now player 1's turn 1.
        let deck_before = state.players[1].deck.len();
        let hand_before = state.players[1].hand.len();
        start_turn(&mut state, &db);
        assert_eq!(state.players[1].hand.len(), hand_before + 1);
        assert_eq!(state.players[1].deck.len(), deck_before - 1);
        assert!(state.players[1].energy_available.is_some());
    }

    #[test]
    fn start_turn_energy_is_set_from_pool() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        state.players[0].energy_types = vec![Element::Fire];
        // Advance to a non-zero turn for player 0.
        start_turn(&mut state, &db); // turn 0
        end_turn(&mut state);
        start_turn(&mut state, &db); // player 1 turn 1
        end_turn(&mut state);
        start_turn(&mut state, &db); // player 0 turn 2
        // Player 0 only has Fire in pool.
        assert_eq!(state.players[0].energy_available, Some(Element::Fire));
    }

    #[test]
    fn end_turn_switches_player() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        state.current_player = 0;
        end_turn(&mut state);
        assert_eq!(state.current_player, 1);
        end_turn(&mut state);
        assert_eq!(state.current_player, 0);
    }

    #[test]
    fn advance_turn_increments_turn_number() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        // Set up so we're starting from a valid point.
        start_turn(&mut state, &db); // turn 0
        assert_eq!(state.turn_number, 0);
        advance_turn(&mut state, &db); // end turn 0, start turn 1
        assert_eq!(state.turn_number, 1);
    }

    #[test]
    fn per_turn_flags_reset_on_start_turn() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        start_turn(&mut state, &db); // turn 0
        state.players[0].has_attached_energy = true;
        state.players[0].has_played_supporter = true;
        state.players[0].has_retreated = true;
        end_turn(&mut state);
        start_turn(&mut state, &db); // player 1 turn 1
        end_turn(&mut state);
        start_turn(&mut state, &db); // player 0 turn 2
        assert!(!state.players[0].has_attached_energy);
        assert!(!state.players[0].has_played_supporter);
        assert!(!state.players[0].has_retreated);
    }

    // -- Bug 1: two-phase promotion of next-turn flags --
    #[test]
    fn incoming_next_turn_flags_promote_at_affected_player_start_turn() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);

        // Player 0's turn starts.
        start_turn(&mut state, &db); // turn 0, current_player = 0

        // Simulate an opponent effect setting the "incoming" cant_attack flag
        // on player 1's active during player 0's turn.
        state.players[1]
            .active
            .as_mut()
            .unwrap()
            .cant_attack_next_turn_incoming = true;

        // End player 0's turn.
        end_turn(&mut state);
        // The incoming flag must NOT have been cleared by player 0's end_turn.
        assert!(
            state.players[1].active.as_ref().unwrap().cant_attack_next_turn_incoming,
            "Incoming flag must survive the source player's end_turn"
        );
        assert!(
            !state.players[1].active.as_ref().unwrap().cant_attack_next_turn,
            "Active flag should not be set yet"
        );

        // Player 1's turn begins — incoming should promote to active.
        start_turn(&mut state, &db);
        assert!(
            state.players[1].active.as_ref().unwrap().cant_attack_next_turn,
            "Active flag should now be set on the affected player"
        );
        assert!(
            !state.players[1].active.as_ref().unwrap().cant_attack_next_turn_incoming,
            "Incoming flag should be cleared after promotion"
        );

        // Player 1 ends their turn — active flag should be cleared now.
        end_turn(&mut state);
        assert!(
            !state.players[1].active.as_ref().unwrap().cant_attack_next_turn,
            "Active flag should be cleared at end of affected player's turn"
        );
    }

    #[test]
    fn turns_in_play_increments_each_turn() {
        let db = load_db();
        let mut state = make_state_with_deck(&db);
        start_turn(&mut state, &db); // turn 0 for p0
        assert_eq!(state.players[0].active.as_ref().unwrap().turns_in_play, 1);
        end_turn(&mut state);
        start_turn(&mut state, &db); // turn 1 for p1
        assert_eq!(state.players[1].active.as_ref().unwrap().turns_in_play, 1);
        end_turn(&mut state);
        start_turn(&mut state, &db); // turn 2 for p0
        assert_eq!(state.players[0].active.as_ref().unwrap().turns_in_play, 2);
    }
}
