#![allow(dead_code, unused_imports, unused_variables)]
use rand::seq::SliceRandom;
use rand::Rng;
use crate::card::CardDb;
use crate::constants::POINTS_TO_WIN;
use crate::state::GameState;
use crate::effects::EffectContext;
use crate::types::{CardKind, Stage, Element};

// ------------------------------------------------------------------ //
// Internal helpers
// ------------------------------------------------------------------ //

/// Draw one card from the top of `player`'s deck into their hand.
/// Deck is stored as Vec<u16> where `pop()` takes from the "top".
fn draw_one_for(state: &mut GameState, player: usize) {
    if let Some(card) = state.players[player].deck.pop() {
        state.players[player].hand.push(card);
    }
}

/// Remove `count` random cards from `player`'s hand, add them to discard.
fn discard_random_from_hand(state: &mut GameState, player: usize, count: u8) {
    for _ in 0..count {
        if state.players[player].hand.is_empty() {
            break;
        }
        let len = state.players[player].hand.len();
        // Use rng to pick a random index
        let idx = state.rng.gen_range(0..len);
        let card = state.players[player].hand.remove(idx);
        state.players[player].discard.push(card);
    }
}

// ------------------------------------------------------------------ //
// Draw effects
// ------------------------------------------------------------------ //

/// Draw `count` cards from top of deck to hand.
pub fn draw_cards(state: &mut GameState, count: u8, ctx: &EffectContext) {
    let player = ctx.acting_player;
    for _ in 0..count {
        draw_one_for(state, player);
    }
}

/// Draw 1 card.
pub fn draw_one_card(state: &mut GameState, ctx: &EffectContext) {
    draw_cards(state, 1, ctx);
}

/// Draw cards until you get a Basic Pokemon, shuffle rest back.
/// In this simulation, we find all Basic Pokemon in deck, pick one at random
/// and add to hand (matching Python's draw_basic_pokemon which picks randomly).
pub fn draw_basic_pokemon(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;
    // Collect indices of Basic Pokemon in the deck
    let basic_positions: Vec<usize> = state.players[player].deck
        .iter()
        .enumerate()
        .filter(|(_, &cid)| {
            let card = db.get_by_idx(cid);
            card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic)
        })
        .map(|(i, _)| i)
        .collect();

    if basic_positions.is_empty() {
        return;
    }

    // Pick a random Basic Pokemon from its positions
    let pick_pos = basic_positions[state.rng.gen_range(0..basic_positions.len())];
    let card = state.players[player].deck.remove(pick_pos);
    state.players[player].hand.push(card);
    // Shuffle remaining deck
    state.players[player].deck.shuffle(&mut state.rng);
}

// ------------------------------------------------------------------ //
// Iono / Mars / shuffle effects
// ------------------------------------------------------------------ //

/// Iono: each player shuffles their hand into their deck then draws cards
/// equal to their OWN pre-shuffle hand size.
pub fn iono_hand_shuffle(state: &mut GameState, ctx: &EffectContext) {
    let acting = ctx.acting_player;
    let opponent = 1 - acting;

    // Record hand sizes BEFORE shuffling — each player draws their own count.
    let acting_draw_count = state.players[acting].hand.len() as u8;
    let opponent_draw_count = state.players[opponent].hand.len() as u8;

    // Both players shuffle hand into deck
    let acting_hand: Vec<u16> = state.players[acting].hand.drain(..).collect();
    state.players[acting].deck.extend(acting_hand);
    state.players[acting].deck.shuffle(&mut state.rng);

    let opp_hand: Vec<u16> = state.players[opponent].hand.drain(..).collect();
    state.players[opponent].deck.extend(opp_hand);
    state.players[opponent].deck.shuffle(&mut state.rng);

    // Both players draw their assigned counts
    for _ in 0..acting_draw_count {
        draw_one_for(state, acting);
    }
    for _ in 0..opponent_draw_count {
        draw_one_for(state, opponent);
    }
}

