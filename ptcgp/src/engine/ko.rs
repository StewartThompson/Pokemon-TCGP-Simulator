//! KO handling, bench promotion, and win condition checking.
//!
//! Ported from `ptcgp/engine/ko.py`.

use crate::card::CardDb;
use crate::constants::{POINTS_TO_WIN, MAX_TURNS};
use crate::state::{GameState, get_slot, set_slot};
use crate::actions::SlotRef;
use crate::types::GamePhase;

/// Handle a KO'd Pokemon at `ko_slot`:
///
/// 1. Award points to the opponent (1 for regular, 2 for EX, 3 for Mega EX).
/// 2. Move the Pokemon + its attached tool to the loser's discard pile.
/// 3. Remove the slot from play.
/// 4. Check win condition — set `state.winner` and phase to `GameOver` if
///    the scoring player has reached `POINTS_TO_WIN`, the KO'd Pokemon
///    awarded 3 points (Mega EX instant-win), or there are no Pokemon left.
/// 5. If the KO'd slot was the active and the bench still has Pokemon, set
///    phase to `AwaitingBenchPromotion`.
pub fn handle_ko(state: &mut GameState, db: &CardDb, ko_slot: SlotRef) {
    let slot = match get_slot(state, ko_slot) {
        Some(s) => s.clone(),
        None => return, // nothing to KO
    };

    let card = db.get_by_idx(slot.card_idx);
    let ko_points = card.ko_points;

    // Award points to the opponent (the one who caused the KO).
    let awarding_player = 1 - ko_slot.player as usize;
    state.players[awarding_player].points += ko_points;

    // Move the KO'd Pokemon (and its tool) to the losing player's discard pile.
    let loser = ko_slot.player as usize;
    state.players[loser].discard.push(slot.card_idx);
    if let Some(tool_idx) = slot.tool_idx {
        state.players[loser].discard.push(tool_idx);
    }

    // Remove the slot from play.
    set_slot(state, ko_slot, None);

    // -- Win-condition checks --

    let awarding_points = state.players[awarding_player].points;
    let other_points = state.players[loser].points;

    // Simultaneous KO tie: both players at >= POINTS_TO_WIN.
    if awarding_points >= POINTS_TO_WIN && other_points >= POINTS_TO_WIN {
        state.winner = Some(-1);
        state.phase = GamePhase::GameOver;
        return;
    }

    // Normal point-based win, or Mega EX instant-win (3 points).
    if awarding_points >= POINTS_TO_WIN || ko_points == 3 {
        state.winner = Some(awarding_player as i8);
        state.phase = GamePhase::GameOver;
        return;
    }

    // If the active was KO'd, check whether the losing player can promote.
    if ko_slot.is_active() {
        let has_bench = state.players[loser].bench.iter().any(|s| s.is_some());
        if has_bench {
            state.phase = GamePhase::AwaitingBenchPromotion;
        } else {
            // No Pokemon left — the losing player loses.
            state.winner = Some(awarding_player as i8);
            state.phase = GamePhase::GameOver;
        }
    }
}

/// Check whether any active Pokemon has `current_hp <= 0` and call
/// `handle_ko` for each one.  Also detects if a player has no Pokemon at
/// all (instant loss even without an explicit 0-hp check).
///
/// Returns `true` if at least one KO was processed.
pub fn check_and_handle_kos(state: &mut GameState, db: &CardDb) -> bool {
    let mut had_ko = false;

    // Collect all slots that need to be KO'd before mutating state.
    let mut ko_slots: Vec<SlotRef> = Vec::new();

    for player_idx in 0..2usize {
        if let Some(ref active) = state.players[player_idx].active {
            if active.current_hp <= 0 {
                ko_slots.push(SlotRef::active(player_idx));
            }
        }
        for bench_idx in 0..3usize {
            if let Some(ref bench) = state.players[player_idx].bench[bench_idx] {
                if bench.current_hp <= 0 {
                    ko_slots.push(SlotRef::bench(player_idx, bench_idx));
                }
            }
        }
    }

    for slot_ref in ko_slots {
        handle_ko(state, db, slot_ref);
        had_ko = true;
        // Stop early if game is already over.
        if state.phase == GamePhase::GameOver {
            return had_ko;
        }
    }

    // Also handle the "no Pokemon left" case even when HP > 0 (e.g. deck-out
    // scenarios or edge cases where KOs were already processed individually).
    for player_idx in 0..2usize {
        if !state.players[player_idx].has_any_pokemon() && state.winner.is_none() {
            let winner = 1 - player_idx;
            state.winner = Some(winner as i8);
            state.phase = GamePhase::GameOver;
            had_ko = true;
        }
    }

    had_ko
}

