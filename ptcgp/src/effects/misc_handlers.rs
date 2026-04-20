#![allow(dead_code, unused_imports, unused_variables)]
use rand::Rng;
use rand::seq::SliceRandom;
use crate::card::CardDb;
use crate::state::{GameState, get_slot_mut};
use crate::actions::SlotRef;
use crate::effects::EffectContext;
use crate::types::{CardKind, Stage};

// ------------------------------------------------------------------ //
// Misc: next-turn flags on opponent
// ------------------------------------------------------------------ //

/// Prevent the opponent's active Pokémon from retreating during their next turn.
pub fn cant_retreat_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    if let Some(slot) = state.players[opp].active.as_mut() {
        slot.cant_retreat_next_turn_incoming = true;
    }
}

/// Prevent the opponent's active Pokémon from attacking during their next turn
/// (coin-flip gating is handled at the call site; this simply sets the flag).
pub fn cant_attack_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    if let Some(slot) = state.players[opp].active.as_mut() {
        slot.cant_attack_next_turn_incoming = true;
    }
}

// NOTE: `coin_flip_attack_block_next_turn` previously lived here, but it was a
// duplicate of `status_handlers::coin_flip_attack_block_next_turn` which is the
// version dispatch.rs actually wires up. Removed to eliminate the dead/dup copy.

/// Coin-flip: flip a coin; on **TAILS**, the acting player's own active cannot
/// attack next turn. (Self-inflicted attack-block — used by attacks like
/// "Hyper Beam"-style risk attacks.)
pub fn coin_flip_self_cant_attack_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let heads = state.rng.gen_bool(0.5);
    state.coin_flip_log.push(if heads {
        "🪙 Heads! Self can attack next turn".to_string()
    } else {
        "🪙 Tails! Self cannot attack next turn".to_string()
    });
    if !heads {
        let p = ctx.acting_player;
        if let Some(slot) = state.players[p].active.as_mut() {
            slot.cant_attack_next_turn_incoming = true;
        }
    }
}

/// This Pokémon cannot attack during the acting player's next turn.
pub fn self_cant_attack_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.cant_attack_next_turn_incoming = true;
    }
}

/// This Pokémon cannot use a specific attack next turn.
/// Simplified to block all attacks (mirrors the Python behaviour).
pub fn self_cant_use_specific_attack(state: &mut GameState, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.cant_attack_next_turn_incoming = true;
    }
}

/// Grant the acting player's active a self-attack buff for its next turn.
pub fn self_attack_buff_next_turn(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.attack_bonus_next_turn_self_incoming = amount;
    }
}

/// Coin-flip: on heads, prevent all damage to the source Pokémon next turn.
pub fn prevent_damage_next_turn(state: &mut GameState, ctx: &EffectContext) {
    if state.rng.gen_bool(0.5) {
        let p = ctx.acting_player;
        if let Some(slot) = state.players[p].active.as_mut() {
            slot.prevent_damage_next_turn_incoming = true;
        }
    }
}

/// Source Pokémon takes –amount damage from attacks on the opponent's next turn.
pub fn take_less_damage_next_turn(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.incoming_damage_reduction_incoming = amount;
    }
}

/// The attacking player's active takes +amount MORE damage next turn (negative reduction).
pub fn take_more_damage_next_turn(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.incoming_damage_reduction_incoming = -(amount);
    }
}

/// Defending Pokémon's attacks do –amount damage during the opponent's next turn.
pub fn defender_attacks_do_less_damage(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    if let Some(slot) = state.players[opp].active.as_mut() {
        slot.attack_bonus_next_turn_self_incoming = -(amount);
    }
}

/// Simplified stand-in for next_turn_all_damage_reduction (damage pipeline handles the real check).
/// Sets incoming_damage_reduction on the source Pokémon.
pub fn next_turn_all_damage_reduction(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.incoming_damage_reduction_incoming = amount;
    }
}

