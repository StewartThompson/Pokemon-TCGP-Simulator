#![allow(dead_code, unused_imports, unused_variables)]

use rand::seq::SliceRandom;
use crate::card::CardDb;
use crate::state::GameState;
use crate::actions::SlotRef;
use crate::effects::EffectContext;
use crate::types::{Stage, Element, StatusEffect};

// ------------------------------------------------------------------ //
// Internal helpers
// ------------------------------------------------------------------ //

fn get_opponent(ctx: &EffectContext) -> usize {
    1 - ctx.acting_player
}

/// Swap active ↔ bench[bench_idx] for a player (no retreat cost).
/// Clears volatile status conditions (Paralyzed, Asleep, Confused) from the
/// Pokémon being forced out of the Active Spot, matching PTCGP switching rules.
fn swap_active_bench(state: &mut GameState, player: usize, bench_idx: usize) {
    // Clear volatile statuses from the currently active pokemon before it moves.
    if let Some(ref mut slot) = state.players[player].active {
        slot.remove_status(StatusEffect::Paralyzed);
        slot.remove_status(StatusEffect::Asleep);
        slot.remove_status(StatusEffect::Confused);
    }

    let bench_slot = state.players[player].bench[bench_idx].take();
    let old_active = state.players[player].active.take();
    state.players[player].active = bench_slot;
    state.players[player].bench[bench_idx] = old_active;
}

/// Collect all bench indices that are occupied.
fn occupied_bench_indices(state: &GameState, player: usize) -> Vec<usize> {
    state.players[player]
        .bench
        .iter()
        .enumerate()
        .filter_map(|(i, s)| if s.is_some() { Some(i) } else { None })
        .collect()
}

// ------------------------------------------------------------------ //
// Public movement handlers
// ------------------------------------------------------------------ //

/// Force the opponent to switch their Active with a **random** bench Pokémon.
/// Maps to Python `switch_opponent_active`.
pub fn switch_opponent_active_random(state: &mut GameState, ctx: &EffectContext) {
    let opp = get_opponent(ctx);
    let bench_indices = occupied_bench_indices(state, opp);
    if let Some(&idx) = bench_indices.choose(&mut state.rng) {
        swap_active_bench(state, opp, idx);
    }
}

/// The opponent chooses which bench Pokémon to switch in.
/// In simulation, picks randomly (same as `switch_opponent_active_random`).
pub fn switch_opponent_active_choice(state: &mut GameState, ctx: &EffectContext) {
    switch_opponent_active_random(state, ctx);
}

/// Move the acting player's active to bench; promote a bench Pokémon.
/// Respects an optional `target_bench_idx` in ctx.extra["bench_idx"].
/// Falls back to a random occupied bench slot if no preference is given.
/// Maps to Python `switch_self_to_bench`.
pub fn switch_self_active(state: &mut GameState, ctx: &EffectContext) {
    let pi = ctx.acting_player;
    let bench_indices = occupied_bench_indices(state, pi);
    if bench_indices.is_empty() {
        return;
    }
    let slot = if let Some(&bench_idx) = ctx.extra.get("bench_idx") {
        let idx = bench_idx as usize;
        if state.players[pi].bench[idx].is_some() {
            idx
        } else {
            *bench_indices.choose(&mut state.rng).unwrap()
        }
    } else {
        *bench_indices.choose(&mut state.rng).unwrap()
    };
    swap_active_bench(state, pi, slot);
}

/// Move a specific bench Pokémon to the active spot (effect-driven, no energy cost).
/// Maps to Python `ability_bench_to_active`.
pub fn move_bench_to_active(state: &mut GameState, bench_idx: usize, player: usize) {
    if state.players[player].bench[bench_idx].is_none() {
        return;
    }
    swap_active_bench(state, player, bench_idx);
}

/// Swap active ↔ bench[idx] for a player (public, no retreat cost).
pub fn switch_active_bench(state: &mut GameState, player: usize, bench_idx: usize) {
    if state.players[player].bench[bench_idx].is_none() {
        return;
    }
    swap_active_bench(state, player, bench_idx);
}

/// Force one of the opponent's benched **Basic** Pokémon into their Active Spot.
/// Maps to Python `switch_opponent_basic_to_active`.
pub fn switch_opponent_basic_to_active(state: &mut GameState, ctx: &EffectContext, db: &CardDb) {
    let opp = get_opponent(ctx);
    let basic_bench: Vec<usize> = state.players[opp]
        .bench
        .iter()
        .enumerate()
        .filter_map(|(i, s)| {
            let slot = s.as_ref()?;
            let card = db.cards.get(slot.card_idx as usize)?;
            if card.stage == Some(Stage::Basic) {
                Some(i)
            } else {
                None
            }
        })
        .collect();
    if let Some(&idx) = basic_bench.choose(&mut state.rng) {
        swap_active_bench(state, opp, idx);
    }
}