/// Mars: your opponent shuffles their hand into their deck and draws a card
/// for each of their remaining points needed to win (POINTS_TO_WIN - opponent.points).
pub fn mars_hand_shuffle(state: &mut GameState, ctx: &EffectContext) {
    let acting = ctx.acting_player;
    let opponent = 1 - acting;

    // Compute remaining points needed for opponent to win, BEFORE shuffling.
    let opp_points = state.players[opponent].points;
    let draw_count = POINTS_TO_WIN.saturating_sub(opp_points);

    // Opponent shuffles hand into deck.
    let opp_hand: Vec<u16> = state.players[opponent].hand.drain(..).collect();
    state.players[opponent].deck.extend(opp_hand);
    state.players[opponent].deck.shuffle(&mut state.rng);

    // Opponent draws one card per remaining point.
    for _ in 0..draw_count {
        draw_one_for(state, opponent);
    }
}

/// Shuffle all hand cards back into deck.
pub fn shuffle_hand_into_deck(state: &mut GameState, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let hand: Vec<u16> = state.players[player].hand.drain(..).collect();
    state.players[player].deck.extend(hand);
    state.players[player].deck.shuffle(&mut state.rng);
}

/// Shuffle hand into deck, draw cards equal to opponent's hand size.
pub fn shuffle_hand_draw_opponent_count(state: &mut GameState, ctx: &EffectContext) {
    let acting = ctx.acting_player;
    let opponent = 1 - acting;
    let opp_hand_size = state.players[opponent].hand.len() as u8;

    // Shuffle acting player's hand into deck
    let hand: Vec<u16> = state.players[acting].hand.drain(..).collect();
    state.players[acting].deck.extend(hand);
    state.players[acting].deck.shuffle(&mut state.rng);

    // Draw opponent's count
    for _ in 0..opp_hand_size {
        draw_one_for(state, acting);
    }
}

/// Discard `count` cards randomly from hand, then draw `count` cards.
pub fn discard_to_draw(state: &mut GameState, count: u8, ctx: &EffectContext) {
    let player = ctx.acting_player;
    discard_random_from_hand(state, player, count);
    for _ in 0..count {
        draw_one_for(state, player);
    }
}

/// Maintenance: shuffle `shuffle_count` random cards from hand into the deck, then draw `draw_count`.
/// Net effect: cycles unwanted cards back to deck while gaining fewer new cards (hand shrinks by shuffle_count - draw_count).
pub fn maintenance_shuffle(state: &mut GameState, shuffle_count: u8, draw_count: u8, ctx: &EffectContext) {
    use rand::seq::SliceRandom;
    let player = ctx.acting_player;
    for _ in 0..shuffle_count {
        if state.players[player].hand.is_empty() {
            break;
        }
        let len = state.players[player].hand.len();
        let idx = state.rng.gen_range(0..len);
        let card = state.players[player].hand.remove(idx);
        state.players[player].deck.push(card);
    }
    state.players[player].deck.shuffle(&mut state.rng);
    for _ in 0..draw_count {
        draw_one_for(state, player);
    }
}

/// Opponent shuffles hand into deck then draws `count` cards.
pub fn opponent_shuffle_hand_draw(state: &mut GameState, count: u8, ctx: &EffectContext) {
    let opponent = 1 - ctx.acting_player;

    let opp_hand: Vec<u16> = state.players[opponent].hand.drain(..).collect();
    state.players[opponent].deck.extend(opp_hand);
    state.players[opponent].deck.shuffle(&mut state.rng);

    for _ in 0..count {
        draw_one_for(state, opponent);
    }
}

// ------------------------------------------------------------------ //
// Search effects
// ------------------------------------------------------------------ //

/// Search deck for a Basic Pokemon with matching name, add to hand.
pub fn search_deck_named_basic(state: &mut GameState, db: &CardDb, name: &str, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let pos = state.players[player].deck.iter().position(|&cid| {
        let card = db.get_by_idx(cid);
        card.kind == CardKind::Pokemon
            && card.stage == Some(Stage::Basic)
            && card.name.eq_ignore_ascii_case(name)
    });
    if let Some(idx) = pos {
        let card = state.players[player].deck.remove(idx);
        state.players[player].hand.push(card);
        state.players[player].deck.shuffle(&mut state.rng);
    }
}

