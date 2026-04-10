//! Functions for playing cards from hand.
//!
//! Ported from `ptcgp/engine/play_card.py`.

use crate::card::CardDb;
use crate::state::{GameState, PokemonSlot, get_slot_mut};
use crate::actions::SlotRef;
use crate::types::{CardKind, Stage};
use crate::effects::EffectContext;
use crate::effects::dispatch::apply_effects;

/// Play a Basic Pokemon from hand to a bench slot.
pub fn play_basic(
    state: &mut GameState,
    db: &CardDb,
    hand_index: usize,
    bench_slot: usize,
) {
    let current = state.current_player;
    let player = &state.players[current];

    assert!(
        hand_index < player.hand.len(),
        "Invalid hand_index {}: hand has {} cards",
        hand_index,
        player.hand.len()
    );

    let card_idx = player.hand[hand_index];
    let card = db.get_by_idx(card_idx);

    assert_eq!(card.kind, CardKind::Pokemon, "Card {:?} is not a Pokemon", card.name);
    assert_eq!(
        card.stage,
        Some(Stage::Basic),
        "Card {:?} is not a Basic Pokemon (stage: {:?})",
        card.name,
        card.stage
    );

    assert!(bench_slot < 3, "Invalid bench_slot {}", bench_slot);
    assert!(
        state.players[current].bench[bench_slot].is_none(),
        "Bench slot {} is already occupied",
        bench_slot
    );

    let hp = card.hp;
    // Remove from hand
    state.players[current].hand.remove(hand_index);
    // Place in bench
    state.players[current].bench[bench_slot] = Some(PokemonSlot::new(card_idx, hp));
}

/// Play an Item card: discard it and apply its effects.
///
/// `extra_hand_index` is used by Rare Candy to point to the Stage 2 card.
pub fn play_item(
    state: &mut GameState,
    db: &CardDb,
    hand_index: usize,
    target: Option<SlotRef>,
    extra_hand_index: Option<usize>,
) {
    let current = state.current_player;
    let player = &state.players[current];

    assert!(
        hand_index < player.hand.len(),
        "Invalid hand_index {}: hand has {} cards",
        hand_index,
        player.hand.len()
    );

    let card_idx = player.hand[hand_index];
    let card = db.get_by_idx(card_idx);
    assert_eq!(card.kind, CardKind::Item, "Card {:?} is not an Item", card.name);

    // Capture the extra card index BEFORE popping the item from hand,
    // so indices stay stable.
    let extra_card_idx: Option<u16> = extra_hand_index.and_then(|ei| {
        if ei < state.players[current].hand.len() {
            Some(state.players[current].hand[ei])
        } else {
            None
        }
    });

    // Pop item from hand, discard it.
    state.players[current].hand.remove(hand_index);
    state.players[current].discard.push(card_idx);

    // Adjust extra_hand_index after the pop: if extra came after item, shift down by 1.
    let adjusted_extra_idx: Option<usize> = extra_hand_index.map(|ei| {
        if ei > hand_index { ei - 1 } else { ei }
    });

    // Build context. Wave 6 will wire real effects::EffectKind dispatch.
    // card.trainer_effects uses the card::EffectKind placeholder — pass empty slice.
    let mut ctx = EffectContext {
        acting_player: current,
        extra: Default::default(),
    };
    if let Some(evo_idx) = extra_card_idx {
        ctx.extra.insert("evo_card_idx".to_string(), evo_idx as i32);
    }
    if let Some(adj_idx) = adjusted_extra_idx {
        ctx.extra.insert("evo_hand_index".to_string(), adj_idx as i32);
    }
    if let Some(t) = target {
        ctx.extra.insert("target_player".to_string(), t.player as i32);
        ctx.extra.insert("target_slot".to_string(), t.slot as i32);
    }

    apply_effects(state, db, &[], &ctx);
}