/// Same as next_turn_all_damage_reduction but restricted to Metal-type attackers.
/// The damage pipeline should check the attacker type; we store the same field as a hint.
pub fn next_turn_metal_damage_reduction(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    // The damage pipeline checks the attacker's type; storing the reduction unconditionally
    // here is a simplification that matches the Python behaviour for now.
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.incoming_damage_reduction_incoming = amount;
    }
}

// ------------------------------------------------------------------ //
// Misc: player-level flags
// ------------------------------------------------------------------ //

/// Block the opponent from playing Supporter cards on their next turn.
pub fn opponent_no_supporter_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    state.players[opp].cant_play_supporter_incoming = true;
}

/// Block the opponent from playing Item cards on their next turn.
pub fn opponent_no_items_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    state.players[opp].cant_play_items_incoming = true;
}

/// Block the opponent from taking Energy from the Energy Zone on their next turn.
pub fn opponent_no_energy_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    state.players[opp].cant_attach_energy_incoming = true;
}

/// Raise the opponent's retreat / attack costs by amount next turn.
/// Simplified: sets cant_retreat_next_turn on the opponent's active (mirrors Python stub).
pub fn opponent_cost_increase_next_turn(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    if let Some(slot) = state.players[opp].active.as_mut() {
        slot.cant_retreat_next_turn_incoming = true;
    }
}

// ------------------------------------------------------------------ //
// Misc: trainer / supporter damage buffs
// ------------------------------------------------------------------ //

/// Giovanni / Blaine: buff this turn's attack damage by `amount`.
/// If `names` is non-empty, the buff only applies when the attacker matches one of those names.
pub fn supporter_damage_aura(
    state: &mut GameState,
    amount: i8,
    names: &[String],
    ctx: &EffectContext,
) {
    let p = ctx.acting_player;
    let player = &mut state.players[p];
    if amount > player.attack_damage_bonus {
        player.attack_damage_bonus = amount;
    }
    if !names.is_empty() {
        player.attack_damage_bonus_names = names.iter().cloned().collect();
    }
}

/// Variant of supporter_damage_aura restricted to EX Pokémon targets.
/// The damage pipeline reads attack_damage_bonus_names to filter; this sets the amount.
pub fn supporter_damage_aura_vs_ex(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    let p = ctx.acting_player;
    let player = &mut state.players[p];
    if amount > player.attack_damage_bonus {
        player.attack_damage_bonus = amount;
    }
    // The name filter "ex" acts as a sentinel; the damage pipeline must handle it.
    player.attack_damage_bonus_names = smallvec::smallvec!["ex".to_string()];
}

/// X Speed: reduce the retreat cost of the acting player's Active Pokémon by `amount` this turn.
pub fn reduce_retreat_cost(state: &mut GameState, amount: i8, ctx: &EffectContext) {
    state.players[ctx.acting_player].retreat_cost_modifier -= amount;
}

// ------------------------------------------------------------------ //
// Copy attack — complex, no-op for now
// ------------------------------------------------------------------ //

