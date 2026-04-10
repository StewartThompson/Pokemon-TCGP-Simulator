#![allow(dead_code, unused_imports, unused_variables)]

use rand::Rng;

use crate::actions::SlotRef;
use crate::card::CardDb;
use crate::effects::EffectContext;
use crate::state::{GameState, PokemonSlot, get_slot_mut};
use crate::types::{Element, Stage};

// ------------------------------------------------------------------ //
// Internal helper
// ------------------------------------------------------------------ //

/// Clamp current_hp to [current_hp + amount, max_hp].
fn heal_slot(state: &mut GameState, target: SlotRef, amount: i16) {
    if let Some(slot) = get_slot_mut(state, target) {
        slot.current_hp = (slot.current_hp + amount).min(slot.max_hp);
    }
}

/// Build a flat Vec<Element> of all energy tokens on a slot (one entry per token).
fn flat_energy(slot: &PokemonSlot) -> Vec<Element> {
    let mut list: Vec<Element> = Vec::new();
    for el_idx in 0..8usize {
        let count = slot.energy[el_idx];
        for _ in 0..count {
            list.push(idx_to_element(el_idx));
        }
    }
    list
}

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

/// Randomly discard one energy token from the given slot (if any energy present).
fn discard_one_energy_randomly(state: &mut GameState, target: SlotRef) {
    // Collect available energies first (immutable borrow).
    let energy_list = {
        let slot = match get_slot_mut(state, target) {
            Some(s) => {
                let list = flat_energy(s);
                list
            }
            None => return,
        };
        slot
    };

    if energy_list.is_empty() {
        return;
    }

    let idx = state.rng.gen_range(0..energy_list.len());
    let el = energy_list[idx];

    if let Some(slot) = get_slot_mut(state, target) {
        slot.remove_energy(el, 1);
    }
}

// ------------------------------------------------------------------ //
// Public heal handlers
// ------------------------------------------------------------------ //

/// Heal the acting player's active Pokemon.
pub fn heal_self(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let p = ctx.acting_player;
    heal_slot(state, SlotRef::active(p), amount);
}

/// Heal the target slot (from ctx.extra["target_slot"]) or opponent's active.
pub fn heal_target(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let target = if let Some(&raw) = ctx.extra.get("target_slot") {
        // raw encoding: player * 10 + slot_index, with -1 active encoded as -1 offset
        // Use the same convention: player=raw/10, slot=raw%10-1 maps active as -1
        // Simpler: encode as player*4 + (slot+1) where slot=-1..2 => 0..3
        // Check what encoding is used. Since EffectContext.extra is HashMap<String, i32>,
        // we decode: if raw < 0, it's p=0 active; otherwise player = raw / 10, slot = raw % 10 - 1
        // Actually let's use a simple convention: negative means p0 active, etc.
        // The safest approach: if target_slot key exists, decode as SlotRef directly.
        // Encoding: player * 10 + (slot + 1), so active(p) = p*10+0, bench(p,0)=p*10+1, etc.
        let player = (raw / 10) as usize;
        let slot_enc = raw % 10;
        if slot_enc == 0 {
            SlotRef::active(player)
        } else {
            SlotRef::bench(player, (slot_enc - 1) as usize)
        }
    } else {
        // Default: opponent's active
        let opp = 1 - ctx.acting_player;
        SlotRef::active(opp)
    };
    heal_slot(state, target, amount);
}

/// Heal acting player's active Pokemon (alias of heal_self for different card text).
pub fn heal_active(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    heal_self(state, amount, ctx);
}

/// Heal ALL of acting player's Pokemon (active + all bench slots).
pub fn heal_all_own(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let p = ctx.acting_player;
    // Heal active
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.current_hp = (slot.current_hp + amount).min(slot.max_hp);
    }
    // Heal bench
    for slot in state.players[p].bench.iter_mut().flatten() {
        slot.current_hp = (slot.current_hp + amount).min(slot.max_hp);
    }
}

/// Heal target only if target card's element == Grass.
pub fn heal_grass_target(state: &mut GameState, db: &CardDb, amount: i16, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    let target = SlotRef::active(opp);
    let should_heal = if let Some(slot) = crate::state::get_slot(state, target) {
        let card = db.get_by_idx(slot.card_idx);
        card.element == Some(Element::Grass)
    } else {
        false
    };
    if should_heal {
        heal_slot(state, target, amount);
    }
}

/// Heal target only if target card's element == Water.
pub fn heal_water_pokemon(state: &mut GameState, db: &CardDb, amount: i16, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    let target = SlotRef::active(opp);
    let should_heal = if let Some(slot) = crate::state::get_slot(state, target) {
        let card = db.get_by_idx(slot.card_idx);
        card.element == Some(Element::Water)
    } else {
        false
    };
    if should_heal {
        heal_slot(state, target, amount);
    }
}

/// Heal target only if target card's stage == Stage2.
pub fn heal_stage2_target(state: &mut GameState, db: &CardDb, amount: i16, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    let target = SlotRef::active(opp);
    let should_heal = if let Some(slot) = crate::state::get_slot(state, target) {
        let card = db.get_by_idx(slot.card_idx);
        card.stage == Some(Stage::Stage2)
    } else {
        false
    };
    if should_heal {
        heal_slot(state, target, amount);
    }
}

