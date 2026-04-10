#![allow(dead_code, unused_imports, unused_variables)]

use rand::Rng;
use rand::seq::SliceRandom;
use crate::card::CardDb;
use crate::state::{GameState, get_slot_mut, PokemonSlot};
use crate::actions::SlotRef;
use crate::effects::EffectContext;
use crate::types::Element;

// ------------------------------------------------------------------ //
// Internal helpers
// ------------------------------------------------------------------ //

/// Discard exactly 1 random energy from a slot.  Does nothing if the slot
/// has no energy attached.
fn discard_random_energy(slot: &mut PokemonSlot, rng: &mut impl Rng) {
    let total: u8 = slot.energy.iter().sum();
    if total == 0 {
        return;
    }
    let pick = rng.gen_range(0..total) as usize;
    let mut acc = 0usize;
    for i in 0..8 {
        acc += slot.energy[i] as usize;
        if acc > pick {
            slot.energy[i] -= 1;
            return;
        }
    }
}

/// Return the first bench slot index for the given player that is occupied.
/// If `element_filter` is Some, only considers Pokémon of that element type
/// (card element lookup is skipped if we have no db access, so this variant
/// purely checks by slot occupancy when no db is present).
fn find_bench_occupied(state: &GameState, player: usize) -> Option<usize> {
    for (i, slot) in state.players[player].bench.iter().enumerate() {
        if slot.is_some() {
            return Some(i);
        }
    }
    None
}

/// Return the first bench slot index for the given player that is occupied
/// *and* whose Pokémon element matches `filter_el`, using the card database.
fn find_bench_by_element(
    state: &GameState,
    db: &CardDb,
    player: usize,
    filter_el: Element,
) -> Option<usize> {
    for (i, slot) in state.players[player].bench.iter().enumerate() {
        if let Some(s) = slot {
            if let Some(card) = db.try_get_by_idx(s.card_idx) {
                if card.element == Some(filter_el) {
                    return Some(i);
                }
            }
        }
    }
    None
}

// ------------------------------------------------------------------ //
// Attach energy — self
// ------------------------------------------------------------------ //

/// Attach `count` energy of `element` from the Energy Zone to the source Pokémon.
pub fn attach_energy_zone_self(
    state: &mut GameState,
    ctx: &EffectContext,
    element: Element,
    count: u8,
) {
    let src = match ctx.source_ref {
        Some(r) => r,
        None => SlotRef::active(ctx.acting_player),
    };
    if let Some(slot) = get_slot_mut(state, src) {
        slot.add_energy(element, count);
    }
}

/// Attach 1 Psychic Energy from the Energy Zone to the source Pokémon.
/// The turn ends after this ability fires (handled structurally by the engine).
pub fn ability_attach_energy_end_turn(state: &mut GameState, ctx: &EffectContext) {
    attach_energy_zone_self(state, ctx, Element::Psychic, 1);
}

/// Passive/structural: attach energy to self at end of first turn.
/// Handled structurally — no-op here.
pub fn first_turn_energy_attach(_state: &mut GameState, _ctx: &EffectContext, _element: Element) {}

// ------------------------------------------------------------------ //
// Attach energy — bench
// ------------------------------------------------------------------ //

/// Attach 1 energy of `element` to the first eligible benched Pokémon.
/// If `target_type` is Some, restrict to Pokémon of that element (needs db).
pub fn attach_energy_zone_bench(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    element: Element,
    target_type: Option<Element>,
) {
    let pi = ctx.acting_player;

    // Use explicit target if provided, otherwise find a bench slot.
    let bench_idx = match ctx.target_ref {
        Some(r) if r.is_bench() && r.player as usize == pi => Some(r.bench_index()),
        _ => match target_type {
            Some(filter_el) => find_bench_by_element(state, db, pi, filter_el),
            None => find_bench_occupied(state, pi),
        },
    };

    if let Some(idx) = bench_idx {
        if let Some(slot) = state.players[pi].bench[idx].as_mut() {
            slot.add_energy(element, 1);
        }
    }
}