/// Mew ex (Genome Hacking) / Ditto / Mewtwo copy semantics: copy the opponent's
/// **first** attack (`attacks[0]`) and execute it as if our active had used it,
/// **ignoring our own energy cost** (this is the copy semantic — the cost was
/// already paid for the copy effect itself).
///
/// TODO (partial implementation):
/// - This does NOT execute the copied attack's effect tokens / handler string
///   (so e.g. status applies, coin flips, splash damage from the copied attack
///   are dropped). Full execution would require recursing through
///   `engine::attack::execute_attack` with a temporary attack-index swap, which
///   is non-trivial because the engine reads the attack list off the attacker's
///   own card. Real Mew ex / Ditto support needs that wiring.
/// - This DOES apply: base damage, weakness vs the defender, supporter aura
///   (Giovanni etc.), defender's incoming damage reduction, and prevent_damage.
pub fn copy_opponent_attack(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let p = ctx.acting_player;
    let opp = 1 - p;

    // Identify attacker and defender cards.
    let attacker_card_idx = match state.players[p].active.as_ref() {
        Some(s) => s.card_idx,
        None => return,
    };
    let defender_card_idx = match state.players[opp].active.as_ref() {
        Some(s) => s.card_idx,
        None => return,
    };

    let attacker_card = db.get_by_idx(attacker_card_idx).clone();
    let opp_card = db.get_by_idx(defender_card_idx).clone();

    // Per spec: copy the opponent's *first* attack.
    let copied = match opp_card.attacks.first() {
        Some(a) => a.clone(),
        None => return,
    };

    let base_damage = copied.damage;
    if base_damage == 0 {
        // Even a 0-damage copied attack could carry effects, but we don't apply
        // those yet (see TODO above). Bail out so we don't no-op silently.
        state.coin_flip_log.push(format!(
            "🪿 Copy: opponent's first attack '{}' has 0 base damage; effect tokens not yet supported (TODO)",
            copied.name
        ));
        return;
    }

    let mut damage = base_damage;

    // Apply acting player's damage bonus aura (e.g. Giovanni).
    damage += state.players[p].attack_damage_bonus as i16;

    // Weakness: does the attacker's type match the defender's weakness?
    if attacker_card.element.is_some()
        && opp_card.weakness == attacker_card.element
    {
        damage += crate::constants::WEAKNESS_BONUS;
    }

    // Defender's incoming damage reduction (Giant Cape, Rocky Helmet reduction, etc.).
    let reduction = state.players[opp].active
        .as_ref()
        .map(|s| s.incoming_damage_reduction as i16)
        .unwrap_or(0);
    damage = (damage - reduction).max(0);

    // Check prevent_damage flag.
    if state.players[opp].active.as_ref().map(|s| s.prevent_damage_next_turn).unwrap_or(false) {
        state.coin_flip_log.push(format!(
            "🪿 Copy: '{}' for {}dmg — prevented by defender's prevent_damage_next_turn",
            copied.name, damage
        ));
        return;
    }

    // Apply damage.
    if let Some(slot) = state.players[opp].active.as_mut() {
        slot.current_hp = (slot.current_hp - damage).max(0);
    }
    state.coin_flip_log.push(format!(
        "🪿 Copy: used opponent's '{}' for {}dmg (effect tokens not applied — TODO)",
        copied.name, damage
    ));
}

// ------------------------------------------------------------------ //
// Item-card effects
// ------------------------------------------------------------------ //

/// Full Heal: cure all special status conditions on the acting player's active.
pub fn full_heal(state: &mut GameState, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.status = 0;
    }
}

/// Potion: heal `amount` damage from the acting player's active Pokémon.
pub fn potion_heal(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.current_hp = (slot.current_hp + amount).min(slot.max_hp);
    }
}

/// Pokéball search: put a random Basic Pokémon from the deck into the hand.
pub fn pokeball_search(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let p = ctx.acting_player;
    let basic_indices: Vec<usize> = state.players[p]
        .deck
        .iter()
        .enumerate()
        .filter(|(_, &idx)| {
            let card = db.get_by_idx(idx);
            card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic)
        })
        .map(|(i, _)| i)
        .collect();

    if basic_indices.is_empty() {
        return;
    }

    let chosen_pos = basic_indices[state.rng.gen_range(0..basic_indices.len())];
    let card_idx = state.players[p].deck.remove(chosen_pos);
    state.players[p].hand.push(card_idx);
}

/// Big Malasada: heal 20 damage and cure all status conditions on the active Pokémon.
pub fn big_malasada(state: &mut GameState, ctx: &EffectContext) {
    let p = ctx.acting_player;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.current_hp = (slot.current_hp + 20).min(slot.max_hp);
        slot.status = 0;
    }
}

