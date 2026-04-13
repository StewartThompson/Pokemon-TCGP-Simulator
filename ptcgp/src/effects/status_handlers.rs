#![allow(dead_code, unused_imports, unused_variables)]

use rand::Rng;
use crate::state::{GameState, get_slot_mut};
use crate::types::StatusEffect;
use crate::actions::SlotRef;
use crate::effects::EffectContext;

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //

fn get_opponent(ctx: &EffectContext) -> usize {
    1 - ctx.acting_player
}

/// Set a status bit on the given slot.
fn set_status(state: &mut GameState, target: SlotRef, se: StatusEffect) {
    if let Some(slot) = get_slot_mut(state, target) {
        slot.add_status(se);
    }
}

/// Clear a status bit from the given slot.
fn clear_status(state: &mut GameState, target: SlotRef, se: StatusEffect) {
    if let Some(slot) = get_slot_mut(state, target) {
        slot.remove_status(se);
    }
}

// ------------------------------------------------------------------ //
// Opponent-targeting status appliers
// ------------------------------------------------------------------ //

/// Apply Poisoned to the opponent's active Pokémon.
pub fn apply_poison(state: &mut GameState, ctx: &EffectContext) {
    let target = SlotRef::active(get_opponent(ctx));
    set_status(state, target, StatusEffect::Poisoned);
}

/// Apply Burned to the opponent's active Pokémon.
pub fn apply_burn(state: &mut GameState, ctx: &EffectContext) {
    let target = SlotRef::active(get_opponent(ctx));
    set_status(state, target, StatusEffect::Burned);
}

/// Apply Asleep to the opponent's active Pokémon.
pub fn apply_sleep(state: &mut GameState, ctx: &EffectContext) {
    let target = SlotRef::active(get_opponent(ctx));
    set_status(state, target, StatusEffect::Asleep);
}

/// Apply Paralyzed to the opponent's active Pokémon.
pub fn apply_paralysis(state: &mut GameState, ctx: &EffectContext) {
    let target = SlotRef::active(get_opponent(ctx));
    set_status(state, target, StatusEffect::Paralyzed);
}

/// Apply Confused to the opponent's active Pokémon.
pub fn apply_confusion(state: &mut GameState, ctx: &EffectContext) {
    let target = SlotRef::active(get_opponent(ctx));
    set_status(state, target, StatusEffect::Confused);
}

/// Pick a random status from [Poisoned, Burned, Paralyzed, Asleep, Confused]
/// and apply it to the opponent's active Pokémon.
pub fn apply_random_status(state: &mut GameState, ctx: &EffectContext) {
    let all_statuses = [
        StatusEffect::Poisoned,
        StatusEffect::Burned,
        StatusEffect::Paralyzed,
        StatusEffect::Asleep,
        StatusEffect::Confused,
    ];
    let idx = state.rng.gen_range(0..all_statuses.len());
    let chosen = all_statuses[idx];
    let target = SlotRef::active(get_opponent(ctx));
    set_status(state, target, chosen);
}

/// Toxic poison — applies Poisoned status AND increases the opponent's per-turn
/// poison damage by 20 (Nihilego "More Poison" ability). Stacks each use.
pub fn toxic_poison(state: &mut GameState, ctx: &EffectContext) {
    apply_poison(state, ctx);
    let opp = 1 - ctx.acting_player;
    state.players[opp].extra_poison_damage += 20;
}

// ------------------------------------------------------------------ //
// Coin-flip status appliers
// ------------------------------------------------------------------ //

/// Flip a coin. On heads, apply Paralyzed to the opponent's active Pokémon.
pub fn coin_flip_apply_paralysis(state: &mut GameState, ctx: &EffectContext) {
    let heads = state.rng.gen::<f64>() < 0.5;
    state.coin_flip_log.push(if heads {
        "🪙 Heads! Opponent is Paralyzed".to_string()
    } else {
        "🪙 Tails! No Paralysis".to_string()
    });
    if heads { apply_paralysis(state, ctx); }
}