/// Search deck for a random Pokemon, add to hand.
pub fn search_deck_random_pokemon(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let positions: Vec<usize> = state.players[player].deck
        .iter()
        .enumerate()
        .filter(|(_, &cid)| db.get_by_idx(cid).kind == CardKind::Pokemon)
        .map(|(i, _)| i)
        .collect();

    if positions.is_empty() {
        return;
    }

    let pick = positions[state.rng.gen_range(0..positions.len())];
    let card = state.players[player].deck.remove(pick);
    state.players[player].hand.push(card);
    state.players[player].deck.shuffle(&mut state.rng);
}

/// Search deck for a Pokemon that evolves from `name`.
pub fn search_deck_evolves_from(state: &mut GameState, db: &CardDb, name: &str, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let positions: Vec<usize> = state.players[player].deck
        .iter()
        .enumerate()
        .filter(|(_, &cid)| {
            let card = db.get_by_idx(cid);
            card.kind == CardKind::Pokemon
                && card.evolves_from.as_deref()
                    .map(|ef| ef.eq_ignore_ascii_case(name))
                    .unwrap_or(false)
        })
        .map(|(i, _)| i)
        .collect();

    if positions.is_empty() {
        return;
    }

    let pick = positions[state.rng.gen_range(0..positions.len())];
    let card = state.players[player].deck.remove(pick);
    state.players[player].hand.push(card);
    state.players[player].deck.shuffle(&mut state.rng);
}

/// Search deck for any card with matching name.
pub fn search_deck_named(state: &mut GameState, db: &CardDb, name: &str, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let pos = state.players[player].deck.iter().position(|&cid| {
        db.get_by_idx(cid).name.eq_ignore_ascii_case(name)
    });
    if let Some(idx) = pos {
        let card = state.players[player].deck.remove(idx);
        state.players[player].hand.push(card);
        state.players[player].deck.shuffle(&mut state.rng);
    }
}

/// Gladion-style: search deck for a random card whose name matches any entry in `names`
/// and put it into the hand.
pub fn search_deck_multi_named(state: &mut GameState, db: &CardDb, names: &[String], ctx: &EffectContext) {
    let player = ctx.acting_player;
    let positions: Vec<usize> = state.players[player].deck
        .iter()
        .enumerate()
        .filter(|(_, &cid)| {
            let card_name = &db.get_by_idx(cid).name;
            names.iter().any(|n| n.eq_ignore_ascii_case(card_name))
        })
        .map(|(i, _)| i)
        .collect();

    if positions.is_empty() {
        return;
    }

    let pick = positions[state.rng.gen_range(0..positions.len())];
    let card = state.players[player].deck.remove(pick);
    state.players[player].hand.push(card);
    state.players[player].deck.shuffle(&mut state.rng);
}

/// Search deck for a random Grass Pokemon.
pub fn search_deck_grass_pokemon(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let positions: Vec<usize> = state.players[player].deck
        .iter()
        .enumerate()
        .filter(|(_, &cid)| {
            let card = db.get_by_idx(cid);
            card.kind == CardKind::Pokemon && card.element == Some(Element::Grass)
        })
        .map(|(i, _)| i)
        .collect();

    if positions.is_empty() {
        return;
    }

    let pick = positions[state.rng.gen_range(0..positions.len())];
    let card = state.players[player].deck.remove(pick);
    state.players[player].hand.push(card);
    state.players[player].deck.shuffle(&mut state.rng);
}

/// Search deck for a random Basic Pokemon.
pub fn search_deck_random_basic(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let positions: Vec<usize> = state.players[player].deck
        .iter()
        .enumerate()
        .filter(|(_, &cid)| {
            let card = db.get_by_idx(cid);
            card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic)
        })
        .map(|(i, _)| i)
        .collect();

    if positions.is_empty() {
        return;
    }

    let pick = positions[state.rng.gen_range(0..positions.len())];
    let card = state.players[player].deck.remove(pick);
    state.players[player].hand.push(card);
    state.players[player].deck.shuffle(&mut state.rng);
}