/// Mythical Slab: look at the top card of your deck; if it's a Psychic Pokémon, add it to hand.
/// Simplified: put it in hand if it's a Psychic Pokémon; otherwise leave it on top.
///
/// NOTE: deck Vec uses `pop()` for draw, so the **top of deck = last element**.
pub fn mythical_slab(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let p = ctx.acting_player;
    let top_idx = match state.players[p].deck.last().copied() {
        Some(idx) => idx,
        None => return,
    };
    let card = db.get_by_idx(top_idx);
    if card.kind == CardKind::Pokemon
        && card.element == Some(crate::types::Element::Psychic)
    {
        // Pop the last element (top of deck) and put it into hand.
        let drawn = state.players[p].deck.pop().expect("deck non-empty (just checked)");
        state.players[p].hand.push(drawn);
    }
    // Otherwise leave the card on top of the deck.
}

/// Beast Wall Protection: passive — handled structurally by the damage pipeline.
/// No state mutation needed; this is a no-op registration marker.
pub fn beast_wall_protection(state: &mut GameState, ctx: &EffectContext) {
    // PASSIVE: handled structurally by the damage pipeline.
    let _ = (state, ctx);
}

/// Rare Candy Evolve: evolve a Basic Pokémon directly to Stage 2.
/// The acting engine already validates the evolution path; this handler just performs the swap.
///
/// ctx.extra encoding:
///   "evo_card_idx"  — u16 card index of the Stage 2 card (stored as i32)
///   "evo_hand_pos"  — index into the acting player's hand
///   "target_slot"   — encoded target slot: player*10 + (bench+1), 0 = active
pub fn rare_candy_evolve(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let evo_card_idx = match ctx.extra.get("evo_card_idx") {
        Some(&v) if v >= 0 => v as u16,
        _ => return,
    };

    // Resolve target slot from extra; default to acting player's active.
    let target = if let Some(&raw) = ctx.extra.get("target_slot") {
        let player = (raw / 10) as usize;
        let slot_enc = raw % 10;
        if slot_enc == 0 {
            SlotRef::active(player)
        } else {
            SlotRef::bench(player, (slot_enc - 1) as usize)
        }
    } else {
        SlotRef::active(ctx.acting_player)
    };

    let new_hp = db.get_by_idx(evo_card_idx).hp;

    if let Some(slot) = get_slot_mut(state, target) {
        let damage_taken = slot.max_hp - slot.current_hp;
        slot.card_idx = evo_card_idx;
        slot.max_hp = new_hp;
        slot.current_hp = (new_hp - damage_taken).max(0);
        slot.status = 0;
        slot.evolved_this_turn = true;
        slot.ability_used_this_turn = false;
    }

    // Remove Stage 2 card from hand.
    if let Some(&hand_pos) = ctx.extra.get("evo_hand_pos") {
        let p = ctx.acting_player;
        let hand_pos = hand_pos as usize;
        if hand_pos < state.players[p].hand.len()
            && state.players[p].hand[hand_pos] == evo_card_idx
        {
            state.players[p].hand.remove(hand_pos);
        }
    }
}

/// HP Bonus (Giant Cape): increase the target Pokémon's max_hp and current_hp by `amount`.
/// Called when the tool is attached.
///
/// ctx.extra["target_slot"] encodes the slot: player*10 + (bench+1), 0 = active.
/// Defaults to acting player's active if not present.
pub fn hp_bonus(state: &mut GameState, amount: i16, ctx: &EffectContext) {
    let target = if let Some(&raw) = ctx.extra.get("target_slot") {
        let player = (raw / 10) as usize;
        let slot_enc = raw % 10;
        if slot_enc == 0 {
            SlotRef::active(player)
        } else {
            SlotRef::bench(player, (slot_enc - 1) as usize)
        }
    } else {
        SlotRef::active(ctx.acting_player)
    };
    if let Some(slot) = get_slot_mut(state, target) {
        slot.max_hp += amount;
        slot.current_hp += amount;
    }
}

