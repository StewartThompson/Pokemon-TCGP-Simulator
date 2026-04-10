//! Damage modifier effect handlers (Wave 6 T19).
//!
//! These functions implement the damage-modifier and damage-side-effect
//! behaviours described in `ptcgp/effects/damage_modifiers.py` and
//! `ptcgp/effects/damage_effects.py`.
//!
//! **Return-value convention**
//! Functions that *compute* a bonus return `i16` — the caller adds the result
//! to the base damage.  Functions that *apply* a state mutation (prevention,
//! reduction, bench damage …) return nothing and mutate `state` directly.
//!
//! Because the Rust `EffectContext` only carries `acting_player` and `extra`,
//! functions that need the source or target slot accept them as explicit
//! `Option<SlotRef>` parameters.

#![allow(dead_code, unused_imports, unused_variables)]

use rand::Rng;
use crate::card::CardDb;
use crate::state::{GameState, PokemonSlot, get_slot, get_slot_mut};
use crate::actions::SlotRef;
use crate::effects::EffectContext;
use crate::types::Element;

// ------------------------------------------------------------------ //
// Internal helpers
// ------------------------------------------------------------------ //

/// Flip a coin: `true` = heads.
fn flip(state: &mut GameState) -> bool {
    state.rng.gen::<f32>() < 0.5
}

/// Deal `amount` damage to the slot identified by `slot_ref`, clamped to 0.
/// Does **not** trigger KO handling — that is the caller's responsibility.
fn damage_slot(state: &mut GameState, slot_ref: SlotRef, amount: i16) {
    if let Some(slot) = get_slot_mut(state, slot_ref) {
        slot.current_hp = (slot.current_hp - amount).max(0);
    }
}

// ------------------------------------------------------------------ //
// Extra damage — these return the bonus amount
// ------------------------------------------------------------------ //

/// Flat bonus damage (unconditional, e.g. "+30 from a supporter aura").
pub fn extra_damage(
    _state: &mut GameState,
    amount: i16,
    _ctx: &EffectContext,
) -> i16 {
    amount
}

/// Extra `amount` for each energy attached to the attacker's active Pokémon.
pub fn extra_damage_per_own_energy(
    state: &mut GameState,
    _db: &CardDb,
    amount: i16,
    source_ref: Option<SlotRef>,
    _ctx: &EffectContext,
) -> i16 {
    let total = source_ref
        .and_then(|r| get_slot(state, r))
        .map(|s| s.total_energy() as i16)
        .unwrap_or(0);
    amount * total
}

/// Extra damage if the opponent's active Pokémon has taken damage (hp < max).
pub fn extra_damage_if_damaged(
    state: &mut GameState,
    amount: i16,
    ctx: &EffectContext,
) -> i16 {
    let opp_idx = 1 - ctx.acting_player;
    let damaged = state.players[opp_idx]
        .active
        .as_ref()
        .map(|s| s.current_hp < s.max_hp)
        .unwrap_or(false);
    if damaged { amount } else { 0 }
}

/// Extra damage if the attacker itself has damage counters.
pub fn extra_damage_if_self_damaged(
    state: &mut GameState,
    amount: i16,
    source_ref: Option<SlotRef>,
    _ctx: &EffectContext,
) -> i16 {
    let damaged = source_ref
        .and_then(|r| get_slot(state, r))
        .map(|s| s.current_hp < s.max_hp)
        .unwrap_or(false);
    if damaged { amount } else { 0 }
}

/// Extra damage per energy attached to the *opponent's* active Pokémon.
pub fn extra_damage_per_opponent_energy(
    state: &mut GameState,
    amount: i16,
    ctx: &EffectContext,
) -> i16 {
    let opp_idx = 1 - ctx.acting_player;
    let total = state.players[opp_idx]
        .active
        .as_ref()
        .map(|s| s.total_energy() as i16)
        .unwrap_or(0);
    amount * total
}

