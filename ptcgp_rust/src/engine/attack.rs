//! Attack execution logic.
//!
//! Ported from `ptcgp/engine/attack.py`.

use std::collections::HashMap;
use rand::Rng;
use regex::Regex;

use crate::card::{Card, CardDb};
use crate::state::{GameState, PokemonSlot};
use crate::actions::SlotRef;
use crate::types::{CostSymbol, StatusEffect};
use crate::constants::WEAKNESS_BONUS;
use crate::effects::EffectContext;
use crate::effects::dispatch::{apply_effects, compute_damage_modifier};

/// Returns true if the slot has enough energy to pay the given cost.
///
/// Typed requirements are matched first; any leftover energy satisfies
/// Colorless requirements.
pub fn can_pay_cost(slot: &PokemonSlot, cost: &[CostSymbol]) -> bool {
    // Track remaining energy per element (copy of the slot's energy array).
    let mut remaining: [i8; 8] = [0; 8];
    for i in 0..8 {
        remaining[i] = slot.energy[i] as i8;
    }

    let mut colorless_needed: u8 = 0;

    for symbol in cost {
        match symbol {
            CostSymbol::Colorless => {
                colorless_needed += 1;
            }
            _ => {
                let el = symbol.to_element().expect("Non-colorless CostSymbol has element");
                if remaining[el as usize] > 0 {
                    remaining[el as usize] -= 1;
                } else {
                    return false; // can't pay typed requirement
                }
            }
        }
    }

    // Colorless can be paid by any remaining energy.
    let total_remaining: i8 = remaining.iter().sum();
    total_remaining >= colorless_needed as i8
}

/// Compute retaliate damage from Rocky Helmet / Druddigon-style passives.
///
/// Scans both the defender's ability text and attached tool text for the
/// pattern "is damaged by an attack...do X damage to the attacking".
fn retaliate_damage(defender_slot: &PokemonSlot, defender_card: &Card, db: &CardDb) -> i16 {
    // Compiled lazily — regex crate doesn't have a built-in once_cell here,
    // but for the stubbed Wave 5 use this is fine (called infrequently).
    let pattern = Regex::new(
        r"(?i)is damaged by an attack.*?do (\d+) damage to the attacking",
    )
    .expect("Invalid retaliate regex");

    let mut total: i16 = 0;

    // Ability retaliate (e.g. Druddigon).
    if let Some(ref ability) = defender_card.ability {
        if let Some(m) = pattern.captures(&ability.effect_text) {
            if let Some(n) = m.get(1).and_then(|s| s.as_str().parse::<i16>().ok()) {
                total += n;
            }
        }
    }

    // Tool retaliate (e.g. Rocky Helmet).
    if let Some(tool_idx) = defender_slot.tool_idx {
        let tool_card = db.get_by_idx(tool_idx);
        if let Some(m) = pattern.captures(&tool_card.trainer_effect_text) {
            if let Some(n) = m.get(1).and_then(|s| s.as_str().parse::<i16>().ok()) {
                total += n;
            }
        }
    }

    total
}