/// Flip a coin. On heads, apply Asleep to the opponent's active Pokémon.
pub fn coin_flip_apply_sleep(state: &mut GameState, ctx: &EffectContext) {
    let heads = state.rng.gen::<f64>() < 0.5;
    state.coin_flip_log.push(if heads {
        "🪙 Heads! Opponent is Asleep".to_string()
    } else {
        "🪙 Tails! No Sleep".to_string()
    });
    if heads { apply_sleep(state, ctx); }
}

// ------------------------------------------------------------------ //
// Self-targeting status appliers
// ------------------------------------------------------------------ //

/// Apply Confused to the acting player's own active Pokémon.
pub fn self_confuse(state: &mut GameState, ctx: &EffectContext) {
    let target = SlotRef::active(ctx.acting_player);
    set_status(state, target, StatusEffect::Confused);
}

/// Apply Asleep to the acting player's own active Pokémon.
pub fn self_sleep(state: &mut GameState, ctx: &EffectContext) {
    let target = SlotRef::active(ctx.acting_player);
    set_status(state, target, StatusEffect::Asleep);
}

// ------------------------------------------------------------------ //
// Attack-block handlers
// ------------------------------------------------------------------ //

/// Flip a coin. On heads, set cant_attack_next_turn on the OPPONENT's active
/// (the Defending Pokémon can't attack during your opponent's next turn).
pub fn coin_flip_attack_block_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let heads = state.rng.gen::<f64>() < 0.5;
    state.coin_flip_log.push(if heads {
        "🪙 Heads! Opponent can't attack next turn".to_string()
    } else {
        "🪙 Tails! No effect".to_string()
    });
    if heads {
        let opp = get_opponent(ctx);
        if let Some(slot) = state.players[opp].active.as_mut() {
            slot.cant_attack_next_turn = true;
        }
    }
}

