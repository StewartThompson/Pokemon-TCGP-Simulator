//! KO handling, bench promotion, and win condition checking.
//!
//! Ported from `ptcgp/engine/ko.py`.

use crate::card::CardDb;
use crate::constants::{POINTS_TO_WIN, MAX_TURNS};
use crate::state::{GameState, get_slot, set_slot};
use crate::actions::SlotRef;
use crate::types::GamePhase;

/// Process the bookkeeping for a single KO without making any win-condition
/// decisions.  Returns `(awarding_player, ko_points, was_active)` so the
/// caller can aggregate results across multiple simultaneous KOs (Bug 2).
///
/// 1. Awards points to the opponent (1 for regular, 2 for EX, 3 for Mega EX).
/// 2. Moves the Pokemon + its attached tool to the loser's discard pile.
/// 3. Removes the slot from play.
fn award_ko(state: &mut GameState, db: &CardDb, ko_slot: SlotRef) -> (usize, u8, bool) {
    let slot = get_slot(state, ko_slot)
        .expect("award_ko called on empty slot")
        .clone();

    let card = db.get_by_idx(slot.card_idx);
    let ko_points = card.ko_points;

    let awarding_player = 1 - ko_slot.player as usize;
    state.players[awarding_player].points += ko_points;

    let loser = ko_slot.player as usize;
    state.players[loser].discard.push(slot.card_idx);
    if let Some(tool_idx) = slot.tool_idx {
        state.players[loser].discard.push(tool_idx);
    }

    set_slot(state, ko_slot, None);

    (awarding_player, ko_points, ko_slot.is_active())
}

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
    if get_slot(state, ko_slot).is_none() {
        return; // nothing to KO
    }

    let (awarding_player, ko_points, was_active) = award_ko(state, db, ko_slot);
    let loser = 1 - awarding_player;

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
    if was_active {
        let has_bench = state.players[loser].bench.iter().any(|s| s.is_some());
        if has_bench {
            state.players[loser].needs_promotion = true;
            state.phase = GamePhase::AwaitingBenchPromotion;
        } else {
            // No Pokemon left — the losing player loses.
            state.winner = Some(awarding_player as i8);
            state.phase = GamePhase::GameOver;
        }
    }
}

/// Check whether any active Pokemon has `current_hp <= 0` and process every
/// pending KO.  Bug 2 fix: all KOs are awarded *before* the win condition is
/// checked, so simultaneous KOs that bring both players to `POINTS_TO_WIN`
/// correctly produce a tie.  Bug 3 fix: per-player `needs_promotion` flags
/// are set so both players can be queued for bench promotion when both
/// actives KO simultaneously.
///
/// Returns `true` if at least one KO was processed.
pub fn check_and_handle_kos(state: &mut GameState, db: &CardDb) -> bool {
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

    if ko_slots.is_empty() {
        // Even with no HP-based KOs, a player may have somehow ended up with
        // no Pokemon at all (e.g. discard-style effects).  Handle that here.
        for player_idx in 0..2usize {
            if !state.players[player_idx].has_any_pokemon() && state.winner.is_none() {
                let winner = 1 - player_idx;
                state.winner = Some(winner as i8);
                state.phase = GamePhase::GameOver;
                return true;
            }
        }
        return false;
    }

    // -- Phase 1: award all KOs (points, discard, slot clearing, promotion flags) --
    let mut max_ko_points: u8 = 0;
    let mut active_ko_loser: Option<usize> = None; // last loser whose active was KO'd
    for slot_ref in &ko_slots {
        let (awarding_player, ko_points, was_active) = award_ko(state, db, *slot_ref);
        let _ = awarding_player;
        if ko_points > max_ko_points {
            max_ko_points = ko_points;
        }
        if was_active {
            let loser = slot_ref.player as usize;
            // Mark this player as needing to promote a bench Pokemon (Bug 3).
            // Only set the flag if they actually have a bench Pokemon to promote;
            // otherwise they have no Pokemon left and the win check below will
            // hand the game to the opponent.
            if state.players[loser].bench.iter().any(|s| s.is_some()) {
                state.players[loser].needs_promotion = true;
                active_ko_loser = Some(loser);
            }
        }
    }

    // -- Phase 2: global win-condition resolution --
    let p0_at_win = state.players[0].points >= POINTS_TO_WIN;
    let p1_at_win = state.players[1].points >= POINTS_TO_WIN;

    if p0_at_win && p1_at_win {
        // Both reached POINTS_TO_WIN — tie (RULES.md §10).
        state.winner = Some(-1);
        state.phase = GamePhase::GameOver;
        return true;
    }
    if p0_at_win {
        state.winner = Some(0);
        state.phase = GamePhase::GameOver;
        return true;
    }
    if p1_at_win {
        state.winner = Some(1);
        state.phase = GamePhase::GameOver;
        return true;
    }

    // Mega EX instant-win.  If a 3-point KO was scored, whoever caused it
    // (whose opponent's Pokemon was KO'd) wins — but if BOTH players KO'd
    // each other's Mega EX simultaneously the point check above already
    // handled it as a tie.  We replay the KO list to find the awarder.
    if max_ko_points == 3 {
        // Find the awarder.  If multiple 3-point KOs by different awarders,
        // both points are >=3 so the tie/winner logic above already returned.
        for slot_ref in &ko_slots {
            let card_idx = state.players[slot_ref.player as usize]
                .discard
                .iter()
                .rev()
                .next()
                .copied();
            // We can't reliably re-derive the card here after discards, so
            // instead just declare the player who has any non-zero points the
            // winner — but if neither side has hit threshold yet, the only
            // way max_ko_points==3 without a points-threshold trigger is if
            // a single Mega EX was KO'd.  In that case the awarder has at
            // least 3 points, so the points check above already fired.  So
            // this branch is effectively unreachable; leave a defensive
            // GameOver fall-through.
            let _ = card_idx;
            let awarder = 1 - slot_ref.player as usize;
            if state.players[awarder].points >= 3 {
                state.winner = Some(awarder as i8);
                state.phase = GamePhase::GameOver;
                return true;
            }
        }
    }

    // No Pokemon left — opponent wins.
    for player_idx in 0..2usize {
        if !state.players[player_idx].has_any_pokemon() && state.winner.is_none() {
            let winner = 1 - player_idx;
            state.winner = Some(winner as i8);
            state.phase = GamePhase::GameOver;
            return true;
        }
    }

    // -- Phase 3: bench promotion --
    if state.players[0].needs_promotion || state.players[1].needs_promotion {
        state.phase = GamePhase::AwaitingBenchPromotion;
    }
    let _ = active_ko_loser;

    true
}

