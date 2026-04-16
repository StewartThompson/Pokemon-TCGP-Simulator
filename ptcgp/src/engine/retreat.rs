//! Retreat logic: swap active Pokemon with a bench Pokemon.
//!
//! Ported from `ptcgp/engine/retreat.py`.

use rand::Rng;
use crate::card::CardDb;
use crate::effects::EffectKind;
use crate::state::GameState;
use crate::types::{Element, StatusEffect};

/// Retreat the active Pokemon to the bench, swapping with bench[bench_slot].
///
/// Validates:
/// - Player has not already retreated this turn.
/// - Active Pokemon exists and is not Paralyzed or Asleep.
/// - Active Pokemon's `cant_retreat_next_turn` flag is not set.
/// - There is enough total energy to pay the retreat cost.
///
/// Then randomly discards `retreat_cost` energy tokens and swaps active/bench.
pub fn retreat(state: &mut GameState, db: &CardDb, bench_slot: usize) {
    let current = state.current_player;

    assert!(
        !state.players[current].has_retreated,
        "Player {} has already retreated this turn",
        current
    );

    let active = state.players[current]
        .active
        .as_ref()
        .expect("No active Pokemon to retreat");

    assert!(
        !active.has_status(StatusEffect::Paralyzed),
        "Active Pokemon is Paralyzed and cannot retreat"
    );
    assert!(
        !active.has_status(StatusEffect::Asleep),
        "Active Pokemon is Asleep and cannot retreat"
    );
    assert!(
        !active.cant_retreat_next_turn,
        "Active Pokemon cannot retreat this turn (cant_retreat flag set)"
    );

    assert!(bench_slot < 3, "Invalid bench_slot {}", bench_slot);
    assert!(
        state.players[current].bench[bench_slot].is_some(),
        "No Pokemon in bench slot {}",
        bench_slot
    );

    let active_card_idx = active.card_idx;
    let active_card = db.get_by_idx(active_card_idx);
    // Sentinel: card.rs sets retreat_cost = u8::MAX for "can't retreat" Pokémon.
    // legal_actions filters Retreat in this case, but a buggy agent could still
    // submit one — return gracefully instead of panicking the simulator.
    if active_card.retreat_cost == u8::MAX {
        eprintln!(
            "warning: retreat blocked — Pokémon '{}' has retreat_cost == u8::MAX (cannot retreat)",
            active_card.name
        );
        return;
    }
    // Tool passive: check for retreat cost reduction (e.g. Inflatable Boat).
    let tool_reduction: i8 = active.tool_idx
        .and_then(|tidx| db.try_get_by_idx(tidx))
        .map(|tool| {
            tool.trainer_effects.iter().find_map(|e| {
                if let EffectKind::PassiveBenchRetreatReduction { amount } = e {
                    Some(*amount as i8)
                } else {
                    None
                }
            }).unwrap_or(0)
        })
        .unwrap_or(0);
    let retreat_cost = (active_card.retreat_cost as i8
        + state.players[current].retreat_cost_modifier
        - tool_reduction)
        .max(0) as u8;

    let total_energy = state.players[current]
        .active
        .as_ref()
        .unwrap()
        .total_energy();
    assert!(
        total_energy >= retreat_cost,
        "Not enough energy to retreat: need {}, have {}",
        retreat_cost,
        total_energy
    );

    // Randomly discard `retreat_cost` energy tokens.
    if retreat_cost > 0 {
        // Build flat list of (element_idx, count) pairs.
        let mut energy_list: Vec<Element> = Vec::new();
        let active_slot = state.players[current].active.as_ref().unwrap();
        for el_idx in 0..8usize {
            let count = active_slot.energy[el_idx];
            if count > 0 {
                // Map index back to Element.
                let el = idx_to_element(el_idx);
                for _ in 0..count {
                    energy_list.push(el);
                }
            }
        }

        // Fisher-Yates partial shuffle to pick `retreat_cost` random tokens.
        let n = energy_list.len();
        let cost = retreat_cost as usize;
        let mut shuffled = energy_list.clone();
        for i in 0..cost {
            let j = i + state.rng.gen_range(0..(n - i));
            shuffled.swap(i, j);
        }
        // Discard the first `retreat_cost` tokens from the shuffled list.
        let discarded = &shuffled[..cost];
        let active_slot = state.players[current].active.as_mut().unwrap();
        for &el in discarded {
            active_slot.remove_energy(el, 1);
        }
    }

    // Clear status effects from the retreating Pokemon (old active).
    // Also clear the cant_attack_next_turn flag — it is tied to being in the
    // active position, not to the Pokémon itself.  If the Pokémon retreats, the
    // debuff ends (same real-game behaviour as Paralysis/Sleep on retreat).
    {
        let slot = state.players[current].active.as_mut().unwrap();
        slot.clear_status();
        slot.cant_attack_next_turn = false;
    }

    // Swap active <-> bench[bench_slot].
    let new_active = state.players[current].bench[bench_slot].take();
    let old_active = state.players[current].active.take();
    state.players[current].active = new_active;
    state.players[current].bench[bench_slot] = old_active;

    // NOTE (Bug 4 fix): We deliberately do NOT clear status on the newly
    // promoted active.  Per RULES.md §5 only the *retreating* Pokémon has its
    // status effects removed.  The Pokémon coming up from the bench keeps any
    // legitimate statuses it had while benched.

    state.players[current].has_retreated = true;
}

