/// Legal action generation for the battle engine.
///
/// Ports `ptcgp/engine/legal_actions.py` to Rust.
use crate::actions::{Action, SlotRef};
use crate::card::CardDb;
use crate::state::{GameState, PokemonSlot};
use crate::types::{CardKind, CostSymbol, GamePhase, Stage, StatusEffect};

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //

/// Check whether a slot's attached energy can pay the given cost.
///
/// CostSymbol::Colorless = any one energy.
/// Typed symbols must first be satisfied by that specific element; any
/// remaining typed requirement is a hard failure.
/// Colorless requirements are satisfied by whatever energy is left.
fn can_pay_cost(slot: &PokemonSlot, cost: &[CostSymbol]) -> bool {
    let mut remaining = slot.energy; // EnergyArray = [u8; 8]
    let mut colorless_needed: u8 = 0;
    for sym in cost {
        match sym.to_element() {
            None => colorless_needed += 1, // Colorless
            Some(el) => {
                let idx = el as usize;
                if remaining[idx] > 0 {
                    remaining[idx] -= 1;
                } else {
                    return false;
                }
            }
        }
    }
    let total: u8 = remaining.iter().sum();
    total >= colorless_needed
}

/// Check if the opponent's Active Pokemon has a passive ability whose text
/// blocks supporter cards (e.g. "can't use any supporter cards … active spot").
fn opponent_blocks_supporters(state: &GameState, db: &CardDb) -> bool {
    const BLOCK_TEXT: &str = "can't use any supporter cards";
    let opp = state.opponent();
    let slot = match opp.active.as_ref() {
        Some(s) => s,
        None => return false,
    };
    let card = db.get_by_idx(slot.card_idx);
    let ab = match card.ability.as_ref() {
        Some(a) => a,
        None => return false,
    };
    if ab.effect_text.is_empty() {
        return false;
    }
    let low = ab.effect_text.to_lowercase();
    low.contains(BLOCK_TEXT) && low.contains("active spot")
}

/// Enumerate legal Rare Candy plays for the current player.
///
/// For each Basic Pokemon in play that has been in play at least one turn
/// and hasn't evolved this turn, find every Stage 2 card in hand whose
/// evolution chain's Basic name matches.
fn rare_candy_actions(
    state: &GameState,
    db: &CardDb,
    rare_candy_hand_idx: usize,
) -> Vec<Action> {
    let cp = state.current_player;
    let player = state.current();
    let mut actions: Vec<Action> = Vec::new();

    // Turn restriction: same as regular evolve — no evolving on turn 0/1.
    if state.turn_number < 2 {
        return actions;
    }

    // Helper closure: check a single slot and append matching actions.
    let mut check_slot = |slot_ref: SlotRef| {
        let slot = match crate::state::get_slot(state, slot_ref) {
            Some(s) => s,
            None => return,
        };
        if slot.turns_in_play < 1 || slot.evolved_this_turn {
            return;
        }
        let basic_card = db.get_by_idx(slot.card_idx);
        if basic_card.stage != Some(Stage::Basic) {
            return;
        }
        let reachable = match db.basic_to_stage2.get(&basic_card.name) {
            Some(r) if !r.is_empty() => r,
            _ => return,
        };

        for (hidx, &card_idx) in player.hand.iter().enumerate() {
            if hidx == rare_candy_hand_idx {
                continue;
            }
            let hand_card = db.get_by_idx(card_idx);
            if hand_card.stage != Some(Stage::Stage2) {
                continue;
            }
            if reachable.contains(&hand_card.name) {
                actions.push(Action::play_rare_candy(rare_candy_hand_idx, slot_ref, hidx));
            }
        }
    };

    if player.active.is_some() {
        check_slot(SlotRef::active(cp));
    }
    for j in 0..3 {
        if player.bench[j].is_some() {
            check_slot(SlotRef::bench(cp, j));
        }
    }

    actions
}

// ------------------------------------------------------------------ //
// Public API
// ------------------------------------------------------------------ //