/// Attach `count` energy of `element` to 1 benched Pokémon.
pub fn attach_n_energy_zone_bench(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    element: Element,
    count: u8,
) {
    let pi = ctx.acting_player;
    let bench_idx = match ctx.target_ref {
        Some(r) if r.is_bench() && r.player as usize == pi => Some(r.bench_index()),
        _ => find_bench_occupied(state, pi),
    };
    if let Some(idx) = bench_idx {
        if let Some(slot) = state.players[pi].bench[idx].as_mut() {
            slot.add_energy(element, count);
        }
    }
}

/// Colorless Energy does not exist in the Energy Zone — no-op.
pub fn attach_colorless_energy_zone_bench(_state: &mut GameState, _ctx: &EffectContext) {}

/// Choose 2 benched Pokémon and attach 1 Water Energy to each.
pub fn attach_water_two_bench(state: &mut GameState, ctx: &EffectContext) {
    let pi = ctx.acting_player;
    // Collect eligible bench indices
    let eligible: Vec<usize> = state.players[pi]
        .bench
        .iter()
        .enumerate()
        .filter_map(|(i, s)| if s.is_some() { Some(i) } else { None })
        .collect();
    if eligible.is_empty() {
        return;
    }
    // Pick up to 2 at random
    let pick_count = eligible.len().min(2);
    let mut indices = eligible.clone();
    // Shuffle and take first pick_count
    // We need to use the state rng; temporarily split the borrow.
    let chosen: Vec<usize> = {
        let mut tmp = indices;
        tmp.shuffle(&mut state.rng);
        tmp.into_iter().take(pick_count).collect()
    };
    for idx in chosen {
        if let Some(slot) = state.players[pi].bench[idx].as_mut() {
            slot.add_energy(Element::Water, 1);
        }
    }
}

/// Attach 1 Grass Energy to an own Grass-type Pokémon (Active first, then bench).
pub fn attach_energy_zone_to_grass(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let pi = ctx.acting_player;

    // Check active first
    let active_is_grass = state.players[pi]
        .active
        .as_ref()
        .and_then(|s| db.try_get_by_idx(s.card_idx))
        .map(|c| c.element == Some(Element::Grass))
        .unwrap_or(false);

    if active_is_grass {
        if let Some(slot) = state.players[pi].active.as_mut() {
            slot.add_energy(Element::Grass, 1);
        }
        return;
    }

    // Otherwise find a benched Grass Pokémon
    if let Some(idx) = find_bench_by_element(state, db, pi, Element::Grass) {
        if let Some(slot) = state.players[pi].bench[idx].as_mut() {
            slot.add_energy(Element::Grass, 1);
        }
    }
}

/// Attach 1 energy of `element` to a named own Pokémon (Active preferred; then bench).
pub fn attach_energy_zone_named(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    element: Element,
    names: &[&str],
) {
    let pi = ctx.acting_player;
    let name_set: std::collections::HashSet<String> =
        names.iter().map(|n| n.to_lowercase()).collect();

    let matches_name = |slot: &PokemonSlot| -> bool {
        db.try_get_by_idx(slot.card_idx)
            .map(|c| name_set.contains(&c.name.to_lowercase()))
            .unwrap_or(false)
    };

    // Check active slot first
    let active_matches = state.players[pi]
        .active
        .as_ref()
        .map(|s| matches_name(s))
        .unwrap_or(false);

    if active_matches {
        if let Some(slot) = state.players[pi].active.as_mut() {
            slot.add_energy(element, 1);
        }
        return;
    }

    // Check bench
    let bench_idx = (0..3).find(|&i| {
        state.players[pi].bench[i]
            .as_ref()
            .map(|s| matches_name(s))
            .unwrap_or(false)
    });
    if let Some(idx) = bench_idx {
        if let Some(slot) = state.players[pi].bench[idx].as_mut() {
            slot.add_energy(element, 1);
        }
    }
}

/// Misty: flip coins until tails; attach that many Water Energy to the target.
pub fn coin_flip_until_tails_attach_energy(
    state: &mut GameState,
    ctx: &EffectContext,
    element: Element,
) {
    let mut heads = 0u8;
    while state.rng.gen::<f64>() < 0.5 {
        heads += 1;
    }
    if heads == 0 {
        return;
    }
    let tgt = match ctx.target_ref {
        Some(r) => r,
        None => return,
    };
    if let Some(slot) = get_slot_mut(state, tgt) {
        slot.add_energy(element, heads);
    }
}