// ------------------------------------------------------------------ //
// Passive tool / ability markers — no-op; handled by the damage pipeline
// ------------------------------------------------------------------ //

/// Passive damage reduction marker (e.g. Rocky Helmet style defend-side).
/// Actual reduction is applied in the damage pipeline; this is a no-op registration.
pub fn passive_damage_reduction(state: &mut GameState, ctx: &EffectContext) {
    let _ = (state, ctx);
}

/// Passive retaliate marker (Rocky Helmet).
/// Actual retaliation is applied in attack.rs; this is a no-op registration.
pub fn passive_retaliate(state: &mut GameState, ctx: &EffectContext) {
    let _ = (state, ctx);
}

/// Passive block supporters marker (Hex Maniac style).
///
/// PTCGP rule: while this Pokémon is the opponent-facing active, the OPPONENT
/// cannot play Supporter cards. Ideally this is a CONTINUOUS check evaluated in
/// `legal_actions`/`play_card` against whether the opposing active still has
/// this passive — gap: the engine currently has no continuous-passive registry.
///
/// As a partial implementation, whenever this passive handler is dispatched we
/// set the per-turn `cant_play_supporter_this_turn` flag (so it bites for the
/// current turn) plus the `_incoming` companion (so the next start_turn promotes
/// it). This still leaks: if the active changes mid-turn, the opponent will
/// remain blocked for the rest of the turn even though the source is no longer
/// active. TODO: replace with a continuous-passive check in `legal_actions`.
pub fn passive_block_supporters(state: &mut GameState, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    state.players[opp].cant_play_supporter_this_turn = true;
    state.players[opp].cant_play_supporter_incoming = true;
}

/// Passive Ditto impostor marker.
pub fn passive_ditto_impostor(state: &mut GameState, ctx: &EffectContext) {
    let _ = (state, ctx);
}

// ------------------------------------------------------------------ //
// Discard-from-hand helpers
// ------------------------------------------------------------------ //

/// Discard a random Pokémon Tool card from the opponent's hand.
pub fn discard_random_tool_from_hand(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    let tool_indices: Vec<usize> = state.players[opp]
        .hand
        .iter()
        .enumerate()
        .filter(|(_, &idx)| db.get_by_idx(idx).kind == CardKind::Tool)
        .map(|(i, _)| i)
        .collect();

    if tool_indices.is_empty() {
        return;
    }

    let chosen = tool_indices[state.rng.gen_range(0..tool_indices.len())];
    let card = state.players[opp].hand.remove(chosen);
    state.players[opp].discard.push(card);
}

/// Discard a random Item card from the opponent's hand.
pub fn discard_random_item_from_hand(state: &mut GameState, db: &CardDb, ctx: &EffectContext) {
    let opp = 1 - ctx.acting_player;
    let item_indices: Vec<usize> = state.players[opp]
        .hand
        .iter()
        .enumerate()
        .filter(|(_, &idx)| db.get_by_idx(idx).kind == CardKind::Item)
        .map(|(i, _)| i)
        .collect();

    if item_indices.is_empty() {
        return;
    }

    let chosen = item_indices[state.rng.gen_range(0..item_indices.len())];
    let card = state.players[opp].hand.remove(chosen);
    state.players[opp].discard.push(card);
}

/// Discard a random card from the opponent's hand (coin-flip wrapper; flip is handled here).
pub fn discard_random_card_opponent(state: &mut GameState, ctx: &EffectContext) {
    if !state.rng.gen_bool(0.5) {
        return;
    }
    let opp = 1 - ctx.acting_player;
    if state.players[opp].hand.is_empty() {
        return;
    }
    let len = state.players[opp].hand.len();
    let idx = state.rng.gen_range(0..len);
    let card = state.players[opp].hand.remove(idx);
    state.players[opp].discard.push(card);
}

