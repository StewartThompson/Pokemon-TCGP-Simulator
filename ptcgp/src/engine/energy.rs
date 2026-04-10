//! Energy attachment logic.
//!
//! Ported from `ptcgp/engine/turn.py` (attach_energy section).

use crate::card::CardDb;
use crate::state::{GameState, get_slot_mut};
use crate::actions::SlotRef;

/// Attach the currently generated energy to the target slot.
///
/// Panics if no energy is available or the player has already attached this turn.
pub fn attach_energy(state: &mut GameState, _db: &CardDb, target: SlotRef) {
    let current = state.current_player;

    let element = state.players[current]
        .energy_available
        .expect("No energy available to attach this turn");

    assert!(
        !state.players[current].has_attached_energy,
        "Player {} has already attached energy this turn",
        current
    );

    // Attach energy to the target slot.
    {
        let slot = get_slot_mut(state, target)
            .expect("No Pokemon at target slot for energy attachment");
        slot.add_energy(element, 1);
    }

    // Mark flags.
    state.players[current].has_attached_energy = true;
    state.players[current].energy_available = None;
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::CardDb;
    use crate::state::{GameState, PokemonSlot};
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

    fn make_state_with_active(db: &CardDb) -> GameState {
        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        state.players[0].active = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[0].energy_available = Some(Element::Grass);
        state
    }

    #[test]
    fn attach_energy_adds_to_slot_and_sets_flag() {
        let db = load_db();
        let mut state = make_state_with_active(&db);
        let target = SlotRef::active(0);

        assert!(!state.players[0].has_attached_energy);
        let energy_before = state.players[0].active.as_ref().unwrap().total_energy();

        attach_energy(&mut state, &db, target);

        assert!(state.players[0].has_attached_energy, "has_attached_energy should be true");
        assert!(state.players[0].energy_available.is_none(), "energy_available should be cleared");
        let energy_after = state.players[0].active.as_ref().unwrap().total_energy();
        assert_eq!(energy_after, energy_before + 1, "Energy count should increase by 1");
        let grass_count = state.players[0].active.as_ref().unwrap().energy_count(Element::Grass);
        assert_eq!(grass_count, 1);
    }

    #[test]
    #[should_panic(expected = "No energy available")]
    fn attach_energy_no_energy_panics() {
        let db = load_db();
        let mut state = make_state_with_active(&db);
        state.players[0].energy_available = None;
        attach_energy(&mut state, &db, SlotRef::active(0));
    }

    #[test]
    #[should_panic(expected = "already attached energy")]
    fn attach_energy_twice_panics() {
        let db = load_db();
        let mut state = make_state_with_active(&db);
        state.players[0].has_attached_energy = true;
        attach_energy(&mut state, &db, SlotRef::active(0));
    }
}