/// Check win conditions without processing KOs:
///
/// - A player has `POINTS_TO_WIN` or more points.
/// - A player has no Pokemon in play.
/// - Turn limit exceeded (treated as a draw).
///
/// Sets `state.winner` and `state.phase = GameOver` if a win condition is met.
pub fn check_winner(state: &mut GameState) {
    if state.winner.is_some() {
        return;
    }

    // Point threshold.
    for i in 0..2usize {
        if state.players[i].points >= POINTS_TO_WIN {
            // Check for simultaneous win.
            let j = 1 - i;
            if state.players[j].points >= POINTS_TO_WIN {
                state.winner = Some(-1);
            } else {
                state.winner = Some(i as i8);
            }
            state.phase = GamePhase::GameOver;
            return;
        }
    }

    // No Pokemon in play.
    for i in 0..2usize {
        if !state.players[i].has_any_pokemon() {
            let winner = 1 - i;
            state.winner = Some(winner as i8);
            state.phase = GamePhase::GameOver;
            return;
        }
    }

    // Turn limit — draw.
    if state.turn_number >= MAX_TURNS {
        state.winner = Some(-1);
        state.phase = GamePhase::GameOver;
    }
}

/// Promote a bench Pokemon to the active slot.
///
/// `bench_slot` is the index (0-2) in the bench array.
/// `player_idx` is which player is promoting.
///
/// Panics in debug mode if the phase is wrong or the bench slot is empty.
pub fn promote_bench(state: &mut GameState, bench_slot: usize, player_idx: usize) {
    debug_assert_eq!(
        state.phase,
        GamePhase::AwaitingBenchPromotion,
        "promote_bench called while phase is {:?}",
        state.phase,
    );
    debug_assert!(
        state.players[player_idx].bench[bench_slot].is_some(),
        "No Pokemon at bench slot {} for player {}",
        bench_slot,
        player_idx,
    );

    let slot = state.players[player_idx].bench[bench_slot].take();
    state.players[player_idx].active = slot;
    state.phase = GamePhase::Main;
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use crate::card::CardDb;
    use crate::state::PokemonSlot;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    fn load_db() -> CardDb {
        CardDb::load_from_dir(&assets_dir())
    }

    /// Return the card idx for Bulbasaur (a1-001).
    fn bulbasaur_idx(db: &CardDb) -> u16 {
        db.get_by_id("a1-001").expect("a1-001 not found").idx
    }

    fn make_state_with_actives(db: &CardDb) -> GameState {
        let mut state = GameState::new(42);
        let idx = bulbasaur_idx(db);
        state.players[0].active = Some(PokemonSlot::new(idx, 70));
        state.players[1].active = Some(PokemonSlot::new(idx, 70));
        state.phase = GamePhase::Main;
        state
    }

    #[test]
    fn test_ko_awards_one_point_for_normal_pokemon() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);

        // Set player 0's active to 0 HP.
        state.players[0].active.as_mut().unwrap().current_hp = 0;

        let had_ko = check_and_handle_kos(&mut state, &db);

        assert!(had_ko, "Expected a KO to be processed");
        // Player 1 (the opponent) should receive 1 point.
        assert_eq!(state.players[1].points, 1, "Expected 1 point for normal KO");
        // Player 0's active should be gone.
        assert!(state.players[0].active.is_none(), "KO'd slot should be cleared");
    }

    #[test]
    fn test_ko_moves_card_to_discard() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        state.players[0].active.as_mut().unwrap().current_hp = 0;
        check_and_handle_kos(&mut state, &db);

        assert!(
            state.players[0].discard.contains(&idx),
            "KO'd card should be in discard"
        );
    }

    #[test]
    fn test_ko_with_no_bench_sets_winner() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);

        // Kill player 0's active with no bench Pokemon.
        state.players[0].active.as_mut().unwrap().current_hp = 0;
        check_and_handle_kos(&mut state, &db);

        assert_eq!(state.winner, Some(1), "Player 1 should win when player 0 has no bench");
        assert_eq!(state.phase, GamePhase::GameOver);
    }

    #[test]
    fn test_ko_active_with_bench_sets_awaiting_promotion() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        // Give player 0 a bench Pokemon.
        state.players[0].bench[0] = Some(PokemonSlot::new(idx, 70));
        // Kill player 0's active.
        state.players[0].active.as_mut().unwrap().current_hp = 0;

        check_and_handle_kos(&mut state, &db);

        assert_eq!(
            state.phase,
            GamePhase::AwaitingBenchPromotion,
            "Phase should be AwaitingBenchPromotion when bench has Pokemon"
        );
        assert!(state.winner.is_none(), "Game should not be over yet");
    }

    #[test]
    fn test_promote_bench_moves_pokemon_to_active() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        state.players[0].bench[1] = Some(PokemonSlot::new(idx, 70));
        state.players[0].active.as_mut().unwrap().current_hp = 0;
        check_and_handle_kos(&mut state, &db);

        assert_eq!(state.phase, GamePhase::AwaitingBenchPromotion);

        promote_bench(&mut state, 1, 0);

        assert!(state.players[0].active.is_some(), "Active should be filled after promotion");
        assert!(state.players[0].bench[1].is_none(), "Bench slot should be cleared");
        assert_eq!(state.phase, GamePhase::Main);
    }

    #[test]
    fn test_win_by_points() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);

        // Give player 1 enough points to win on their next KO.
        state.players[1].points = POINTS_TO_WIN - 1;
        state.players[0].active.as_mut().unwrap().current_hp = 0;

        check_and_handle_kos(&mut state, &db);

        assert_eq!(state.winner, Some(1), "Player 1 should win by reaching point threshold");
        assert_eq!(state.phase, GamePhase::GameOver);
    }

    #[test]
    fn test_bench_ko_does_not_set_promotion_phase() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        // Both players have a bench Pokemon; player 0's bench gets KO'd.
        state.players[0].bench[0] = Some(PokemonSlot::new(idx, 0)); // 0 HP — KO'd
        state.players[1].bench[0] = Some(PokemonSlot::new(idx, 70));

        check_and_handle_kos(&mut state, &db);

        // Bench KO should not trigger promotion (active is still alive).
        assert_eq!(state.phase, GamePhase::Main, "Phase should remain Main after bench KO");
        assert!(state.players[0].bench[0].is_none(), "Bench slot should be cleared");
        assert_eq!(state.players[1].points, 1, "Player 1 gains 1 point for bench KO");
    }

    #[test]
    fn test_check_winner_turn_limit() {
        let db = load_db();
        let _ = db;
        let mut state = GameState::new(0);
        let idx = 0u16;
        state.players[0].active = Some(PokemonSlot::new(idx, 70));
        state.players[1].active = Some(PokemonSlot::new(idx, 70));
        state.phase = GamePhase::Main;
        state.turn_number = MAX_TURNS;

        check_winner(&mut state);

        assert_eq!(state.winner, Some(-1), "Turn limit should result in a draw");
        assert_eq!(state.phase, GamePhase::GameOver);
    }

    #[test]
    fn test_check_winner_no_pokemon() {
        let mut state = GameState::new(0);
        let idx = 0u16;
        // Player 0 has no Pokemon; player 1 has an active.
        state.players[1].active = Some(PokemonSlot::new(idx, 70));
        state.phase = GamePhase::Main;

        check_winner(&mut state);

        assert_eq!(state.winner, Some(1), "Player 1 wins when player 0 has no Pokemon");
        assert_eq!(state.phase, GamePhase::GameOver);
    }
}