/// Returns the player who still needs to promote a bench Pokemon to active,
/// preferring the current player (whose turn it is) per RULES.md §10
/// convention.  Returns `None` if neither player needs promotion.
pub fn next_promotion_player(state: &GameState) -> Option<usize> {
    let cur = state.current_player;
    let other = 1 - cur;
    if state.players[cur].needs_promotion {
        Some(cur)
    } else if state.players[other].needs_promotion {
        Some(other)
    } else {
        None
    }
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
    state.players[player_idx].needs_promotion = false;

    // If the OTHER player also still needs to promote (Bug 3 — simultaneous
    // active KOs), stay in AwaitingBenchPromotion so the runner loop calls
    // promote_bench again for that player.  Otherwise, return to Main.
    let other = 1 - player_idx;
    if state.players[other].needs_promotion {
        state.phase = GamePhase::AwaitingBenchPromotion;
    } else {
        state.phase = GamePhase::Main;
    }
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

    // -- Bug 2: simultaneous KOs that bring both players to 3 points = TIE --
    #[test]
    fn test_simultaneous_ko_to_three_points_is_tie() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        // Both players already at 2 points; both actives KO simultaneously
        // and each is worth 1 point — both reach 3 → tie.
        state.players[0].points = POINTS_TO_WIN - 1;
        state.players[1].points = POINTS_TO_WIN - 1;
        // Give both players a bench so the loss-by-no-pokemon path is not taken.
        state.players[0].bench[0] = Some(PokemonSlot::new(idx, 70));
        state.players[1].bench[0] = Some(PokemonSlot::new(idx, 70));
        state.players[0].active.as_mut().unwrap().current_hp = 0;
        state.players[1].active.as_mut().unwrap().current_hp = 0;

        check_and_handle_kos(&mut state, &db);

        assert_eq!(state.winner, Some(-1), "Simultaneous KOs to 3 points should tie");
        assert_eq!(state.phase, GamePhase::GameOver);
        assert_eq!(state.players[0].points, POINTS_TO_WIN);
        assert_eq!(state.players[1].points, POINTS_TO_WIN);
    }

    // -- Bug 3: dual active KOs queue both players for promotion --
    #[test]
    fn test_dual_active_ko_sets_both_promotion_flags() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        // Both bench slots populated so both can promote.
        state.players[0].bench[0] = Some(PokemonSlot::new(idx, 70));
        state.players[1].bench[0] = Some(PokemonSlot::new(idx, 70));
        state.players[0].active.as_mut().unwrap().current_hp = 0;
        state.players[1].active.as_mut().unwrap().current_hp = 0;

        check_and_handle_kos(&mut state, &db);

        assert!(state.winner.is_none(), "Game should not be over yet");
        assert_eq!(state.phase, GamePhase::AwaitingBenchPromotion);
        assert!(state.players[0].needs_promotion, "Player 0 should need promotion");
        assert!(state.players[1].needs_promotion, "Player 1 should need promotion");
    }

    #[test]
    fn test_next_promotion_player_prefers_current_player() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        state.players[0].bench[0] = Some(PokemonSlot::new(idx, 70));
        state.players[1].bench[0] = Some(PokemonSlot::new(idx, 70));
        state.players[0].active.as_mut().unwrap().current_hp = 0;
        state.players[1].active.as_mut().unwrap().current_hp = 0;
        state.current_player = 1;

        check_and_handle_kos(&mut state, &db);

        // Both flagged; next_promotion_player should return current_player (1) first.
        assert_eq!(next_promotion_player(&state), Some(1));

        // After player 1 promotes, player 0 should be next.
        promote_bench(&mut state, 0, 1);
        assert_eq!(state.phase, GamePhase::AwaitingBenchPromotion);
        assert_eq!(next_promotion_player(&state), Some(0));

        // After player 0 promotes, no one needs promotion → Main.
        promote_bench(&mut state, 0, 0);
        assert_eq!(state.phase, GamePhase::Main);
        assert_eq!(next_promotion_player(&state), None);
    }

    #[test]
    fn test_dual_active_ko_no_bench_loser_loses() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let idx = bulbasaur_idx(&db);

        // Only player 1 has a bench; player 0 has none.
        state.players[1].bench[0] = Some(PokemonSlot::new(idx, 70));
        state.players[0].active.as_mut().unwrap().current_hp = 0;
        state.players[1].active.as_mut().unwrap().current_hp = 0;

        check_and_handle_kos(&mut state, &db);

        // Player 0 has no Pokemon left → player 1 wins (assuming neither
        // already at point threshold).  Both gained 1 point each (still < 3).
        assert_eq!(state.winner, Some(1));
        assert_eq!(state.phase, GamePhase::GameOver);
    }
}