/// Play a Supporter card: discard, mark flag, apply effects.
pub fn play_supporter(
    state: &mut GameState,
    db: &CardDb,
    hand_index: usize,
    target: Option<SlotRef>,
) {
    let current = state.current_player;
    let player = &state.players[current];

    assert!(
        hand_index < player.hand.len(),
        "Invalid hand_index {}: hand has {} cards",
        hand_index,
        player.hand.len()
    );

    let card_idx = player.hand[hand_index];
    let card = db.get_by_idx(card_idx);
    assert_eq!(
        card.kind,
        CardKind::Supporter,
        "Card {:?} is not a Supporter",
        card.name
    );

    // Pop from hand, discard, mark flag.
    state.players[current].hand.remove(hand_index);
    state.players[current].discard.push(card_idx);
    state.players[current].has_played_supporter = true;

    // Wave 6 will wire real effects::EffectKind dispatch for supporter effects.
    let mut ctx = EffectContext {
        acting_player: current,
        extra: Default::default(),
    };
    if let Some(t) = target {
        ctx.extra.insert("target_player".to_string(), t.player as i32);
        ctx.extra.insert("target_slot".to_string(), t.slot as i32);
    }

    apply_effects(state, db, &[], &ctx);
}

/// Attach a Tool card to a Pokemon.
pub fn attach_tool(
    state: &mut GameState,
    db: &CardDb,
    hand_index: usize,
    target: SlotRef,
) {
    let current = state.current_player;
    let player = &state.players[current];

    assert!(
        hand_index < player.hand.len(),
        "Invalid hand_index {}: hand has {} cards",
        hand_index,
        player.hand.len()
    );

    let card_idx = player.hand[hand_index];
    let card = db.get_by_idx(card_idx);
    assert_eq!(card.kind, CardKind::Tool, "Card {:?} is not a Tool", card.name);

    {
        let slot = get_slot_mut(state, target).expect("No Pokemon at target slot");
        assert!(
            slot.tool_idx.is_none(),
            "Target Pokemon already has a tool attached"
        );
        slot.tool_idx = Some(card_idx);
    }

    // Pop from hand (do NOT go to discard — tool stays attached).
    state.players[current].hand.remove(hand_index);

    // Apply passive tool effects. Wave 6 will wire real effects dispatch.
    let mut ctx = EffectContext {
        acting_player: current,
        extra: Default::default(),
    };
    ctx.extra.insert("target_player".to_string(), target.player as i32);
    ctx.extra.insert("target_slot".to_string(), target.slot as i32);

    apply_effects(state, db, &[], &ctx);
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::CardDb;
    use crate::state::GameState;
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

    fn make_state(db: &CardDb) -> GameState {
        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        // Give player 0 a Bulbasaur in hand.
        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        state.players[0].hand.push(bulb.idx);
        state
    }

    #[test]
    fn play_basic_places_card_on_bench() {
        let db = load_db();
        let mut state = make_state(&db);
        let hand_len_before = state.players[0].hand.len();
        play_basic(&mut state, &db, 0, 0);
        assert_eq!(state.players[0].hand.len(), hand_len_before - 1, "Card should be removed from hand");
        assert!(state.players[0].bench[0].is_some(), "Bench slot 0 should be occupied");
        let slot = state.players[0].bench[0].as_ref().unwrap();
        let bulb = db.get_by_id("a1-001").unwrap();
        assert_eq!(slot.card_idx, bulb.idx);
        assert_eq!(slot.current_hp, bulb.hp);
        assert_eq!(slot.max_hp, bulb.hp);
        assert_eq!(slot.turns_in_play, 0);
    }

    #[test]
    #[should_panic(expected = "Bench slot 0 is already occupied")]
    fn play_basic_occupied_bench_panics() {
        let db = load_db();
        let mut state = make_state(&db);
        let bulb = db.get_by_id("a1-001").unwrap();
        // Pre-occupy slot 0.
        state.players[0].bench[0] = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        play_basic(&mut state, &db, 0, 0);
    }
}