/// Coin-flip: on heads, take a random card from opponent's hand and shuffle it into their deck.
pub fn coin_flip_shuffle_opponent_card(state: &mut GameState, ctx: &EffectContext) {
    if !state.rng.gen_bool(0.5) {
        return;
    }
    let opp = 1 - ctx.acting_player;
    if state.players[opp].hand.is_empty() {
        return;
    }
    let len = state.players[opp].hand.len();
    let idx = state.rng.gen_range(0..len);
    let card = state.players[opp].hand.remove(idx);
    state.players[opp].deck.push(card);
    state.players[opp].deck.shuffle(&mut state.rng);
}

/// Flip `count` coins; for each heads, shuffle a random card from opponent's hand into their deck.
pub fn multi_coin_shuffle_opponent_cards(state: &mut GameState, count: u8, ctx: &EffectContext) {
    let heads: u8 = (0..count).map(|_| state.rng.gen_bool(0.5) as u8).sum();
    if heads == 0 {
        return;
    }
    let opp = 1 - ctx.acting_player;
    for _ in 0..heads {
        if state.players[opp].hand.is_empty() {
            break;
        }
        let len = state.players[opp].hand.len();
        let idx = state.rng.gen_range(0..len);
        let card = state.players[opp].hand.remove(idx);
        state.players[opp].deck.push(card);
    }
    if !state.players[opp].deck.is_empty() {
        state.players[opp].deck.shuffle(&mut state.rng);
    }
}

// ------------------------------------------------------------------ //
// Element-gated energy attachment
// ------------------------------------------------------------------ //

/// Returns true when the acting player's active Pokémon's element matches
/// `required_active_type` (or `required_active_type` is empty).
fn active_matches_type(
    state: &GameState,
    db: &CardDb,
    player: usize,
    required_active_type: &str,
) -> bool {
    if required_active_type.is_empty() {
        return state.players[player].active.is_some();
    }
    let required = match crate::types::Element::from_str(required_active_type) {
        Some(e) => e,
        None => return false,
    };
    let active = match state.players[player].active.as_ref() {
        Some(s) => s,
        None => return false,
    };
    let active_el = db.try_get_by_idx(active.card_idx).and_then(|c| c.element);
    active_el == Some(required)
}

/// Attach 1 energy of `energy_type` from the Energy Zone to the acting
/// player's active Pokémon, gated on the active's element matching
/// `required_active_type`.  Used by ON-EVOLVE triggers (Charmeleon Ignition).
pub fn attach_energy_to_active_typed(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    energy_type: &str,
    required_active_type: &str,
) {
    let p = ctx.acting_player;
    if !active_matches_type(state, db, p, required_active_type) {
        return;
    }
    let element = match crate::types::Element::from_str(energy_type) {
        Some(e) => e,
        None => return,
    };
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.add_energy(element, 1);
    }
}

/// Flame Patch (B1-217): take 1 energy of `energy_type` *from the acting
/// player's energy discard pile* and attach it to the active Pokémon.  No-op
/// when the discard has none, or when the active doesn't match
/// `required_active_type` (preserving the discarded energy untouched in that
/// case so the agent can try again later).
pub fn attach_discarded_energy_to_active(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    energy_type: &str,
    required_active_type: &str,
) {
    let p = ctx.acting_player;
    let element = match crate::types::Element::from_str(energy_type) {
        Some(e) => e,
        None => return,
    };
    // Discard pile must have at least 1 of `element`.
    if state.players[p].energy_discard[element as usize] == 0 {
        return;
    }
    // Active must match the required element gate.
    if !active_matches_type(state, db, p, required_active_type) {
        return;
    }
    state.players[p].energy_discard[element as usize] -= 1;
    if let Some(slot) = state.players[p].active.as_mut() {
        slot.add_energy(element, 1);
    }
}

// ------------------------------------------------------------------ //
// May (B1-223) — random deck/hand Pokémon swap
// ------------------------------------------------------------------ //