/// Extra damage for each of the current player's benched Pokémon.
pub fn extra_damage_per_own_bench(
    state: &mut GameState,
    amount: i16,
    ctx: &EffectContext,
) -> i16 {
    let count = state.players[ctx.acting_player].bench_count() as i16;
    amount * count
}

/// Extra damage for each of the opponent's benched Pokémon.
pub fn extra_damage_per_opponent_bench(
    state: &mut GameState,
    amount: i16,
    ctx: &EffectContext,
) -> i16 {
    let opp_idx = 1 - ctx.acting_player;
    let count = state.players[opp_idx].bench_count() as i16;
    amount * count
}

/// Extra damage if the opponent's active Pokémon is an *ex* card.
pub fn extra_damage_if_opponent_ex(
    state: &mut GameState,
    db: &CardDb,
    amount: i16,
    ctx: &EffectContext,
) -> i16 {
    let opp_idx = 1 - ctx.acting_player;
    let is_ex = state.players[opp_idx]
        .active
        .as_ref()
        .map(|s| db.get_by_idx(s.card_idx).is_ex)
        .unwrap_or(false);
    if is_ex { amount } else { 0 }
}

/// Extra damage equal to the damage the attacker has already taken.
pub fn extra_damage_equal_to_damage_taken(
    state: &mut GameState,
    source_ref: Option<SlotRef>,
    _ctx: &EffectContext,
) -> i16 {
    source_ref
        .and_then(|r| get_slot(state, r))
        .map(|s| (s.max_hp - s.current_hp).max(0))
        .unwrap_or(0)
}

// ------------------------------------------------------------------ //
// Coin-flip damage helpers
// ------------------------------------------------------------------ //

/// Flip `flips` coins; return `amount * heads_count` as bonus damage.
pub fn coin_flip_extra_damage(
    state: &mut GameState,
    amount: i16,
    flips: u8,
    _ctx: &EffectContext,
) -> i16 {
    let heads: i16 = (0..flips).filter(|_| flip(state)).count() as i16;
    amount * heads
}

/// Flip until tails; return `amount * heads_count` as bonus damage.
pub fn flip_until_tails_extra_damage(
    state: &mut GameState,
    amount: i16,
    _ctx: &EffectContext,
) -> i16 {
    let mut heads: i16 = 0;
    while flip(state) {
        heads += 1;
    }
    amount * heads
}

/// Flip 1 coin: heads → return `(bonus, 0)`, tails → return `(0, self_damage)`.
/// The caller is responsible for applying self-damage on tails.
pub fn coin_flip_bonus_or_self_damage(
    state: &mut GameState,
    bonus: i16,
    self_damage_amount: i16,
    _ctx: &EffectContext,
) -> (i16, i16) {
    if flip(state) {
        (bonus, 0)
    } else {
        (0, self_damage_amount)
    }
}

// ------------------------------------------------------------------ //
// Damage prevention / reduction
// ------------------------------------------------------------------ //

/// Set `prevent_damage_next_turn = true` on the acting player's active slot.
pub fn prevent_damage_next_turn(state: &mut GameState, ctx: &EffectContext) {
    if let Some(slot) = state.players[ctx.acting_player].active.as_mut() {
        slot.prevent_damage_next_turn = true;
    }
}

/// Reduce incoming attack damage by `amount` for the acting player's active
/// slot (stored in `incoming_damage_reduction`, checked in `attack.rs`).
pub fn reduce_opponent_attack_damage(
    state: &mut GameState,
    amount: i16,
    ctx: &EffectContext,
) {
    if let Some(slot) = state.players[ctx.acting_player].active.as_mut() {
        slot.incoming_damage_reduction = amount as i8;
    }
}

/// Make the acting player's active Pokémon free to retreat this turn by
/// setting `retreat_cost_modifier` to negate the card's retreat cost.
pub fn set_retreat_cost_zero(state: &mut GameState, ctx: &EffectContext, db: &CardDb) {
    let retreat_cost = state.players[ctx.acting_player]
        .active
        .as_ref()
        .map(|s| db.get_by_idx(s.card_idx).retreat_cost as i8)
        .unwrap_or(0);
    state.players[ctx.acting_player].retreat_cost_modifier = -retreat_cost;
}