/// Convert an EnergyArray index (0-7) back to an Element.
fn idx_to_element(idx: usize) -> Element {
    match idx {
        0 => Element::Grass,
        1 => Element::Fire,
        2 => Element::Water,
        3 => Element::Lightning,
        4 => Element::Psychic,
        5 => Element::Fighting,
        6 => Element::Darkness,
        7 => Element::Metal,
        _ => panic!("Invalid element index {}", idx),
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
    use crate::types::{Element, GamePhase, StatusEffect};
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

    fn make_state_for_retreat(db: &CardDb) -> (GameState, u16) {
        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        // Active Bulbasaur with 1 energy (retreat_cost = 1).
        let mut active = PokemonSlot::new(bulb.idx, bulb.hp);
        active.add_energy(Element::Grass, 1);
        state.players[0].active = Some(active);
        // Bench Pokemon to swap with.
        state.players[0].bench[0] = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        (state, bulb.idx)
    }

    #[test]
    fn retreat_swaps_active_and_bench() {
        let db = load_db();
        let (mut state, _bulb_idx) = make_state_for_retreat(&db);

        retreat(&mut state, &db, 0);

        // The previously active card should now be on the bench.
        assert!(state.players[0].bench[0].is_some());
        assert!(state.players[0].active.is_some());
        assert!(state.players[0].has_retreated, "has_retreated should be set");
    }

    #[test]
    fn retreat_discards_energy() {
        let db = load_db();
        let (mut state, _bulb_idx2) = make_state_for_retreat(&db);
        let energy_before = state.players[0].active.as_ref().unwrap().total_energy();
        // Bulbasaur retreat_cost == 1
        let retreat_cost = db.get_by_id("a1-001").unwrap().retreat_cost;
        retreat(&mut state, &db, 0);
        // After retreat the slot is now on bench; check old active (now bench[0]).
        let old_active = state.players[0].bench[0].as_ref().unwrap();
        let energy_after = old_active.total_energy();
        assert_eq!(
            energy_after,
            energy_before.saturating_sub(retreat_cost),
            "Energy should be reduced by retreat cost"
        );
    }

    #[test]
    #[should_panic(expected = "Paralyzed and cannot retreat")]
    fn retreat_paralyzed_panics() {
        let db = load_db();
        let (mut state, _bulb_idx3) = make_state_for_retreat(&db);
        state.players[0].active.as_mut().unwrap().add_status(StatusEffect::Paralyzed);
        retreat(&mut state, &db, 0);
    }

    // -- u8::MAX retreat_cost sentinel: cannot retreat even with abundant energy --
    // The function returns gracefully (no panic) and leaves state untouched so
    // a buggy agent doesn't crash the simulator.
    #[test]
    fn retreat_max_cost_no_op_even_with_energy() {
        use crate::card::Card;
        use crate::types::{CardKind, Stage};

        // Build a synthetic card with retreat_cost = u8::MAX.
        let card = Card {
            id: "test-noretreat".to_string(),
            idx: 0,
            name: "NoRetreatMon".to_string(),
            kind: CardKind::Pokemon,
            stage: Some(Stage::Basic),
            element: Some(Element::Grass),
            hp: 100,
            weakness: None,
            retreat_cost: u8::MAX,
            is_ex: false,
            is_mega_ex: false,
            evolves_from: None,
            attacks: vec![],
            ability: None,
            trainer_effect_text: String::new(),
            trainer_handler: String::new(),
            trainer_effects: vec![],
            ko_points: 1,
        };
        let mut db = CardDb::new_empty();
        db.id_to_idx.insert(card.id.clone(), 0u16);
        db.name_to_indices.insert(card.name.clone(), vec![0u16]);
        db.cards.push(card);

        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        let mut active = PokemonSlot::new(0, 100);
        // Give it a huge amount of energy so the only blocker is the sentinel.
        active.add_energy(Element::Grass, 8);
        state.players[0].active = Some(active);
        state.players[0].bench[0] = Some(PokemonSlot::new(0, 100));

        // Should not panic. Should leave state unchanged (no swap, no energy spent).
        retreat(&mut state, &db, 0);
        assert!(
            !state.players[0].has_retreated,
            "retreat() with sentinel cost should be a no-op (no has_retreated flip)"
        );
        assert_eq!(
            state.players[0].active.as_ref().unwrap().total_energy(),
            8,
            "retreat() with sentinel cost should not consume energy"
        );
        assert_eq!(
            state.players[0].active.as_ref().unwrap().card_idx, 0,
            "retreat() with sentinel cost should not swap active and bench"
        );
    }

    #[test]
    fn legal_actions_emits_no_retreat_when_cost_is_max() {
        use crate::card::Card;
        use crate::engine::legal_actions::get_legal_actions;
        use crate::types::{ActionKind, CardKind, Stage};

        let card = Card {
            id: "test-noretreat-la".to_string(),
            idx: 0,
            name: "NoRetreatMon".to_string(),
            kind: CardKind::Pokemon,
            stage: Some(Stage::Basic),
            element: Some(Element::Grass),
            hp: 100,
            weakness: None,
            retreat_cost: u8::MAX,
            is_ex: false,
            is_mega_ex: false,
            evolves_from: None,
            attacks: vec![],
            ability: None,
            trainer_effect_text: String::new(),
            trainer_handler: String::new(),
            trainer_effects: vec![],
            ko_points: 1,
        };
        let mut db = CardDb::new_empty();
        db.id_to_idx.insert(card.id.clone(), 0u16);
        db.name_to_indices.insert(card.name.clone(), vec![0u16]);
        db.cards.push(card);

        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 5;
        let mut active = PokemonSlot::new(0, 100);
        active.add_energy(Element::Grass, 8);
        state.players[0].active = Some(active);
        state.players[0].bench[0] = Some(PokemonSlot::new(0, 100));

        let actions = get_legal_actions(&state, &db);
        assert!(
            !actions.iter().any(|a| a.kind == ActionKind::Retreat),
            "Should emit no Retreat action when retreat_cost == u8::MAX"
        );
    }

    // -- Bug 4: status on the bench Pokemon must be preserved after retreat --
    #[test]
    fn retreat_preserves_status_on_promoted_active() {
        let db = load_db();
        let (mut state, _bulb_idx) = make_state_for_retreat(&db);
        // Apply a (legitimate) status effect to the bench Pokémon before retreat.
        state.players[0].bench[0].as_mut().unwrap().add_status(StatusEffect::Poisoned);

        retreat(&mut state, &db, 0);

        // After retreat the previously-benched Pokémon is now active and
        // should STILL carry its Poisoned status (Bug 4: previous code
        // incorrectly cleared status on the newly promoted active).
        let new_active = state.players[0].active.as_ref().unwrap();
        assert!(
            new_active.has_status(StatusEffect::Poisoned),
            "Newly promoted active should keep its bench-side status (Bug 4 fix)"
        );

        // The retreating Pokémon (now on bench) should have its statuses
        // cleared (rules of retreat).
        let retreated = state.players[0].bench[0].as_ref().unwrap();
        assert!(
            !retreated.has_any_status(),
            "Retreating Pokémon should have all statuses removed"
        );
    }
}
