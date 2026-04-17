//! Attack execution logic.
//!
//! Ported from `ptcgp/engine/attack.py`.

use std::collections::HashMap;
use std::sync::OnceLock;
use rand::Rng;
use regex::Regex;

use crate::card::{Card, CardDb};
use crate::state::{GameState, PokemonSlot};
use crate::actions::SlotRef;
use crate::types::{CostSymbol, StatusEffect};
use crate::constants::WEAKNESS_BONUS;
use crate::effects::{EffectContext, EffectKind};
use crate::effects::dispatch::{apply_effects, compute_damage_modifier};

#[inline]
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
    // Compiled once at first call via OnceLock — avoids re-compiling on every attack.
    static RE: OnceLock<Regex> = OnceLock::new();
    let pattern = RE.get_or_init(|| {
        Regex::new(r"(?i)is damaged by an attack.*?do (\d+) damage to the attacking")
            .expect("Invalid retaliate regex")
    });

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
    sub_target: Option<SlotRef>,
    extra_target: Option<SlotRef>,
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
    if is_confused {
        let heads = state.rng.gen::<f64>() < 0.5;
        state.coin_flip_log.push(if heads {
            "🪙 Confusion flip: Heads! Attack succeeds".to_string()
        } else {
            // PTCGP confusion has NO self-damage on tails — attack just fails.
            "🪙 Confusion flip: Tails! Attack fails.".to_string()
        });
        if !heads {
            // The attack failed but still ends the turn.  The runner's dispatch
            // for ActionKind::Attack calls advance_turn after this returns,
            // so we do not call advance_turn directly here.
            return;
        }
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
    // Only apply the +20 weakness bonus when the attack has a non-zero base
    // damage.  Zero-damage attacks (e.g. Tail Whip) must not deal bonus damage
    // simply because of a type match-up.
    let mut base_damage = attack.damage;
    if attack.damage > 0 && attacker_element.is_some() && defender_card.weakness == attacker_element {
        base_damage += WEAKNESS_BONUS;
    }

    // 6. Compute damage modifier.
    let ctx = EffectContext {
        acting_player: state.current_player,
        source_ref: Some(SlotRef::active(state.current_player)),
        target_ref: sub_target,
        extra_target_ref: extra_target,
        extra: HashMap::new(),
    };
    // Use pre-parsed attack effects (parsed at card load time).
    let attack_effects = attack.effects.clone();
    let (mut final_damage, mod_skip, modifier_result) =
        compute_damage_modifier(state, db, base_damage, &attack_effects, &ctx);

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

    // 7b. PassivePreventExDamage (Oricorio Safeguard): if the defender's active
    // ability has this passive and the attacker is an ex Pokemon, negate damage.
    let attacker_is_ex = db.get_by_idx(attacker_card_idx).is_ex;
    if attacker_is_ex && !mod_skip {
        let defender_has_safeguard = state.players[opponent_idx]
            .active
            .as_ref()
            .map(|s| {
                let card = db.get_by_idx(s.card_idx);
                card.ability.as_ref().map(|ab| {
                    ab.effects.iter().any(|e| matches!(e, EffectKind::PassivePreventExDamage))
                }).unwrap_or(false)
            })
            .unwrap_or(false);
        if defender_has_safeguard {
            final_damage = 0;
        }
    }

    // 8. Apply damage — first subtract the defender's incoming_damage_reduction
    // (set by effects like PassiveIncomingDamageReduction), clamped at 0.
    if !mod_skip && final_damage > 0 {
        let reduction = state.players[opponent_idx]
            .active
            .as_ref()
            .unwrap()
            .incoming_damage_reduction as i16;
        if reduction > 0 {
            final_damage = (final_damage - reduction).max(0);
        }
    }

    let damage_dealt: i16;
    let opponent_ko: bool;
    if !mod_skip && final_damage > 0 {
        let defender_hp = state.players[opponent_idx].active.as_ref().unwrap().current_hp;
        damage_dealt = final_damage.min(defender_hp);
        let new_hp = (defender_hp - final_damage).max(0);
        state.players[opponent_idx].active.as_mut().unwrap().current_hp = new_hp;
        opponent_ko = new_hp == 0;
    } else {
        damage_dealt = 0;
        opponent_ko = false;
    }

    // 9. Retaliate (Rocky Helmet / Druddigon).
    if damage_dealt > 0 {
        let defender_slot_ref = state.players[opponent_idx].active.as_ref().unwrap();
        let retaliate = retaliate_damage(defender_slot_ref, &defender_card, db);
        if retaliate > 0 {
            let attacker = state.players[state.current_player].active.as_mut().unwrap();
            attacker.current_hp = (attacker.current_hp - retaliate).max(0);
        }

        // Poison Barb: if defender's tool has PassiveRetaliatePoison, poison the attacker.
        let has_poison_barb = state.players[opponent_idx].active.as_ref()
            .and_then(|slot| slot.tool_idx)
            .and_then(|tidx| db.try_get_by_idx(tidx))
            .map(|tool| {
                tool.trainer_effects.iter().any(|e| matches!(e, EffectKind::PassiveRetaliatePoison))
            })
            .unwrap_or(false);
        if has_poison_barb {
            if let Some(attacker) = state.players[state.current_player].active.as_mut() {
                attacker.add_status(StatusEffect::Poisoned);
            }
        }
    }

    // 10. Apply side-effect handlers.
    let attacker_ref = SlotRef::active(state.current_player);
    let ctx_with_damage = EffectContext {
        acting_player: state.current_player,
        source_ref: Some(attacker_ref),
        target_ref: sub_target,
        extra_target_ref: extra_target,
        extra: {
            let mut m = modifier_result
                .iter()
                .map(|(k, &v)| (k.clone(), v))
                .collect::<HashMap<String, i32>>();
            m.insert("damage_dealt".to_string(), damage_dealt as i32);
            m.insert("opponent_ko".to_string(), opponent_ko as i32);
            m
        },
    };

    // Apply post-damage side effects (status conditions, splash, heal, etc.).
    apply_effects(state, db, &attack_effects, &ctx_with_damage);

    // Resolve any KOs caused by the attack (or by retaliate damage) so the
    // state is consistent before the runner advances the turn.
    crate::engine::ko::check_and_handle_kos(state, db);

    // PTCGP rule: an attack always ends the attacker's turn.  If the KO
    // pushed us into AwaitingBenchPromotion, the runner can't `advance_turn`
    // immediately — the defender must promote first.  Set a flag so the
    // runner / MCTS knows to advance after promotion completes.
    if state.phase == crate::types::GamePhase::AwaitingBenchPromotion {
        state.attack_pending_advance = true;
    }
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