/// Reduce the retreat cost of the acting player's active Pokémon by `amount`.
pub fn reduce_retreat_cost(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let current = state.players[ctx.acting_player].retreat_cost_modifier;
    state.players[ctx.acting_player].retreat_cost_modifier =
        current.saturating_sub(amount as i8);
}

// ------------------------------------------------------------------ //
// Bench / splash damage
// ------------------------------------------------------------------ //

/// Deal `amount` damage to every benched Pokémon of the opponent (not Active).
/// Clamps HP to 0 but does NOT call KO handling.
pub fn damage_all_opponent_bench(
    state: &mut GameState,
    amount: i16,
    ctx: &EffectContext,
) {
    let opp_idx = 1 - ctx.acting_player;
    for i in 0..state.players[opp_idx].bench.len() {
        if state.players[opp_idx].bench[i].is_some() {
            damage_slot(state, SlotRef::bench(opp_idx, i), amount);
        }
    }
}

/// Deal `amount` damage to every benched Pokémon on *both* sides (not Active).
pub fn damage_all_bench(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let opp_idx = 1 - ctx.acting_player;
    // Damage own bench
    for i in 0..state.players[ctx.acting_player].bench.len() {
        if state.players[ctx.acting_player].bench[i].is_some() {
            damage_slot(state, SlotRef::bench(ctx.acting_player, i), amount);
        }
    }
    // Damage opponent bench
    for i in 0..state.players[opp_idx].bench.len() {
        if state.players[opp_idx].bench[i].is_some() {
            damage_slot(state, SlotRef::bench(opp_idx, i), amount);
        }
    }
}

/// Deal `amount` damage to the bench slot identified by `target_ref`,
/// or to the first available opponent bench slot as a fallback.
pub fn damage_specific_bench(
    state: &mut GameState,
    amount: i16,
    target_ref: Option<SlotRef>,
    ctx: &EffectContext,
) {
    let opp_idx = 1 - ctx.acting_player;

    // Use target_ref if it points to a valid opponent bench slot.
    if let Some(target) = target_ref {
        if target.player == opp_idx as u8 && target.slot >= 0 {
            damage_slot(state, target, amount);
            return;
        }
    }

    // Fallback: first available opponent bench slot.
    for i in 0..state.players[opp_idx].bench.len() {
        if state.players[opp_idx].bench[i].is_some() {
            damage_slot(state, SlotRef::bench(opp_idx, i), amount);
            return;
        }
    }
}

/// Deal `amount` self-damage to the slot identified by `source_ref`.
pub fn self_damage(
    state: &mut GameState,
    amount: i16,
    source_ref: Option<SlotRef>,
    _ctx: &EffectContext,
) {
    if let Some(src) = source_ref {
        damage_slot(state, src, amount);
    }
}

/// Deal `amount` damage to every Pokémon of the opponent (Active + Bench).
pub fn damage_all_opponent(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let opp_idx = 1 - ctx.acting_player;
    if state.players[opp_idx].active.is_some() {
        damage_slot(state, SlotRef::active(opp_idx), amount);
    }
    for i in 0..state.players[opp_idx].bench.len() {
        if state.players[opp_idx].bench[i].is_some() {
            damage_slot(state, SlotRef::bench(opp_idx, i), amount);
        }
    }
}