/// Flip a coin. On heads, set cant_attack_next_turn on the ACTING player's
/// own active (self-inflicted attack block).
pub fn coin_flip_self_cant_attack_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let heads = state.rng.gen::<f64>() < 0.5;
    if heads {
        if let Some(slot) = state.players[ctx.acting_player].active.as_mut() {
            slot.cant_attack_next_turn = true;
        }
    }
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};
    use crate::effects::EffectContext;

    fn make_state_with_two_active() -> (GameState, EffectContext) {
        let mut state = GameState::new(12345);
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state.players[1].active = Some(PokemonSlot::new(1, 100));
        let ctx = EffectContext::new(0); // acting_player = 0, opponent = 1
        (state, ctx)
    }

    #[test]
    fn apply_poison_sets_poisoned_on_opponent() {
        let (mut state, ctx) = make_state_with_two_active();
        apply_poison(&mut state, &ctx);
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(opp_active.has_status(StatusEffect::Poisoned));
        // Acting player's active should be unaffected
        let own_active = state.players[0].active.as_ref().unwrap();
        assert!(!own_active.has_status(StatusEffect::Poisoned));
    }

    #[test]
    fn apply_burn_sets_burned_on_opponent() {
        let (mut state, ctx) = make_state_with_two_active();
        apply_burn(&mut state, &ctx);
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(opp_active.has_status(StatusEffect::Burned));
    }

    #[test]
    fn apply_sleep_sets_asleep_on_opponent() {
        let (mut state, ctx) = make_state_with_two_active();
        apply_sleep(&mut state, &ctx);
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(opp_active.has_status(StatusEffect::Asleep));
    }

    #[test]
    fn apply_paralysis_sets_paralyzed_on_opponent() {
        let (mut state, ctx) = make_state_with_two_active();
        apply_paralysis(&mut state, &ctx);
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(opp_active.has_status(StatusEffect::Paralyzed));
    }

    #[test]
    fn apply_confusion_sets_confused_on_opponent() {
        let (mut state, ctx) = make_state_with_two_active();
        apply_confusion(&mut state, &ctx);
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(opp_active.has_status(StatusEffect::Confused));
    }

    #[test]
    fn self_confuse_sets_confused_on_acting_player() {
        let (mut state, ctx) = make_state_with_two_active();
        self_confuse(&mut state, &ctx);
        let own_active = state.players[0].active.as_ref().unwrap();
        assert!(own_active.has_status(StatusEffect::Confused));
        // Opponent should be unaffected
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(!opp_active.has_status(StatusEffect::Confused));
    }

    #[test]
    fn self_sleep_sets_asleep_on_acting_player() {
        let (mut state, ctx) = make_state_with_two_active();
        self_sleep(&mut state, &ctx);
        let own_active = state.players[0].active.as_ref().unwrap();
        assert!(own_active.has_status(StatusEffect::Asleep));
    }

    #[test]
    fn toxic_poison_applies_poisoned() {
        let (mut state, ctx) = make_state_with_two_active();
        toxic_poison(&mut state, &ctx);
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(opp_active.has_status(StatusEffect::Poisoned));
    }

    #[test]
    fn apply_random_status_sets_some_status_on_opponent() {
        let (mut state, ctx) = make_state_with_two_active();
        apply_random_status(&mut state, &ctx);
        let opp_active = state.players[1].active.as_ref().unwrap();
        assert!(opp_active.has_any_status(), "opponent should have at least one status after apply_random_status");
    }

    #[test]
    fn coin_flip_apply_paralysis_roughly_50_percent() {
        let trials = 1000;
        let mut heads_count = 0usize;
        // Use different seeds to get independent results
        for seed in 0..trials {
            let (mut state, ctx) = (GameState::new(seed as u64), EffectContext::new(0));
            state.players[0].active = Some(PokemonSlot::new(0, 100));
            state.players[1].active = Some(PokemonSlot::new(1, 100));
            coin_flip_apply_paralysis(&mut state, &ctx);
            if state.players[1].active.as_ref().unwrap().has_status(StatusEffect::Paralyzed) {
                heads_count += 1;
            }
        }
        // Expect roughly 450-550 out of 1000
        assert!(
            heads_count >= 420 && heads_count <= 580,
            "coin flip paralysis out of expected range: {} / {}",
            heads_count,
            trials
        );
    }

    #[test]
    fn coin_flip_attack_block_next_turn_sets_cant_attack_on_opponent() {
        // Run many times to ensure it sometimes fires; check that when it does, it's on the opponent
        let mut any_blocked = false;
        for seed in 0..200u64 {
            let (mut state, ctx) = (GameState::new(seed), EffectContext::new(0));
            state.players[0].active = Some(PokemonSlot::new(0, 100));
            state.players[1].active = Some(PokemonSlot::new(1, 100));
            coin_flip_attack_block_next_turn(&mut state, &ctx);
            let opp = state.players[1].active.as_ref().unwrap();
            let own = state.players[0].active.as_ref().unwrap();
            if opp.cant_attack_next_turn {
                any_blocked = true;
                assert!(!own.cant_attack_next_turn, "own should not have cant_attack set");
            }
        }
        assert!(any_blocked, "Expected at least one heads in 200 trials");
    }

    #[test]
    fn coin_flip_self_cant_attack_next_turn_sets_flag_on_self() {
        let mut any_blocked = false;
        for seed in 0..200u64 {
            let (mut state, ctx) = (GameState::new(seed), EffectContext::new(0));
            state.players[0].active = Some(PokemonSlot::new(0, 100));
            state.players[1].active = Some(PokemonSlot::new(1, 100));
            coin_flip_self_cant_attack_next_turn(&mut state, &ctx);
            let own = state.players[0].active.as_ref().unwrap();
            let opp = state.players[1].active.as_ref().unwrap();
            if own.cant_attack_next_turn {
                any_blocked = true;
                assert!(!opp.cant_attack_next_turn, "opponent should not have cant_attack set");
            }
        }
        assert!(any_blocked, "Expected at least one heads in 200 trials");
    }
}
