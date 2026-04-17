//! Evolve logic.
//!
//! Ported from `ptcgp/engine/state.py` (evolve_pokemon section).

use crate::card::CardDb;
use crate::state::{GameState, get_slot_mut};
use crate::actions::SlotRef;
use crate::effects::{EffectKind, EffectContext};
use crate::effects::dispatch::apply_effects;

/// Evolve a Pokemon: replace the slot's card with the evolution card from hand.
///
/// Validates:
/// - The evolution card's `evolves_from` matches the current base card's name.
/// - The slot has been in play for at least 1 turn.
/// - The slot has not already evolved this turn.
pub fn evolve_pokemon(
    state: &mut GameState,
    db: &CardDb,
    hand_index: usize,
    target: SlotRef,
) {
    let current = state.current_player;
    let player = &state.players[current];

    assert!(
        hand_index < player.hand.len(),
        "Invalid hand_index {}: hand has {} cards",
        hand_index,
        player.hand.len()
    );

    let evo_card_idx = player.hand[hand_index];
    let evo_card = db.get_by_idx(evo_card_idx);

    // Get base card name from target slot.
    let target_slot = get_slot_mut(state, target)
        .expect("No Pokemon at target slot for evolution");

    let base_card_name = db.get_by_idx(target_slot.card_idx).name.clone();

    // Validate evolution chain.
    assert_eq!(
        evo_card.evolves_from.as_deref(),
        Some(base_card_name.as_str()),
        "Evolution card {:?} does not evolve from {:?}",
        evo_card.name,
        base_card_name
    );

    // Validate turns_in_play >= 1 (can't evolve on the turn it was played).
    assert!(
        target_slot.turns_in_play >= 1,
        "Cannot evolve {} — it was just played this turn",
        base_card_name
    );

    // Validate not already evolved this turn.
    assert!(
        !target_slot.evolved_this_turn,
        "Cannot evolve {} — already evolved this turn",
        base_card_name
    );

    // Compute HP delta.
    let old_max_hp = target_slot.max_hp;
    let new_max_hp = evo_card.hp;
    let hp_increase = new_max_hp - old_max_hp;

    // Apply evolution.
    let target_slot = get_slot_mut(state, target).unwrap();
    target_slot.card_idx = evo_card_idx;
    target_slot.max_hp = new_max_hp;
    // Increase current_hp by the difference, capped at new max.
    target_slot.current_hp = (target_slot.current_hp + hp_increase).min(new_max_hp).max(0);
    // Clear all status effects.
    target_slot.clear_status();
    // Mark evolved this turn.
    target_slot.evolved_this_turn = true;
    // Energy, tool, and damage carry over (no clearing needed).

    // Remove evo card from hand.
    state.players[current].hand.remove(hand_index);

    // Fire any on-evolve triggered abilities on the newly-evolved card
    // (e.g. Charmeleon B2b-008 Ignition: attach 1 Fire energy from the
    // Energy Zone to the active Fire Pokémon when played to evolve).
    trigger_on_evolve_abilities(state, db, target, evo_card_idx);
}

/// Fire any "on evolve" triggered ability effects on `evo_card_idx`.
///
/// Currently triggers `EffectKind::OnEvolveAttachEnergyActive`
/// (Charmeleon Ignition).  The acting player is the player who controls
/// the evolved slot (`target.player`).
fn trigger_on_evolve_abilities(
    state: &mut GameState,
    db: &CardDb,
    target: SlotRef,
    evo_card_idx: u16,
) {
    let card = match db.try_get_by_idx(evo_card_idx) {
        Some(c) => c,
        None => return,
    };
    let ability = match card.ability.as_ref() {
        Some(a) => a,
        None => return,
    };
    let effects: Vec<EffectKind> = ability.effects.iter()
        .filter(|e| matches!(e, EffectKind::OnEvolveAttachEnergyActive { .. }))
        .cloned()
        .collect();
    if effects.is_empty() {
        return;
    }
    let p = target.player as usize;
    let ctx = EffectContext {
        acting_player: p,
        source_ref: Some(target),
        target_ref: None,
        extra_target_ref: None,
        extra: Default::default(),
    };
    apply_effects(state, db, &effects, &ctx);
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::CardDb;
    use crate::state::{GameState, PokemonSlot};
    use crate::types::{GamePhase, StatusEffect};
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

    /// Find Ivysaur (stage 1 that evolves from Bulbasaur).
    fn ivysaur_idx(db: &CardDb) -> u16 {
        db.cards
            .iter()
            .find(|c| c.name == "Ivysaur")
            .expect("Ivysaur not found")
            .idx
    }

    fn bulbasaur_idx(db: &CardDb) -> u16 {
        db.get_by_id("a1-001").expect("a1-001 not found").idx
    }

    fn make_state_with_bulbasaur(db: &CardDb) -> GameState {
        let bulb_idx = bulbasaur_idx(db);
        let bulb = db.get_by_idx(bulb_idx);
        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        let mut slot = PokemonSlot::new(bulb_idx, bulb.hp);
        slot.turns_in_play = 1; // can evolve
        state.players[0].active = Some(slot);
        state
    }

    #[test]
    fn evolve_pokemon_updates_card_idx_and_clears_status() {
        let db = load_db();
        let ivysaur_idx = ivysaur_idx(&db);

        let mut state = make_state_with_bulbasaur(&db);
        // Add Ivysaur to hand.
        state.players[0].hand.push(ivysaur_idx);
        // Add a status effect.
        state.players[0].active.as_mut().unwrap().add_status(StatusEffect::Poisoned);
        assert!(state.players[0].active.as_ref().unwrap().has_status(StatusEffect::Poisoned));

        evolve_pokemon(&mut state, &db, 0, SlotRef::active(0));

        let active = state.players[0].active.as_ref().unwrap();
        assert_eq!(active.card_idx, ivysaur_idx, "card_idx should be updated to Ivysaur");
        assert!(!active.has_any_status(), "Status effects should be cleared after evolution");
        assert!(active.evolved_this_turn, "evolved_this_turn should be set");
        assert!(state.players[0].hand.is_empty(), "Evo card should be removed from hand");
    }

    #[test]
    fn evolve_pokemon_increases_hp() {
        let db = load_db();
        let ivysaur_idx = ivysaur_idx(&db);
        let ivysaur_hp = db.get_by_idx(ivysaur_idx).hp;
        let bulb_hp = db.get_by_idx(bulbasaur_idx(&db)).hp;
        let _ = bulb_hp; // used for documentation

        let mut state = make_state_with_bulbasaur(&db);
        state.players[0].hand.push(ivysaur_idx);

        evolve_pokemon(&mut state, &db, 0, SlotRef::active(0));

        let active = state.players[0].active.as_ref().unwrap();
        assert_eq!(active.max_hp, ivysaur_hp);
        // HP should be increased by the difference (Bulbasaur full HP → Ivysaur gets more HP).
        let expected_hp = (bulb_hp + (ivysaur_hp - bulb_hp)).min(ivysaur_hp);
        assert_eq!(active.current_hp, expected_hp);
    }

    #[test]
    #[should_panic(expected = "already evolved this turn")]
    fn evolve_pokemon_twice_panics() {
        let db = load_db();
        let ivysaur_idx = ivysaur_idx(&db);
        let mut state = make_state_with_bulbasaur(&db);
        state.players[0].active.as_mut().unwrap().evolved_this_turn = true;
        state.players[0].hand.push(ivysaur_idx);
        evolve_pokemon(&mut state, &db, 0, SlotRef::active(0));
    }
}
