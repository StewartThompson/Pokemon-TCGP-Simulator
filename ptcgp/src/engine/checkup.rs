use rand::Rng;
use crate::card::CardDb;
use crate::effects::EffectKind;
use crate::state::GameState;
use crate::types::StatusEffect;
use crate::constants::{POISON_DAMAGE, BURN_DAMAGE};

/// Apply between-turns status effects for the current player's active Pokemon.
///
/// Called BEFORE end_turn, so `state.current_player` refers to the player who
/// just finished their turn. Mirrors `ptcgp/engine/checkup.py`.
///
/// Order of operations (per Python reference):
/// 1. Poisoned  — deal POISON_DAMAGE (10) to active
/// 2. Burned    — deal BURN_DAMAGE (20) to active; coin flip heads cures Burn
/// 3. Paralyzed — auto-cured (no damage)
/// 4. Asleep    — coin flip heads cures Sleep (no damage)
/// 5. Confused  — no automatic checkup effect
///
/// HP is clamped to 0 if status damage would take it below. KO resolution
/// is handled one level up.
pub fn resolve_between_turns(state: &mut GameState, db: &CardDb) {
    let p = state.current_player;
    let opp = 1 - p;

    // Check if there is an active Pokemon at all
    if state.players[p].active.is_none() {
        return;
    }

    // --- Poisoned: deal damage (base + any extra from More Poison / Nihilego) ---
    if state.players[p].active.as_ref().unwrap().has_status(StatusEffect::Poisoned) {
        // Count ALL of the opponent's in-play Pokémon (active + bench) that
        // have the ToxicPoison ability (Nihilego "More Poison").  The card
        // text says "+10 damage from being Poisoned" — and per user, it
        // stacks: 2 Nihilegos = +20, 3 = +30, etc.
        let has_toxic_poison = |slot: &crate::state::PokemonSlot| -> bool {
            db.try_get_by_idx(slot.card_idx)
                .and_then(|card| card.ability.as_ref())
                .map(|ab| ab.effects.iter().any(|e| matches!(e, EffectKind::ToxicPoison)))
                .unwrap_or(false)
        };
        let mut nihilego_count: i16 = 0;
        if let Some(s) = state.players[opp].active.as_ref() {
            if has_toxic_poison(s) { nihilego_count += 1; }
        }
        for j in 0..3 {
            if let Some(s) = state.players[opp].bench[j].as_ref() {
                if has_toxic_poison(s) { nihilego_count += 1; }
            }
        }
        let poison_dmg = POISON_DAMAGE + (nihilego_count * 10);
        state.players[p].active.as_mut().unwrap().current_hp -= poison_dmg;
    }

    // --- Burned: deal damage, then coin flip to maybe cure ---
    if state.players[p].active.as_ref().unwrap().has_status(StatusEffect::Burned) {
        state.players[p].active.as_mut().unwrap().current_hp -= BURN_DAMAGE;
        // coin flip: heads (true) cures burn
        let heads = state.rng.gen::<f64>() < 0.5;
        if heads {
            state.players[p].active.as_mut().unwrap().remove_status(StatusEffect::Burned);
        }
    }

    // --- Paralyzed: auto-cure, no damage ---
    if state.players[p].active.as_ref().unwrap().has_status(StatusEffect::Paralyzed) {
        state.players[p].active.as_mut().unwrap().remove_status(StatusEffect::Paralyzed);
    }

    // --- Asleep: coin flip to maybe cure ---
    if state.players[p].active.as_ref().unwrap().has_status(StatusEffect::Asleep) {
        // coin flip: heads wakes up
        let heads = state.rng.gen::<f64>() < 0.5;
        if heads {
            state.players[p].active.as_mut().unwrap().remove_status(StatusEffect::Asleep);
        }
    }

    // --- Clamp HP to 0 ---
    let active = state.players[p].active.as_mut().unwrap();
    if active.current_hp < 0 {
        active.current_hp = 0;
    }
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::CardDb;
    use crate::state::{GameState, PokemonSlot};
    use crate::types::StatusEffect;

    fn empty_db() -> CardDb {
        CardDb::new_empty()
    }

    fn make_state_with_active(hp: i16) -> GameState {
        let mut state = GameState::new(42);
        state.players[0].active = Some(PokemonSlot::new(0, hp));
        state
    }

    #[test]
    fn test_poison_deals_damage() {
        let mut state = make_state_with_active(100);
        state.players[0].active.as_mut().unwrap().add_status(StatusEffect::Poisoned);

        resolve_between_turns(&mut state, &empty_db());

        let hp = state.players[0].active.as_ref().unwrap().current_hp;
        assert_eq!(hp, 90, "Poison should deal 10 damage: expected 90 got {hp}");
    }

    #[test]
    fn test_burn_deals_damage() {
        let mut state = GameState::new(0);
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state.players[0].active.as_mut().unwrap().add_status(StatusEffect::Burned);

        resolve_between_turns(&mut state, &empty_db());

        let hp = state.players[0].active.as_ref().unwrap().current_hp;
        // HP must have dropped by exactly BURN_DAMAGE (20), possibly also cured
        assert!(hp <= 80, "Burn should deal at least 20 damage: expected <=80, got {hp}");
    }

    #[test]
    fn test_paralysis_cured_automatically() {
        let mut state = make_state_with_active(100);
        state.players[0].active.as_mut().unwrap().add_status(StatusEffect::Paralyzed);

        resolve_between_turns(&mut state, &empty_db());

        let still_paralyzed = state.players[0]
            .active.as_ref().unwrap()
            .has_status(StatusEffect::Paralyzed);
        assert!(!still_paralyzed, "Paralysis should be auto-cured between turns");
    }

    #[test]
    fn test_paralysis_deals_no_damage() {
        let mut state = make_state_with_active(100);
        state.players[0].active.as_mut().unwrap().add_status(StatusEffect::Paralyzed);

        resolve_between_turns(&mut state, &empty_db());

        let hp = state.players[0].active.as_ref().unwrap().current_hp;
        assert_eq!(hp, 100, "Paralysis should deal no damage");
    }

    #[test]
    fn test_hp_clamped_to_zero() {
        // Start at 5 HP, apply both poison and burn to guarantee going below 0
        let mut state = make_state_with_active(5);
        {
            let active = state.players[0].active.as_mut().unwrap();
            active.add_status(StatusEffect::Poisoned);
            active.add_status(StatusEffect::Burned);
        }

        resolve_between_turns(&mut state, &empty_db());

        let hp = state.players[0].active.as_ref().unwrap().current_hp;
        assert_eq!(hp, 0, "HP should be clamped to 0, got {hp}");
    }

    #[test]
    fn test_confused_no_checkup_effect() {
        let mut state = make_state_with_active(100);
        state.players[0].active.as_mut().unwrap().add_status(StatusEffect::Confused);

        resolve_between_turns(&mut state, &empty_db());

        let hp = state.players[0].active.as_ref().unwrap().current_hp;
        assert_eq!(hp, 100, "Confused should not deal damage between turns");

        let still_confused = state.players[0]
            .active.as_ref().unwrap()
            .has_status(StatusEffect::Confused);
        assert!(still_confused, "Confused should not be auto-cured between turns");
    }

    #[test]
    fn test_no_active_pokemon_does_not_panic() {
        let mut state = GameState::new(42);
        // No active set — should return cleanly
        resolve_between_turns(&mut state, &empty_db());
    }

    #[test]
    fn test_only_current_player_affected() {
        // Opponent's active should be untouched
        let mut state = GameState::new(42);
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state.players[1].active = Some(PokemonSlot::new(1, 100));
        state.players[1].active.as_mut().unwrap().add_status(StatusEffect::Poisoned);
        state.current_player = 0;

        resolve_between_turns(&mut state, &empty_db());

        let opp_hp = state.players[1].active.as_ref().unwrap().current_hp;
        assert_eq!(opp_hp, 100, "Opponent's active should be unaffected: got {opp_hp}");
    }
}