/// Execute attack at `attack_index` for the current player's active Pokemon.
///
/// `sub_target`: for targeted attacks; `None` = target opponent's active.
pub fn execute_attack(
    state: &mut GameState,
    db: &CardDb,
    attack_index: usize,
    _sub_target: Option<SlotRef>,
) {
    // 1. Validate attacker.
    let attacker_card_idx = state
        .players[state.current_player]
        .active
        .as_ref()
        .expect("Current player has no active Pokemon")
        .card_idx;

    let attacker_card = db.get_by_idx(attacker_card_idx);

    assert!(
        attack_index < attacker_card.attacks.len(),
        "Invalid attack_index {} for {}",
        attack_index,
        attacker_card.name
    );

    // 2. Check can_pay_cost.
    {
        let attacker_slot = state.players[state.current_player].active.as_ref().unwrap();
        let cost = &attacker_card.attacks[attack_index].cost;
        assert!(
            can_pay_cost(attacker_slot, cost),
            "{} cannot pay cost for attack {}",
            attacker_card.name,
            attacker_card.attacks[attack_index].name
        );
    }

    // 3. Confusion check: tails (>= 0.5) means the attack fails.
    let is_confused = state.players[state.current_player]
        .active
        .as_ref()
        .unwrap()
        .has_status(StatusEffect::Confused);
    if is_confused && state.rng.gen::<f64>() >= 0.5 {
        return;
    }

    // 4. Get defender (opponent's active).
    let opponent_idx = state.opponent_index();
    assert!(
        state.players[opponent_idx].active.is_some(),
        "Opponent has no active Pokemon"
    );

    // Clone cards for immutable access while we mutate state below.
    let attack = attacker_card.attacks[attack_index].clone();
    let attacker_element = attacker_card.element;
    let _attacker_card_clone = attacker_card.clone();

    let defender_card_idx = state.players[opponent_idx].active.as_ref().unwrap().card_idx;
    let defender_card = db.get_by_idx(defender_card_idx).clone();

    // 5. Compute base_damage with weakness bonus.
    let mut base_damage = attack.damage;
    if attacker_element.is_some() && defender_card.weakness == attacker_element {
        base_damage += WEAKNESS_BONUS;
    }

    // 6. Compute damage modifier.
    let ctx = EffectContext {
        acting_player: state.current_player,
        source_ref: None,
        target_ref: None,
        extra: HashMap::new(),
    };
    // Note: attack.effects uses the card::EffectKind placeholder type; the real
    // effects::EffectKind dispatch is wired in Wave 6. Pass empty slice for now.
    let (mut final_damage, mod_skip, modifier_result) =
        compute_damage_modifier(state, db, base_damage, &[], &ctx);

    // 7. Respect "prevent damage" flag.
    let prevent = state.players[opponent_idx]
        .active
        .as_ref()
        .unwrap()
        .prevent_damage_next_turn;
    let mod_skip = if prevent {
        final_damage = 0;
        true
    } else {
        mod_skip
    };

    // 8. Apply damage.
    let damage_dealt: i16;
    if !mod_skip && final_damage > 0 {
        let defender_hp = state.players[opponent_idx].active.as_ref().unwrap().current_hp;
        damage_dealt = final_damage.min(defender_hp);
        let new_hp = (defender_hp - final_damage).max(0);
        state.players[opponent_idx].active.as_mut().unwrap().current_hp = new_hp;
    } else {
        damage_dealt = 0;
    }

    // 9. Retaliate (Rocky Helmet / Druddigon).
    if damage_dealt > 0 {
        let defender_slot_ref = state.players[opponent_idx].active.as_ref().unwrap();
        let retaliate = retaliate_damage(defender_slot_ref, &defender_card, db);
        if retaliate > 0 {
            let attacker = state.players[state.current_player].active.as_mut().unwrap();
            attacker.current_hp = (attacker.current_hp - retaliate).max(0);
        }
    }

    // 10. Apply side-effect handlers.
    let ctx_with_damage = EffectContext {
        acting_player: state.current_player,
        source_ref: None,
        target_ref: None,
        extra: {
            let mut m = modifier_result
                .iter()
                .map(|(k, &v)| (k.clone(), v))
                .collect::<HashMap<String, i32>>();
            m.insert("damage_dealt".to_string(), damage_dealt as i32);
            m
        },
    };

    // Wave 6 will wire real effects here; attack.effects are card::EffectKind placeholders.
    // For now, apply_effects is called with an empty slice (stub no-op).
    apply_effects(state, db, &[], &ctx_with_damage);
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::PokemonSlot;
    use crate::types::Element;

    fn make_slot(hp: i16) -> PokemonSlot {
        PokemonSlot::new(0, hp)
    }

    #[test]
    fn can_pay_cost_no_cost() {
        let slot = make_slot(100);
        assert!(can_pay_cost(&slot, &[]));
    }

    #[test]
    fn can_pay_cost_typed_exact() {
        let mut slot = make_slot(100);
        slot.add_energy(Element::Fire, 2);
        let cost = vec![CostSymbol::Fire, CostSymbol::Fire];
        assert!(can_pay_cost(&slot, &cost));
    }

    #[test]
    fn can_pay_cost_typed_insufficient() {
        let mut slot = make_slot(100);
        slot.add_energy(Element::Fire, 1);
        let cost = vec![CostSymbol::Fire, CostSymbol::Fire];
        assert!(!can_pay_cost(&slot, &cost));
    }

    #[test]
    fn can_pay_cost_colorless_satisfied_by_any_energy() {
        let mut slot = make_slot(100);
        slot.add_energy(Element::Water, 1);
        let cost = vec![CostSymbol::Colorless];
        assert!(can_pay_cost(&slot, &cost));
    }

    #[test]
    fn can_pay_cost_colorless_insufficient() {
        let slot = make_slot(100);
        let cost = vec![CostSymbol::Colorless];
        assert!(!can_pay_cost(&slot, &cost));
    }

    #[test]
    fn can_pay_cost_mixed_typed_and_colorless() {
        let mut slot = make_slot(100);
        slot.add_energy(Element::Grass, 1);
        slot.add_energy(Element::Water, 1);
        // Cost: 1 Grass + 1 Colorless
        let cost = vec![CostSymbol::Grass, CostSymbol::Colorless];
        assert!(can_pay_cost(&slot, &cost));
    }

    #[test]
    fn can_pay_cost_typed_cannot_satisfy_colorless_from_wrong_type() {
        let mut slot = make_slot(100);
        // Has exactly 1 Fire — enough for 1 Fire, but not also 1 Water requirement.
        slot.add_energy(Element::Fire, 1);
        let cost = vec![CostSymbol::Fire, CostSymbol::Water];
        assert!(!can_pay_cost(&slot, &cost));
    }
}