/// Search discard for a random Basic Pokemon, add to hand.
pub fn search_discard_random_basic(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let positions: Vec<usize> = state.players[player].discard
        .iter()
        .enumerate()
        .filter(|(_, &cid)| {
            let card = db.get_by_idx(cid);
            card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic)
        })
        .map(|(i, _)| i)
        .collect();

    if positions.is_empty() {
        return;
    }

    let pick = positions[state.rng.gen_range(0..positions.len())];
    let card = state.players[player].discard.remove(pick);
    state.players[player].hand.push(card);
}

// ------------------------------------------------------------------ //
// Look / reveal effects (no-op or draw in simulation)
// ------------------------------------------------------------------ //

/// Look at top `count` cards of deck. Information-only effect: in a perfect-info
/// simulator the agent already has this information, so this is a no-op
/// (cards remain in the deck, are NOT moved to hand).
pub fn look_top_of_deck(_state: &mut GameState, _count: u8, _ctx: &EffectContext) {}

/// No-op: reveal opponent's hand (perfect information in simulation).
pub fn reveal_opponent_hand(_state: &mut GameState, _ctx: &EffectContext) {}

/// No-op: look at opponent's hand.
pub fn look_opponent_hand(_state: &mut GameState, _ctx: &EffectContext) {}

/// No-op: reveal opponent's supporter cards.
pub fn reveal_opponent_supporters(_state: &mut GameState, _ctx: &EffectContext) {}

// ------------------------------------------------------------------ //
// Composite card effects
// ------------------------------------------------------------------ //

/// Fishing Net: search deck for 2 Pokemon, add to hand.
pub fn fishing_net(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    for _ in 0..2 {
        search_deck_random_pokemon(state, db, ctx);
    }
}

/// Pokemon Communication: choose a Pokemon in hand, put it on top of your deck;
/// search deck for a Pokemon, reveal it, put it in hand, then shuffle the deck.
pub fn pokemon_communication(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;

    // Find a Pokemon in hand to return to deck.
    let hand_pokemon_pos = state.players[player].hand
        .iter()
        .position(|&cid| db.get_by_idx(cid).kind == CardKind::Pokemon);

    if let Some(pos) = hand_pokemon_pos {
        // Put the chosen Pokemon on top of the deck (top = last element since pop() is used).
        let returned = state.players[player].hand.remove(pos);
        state.players[player].deck.push(returned);
        // Search deck for a Pokemon and put it in hand; search_deck_random_pokemon shuffles after.
        search_deck_random_pokemon(state, db, ctx);
    }
}

// ------------------------------------------------------------------ //
// Discard effects targeting opponent / hand
// ------------------------------------------------------------------ //

/// Discard a random card from opponent's hand.
pub fn discard_random_card_opponent(state: &mut GameState, ctx: &EffectContext) {
    let opponent = 1 - ctx.acting_player;
    discard_random_from_hand(state, opponent, 1);
}

/// Discard a random Tool card from the acting player's hand.
pub fn discard_random_tool_from_hand(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let tool_positions: Vec<usize> = state.players[player].hand
        .iter()
        .enumerate()
        .filter(|(_, &cid)| db.get_by_idx(cid).kind == CardKind::Tool)
        .map(|(i, _)| i)
        .collect();

    if tool_positions.is_empty() {
        return;
    }

    let pick = tool_positions[state.rng.gen_range(0..tool_positions.len())];
    let card = state.players[player].hand.remove(pick);
    state.players[player].discard.push(card);
}

/// Discard a random Item card from the acting player's hand.
pub fn discard_random_item_from_hand(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let player = ctx.acting_player;
    let item_positions: Vec<usize> = state.players[player].hand
        .iter()
        .enumerate()
        .filter(|(_, &cid)| db.get_by_idx(cid).kind == CardKind::Item)
        .map(|(i, _)| i)
        .collect();

    if item_positions.is_empty() {
        return;
    }

    let pick = item_positions[state.rng.gen_range(0..item_positions.len())];
    let card = state.players[player].hand.remove(pick);
    state.players[player].discard.push(card);
}