/// If this Pokémon is on your bench, switch it with your Active.
/// Maps to Python `ability_bench_to_active` — called with a known source slot.
pub fn ability_bench_to_active(state: &mut GameState, ctx: &EffectContext) {
    let pi = ctx.acting_player;
    let bench_idx = match ctx.extra.get("source_bench_idx") {
        Some(&i) if i >= 0 => i as usize,
        _ => return,
    };
    if state.players[pi].bench[bench_idx].is_none() {
        return;
    }
    swap_active_bench(state, pi, bench_idx);
}

/// Switch your active with a random bench Pokémon of a specific element type.
/// Maps to Python `switch_self_to_bench_typed`.
pub fn switch_self_to_bench_typed(state: &mut GameState, ctx: &EffectContext, db: &CardDb, element: Option<Element>) {
    let pi = ctx.acting_player;
    let bench_indices: Vec<usize> = state.players[pi]
        .bench
        .iter()
        .enumerate()
        .filter_map(|(i, s)| {
            let slot = s.as_ref()?;
            if let Some(filter_el) = element {
                let card = db.cards.get(slot.card_idx as usize)?;
                if card.element != Some(filter_el) {
                    return None;
                }
            }
            Some(i)
        })
        .collect();
    if let Some(&idx) = bench_indices.choose(&mut state.rng) {
        swap_active_bench(state, pi, idx);
    }
}

/// Switch active Ultra Beast with 1 of the bench Pokémon (random in simulation).
/// Maps to Python `switch_ultra_beast`.
pub fn switch_ultra_beast(state: &mut GameState, ctx: &EffectContext) {
    let pi = ctx.acting_player;
    let bench_indices = occupied_bench_indices(state, pi);
    if let Some(&idx) = bench_indices.choose(&mut state.rng) {
        swap_active_bench(state, pi, idx);
    }
}

/// Return the acting player's active Pokémon (by name) to their hand.
/// Tool is discarded; attached energies are lost.
/// Maps to Python `return_active_to_hand_named`.
pub fn return_active_to_hand_named(state: &mut GameState, ctx: &EffectContext, db: &CardDb, names: &[&str]) {
    let pi = ctx.acting_player;
    {
        let active = match state.players[pi].active.as_ref() {
            Some(a) => a,
            None => return,
        };
        if !names.is_empty() {
            let card = match db.cards.get(active.card_idx as usize) {
                Some(c) => c,
                None => return,
            };
            let name_lower = card.name.to_lowercase();
            if !names.iter().any(|n| name_lower == n.to_lowercase()) {
                return;
            }
        }
    }
    let active = state.players[pi].active.take().unwrap();
    state.players[pi].hand.push(active.card_idx);
    if let Some(tool_idx) = active.tool_idx {
        state.players[pi].discard.push(tool_idx);
    }
}

/// Coin flip: on heads, put the opponent's Active back into their hand.
/// Maps to Python `coin_flip_bounce_opponent`.
pub fn coin_flip_bounce_opponent(state: &mut GameState, ctx: &EffectContext) {
    use rand::Rng;
    if state.rng.gen::<f64>() >= 0.5 {
        return;
    }
    let opp = get_opponent(ctx);
    if state.players[opp].active.is_none() {
        return;
    }
    let active = state.players[opp].active.take().unwrap();
    state.players[opp].hand.push(active.card_idx);
    if let Some(tool_idx) = active.tool_idx {
        state.players[opp].discard.push(tool_idx);
    }
}

