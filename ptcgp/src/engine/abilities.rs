//! Ability activation logic.
//!
//! Ported from `ptcgp/engine/abilities.py`.

use crate::card::CardDb;
use crate::state::{GameState, get_slot_mut};
use crate::actions::SlotRef;
use crate::effects::EffectContext;
use crate::effects::dispatch::apply_effects;

/// Activate the non-passive ability of the Pokemon at `slot_ref`.
///
/// Panics if:
/// - No Pokemon at the slot.
/// - The card has no ability.
/// - The ability is passive (cannot be manually activated).
/// - The ability has already been used this turn.
pub fn use_ability(state: &mut GameState, db: &CardDb, slot_ref: SlotRef) {
    // Validate slot.
    let slot = get_slot_mut(state, slot_ref)
        .expect("No Pokemon at slot for ability activation");

    let card_idx = slot.card_idx;
    let card = db.get_by_idx(card_idx);

    // Validate ability exists.
    let ability = card.ability.as_ref().expect(
        "Pokemon has no ability to activate"
    );

    // Validate not passive.
    assert!(
        !ability.is_passive,
        "Ability {:?} is passive and cannot be activated manually",
        ability.name
    );

    // Validate not already used.
    assert!(
        !slot.ability_used_this_turn,
        "Ability {:?} has already been used this turn",
        ability.name
    );

    // Clone effects before any mutable borrow of state.
    let effects = ability.effects.clone();

    // Mark used.
    let slot = get_slot_mut(state, slot_ref).unwrap();
    slot.ability_used_this_turn = true;

    // Build context.
    let ctx = EffectContext {
        acting_player: slot_ref.player as usize,
        source_ref: Some(slot_ref),
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
    use crate::types::GamePhase;
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

    /// Find any card that has a non-passive ability.
    fn find_active_ability_card(db: &CardDb) -> Option<&crate::card::Card> {
        db.cards.iter().find(|c| {
            c.ability.as_ref().map(|a| !a.is_passive).unwrap_or(false)
        })
    }

    #[test]
    fn use_ability_marks_used_this_turn() {
        let db = load_db();
        // Find a card with an active (non-passive) ability.
        let card = match find_active_ability_card(&db) {
            Some(c) => c,
            None => {
                eprintln!("No non-passive ability card found in DB — skipping test");
                return;
            }
        };
        let card_idx = card.idx;

        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        let mut slot = PokemonSlot::new(card_idx, card.hp.max(1));
        slot.turns_in_play = 1;
        state.players[0].active = Some(slot);

        assert!(!state.players[0].active.as_ref().unwrap().ability_used_this_turn);

        use_ability(&mut state, &db, SlotRef::active(0));

        assert!(
            state.players[0].active.as_ref().unwrap().ability_used_this_turn,
            "ability_used_this_turn should be set after activation"
        );
    }

    #[test]
    #[should_panic(expected = "already been used this turn")]
    fn use_ability_twice_panics() {
        let db = load_db();
        let card = match find_active_ability_card(&db) {
            Some(c) => c,
            None => return, // skip if no suitable card
        };
        let card_idx = card.idx;

        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        let mut slot = PokemonSlot::new(card_idx, card.hp.max(1));
        slot.ability_used_this_turn = true;
        state.players[0].active = Some(slot);

        use_ability(&mut state, &db, SlotRef::active(0));
    }
}