/// Heal acting player's active Pokemon and clear all status effects.
pub fn heal_and_cure_status(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.current_hp = (slot.current_hp + amount).min(slot.max_hp);
        slot.status = 0;
    }
}

/// Heal acting player's active Pokemon by the amount of damage dealt this attack.
/// Reads ctx.extra["damage_dealt"].
pub fn heal_self_equal_to_damage_dealt(state: &mut GameState, ctx: &EffectContext) {
    let damage = ctx.extra.get("damage_dealt").copied().unwrap_or(0);
    if damage > 0 {
        heal_self(state, damage as i16, ctx);
    }
}

/// Heal all Pokemon belonging to the acting player whose name matches `name`.
/// For each healed Pokemon, discard 1 energy randomly.
pub fn heal_all_named_discard_energy(
    state: &mut GameState,
    db: &CardDb,
    name: &str,
    amount: i16,
    ctx: &EffectContext,
) {
    let p = ctx.acting_player;

    // Collect slot refs for all own Pokemon with matching name.
    let mut targets: Vec<SlotRef> = Vec::new();

    if let Some(slot) = state.players[p].active.as_ref() {
        let card = db.get_by_idx(slot.card_idx);
        if card.name == name {
            targets.push(SlotRef::active(p));
        }
    }
    for i in 0..3usize {
        if let Some(slot) = state.players[p].bench[i].as_ref() {
            let card = db.get_by_idx(slot.card_idx);
            if card.name == name {
                targets.push(SlotRef::bench(p, i));
            }
        }
    }

    // Heal each matching Pokemon, then discard 1 energy randomly.
    for target in targets {
        heal_slot(state, target, amount);
        discard_one_energy_randomly(state, target);
    }
}

/// Heal all Pokemon of the acting player that match the given element type.
pub fn heal_all_typed(
    state: &mut GameState,
    db: &CardDb,
    element: &str,
    amount: i16,
    ctx: &EffectContext,
) {
    let target_element = match Element::from_str(element) {
        Some(el) => el,
        None => return,
    };

    let p = ctx.acting_player;

    // Collect slot refs for matching own Pokemon.
    let mut targets: Vec<SlotRef> = Vec::new();

    if let Some(slot) = state.players[p].active.as_ref() {
        let card = db.get_by_idx(slot.card_idx);
        if card.element == Some(target_element) {
            targets.push(SlotRef::active(p));
        }
    }
    for i in 0..3usize {
        if let Some(slot) = state.players[p].bench[i].as_ref() {
            let card = db.get_by_idx(slot.card_idx);
            if card.element == Some(target_element) {
                targets.push(SlotRef::bench(p, i));
            }
        }
    }

    for target in targets {
        heal_slot(state, target, amount);
    }
}

// ------------------------------------------------------------------ //
// Unit tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};
    use crate::effects::EffectContext;

    fn make_state() -> GameState {
        let mut state = GameState::new(42);
        // Place a pokemon in player 0's active slot.
        let mut slot = PokemonSlot::new(0, 100);
        slot.current_hp = 60;
        state.players[0].active = Some(slot);
        state
    }

    #[test]
    fn heal_self_increases_hp() {
        let mut state = make_state();
        let ctx = EffectContext::new(0);
        heal_self(&mut state, 20, &ctx);
        assert_eq!(state.players[0].active.as_ref().unwrap().current_hp, 80);
    }

    #[test]
    fn heal_self_caps_at_max_hp() {
        let mut state = make_state();
        let ctx = EffectContext::new(0);
        heal_self(&mut state, 999, &ctx);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().current_hp,
            state.players[0].active.as_ref().unwrap().max_hp
        );
    }

    #[test]
    fn heal_and_cure_status_clears_bits() {
        let mut state = make_state();
        // Set some status bits.
        state.players[0].active.as_mut().unwrap().status = 0b0000_0111;
        let ctx = EffectContext::new(0);
        heal_and_cure_status(&mut state, 10, &ctx);
        assert_eq!(state.players[0].active.as_ref().unwrap().status, 0);
        assert_eq!(state.players[0].active.as_ref().unwrap().current_hp, 70);
    }

    #[test]
    fn heal_self_equal_to_damage_dealt_reads_extra() {
        let mut state = make_state();
        let mut ctx = EffectContext::new(0);
        ctx.extra.insert("damage_dealt".to_string(), 30);
        heal_self_equal_to_damage_dealt(&mut state, &ctx);
        assert_eq!(state.players[0].active.as_ref().unwrap().current_hp, 90);
    }

    #[test]
    fn heal_all_own_heals_active_and_bench() {
        let mut state = GameState::new(1);
        let mut active = PokemonSlot::new(0, 100);
        active.current_hp = 50;
        state.players[0].active = Some(active);
        let mut bench0 = PokemonSlot::new(1, 80);
        bench0.current_hp = 40;
        state.players[0].bench[0] = Some(bench0);

        let ctx = EffectContext::new(0);
        heal_all_own(&mut state, 20, &ctx);

        assert_eq!(state.players[0].active.as_ref().unwrap().current_hp, 70);
        assert_eq!(state.players[0].bench[0].as_ref().unwrap().current_hp, 60);
    }
}