// ------------------------------------------------------------------ //
// Unit tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::GameState;
    use crate::effects::EffectContext;

    fn make_state_with_deck(seed: u64, deck_size: u16) -> GameState {
        let mut state = GameState::new(seed);
        // Fill player 0's deck with card indices 0..deck_size
        state.players[0].deck = (0..deck_size).collect();
        state
    }

    #[test]
    fn draw_cards_moves_from_deck_to_hand() {
        let mut state = make_state_with_deck(1, 10);
        let ctx = EffectContext::new(0);
        assert_eq!(state.players[0].hand.len(), 0);
        assert_eq!(state.players[0].deck.len(), 10);

        draw_cards(&mut state, 3, &ctx);

        assert_eq!(state.players[0].hand.len(), 3);
        assert_eq!(state.players[0].deck.len(), 7);
    }

    #[test]
    fn draw_cards_does_not_panic_on_empty_deck() {
        let mut state = GameState::new(42);
        let ctx = EffectContext::new(0);
        // deck is empty — should silently skip
        draw_cards(&mut state, 5, &ctx);
        assert_eq!(state.players[0].hand.len(), 0);
    }

    #[test]
    fn shuffle_hand_into_deck_empties_hand_and_grows_deck() {
        let mut state = make_state_with_deck(2, 5);
        state.players[0].hand = vec![10, 11, 12];
        let ctx = EffectContext::new(0);

        shuffle_hand_into_deck(&mut state, &ctx);

        assert_eq!(state.players[0].hand.len(), 0);
        assert_eq!(state.players[0].deck.len(), 8); // 5 original + 3 from hand
    }

    #[test]
    fn search_deck_named_finds_correct_card() {
        // We need a CardDb for this — skip if assets not available, check via a mock approach.
        // Build a minimal fake state and check search_deck_named without a real db by directly
        // confirming it picks the right position.
        // Since CardDb::load requires file I/O, test with a real db if available.
        use std::path::PathBuf;
        let mut assets = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        assets.pop();
        assets.push("assets/cards");
        if !assets.exists() {
            return; // skip if no card data
        }

        let db = CardDb::load_from_dir(&assets);
        let bulbasaur_idx = db.get_idx_by_id("a1-001");
        if bulbasaur_idx.is_none() {
            return;
        }
        let idx = bulbasaur_idx.unwrap();

        let mut state = GameState::new(7);
        state.players[0].deck = vec![idx, idx + 1, idx + 2];
        let ctx = EffectContext::new(0);

        search_deck_named(&mut state, &db, "Bulbasaur", &ctx);

        // Bulbasaur should now be in hand
        assert!(state.players[0].hand.contains(&idx));
        // Deck should be smaller
        assert_eq!(state.players[0].deck.len(), 2);
    }

    #[test]
    fn iono_each_player_draws_own_hand_size() {
        let mut state = GameState::new(3);
        // Player 0 has 3 cards in hand, player 1 has 5 cards in hand
        state.players[0].hand = vec![1, 2, 3];
        state.players[1].hand = vec![4, 5, 6, 7, 8];
        // Give each player a deck to draw from
        state.players[0].deck = (10..20).collect();
        state.players[1].deck = (20..30).collect();

        let ctx = EffectContext::new(0); // player 0 plays Iono

        iono_hand_shuffle(&mut state, &ctx);

        // Each player draws cards equal to their OWN pre-shuffle hand size.
        // Player 0 had 3 in hand, draws 3.
        assert_eq!(state.players[0].hand.len(), 3);
        // Player 1 had 5 in hand, draws 5.
        assert_eq!(state.players[1].hand.len(), 5);
    }

    #[test]
    fn discard_random_card_opponent_reduces_opponent_hand() {
        let mut state = GameState::new(4);
        state.players[1].hand = vec![10, 11, 12];
        let ctx = EffectContext::new(0);

        discard_random_card_opponent(&mut state, &ctx);

        assert_eq!(state.players[1].hand.len(), 2);
        assert_eq!(state.players[1].discard.len(), 1);
    }
}