/// Supporter May: put `count` random Pokémon from the deck into the hand.
/// For each Pokémon added in this way, shuffle a random Pokémon from the
/// hand back into the deck.
///
/// Selection rules used (random-agent friendly approximation of "choose"):
///   * Pull `count` random Pokémon from deck → hand.
///   * Then for each one pulled, pick a random Pokémon currently in hand
///     (post-pull) and shuffle it back into the deck.  If the hand has
///     fewer Pokémon than were pulled, do as many swaps as possible.
pub fn may_swap_pokemon(
    state: &mut GameState,
    db: &CardDb,
    ctx: &EffectContext,
    count: u8,
) {
    let p = ctx.acting_player;

    // 1. Pull up to `count` random Pokémon from deck → hand.
    let mut pulled: u8 = 0;
    for _ in 0..count {
        let pokemon_in_deck: Vec<usize> = state.players[p].deck.iter().enumerate()
            .filter(|(_, &idx)| db.try_get_by_idx(idx).map(|c| c.kind == CardKind::Pokemon).unwrap_or(false))
            .map(|(i, _)| i)
            .collect();
        if pokemon_in_deck.is_empty() {
            break;
        }
        let chosen = pokemon_in_deck[state.rng.gen_range(0..pokemon_in_deck.len())];
        let card_idx = state.players[p].deck.remove(chosen);
        state.players[p].hand.push(card_idx);
        pulled += 1;
    }

    if pulled == 0 {
        return;
    }

    // Reshuffle deck since we removed cards from arbitrary positions.
    state.players[p].deck.shuffle(&mut state.rng);

    // 2. For each Pokémon pulled, pick a random Pokémon in hand → shuffle into deck.
    for _ in 0..pulled {
        let pokemon_in_hand: Vec<usize> = state.players[p].hand.iter().enumerate()
            .filter(|(_, &idx)| db.try_get_by_idx(idx).map(|c| c.kind == CardKind::Pokemon).unwrap_or(false))
            .map(|(i, _)| i)
            .collect();
        if pokemon_in_hand.is_empty() {
            break;
        }
        let chosen = pokemon_in_hand[state.rng.gen_range(0..pokemon_in_hand.len())];
        let card_idx = state.players[p].hand.remove(chosen);
        state.players[p].deck.push(card_idx);
        state.players[p].deck.shuffle(&mut state.rng);
    }
}