/// Moltres EX-style: flip `count` coins; attach one energy per heads to benched
/// Pokémon matching `filter_el`, distributed round-robin.
pub fn multi_coin_attach_bench(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    count: u8,
    element: Element,
    filter_el: Option<Element>,
) {
    let pi = ctx.acting_player;

    // Collect eligible bench indices
    let eligible: Vec<usize> = (0..3)
        .filter(|&i| {
            if let Some(s) = &state.players[pi].bench[i] {
                match filter_el {
                    Some(fe) => db
                        .try_get_by_idx(s.card_idx)
                        .map(|c| c.element == Some(fe))
                        .unwrap_or(false),
                    None => true,
                }
            } else {
                false
            }
        })
        .collect();
    if eligible.is_empty() {
        return;
    }

    let heads: u8 = (0..count)
        .filter(|_| state.rng.gen::<f64>() < 0.5)
        .count() as u8;
    if heads == 0 {
        return;
    }

    // Distribute round-robin
    for k in 0..heads as usize {
        let idx = eligible[k % eligible.len()];
        if let Some(slot) = state.players[pi].bench[idx].as_mut() {
            slot.add_energy(element, 1);
        }
    }
}

// ------------------------------------------------------------------ //
// Discard energy — self
// ------------------------------------------------------------------ //

/// Discard 1 energy of `element` from the source Pokémon.
pub fn discard_energy_self(state: &mut GameState, ctx: &EffectContext, element: Element) {
    let src = match ctx.source_ref {
        Some(r) => r,
        None => SlotRef::active(ctx.acting_player),
    };
    if let Some(slot) = get_slot_mut(state, src) {
        if slot.energy[element as usize] > 0 {
            slot.energy[element as usize] -= 1;
        }
    }
}

/// Discard `count` energy of `element` from the source Pokémon.
pub fn discard_n_energy_self(
    state: &mut GameState,
    ctx: &EffectContext,
    element: Element,
    count: u8,
) {
    let src = match ctx.source_ref {
        Some(r) => r,
        None => SlotRef::active(ctx.acting_player),
    };
    for _ in 0..count {
        if let Some(slot) = get_slot_mut(state, src) {
            if slot.energy[element as usize] == 0 {
                break;
            }
            slot.energy[element as usize] -= 1;
        }
    }
}

/// Discard ALL energy from the source Pokémon.
pub fn discard_all_energy_self(state: &mut GameState, ctx: &EffectContext) {
    let src = match ctx.source_ref {
        Some(r) => r,
        None => SlotRef::active(ctx.acting_player),
    };
    if let Some(slot) = get_slot_mut(state, src) {
        slot.energy = [0; 8];
    }
}

/// Discard all energy of a specific type from the source Pokémon.
pub fn discard_all_typed_energy_self(
    state: &mut GameState,
    ctx: &EffectContext,
    element: Element,
) {
    let src = match ctx.source_ref {
        Some(r) => r,
        None => SlotRef::active(ctx.acting_player),
    };
    if let Some(slot) = get_slot_mut(state, src) {
        slot.energy[element as usize] = 0;
    }
}

// ------------------------------------------------------------------ //
// Discard energy — opponent / both
// ------------------------------------------------------------------ //

/// Discard 1 random energy from the opponent's Active Pokémon.
pub fn discard_random_energy_opponent(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    let total: u8 = state.players[opp]
        .active
        .as_ref()
        .map(|s| s.energy.iter().sum())
        .unwrap_or(0);
    if total == 0 {
        return;
    }
    // We need to split the borrow: pick first, then mutate.
    let pick = state.rng.gen_range(0..total) as usize;
    if let Some(slot) = state.players[opp].active.as_mut() {
        let mut acc = 0usize;
        for i in 0..8 {
            acc += slot.energy[i] as usize;
            if acc > pick {
                slot.energy[i] -= 1;
                break;
            }
        }
    }
}

/// Flip a coin. On heads, discard 1 random energy from the opponent's Active.
pub fn coin_flip_discard_random_energy_opponent(state: &mut GameState, ctx: &EffectContext) {
    if state.rng.gen::<f64>() < 0.5 {
        discard_random_energy_opponent(state, ctx);
    }
}