/// Coin flip: on heads, shuffle the opponent's Active back into their deck.
/// Maps to Python `shuffle_opponent_active_into_deck`.
pub fn shuffle_opponent_active_into_deck(state: &mut GameState, ctx: &EffectContext) {
    use rand::seq::SliceRandom;
    use rand::Rng;
    if state.rng.gen::<f64>() >= 0.5 {
        return;
    }
    let opp = get_opponent(ctx);
    if state.players[opp].active.is_none() {
        return;
    }
    let active = state.players[opp].active.take().unwrap();
    state.players[opp].deck.push(active.card_idx);
    if let Some(tool_idx) = active.tool_idx {
        state.players[opp].discard.push(tool_idx);
    }
    state.players[opp].deck.shuffle(&mut state.rng);
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};
    use crate::effects::EffectContext;

    fn make_state_with_active_and_bench() -> (GameState, EffectContext) {
        let mut state = GameState::new(42);
        // Player 0 active
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        // Player 1 active + one bench Pokémon
        state.players[1].active = Some(PokemonSlot::new(1, 80));
        state.players[1].bench[0] = Some(PokemonSlot::new(2, 60));
        let ctx = EffectContext::new(0); // acting_player = 0
        (state, ctx)
    }

    #[test]
    fn switch_opponent_active_random_swaps_active_with_bench() {
        let (mut state, ctx) = make_state_with_active_and_bench();

        // Before: opp active = card 1, bench[0] = card 2
        assert_eq!(state.players[1].active.as_ref().unwrap().card_idx, 1);
        assert_eq!(state.players[1].bench[0].as_ref().unwrap().card_idx, 2);

        switch_opponent_active_random(&mut state, &ctx);

        // After: opp active should be the former bench Pokémon (card 2)
        assert_eq!(state.players[1].active.as_ref().unwrap().card_idx, 2);
        // Old active is now on the bench
        assert_eq!(state.players[1].bench[0].as_ref().unwrap().card_idx, 1);
        // Acting player's active is untouched
        assert_eq!(state.players[0].active.as_ref().unwrap().card_idx, 0);
    }

    #[test]
    fn switch_opponent_active_random_noop_when_no_bench() {
        let mut state = GameState::new(99);
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state.players[1].active = Some(PokemonSlot::new(1, 80));
        // No bench for player 1
        let ctx = EffectContext::new(0);

        switch_opponent_active_random(&mut state, &ctx);

        // Active should be unchanged
        assert_eq!(state.players[1].active.as_ref().unwrap().card_idx, 1);
    }

    #[test]
    fn swap_clears_volatile_status_from_outgoing_active() {
        let (mut state, ctx) = make_state_with_active_and_bench();
        // Give opponent's active a status that should be cleared on switch
        if let Some(ref mut slot) = state.players[1].active {
            slot.add_status(StatusEffect::Paralyzed);
            slot.add_status(StatusEffect::Asleep);
        }

        switch_opponent_active_random(&mut state, &ctx);

        // The former active is now on the bench — check status is cleared
        let former_active = state.players[1].bench[0].as_ref().unwrap();
        assert!(!former_active.has_status(StatusEffect::Paralyzed));
        assert!(!former_active.has_status(StatusEffect::Asleep));
    }

    #[test]
    fn switch_self_active_swaps_own_active_with_bench() {
        let mut state = GameState::new(7);
        state.players[0].active = Some(PokemonSlot::new(10, 100));
        state.players[0].bench[1] = Some(PokemonSlot::new(11, 70));
        let ctx = EffectContext::new(0);

        switch_self_active(&mut state, &ctx);

        // The bench Pokémon should now be active
        assert_eq!(state.players[0].active.as_ref().unwrap().card_idx, 11);
        // Old active is on the bench
        assert_eq!(state.players[0].bench[1].as_ref().unwrap().card_idx, 10);
    }

    #[test]
    fn move_bench_to_active_promotes_bench_pokemon() {
        let mut state = GameState::new(3);
        state.players[0].active = Some(PokemonSlot::new(5, 100));
        state.players[0].bench[2] = Some(PokemonSlot::new(6, 90));

        move_bench_to_active(&mut state, 2, 0);

        assert_eq!(state.players[0].active.as_ref().unwrap().card_idx, 6);
        assert_eq!(state.players[0].bench[2].as_ref().unwrap().card_idx, 5);
    }

    #[test]
    fn switch_active_bench_swaps_correctly() {
        let mut state = GameState::new(5);
        state.players[1].active = Some(PokemonSlot::new(20, 100));
        state.players[1].bench[0] = Some(PokemonSlot::new(21, 50));

        switch_active_bench(&mut state, 1, 0);

        assert_eq!(state.players[1].active.as_ref().unwrap().card_idx, 21);
        assert_eq!(state.players[1].bench[0].as_ref().unwrap().card_idx, 20);
    }

    #[test]
    fn switch_active_bench_noop_when_bench_empty() {
        let mut state = GameState::new(5);
        state.players[0].active = Some(PokemonSlot::new(10, 100));
        // bench[0] is None

        switch_active_bench(&mut state, 0, 0);

        // Active unchanged
        assert_eq!(state.players[0].active.as_ref().unwrap().card_idx, 10);
    }

    #[test]
    fn coin_flip_bounce_opponent_sometimes_bounces() {
        let mut bounced = false;
        for seed in 0..200u64 {
            let mut state = GameState::new(seed);
            state.players[0].active = Some(PokemonSlot::new(0, 100));
            state.players[1].active = Some(PokemonSlot::new(1, 80));
            let ctx = EffectContext::new(0);

            coin_flip_bounce_opponent(&mut state, &ctx);

            if state.players[1].active.is_none() {
                // Card should be in hand
                assert!(state.players[1].hand.contains(&1));
                bounced = true;
            }
        }
        assert!(bounced, "Expected at least one coin-flip bounce in 200 trials");
    }

    #[test]
    fn shuffle_opponent_active_into_deck_sometimes_shuffles() {
        let mut shuffled = false;
        for seed in 0..200u64 {
            let mut state = GameState::new(seed);
            state.players[0].active = Some(PokemonSlot::new(0, 100));
            state.players[1].active = Some(PokemonSlot::new(3, 80));
            let ctx = EffectContext::new(0);

            shuffle_opponent_active_into_deck(&mut state, &ctx);

            if state.players[1].active.is_none() {
                assert!(state.players[1].deck.contains(&3));
                shuffled = true;
            }
        }
        assert!(shuffled, "Expected at least one shuffle in 200 trials");
    }
}