/// Return all legal actions for the current player when phase == Main.
pub fn get_legal_actions(state: &GameState, db: &CardDb) -> Vec<Action> {
    if state.phase != GamePhase::Main || state.winner.is_some() {
        return vec![];
    }

    let mut actions: Vec<Action> = Vec::new();
    let cp = state.current_player;
    let player = state.current();

    // ------------------------------------------------------------------ //
    // PLAY_CARD
    // ------------------------------------------------------------------ //
    for (i, &card_idx) in player.hand.iter().enumerate() {
        let card = db.get_by_idx(card_idx);

        match card.kind {
            CardKind::Pokemon if card.stage == Some(Stage::Basic) => {
                // Play basic to each empty bench slot.
                for j in 0..3 {
                    if player.bench[j].is_none() {
                        actions.push(Action::play_basic(i, SlotRef::bench(cp, j)));
                    }
                }
            }

            CardKind::Item => {
                if card.name == "Rare Candy" {
                    for rc in rare_candy_actions(state, db, i) {
                        actions.push(rc);
                    }
                    // Skip the generic play_item path for Rare Candy.
                    continue;
                }
                // Generic item: no specific slot target needed (target=None).
                // Complex targeting (e.g. heal a specific Pokemon) is handled
                // by the effect layer; here we emit one action with no target.
                actions.push(Action::play_item(i, None));
            }

            CardKind::Supporter => {
                if player.has_played_supporter {
                    continue;
                }
                if player.cant_play_supporter_this_turn {
                    continue;
                }
                if opponent_blocks_supporters(state, db) {
                    continue;
                }
                // One action per supporter (no sub-target at this layer).
                actions.push(Action::play_item(i, None));
            }

            CardKind::Tool => {
                // Attach to active if it has no tool.
                if let Some(ref active) = player.active {
                    if active.tool_idx.is_none() {
                        actions.push(Action {
                            kind: crate::types::ActionKind::PlayCard,
                            hand_index: Some(i),
                            target: Some(SlotRef::active(cp)),
                            attack_index: None,
                            extra_hand_index: None,
                        });
                    }
                }
                // Attach to each bench Pokemon that has no tool.
                for j in 0..3 {
                    if let Some(ref slot) = player.bench[j] {
                        if slot.tool_idx.is_none() {
                            actions.push(Action {
                                kind: crate::types::ActionKind::PlayCard,
                                hand_index: Some(i),
                                target: Some(SlotRef::bench(cp, j)),
                                attack_index: None,
                                extra_hand_index: None,
                            });
                        }
                    }
                }
            }

            _ => {} // Stage 1 / Stage 2 Pokemon played via EVOLVE, not PLAY_CARD
        }
    }

    // ------------------------------------------------------------------ //
    // ATTACH_ENERGY
    // ------------------------------------------------------------------ //
    if player.energy_available.is_some() && !player.has_attached_energy {
        if player.active.is_some() {
            actions.push(Action::attach_energy(SlotRef::active(cp)));
        }
        for j in 0..3 {
            if player.bench[j].is_some() {
                actions.push(Action::attach_energy(SlotRef::bench(cp, j)));
            }
        }
    }

    // ------------------------------------------------------------------ //
    // EVOLVE  (not on turn 0 or 1)
    // ------------------------------------------------------------------ //
    if state.turn_number >= 2 {
        // Re-borrow player each iteration to avoid lifetime issues.
        let hand_snapshot: Vec<u16> = state.current().hand.clone();
        for (i, &card_idx) in hand_snapshot.iter().enumerate() {
            let evo_card = db.get_by_idx(card_idx);
            if evo_card.kind != CardKind::Pokemon {
                continue;
            }
            match evo_card.stage {
                Some(Stage::Stage1) | Some(Stage::Stage2) => {}
                _ => continue,
            }
            let evolves_from = match evo_card.evolves_from.as_deref() {
                Some(s) => s,
                None => continue,
            };

            let player = state.current();

            // Check active slot.
            if let Some(ref active) = player.active {
                let active_card = db.get_by_idx(active.card_idx);
                if active_card.name == evolves_from
                    && active.turns_in_play >= 1
                    && !active.evolved_this_turn
                {
                    actions.push(Action::evolve(i, SlotRef::active(cp)));
                }
            }

            // Check bench slots.
            for j in 0..3 {
                if let Some(ref slot) = player.bench[j] {
                    let slot_card = db.get_by_idx(slot.card_idx);
                    if slot_card.name == evolves_from
                        && slot.turns_in_play >= 1
                        && !slot.evolved_this_turn
                    {
                        actions.push(Action::evolve(i, SlotRef::bench(cp, j)));
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // USE_ABILITY
    // ------------------------------------------------------------------ //
    let player = state.current();
    if let Some(ref active) = player.active {
        let card = db.get_by_idx(active.card_idx);
        if let Some(ref ab) = card.ability {
            if !ab.is_passive && !active.ability_used_this_turn {
                actions.push(Action::use_ability(SlotRef::active(cp)));
            }
        }
    }
    for j in 0..3 {
        if let Some(ref slot) = player.bench[j] {
            let card = db.get_by_idx(slot.card_idx);
            if let Some(ref ab) = card.ability {
                if !ab.is_passive && !slot.ability_used_this_turn {
                    actions.push(Action::use_ability(SlotRef::bench(cp, j)));
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // RETREAT
    // ------------------------------------------------------------------ //
    let player = state.current();
    if !player.has_retreated {
        if let Some(ref active) = player.active {
            if !active.has_status(StatusEffect::Paralyzed)
                && !active.has_status(StatusEffect::Asleep)
                && !active.cant_retreat_next_turn
            {
                let active_card = db.get_by_idx(active.card_idx);
                let base_cost = active_card.retreat_cost as i16;
                let effective_cost =
                    (base_cost + player.retreat_cost_modifier as i16).max(0) as u8;
                if active.total_energy() >= effective_cost {
                    // Must have at least one bench Pokemon to swap in.
                    for j in 0..3 {
                        if player.bench[j].is_some() {
                            actions.push(Action::retreat(SlotRef::bench(cp, j)));
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // ATTACK  (not on turn 0 or 1)
    // ------------------------------------------------------------------ //
    if state.turn_number >= 2 {
        let player = state.current();
        if let Some(ref active) = player.active {
            if !active.cant_attack_next_turn
                && !active.has_status(StatusEffect::Paralyzed)
                && !active.has_status(StatusEffect::Asleep)
            {
                let active_card = db.get_by_idx(active.card_idx);
                for (i, attack) in active_card.attacks.iter().enumerate() {
                    if can_pay_cost(active, &attack.cost) {
                        // Sub-target targeting is complex; emit a single
                        // action with target=None (simplified, to be refined).
                        actions.push(Action::attack(i, None));
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // END_TURN — always available
    // ------------------------------------------------------------------ //
    actions.push(Action::end_turn());

    actions
}

/// Return PROMOTE actions for the given player during AwaitingBenchPromotion.
pub fn get_legal_promotions(state: &GameState, player_index: usize) -> Vec<Action> {
    if state.phase != GamePhase::AwaitingBenchPromotion {
        return vec![];
    }

    let player = &state.players[player_index];
    let mut actions: Vec<Action> = Vec::new();
    for j in 0..3 {
        if player.bench[j].is_some() {
            actions.push(Action::promote(SlotRef::bench(player_index, j)));
        }
    }
    actions
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};
    use crate::types::{GamePhase, ActionKind};

    fn minimal_state_main() -> GameState {
        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 3; // past the first-turn restriction
        // Give player 0 an active Pokemon (card_idx 0 -> no attacks in empty db,
        // but the slot is present so retreat / ability / attack paths are visited).
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state
    }

    #[test]
    fn end_turn_always_available() {
        // Build a minimal GameState with phase=Main and verify END_TURN is present.
        let state = minimal_state_main();
        let db = CardDb {
            cards: vec![crate::card::Card {
                id: "test-001".to_string(),
                idx: 0,
                name: "TestMon".to_string(),
                kind: CardKind::Pokemon,
                stage: Some(Stage::Basic),
                element: None,
                hp: 100,
                weakness: None,
                retreat_cost: 1,
                is_ex: false,
                is_mega_ex: false,
                evolves_from: None,
                attacks: vec![],
                ability: None,
                trainer_effect_text: String::new(),
                trainer_handler: String::new(),
                trainer_effects: vec![],
                ko_points: 1,
            }],
            id_to_idx: {
                let mut m = std::collections::HashMap::new();
                m.insert("test-001".to_string(), 0u16);
                m
            },
            name_to_indices: {
                let mut m = std::collections::HashMap::new();
                m.insert("TestMon".to_string(), vec![0u16]);
                m
            },
            basic_to_stage2: std::collections::HashMap::new(),
        };

        let actions = get_legal_actions(&state, &db);
        assert!(
            actions.iter().any(|a| a.kind == ActionKind::EndTurn),
            "END_TURN must always be in legal actions"
        );
    }

    #[test]
    fn no_actions_when_game_over() {
        let mut state = minimal_state_main();
        state.winner = Some(0);
        let db = CardDb {
            cards: vec![],
            id_to_idx: std::collections::HashMap::new(),
            name_to_indices: std::collections::HashMap::new(),
            basic_to_stage2: std::collections::HashMap::new(),
        };
        let actions = get_legal_actions(&state, &db);
        assert!(actions.is_empty(), "No actions when game is over");
    }

    #[test]
    fn no_actions_wrong_phase() {
        let mut state = minimal_state_main();
        state.phase = GamePhase::Setup;
        let db = CardDb {
            cards: vec![],
            id_to_idx: std::collections::HashMap::new(),
            name_to_indices: std::collections::HashMap::new(),
            basic_to_stage2: std::collections::HashMap::new(),
        };
        let actions = get_legal_actions(&state, &db);
        assert!(actions.is_empty(), "No actions outside Main phase");
    }

    #[test]
    fn promotions_returned_during_awaiting_promotion() {
        let mut state = GameState::new(0);
        state.phase = GamePhase::AwaitingBenchPromotion;
        state.players[0].bench[0] = Some(PokemonSlot::new(0, 80));
        state.players[0].bench[2] = Some(PokemonSlot::new(1, 60));

        let promotions = get_legal_promotions(&state, 0);
        assert_eq!(promotions.len(), 2);
        assert!(promotions.iter().all(|a| a.kind == ActionKind::Promote));
    }

    #[test]
    fn attach_energy_action_emitted() {
        let mut state = minimal_state_main();
        state.players[0].energy_available = Some(crate::types::Element::Fire);
        state.players[0].has_attached_energy = false;

        let db = CardDb {
            cards: vec![crate::card::Card {
                id: "test-001".to_string(),
                idx: 0,
                name: "TestMon".to_string(),
                kind: CardKind::Pokemon,
                stage: Some(Stage::Basic),
                element: None,
                hp: 100,
                weakness: None,
                retreat_cost: 0,
                is_ex: false,
                is_mega_ex: false,
                evolves_from: None,
                attacks: vec![],
                ability: None,
                trainer_effect_text: String::new(),
                trainer_handler: String::new(),
                trainer_effects: vec![],
                ko_points: 1,
            }],
            id_to_idx: {
                let mut m = std::collections::HashMap::new();
                m.insert("test-001".to_string(), 0u16);
                m
            },
            name_to_indices: {
                let mut m = std::collections::HashMap::new();
                m.insert("TestMon".to_string(), vec![0u16]);
                m
            },
            basic_to_stage2: std::collections::HashMap::new(),
        };

        let actions = get_legal_actions(&state, &db);
        let attach_count = actions.iter().filter(|a| a.kind == ActionKind::AttachEnergy).count();
        assert_eq!(attach_count, 1, "One ATTACH_ENERGY action for active slot");
    }

    #[test]
    fn can_pay_cost_typed_and_colorless() {
        let mut slot = PokemonSlot::new(0, 100);
        // 2 Fire attached
        slot.add_energy(crate::types::Element::Fire, 2);

        // Cost: [Fire, Colorless] — should pass (2 fire satisfies both)
        assert!(can_pay_cost(&slot, &[CostSymbol::Fire, CostSymbol::Colorless]));

        // Cost: [Fire, Fire, Colorless] — fail (only 2 fire, 2 typed + 1 colorless needs 3)
        assert!(!can_pay_cost(&slot, &[CostSymbol::Fire, CostSymbol::Fire, CostSymbol::Colorless]));

        // Cost: [Water] — fail (no water)
        assert!(!can_pay_cost(&slot, &[CostSymbol::Water]));
    }
}