/// Discard 1 random energy from each Active Pokémon (both players).
pub fn discard_random_energy_both_active(state: &mut GameState, ctx: &EffectContext) {
    for pi in 0..2usize {
        let total: u8 = state.players[pi]
            .active
            .as_ref()
            .map(|s| s.energy.iter().sum())
            .unwrap_or(0);
        if total == 0 {
            continue;
        }
        let pick = state.rng.gen_range(0..total) as usize;
        if let Some(slot) = state.players[pi].active.as_mut() {
            let mut acc = 0usize;
            for i in 0..8 {
                acc += slot.energy[i] as usize;
                if acc > pick {
                    slot.energy[i] -= 1;
                    break;
                }
            }
        }
    }
}

/// Discard 1 random energy from among ALL Pokémon currently in play (both sides).
pub fn discard_random_energy_all_pokemon(state: &mut GameState, ctx: &EffectContext) {
    // Build a flat list of (player_idx, slot_ref) for every attached energy.
    let mut candidates: Vec<SlotRef> = Vec::new();
    for pi in 0..2usize {
        if let Some(s) = &state.players[pi].active {
            for i in 0..8usize {
                for _ in 0..s.energy[i] {
                    candidates.push(SlotRef::active(pi));
                    // We also need to know which element index — encode via a separate list.
                }
            }
        }
        for bench_i in 0..3usize {
            if let Some(s) = &state.players[pi].bench[bench_i] {
                for i in 0..8usize {
                    for _ in 0..s.energy[i] {
                        candidates.push(SlotRef::bench(pi, bench_i));
                    }
                }
            }
        }
    }

    // Rebuild with element info
    let mut flat: Vec<(SlotRef, usize)> = Vec::new();
    for pi in 0..2usize {
        if let Some(s) = &state.players[pi].active {
            for i in 0..8usize {
                for _ in 0..s.energy[i] {
                    flat.push((SlotRef::active(pi), i));
                }
            }
        }
        for bench_i in 0..3usize {
            if let Some(s) = &state.players[pi].bench[bench_i] {
                for i in 0..8usize {
                    for _ in 0..s.energy[i] {
                        flat.push((SlotRef::bench(pi, bench_i), i));
                    }
                }
            }
        }
    }

    if flat.is_empty() {
        return;
    }
    let pick = state.rng.gen_range(0..flat.len());
    let (slot_ref, el_idx) = flat[pick];
    if let Some(slot) = get_slot_mut(state, slot_ref) {
        if slot.energy[el_idx] > 0 {
            slot.energy[el_idx] -= 1;
        }
    }
}

// ------------------------------------------------------------------ //
// Move energy
// ------------------------------------------------------------------ //

/// Dawn: move 1 energy from a benched Pokémon (target_ref or first with energy) to Active.
pub fn move_bench_energy_to_active(state: &mut GameState, ctx: &EffectContext) {
    let pi = ctx.acting_player;
    if state.players[pi].active.is_none() {
        return;
    }

    // Determine source bench index and element.
    let source_idx = match ctx.target_ref {
        Some(r) if r.is_bench() && r.player as usize == pi => {
            let idx = r.bench_index();
            if state.players[pi].bench[idx]
                .as_ref()
                .map(|s| s.total_energy() > 0)
                .unwrap_or(false)
            {
                Some(idx)
            } else {
                None
            }
        }
        _ => (0..3).find(|&i| {
            state.players[pi].bench[i]
                .as_ref()
                .map(|s| s.total_energy() > 0)
                .unwrap_or(false)
        }),
    };

    let Some(bench_idx) = source_idx else { return };

    // Find which element to move (first non-zero).
    let el_idx = match state.players[pi].bench[bench_idx]
        .as_ref()
        .and_then(|s| s.energy.iter().position(|&e| e > 0))
    {
        Some(i) => i,
        None => return,
    };

    // Remove from bench, add to active.
    if let Some(b) = state.players[pi].bench[bench_idx].as_mut() {
        b.energy[el_idx] -= 1;
    }
    if let Some(a) = state.players[pi].active.as_mut() {
        a.energy[el_idx] += 1;
    }
}

