//! Main action dispatcher: apply_action routes each ActionKind to the
//! appropriate sub-module function.
//!
//! Ported from `ptcgp/engine/mutations.py`.

use crate::card::CardDb;
use crate::state::GameState;
use crate::actions::Action;
use crate::types::{ActionKind, CardKind, Stage};
use crate::engine::{
    attack, play_card, energy, evolve, retreat as retreat_mod, abilities,
    turn, ko,
};

/// Apply an action to the game state. Main dispatcher.
pub fn apply_action(state: &mut GameState, db: &CardDb, action: &Action) {
    match action.kind {
        ActionKind::PlayCard => {
            let hand_index = action.hand_index.expect("PlayCard requires hand_index");
            let card_idx = state.current().hand[hand_index];
            let card = db.get_by_idx(card_idx);

            match (card.kind, card.stage) {
                (CardKind::Pokemon, Some(Stage::Basic)) => {
                    let target = action.target.expect("PlayCard Basic requires target bench slot");
                    play_card::play_basic(
                        state,
                        db,
                        hand_index,
                        target.bench_index(),
                    );
                }
                (CardKind::Item, _) => {
                    play_card::play_item(
                        state,
                        db,
                        hand_index,
                        action.target,
                        action.extra_hand_index,
                    );
                }
                (CardKind::Supporter, _) => {
                    play_card::play_supporter(
                        state,
                        db,
                        hand_index,
                        action.target,
                    );
                }
                (CardKind::Tool, _) => {
                    let target = action.target.expect("PlayCard Tool requires a target slot");
                    play_card::attach_tool(state, db, hand_index, target);
                }
                _ => panic!(
                    "Unsupported card kind/stage for PlayCard: {:?}/{:?}",
                    card.kind, card.stage
                ),
            }
        }

        ActionKind::AttachEnergy => {
            let target = action.target.expect("AttachEnergy requires target");
            energy::attach_energy(state, db, target);
        }

        ActionKind::Evolve => {
            let hand_index = action.hand_index.expect("Evolve requires hand_index");
            let target = action.target.expect("Evolve requires target slot");
            evolve::evolve_pokemon(state, db, hand_index, target);
        }

        ActionKind::UseAbility => {
            let slot_ref = action.target.expect("UseAbility requires target slot");
            abilities::use_ability(state, db, slot_ref);
        }

        ActionKind::Retreat => {
            let target = action.target.expect("Retreat requires target bench slot");
            retreat_mod::retreat(state, db, target.bench_index());
        }

        ActionKind::Attack => {
            let attack_index = action.attack_index.expect("Attack requires attack_index");
            attack::execute_attack(state, db, attack_index, action.target);
        }

        ActionKind::EndTurn => {
            turn::advance_turn(state, db);
        }

        ActionKind::Promote => {
            let target = action.target.expect("Promote requires target slot");
            ko::promote_bench(state, target.slot as usize, target.player as usize);
        }
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
    use crate::actions::{Action, SlotRef};
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

    fn make_state_with_actives(db: &CardDb) -> GameState {
        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        state.turn_number = 0;
        state.players[0].active = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[1].active = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[0].energy_types = vec![Element::Grass];
        state.players[1].energy_types = vec![Element::Grass];
        state
    }

    #[test]
    fn apply_action_end_turn_switches_player() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        state.current_player = 0;
        let turn_before = state.turn_number;

        apply_action(&mut state, &db, &Action::end_turn());

        // advance_turn calls end_turn (switches player) and start_turn (increments turn_number).
        assert_eq!(
            state.turn_number,
            turn_before + 1,
            "turn_number should increment after EndTurn"
        );
        // After advance_turn: end_turn switches to 1, start_turn runs for player 1.
        assert_eq!(state.current_player, 1, "current_player should be 1 after advance from 0");
    }

    #[test]
    fn apply_action_attach_energy() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        state.players[0].energy_available = Some(Element::Grass);
        state.players[0].has_attached_energy = false;

        let action = Action::attach_energy(SlotRef::active(0));
        apply_action(&mut state, &db, &action);

        assert!(state.players[0].has_attached_energy);
        assert!(state.players[0].energy_available.is_none());
        let grass = state.players[0].active.as_ref().unwrap().energy_count(Element::Grass);
        assert_eq!(grass, 1);
    }

    #[test]
    fn apply_action_play_basic_to_bench() {
        let db = load_db();
        let mut state = make_state_with_actives(&db);
        let bulb = db.get_by_id("a1-001").unwrap();
        state.players[0].hand.push(bulb.idx);

        let action = Action::play_basic(0, SlotRef::bench(0, 0));
        apply_action(&mut state, &db, &action);

        assert!(state.players[0].bench[0].is_some());
        assert!(state.players[0].hand.is_empty());
    }
}