// ------------------------------------------------------------------ //
// Unit tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};

    fn make_state() -> GameState {
        let mut state = GameState::new(42);
        // Place a basic Pokémon in each player's active slot.
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state.players[1].active = Some(PokemonSlot::new(0, 100));
        state
    }

    fn make_ctx(acting_player: usize) -> EffectContext {
        EffectContext::new(acting_player)
    }

    // ---- cant_retreat_next_turn ----

    #[test]
    fn test_cant_retreat_sets_flag_on_opponent() {
        let mut state = make_state();
        let ctx = make_ctx(0);

        // Before: flag is false
        assert!(!state.players[1].active.as_ref().unwrap().cant_retreat_next_turn_incoming);

        cant_retreat_next_turn(&mut state, &ctx);

        // After: flag is true on opponent (player 1) — written to _incoming for promotion
        assert!(state.players[1].active.as_ref().unwrap().cant_retreat_next_turn_incoming);
        // Acting player's flag is untouched
        assert!(!state.players[0].active.as_ref().unwrap().cant_retreat_next_turn_incoming);
    }

    #[test]
    fn test_cant_retreat_player1_acting() {
        let mut state = make_state();
        let ctx = make_ctx(1);
        cant_retreat_next_turn(&mut state, &ctx);
        // Player 1 is acting, so player 0 is the opponent
        assert!(state.players[0].active.as_ref().unwrap().cant_retreat_next_turn_incoming);
        assert!(!state.players[1].active.as_ref().unwrap().cant_retreat_next_turn_incoming);
    }

    // ---- full_heal ----

    #[test]
    fn test_full_heal_clears_all_status_bits() {
        let mut state = make_state();
        let ctx = make_ctx(0);

        // Set a non-zero status on the acting player's active
        state.players[0].active.as_mut().unwrap().status = 0b1111_1111;

        full_heal(&mut state, &ctx);

        assert_eq!(state.players[0].active.as_ref().unwrap().status, 0);
        // Opponent's status should be untouched
        assert_eq!(state.players[1].active.as_ref().unwrap().status, 0);
    }

    #[test]
    fn test_full_heal_no_panic_if_no_active() {
        let mut state = GameState::new(1);
        let ctx = make_ctx(0);
        // No active Pokémon — should not panic
        full_heal(&mut state, &ctx);
    }

    // ---- potion_heal ----

    #[test]
    fn test_potion_heal_restores_hp() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        state.players[0].active.as_mut().unwrap().current_hp = 60;

        potion_heal(&mut state, 30, &ctx);

        assert_eq!(state.players[0].active.as_ref().unwrap().current_hp, 90);
    }

    #[test]
    fn test_potion_heal_does_not_exceed_max_hp() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        // Already at max
        potion_heal(&mut state, 50, &ctx);
        assert_eq!(state.players[0].active.as_ref().unwrap().current_hp, 100);
    }

    // ---- self_attack_buff_next_turn ----

    #[test]
    fn test_self_attack_buff_next_turn_sets_field() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        self_attack_buff_next_turn(&mut state, 20, &ctx);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().attack_bonus_next_turn_self_incoming,
            20
        );
    }

    // ---- take_less_damage_next_turn ----

    #[test]
    fn test_take_less_damage_stores_reduction() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        take_less_damage_next_turn(&mut state, 30, &ctx);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().incoming_damage_reduction_incoming,
            30
        );
    }

    // ---- take_more_damage_next_turn ----

    #[test]
    fn test_take_more_damage_stores_negative_reduction() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        take_more_damage_next_turn(&mut state, 30, &ctx);
        assert_eq!(
            state.players[0].active.as_ref().unwrap().incoming_damage_reduction_incoming,
            -30
        );
    }

    // ---- opponent_no_supporter_next_turn ----

    #[test]
    fn test_opponent_no_supporter_sets_flag() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        assert!(!state.players[1].cant_play_supporter_incoming);
        opponent_no_supporter_next_turn(&mut state, &ctx);
        assert!(state.players[1].cant_play_supporter_incoming);
        assert!(!state.players[0].cant_play_supporter_incoming);
    }

    // ---- reduce_retreat_cost ----

    #[test]
    fn test_reduce_retreat_cost_lowers_modifier() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        assert_eq!(state.players[0].retreat_cost_modifier, 0);
        reduce_retreat_cost(&mut state, 1, &ctx);
        assert_eq!(state.players[0].retreat_cost_modifier, -1);
    }

    // ---- big_malasada ----

    #[test]
    fn test_big_malasada_heals_and_cures() {
        let mut state = make_state();
        let ctx = make_ctx(0);
        state.players[0].active.as_mut().unwrap().current_hp = 70;
        state.players[0].active.as_mut().unwrap().status = 0b0000_0011;

        big_malasada(&mut state, &ctx);

        let active = state.players[0].active.as_ref().unwrap();
        assert_eq!(active.current_hp, 90);
        assert_eq!(active.status, 0);
    }

    // ---- hp_bonus ----

    #[test]
    fn test_hp_bonus_increases_max_and_current_hp() {
        let mut state = make_state();
        // Default: no target_slot in extra => acts on acting player's active
        let ctx = make_ctx(0);

        hp_bonus(&mut state, 20, &ctx);

        let active = state.players[0].active.as_ref().unwrap();
        assert_eq!(active.max_hp, 120);
        assert_eq!(active.current_hp, 120);
    }
}