/// Move 1 Water Energy from a benched Water Pokémon to the Active Pokémon.
pub fn move_water_bench_to_active(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let pi = ctx.acting_player;
    if state.players[pi].active.is_none() {
        return;
    }

    // Find first benched Water Pokémon with Water energy attached.
    let source_idx = (0..3).find(|&i| {
        if let Some(s) = &state.players[pi].bench[i] {
            let is_water = db
                .try_get_by_idx(s.card_idx)
                .map(|c| c.element == Some(Element::Water))
                .unwrap_or(false);
            is_water && s.energy[Element::Water as usize] > 0
        } else {
            false
        }
    });

    let Some(idx) = source_idx else { return };

    if let Some(b) = state.players[pi].bench[idx].as_mut() {
        b.energy[Element::Water as usize] -= 1;
    }
    if let Some(a) = state.players[pi].active.as_mut() {
        a.energy[Element::Water as usize] += 1;
    }
}

/// Move all energy of `energy_el` from 1 benched Pokémon (optionally filtered
/// by `filter_el` element type) to the Active Pokémon.
pub fn move_all_typed_energy_bench_to_active(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    energy_el: Element,
    filter_el: Option<Element>,
) {
    let pi = ctx.acting_player;
    if state.players[pi].active.is_none() {
        return;
    }

    let source_idx = (0..3).find(|&i| {
        if let Some(s) = &state.players[pi].bench[i] {
            let element_ok = match filter_el {
                Some(fe) => db
                    .try_get_by_idx(s.card_idx)
                    .map(|c| c.element == Some(fe))
                    .unwrap_or(false),
                None => true,
            };
            element_ok && s.energy[energy_el as usize] > 0
        } else {
            false
        }
    });

    let Some(idx) = source_idx else { return };

    let amount = state.players[pi].bench[idx]
        .as_ref()
        .map(|s| s.energy[energy_el as usize])
        .unwrap_or(0);
    if amount == 0 {
        return;
    }

    if let Some(b) = state.players[pi].bench[idx].as_mut() {
        b.energy[energy_el as usize] = 0;
    }
    if let Some(a) = state.players[pi].active.as_mut() {
        a.energy[energy_el as usize] =
            a.energy[energy_el as usize].saturating_add(amount);
    }
}

/// Move all Lightning energy from own bench to Active, if Active's name is in `names`.
pub fn move_all_electric_to_active_named(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    names: &[&str],
) {
    let pi = ctx.acting_player;

    // Check that Active exists and its name matches.
    if !names.is_empty() {
        let name_ok = state.players[pi]
            .active
            .as_ref()
            .and_then(|s| db.try_get_by_idx(s.card_idx))
            .map(|c| {
                names
                    .iter()
                    .any(|n| n.to_lowercase() == c.name.to_lowercase())
            })
            .unwrap_or(false);
        if !name_ok {
            return;
        }
    } else if state.players[pi].active.is_none() {
        return;
    }

    // Sum all Lightning from bench and zero it out.
    let mut moved = 0u8;
    for i in 0..3 {
        if let Some(slot) = state.players[pi].bench[i].as_mut() {
            let n = slot.energy[Element::Lightning as usize];
            if n > 0 {
                moved = moved.saturating_add(n);
                slot.energy[Element::Lightning as usize] = 0;
            }
        }
    }
    if moved > 0 {
        if let Some(a) = state.players[pi].active.as_mut() {
            a.energy[Element::Lightning as usize] =
                a.energy[Element::Lightning as usize].saturating_add(moved);
        }
    }
}

// ------------------------------------------------------------------ //
// Deck operations related to energy (discard_top_deck lives here
// because the Python file placed it alongside energy handlers)
// ------------------------------------------------------------------ //