// ------------------------------------------------------------------ //
// Unit tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};
    use crate::effects::EffectContext;

    fn make_state() -> GameState {
        let mut state = GameState::new(12345);
        // Player 0 active
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        // Player 1 active + two bench slots
        state.players[1].active = Some(PokemonSlot::new(1, 80));
        state.players[1].bench[0] = Some(PokemonSlot::new(2, 60));
        state.players[1].bench[1] = Some(PokemonSlot::new(3, 60));
        state
    }

    fn ctx(acting: usize) -> EffectContext {
        EffectContext::new(acting)
    }

    // --- prevent_damage_next_turn sets the flag ---
    #[test]
    fn test_prevent_damage_next_turn_sets_flag() {
        let mut state = make_state();
        let c = ctx(0);
        assert!(!state.players[0].active.as_ref().unwrap().prevent_damage_next_turn);
        prevent_damage_next_turn(&mut state, &c);
        assert!(state.players[0].active.as_ref().unwrap().prevent_damage_next_turn);
    }

    // --- prevent_damage_next_turn does not affect opponent ---
    #[test]
    fn test_prevent_damage_next_turn_does_not_affect_opponent() {
        let mut state = make_state();
        let c = ctx(0);
        prevent_damage_next_turn(&mut state, &c);
        assert!(!state.players[1].active.as_ref().unwrap().prevent_damage_next_turn);
    }

    // --- damage_all_opponent_bench deals to all bench slots ---
    #[test]
    fn test_damage_all_opponent_bench() {
        let mut state = make_state();
        let c = ctx(0); // acting player = 0, opponent = 1
        damage_all_opponent_bench(&mut state, 20, &c);
        // bench[0] and bench[1] each lose 20 HP
        assert_eq!(state.players[1].bench[0].as_ref().unwrap().current_hp, 40);
        assert_eq!(state.players[1].bench[1].as_ref().unwrap().current_hp, 40);
        // Opponent *active* untouched
        assert_eq!(state.players[1].active.as_ref().unwrap().current_hp, 80);
    }

    // --- damage_all_opponent_bench clamps HP to 0 ---
    #[test]
    fn test_damage_all_opponent_bench_clamps_to_zero() {
        let mut state = make_state();
        let c = ctx(0);
        damage_all_opponent_bench(&mut state, 200, &c);
        assert_eq!(state.players[1].bench[0].as_ref().unwrap().current_hp, 0);
        assert_eq!(state.players[1].bench[1].as_ref().unwrap().current_hp, 0);
    }

    // --- extra_damage returns the flat amount unchanged ---
    #[test]
    fn test_extra_damage_flat() {
        let mut state = make_state();
        let c = ctx(0);
        assert_eq!(extra_damage(&mut state, 30, &c), 30);
    }

    // --- extra_damage_if_damaged returns 0 when opponent is at full HP ---
    #[test]
    fn test_extra_damage_if_damaged_full_hp() {
        let mut state = make_state();
        let c = ctx(0);
        assert_eq!(extra_damage_if_damaged(&mut state, 40, &c), 0);
    }

    // --- extra_damage_if_damaged returns bonus when opponent is damaged ---
    #[test]
    fn test_extra_damage_if_damaged_has_damage() {
        let mut state = make_state();
        state.players[1].active.as_mut().unwrap().current_hp = 50; // damaged
        let c = ctx(0);
        assert_eq!(extra_damage_if_damaged(&mut state, 40, &c), 40);
    }

    // --- reduce_opponent_attack_damage sets incoming_damage_reduction ---
    #[test]
    fn test_reduce_opponent_attack_damage() {
        let mut state = make_state();
        let c = ctx(0);
        reduce_opponent_attack_damage(&mut state, 20, &c);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().incoming_damage_reduction,
            20
        );
    }

    // --- coin_flip_extra_damage with 0 flips returns 0 ---
    #[test]
    fn test_coin_flip_extra_damage_zero_flips() {
        let mut state = make_state();
        let c = ctx(0);
        assert_eq!(coin_flip_extra_damage(&mut state, 30, 0, &c), 0);
    }

    // --- self_damage reduces own HP ---
    #[test]
    fn test_self_damage() {
        let mut state = make_state();
        let c = ctx(0);
        let src = Some(SlotRef::active(0));
        self_damage(&mut state, 10, src, &c);
        assert_eq!(state.players[0].active.as_ref().unwrap().current_hp, 90);
    }
}