/// Discard the top `count` cards from the acting player's deck.
pub fn discard_top_deck(state: &mut GameState, ctx: &EffectContext, count: usize) {
    let p = &mut state.players[ctx.acting_player];
    let to_discard = count.min(p.deck.len());
    let discarded: Vec<u16> = p.deck.drain(..to_discard).collect();
    p.discard.extend(discarded);
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};
    use crate::effects::EffectContext;

    fn make_state() -> GameState {
        let mut state = GameState::new(42);
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state.players[1].active = Some(PokemonSlot::new(1, 100));
        state
    }

    fn ctx(acting: usize) -> EffectContext {
        EffectContext::new(acting)
    }

    fn ctx_with_source(acting: usize, src: SlotRef) -> EffectContext {
        EffectContext::new(acting).with_source(src)
    }

    // ---- attach tests ----

    #[test]
    fn attach_energy_zone_self_adds_energy() {
        let mut state = make_state();
        let ctx = ctx_with_source(0, SlotRef::active(0));
        let before: u8 = state.players[0].active.as_ref().unwrap().total_energy();
        attach_energy_zone_self(&mut state, &ctx, Element::Fire, 2);
        let after: u8 = state.players[0].active.as_ref().unwrap().total_energy();
        assert_eq!(after, before + 2);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().energy[Element::Fire as usize],
            2
        );
    }

    #[test]
    fn attach_energy_zone_self_defaults_to_active_when_no_source_ref() {
        let mut state = make_state();
        let ctx = ctx(0); // no source_ref
        attach_energy_zone_self(&mut state, &ctx, Element::Water, 1);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().energy[Element::Water as usize],
            1
        );
    }

    #[test]
    fn attach_n_energy_zone_bench_adds_energy_to_bench() {
        let mut state = make_state();
        state.players[0].bench[0] = Some(PokemonSlot::new(10, 60));
        let ctx = ctx(0);
        // No CardDb available in tests — use no target_ref so we pick first occupied bench
        attach_n_energy_zone_bench(
            &mut state,
            &crate::card::CardDb::new_empty(),
            &ctx,
            Element::Lightning,
            3,
        );
        assert_eq!(
            state.players[0].bench[0]
                .as_ref()
                .unwrap()
                .energy[Element::Lightning as usize],
            3
        );
    }

    // ---- discard tests ----

    #[test]
    fn discard_energy_self_removes_exactly_one() {
        let mut state = make_state();
        if let Some(slot) = state.players[0].active.as_mut() {
            slot.energy[Element::Fire as usize] = 2;
        }
        let ctx = ctx_with_source(0, SlotRef::active(0));
        discard_energy_self(&mut state, &ctx, Element::Fire);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().energy[Element::Fire as usize],
            1
        );
        assert_eq!(state.players[0].active.as_ref().unwrap().total_energy(), 1);
    }

    #[test]
    fn discard_energy_self_noop_when_no_energy() {
        let mut state = make_state();
        let ctx = ctx_with_source(0, SlotRef::active(0));
        discard_energy_self(&mut state, &ctx, Element::Fire); // slot has 0 Fire
        assert_eq!(state.players[0].active.as_ref().unwrap().total_energy(), 0);
    }

    #[test]
    fn discard_n_energy_self_removes_n() {
        let mut state = make_state();
        if let Some(slot) = state.players[0].active.as_mut() {
            slot.energy[Element::Water as usize] = 5;
        }
        let ctx = ctx_with_source(0, SlotRef::active(0));
        discard_n_energy_self(&mut state, &ctx, Element::Water, 3);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().energy[Element::Water as usize],
            2
        );
    }

    #[test]
    fn discard_all_energy_self_zeroes_all() {
        let mut state = make_state();
        if let Some(slot) = state.players[0].active.as_mut() {
            slot.energy[Element::Fire as usize] = 2;
            slot.energy[Element::Water as usize] = 1;
        }
        let ctx = ctx_with_source(0, SlotRef::active(0));
        discard_all_energy_self(&mut state, &ctx);
        assert_eq!(state.players[0].active.as_ref().unwrap().total_energy(), 0);
    }

    #[test]
    fn discard_all_typed_energy_self_only_removes_that_type() {
        let mut state = make_state();
        if let Some(slot) = state.players[0].active.as_mut() {
            slot.energy[Element::Fire as usize] = 3;
            slot.energy[Element::Water as usize] = 2;
        }
        let ctx = ctx_with_source(0, SlotRef::active(0));
        discard_all_typed_energy_self(&mut state, &ctx, Element::Fire);
        let slot = state.players[0].active.as_ref().unwrap();
        assert_eq!(slot.energy[Element::Fire as usize], 0);
        assert_eq!(slot.energy[Element::Water as usize], 2);
    }

    #[test]
    fn discard_random_energy_opponent_removes_exactly_one() {
        let mut state = make_state();
        if let Some(slot) = state.players[1].active.as_mut() {
            slot.energy[Element::Psychic as usize] = 3;
        }
        let ctx = ctx(0); // acting = 0, opponent = 1
        discard_random_energy_opponent(&mut state, &ctx);
        assert_eq!(
            state.players[1].active.as_ref().unwrap().total_energy(),
            2
        );
    }

    #[test]
    fn discard_random_energy_opponent_noop_when_no_energy() {
        let mut state = make_state();
        // opponent active has 0 energy
        let ctx = ctx(0);
        discard_random_energy_opponent(&mut state, &ctx);
        assert_eq!(
            state.players[1].active.as_ref().unwrap().total_energy(),
            0
        );
    }

    #[test]
    fn discard_random_energy_both_active_removes_one_from_each() {
        let mut state = make_state();
        if let Some(slot) = state.players[0].active.as_mut() {
            slot.energy[Element::Fire as usize] = 2;
        }
        if let Some(slot) = state.players[1].active.as_mut() {
            slot.energy[Element::Water as usize] = 2;
        }
        let ctx = ctx(0);
        discard_random_energy_both_active(&mut state, &ctx);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().total_energy(),
            1
        );
        assert_eq!(
            state.players[1].active.as_ref().unwrap().total_energy(),
            1
        );
    }

    // ---- move tests ----

    #[test]
    fn move_bench_energy_to_active_moves_one() {
        let mut state = make_state();
        state.players[0].bench[1] = Some(PokemonSlot::new(5, 80));
        if let Some(b) = state.players[0].bench[1].as_mut() {
            b.energy[Element::Lightning as usize] = 2;
        }
        let ctx = ctx(0);
        move_bench_energy_to_active(&mut state, &ctx);
        assert_eq!(
            state.players[0].bench[1]
                .as_ref()
                .unwrap()
                .energy[Element::Lightning as usize],
            1
        );
        assert_eq!(
            state.players[0]
                .active
                .as_ref()
                .unwrap()
                .energy[Element::Lightning as usize],
            1
        );
    }

    #[test]
    fn move_all_electric_to_active_named_moves_all_lightning() {
        let mut state = make_state();
        // Bench slots each get 2 Lightning
        state.players[0].bench[0] = Some(PokemonSlot::new(2, 60));
        state.players[0].bench[1] = Some(PokemonSlot::new(3, 60));
        for i in 0..2 {
            if let Some(b) = state.players[0].bench[i].as_mut() {
                b.energy[Element::Lightning as usize] = 2;
            }
        }
        // Pass empty names => skip name check
        let ctx = ctx(0);
        move_all_electric_to_active_named(
            &mut state,
            &crate::card::CardDb::new_empty(),
            &ctx,
            &[],
        );
        // Total moved = 4
        assert_eq!(
            state.players[0]
                .active
                .as_ref()
                .unwrap()
                .energy[Element::Lightning as usize],
            4
        );
        for i in 0..2 {
            assert_eq!(
                state.players[0].bench[i]
                    .as_ref()
                    .unwrap()
                    .energy[Element::Lightning as usize],
                0
            );
        }
    }

    #[test]
    fn discard_top_deck_removes_correct_number() {
        let mut state = GameState::new(1);
        state.players[0].deck = vec![1, 2, 3, 4, 5];
        let ctx = ctx(0);
        discard_top_deck(&mut state, &ctx, 3);
        assert_eq!(state.players[0].deck.len(), 2);
        assert_eq!(state.players[0].discard.len(), 3);
        assert_eq!(state.players[0].deck, vec![4, 5]);
    }

    #[test]
    fn attach_colorless_energy_zone_bench_is_noop() {
        let mut state = make_state();
        state.players[0].bench[0] = Some(PokemonSlot::new(10, 60));
        let ctx = ctx(0);
        attach_colorless_energy_zone_bench(&mut state, &ctx);
        // No energy should have been added
        assert_eq!(
            state.players[0].bench[0].as_ref().unwrap().total_energy(),
            0
        );
    }
}
