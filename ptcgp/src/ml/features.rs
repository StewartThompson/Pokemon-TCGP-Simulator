//! State → fixed-size feature vector for the value net.
//!
//! Everything a real player can see, POV-normalised so positions 0..
//! always describe "me" and the later positions describe "opponent". The
//! net therefore doesn't need to learn which player is which — it always
//! predicts "value for me given the state as I see it".
//!
//! # Privacy (imperfect info)
//!
//! The acting player sees:
//! - Their own hand, deck count, discard
//! - Both players' boards (active + bench slots) with HP, energy, status,
//!   tool attachment, card identity
//! - Opponent's hand COUNT (but not identities), deck count, discard pile
//! - Global turn number, points scored, first-player flag, energy available
//!
//! They do NOT see:
//! - Opponent's hand card identities
//! - Opponent's deck order
//!
//! Encoding is version-pinned by [`FEATURE_VERSION`] so a feature-layout
//! change immediately invalidates old checkpoints instead of silently
//! producing garbage predictions.

use crate::card::{Attack, CardDb};
use crate::effects::EffectKind;
use crate::state::{GameState, PokemonSlot};
use crate::types::{CardKind, GamePhase, Stage, StatusEffect};

use super::card_embed::{build_embed_cache, CARD_EMBED_DIM};

/// Bump when the feature layout changes. Old checkpoints with a different
/// `feature_version` in their meta.json will be rejected on load.
pub const FEATURE_VERSION: u32 = 4;

/// Floats stored per board slot. See [`encode_slot_into`] for layout.
///
/// Breakdown (32 floats): card_embed[15] + presence[1] + hp_ratio[1]
/// + energy[8] + status×3 + tool[1] + turns_in_play[1] + evo_in_hand[1]
/// + evolved_this_turn[1]
pub const SLOT_DIM: usize = CARD_EMBED_DIM + 17;

/// 8 board slots: my active, my bench[3], opp active, opp bench[3].
pub const NUM_SLOTS: usize = 8;

/// Global features (turn number, points, hand/deck counts, etc.).
///
/// Breakdown (84 floats): 6 scalar (turn, points×2, first, my-turn, promoting)
/// + 8 energy-one-hot + 7 my-hand-composition + 6 pile sizes +
/// 7 opp-discard-composition + 3 per-turn flags + 3 ban flags + 1 damage-bonus
/// + 8 tactical active-vs-active features (v2)
/// + 11 supporter-category + board-context features (v2)
/// + 15 my-hand-embed-mean (v3)
/// + 9 strategic tempo + type + bench features (v4).
pub const GLOBAL_DIM: usize = 84;

/// Full feature vector size.
pub const FEATURE_DIM: usize = SLOT_DIM * NUM_SLOTS + GLOBAL_DIM;

// ------------------------------------------------------------------ //
// Public API
// ------------------------------------------------------------------ //

/// Encode a game state from `for_player`'s POV into a fixed-size vector.
///
/// The returned vector is always exactly [`FEATURE_DIM`] floats long,
/// so it can be fed directly into a candle `Tensor::from_slice` with a
/// shape of `[1, FEATURE_DIM]`.
pub fn encode(state: &GameState, db: &CardDb, for_player: usize) -> Vec<f32> {
    // Build (or rebuild) the card-embed cache on every call. This is
    // cheap at Wave 2 scale — a few hundred cards × 15 floats. Wave 3 will
    // amortise via a pre-built cache held by the MctsAgent.
    let cache = build_embed_cache(db);
    encode_with_cache(state, db, for_player, &cache)
}

/// Same as [`encode`] but reuses a pre-built card-embed cache. Prefer this
/// in hot paths (self-play, MCTS leaf eval) — the cache is constant for
/// the lifetime of a `CardDb`.
pub fn encode_with_cache(
    state: &GameState,
    db: &CardDb,
    for_player: usize,
    cache: &[[f32; CARD_EMBED_DIM]],
) -> Vec<f32> {
    let mut out = [0.0f32; FEATURE_DIM];
    encode_into(state, db, for_player, cache, &mut out);
    out.to_vec()
}

/// Zero-allocation variant: writes exactly [`FEATURE_DIM`] floats into `out`.
///
/// Prefer this in the MCTS hot path — avoids the heap allocation that
/// `encode_with_cache` pays on every NN leaf evaluation.
///
/// Zeroes `out` at the start so that empty slots and absent energy produce
/// clean zeros even when `out` is a reused thread-local buffer.
pub fn encode_into(
    state: &GameState,
    db: &CardDb,
    for_player: usize,
    cache: &[[f32; CARD_EMBED_DIM]],
    out: &mut [f32; FEATURE_DIM],
) {
    // Always zero first: (a) empty slots write nothing, (b) energy one-hot
    // is all-zero when `energy_available` is None, (c) thread-local reuse
    // must not bleed old values into a new call.
    *out = [0.0f32; FEATURE_DIM];

    debug_assert!(for_player < 2);
    let me = for_player;
    let opp = 1 - me;
    let mut cur = 0usize;
    let my_hand = &state.players[me].hand[..];

    encode_slot_into(out, &mut cur, state.players[me].active.as_ref(), cache, db, Some(my_hand));
    for j in 0..3 {
        encode_slot_into(out, &mut cur, state.players[me].bench[j].as_ref(), cache, db, Some(my_hand));
    }
    encode_slot_into(out, &mut cur, state.players[opp].active.as_ref(), cache, db, None);
    for j in 0..3 {
        encode_slot_into(out, &mut cur, state.players[opp].bench[j].as_ref(), cache, db, None);
    }
    encode_global_into(out, &mut cur, state, db, me, cache);

    debug_assert_eq!(cur, FEATURE_DIM, "encode_into wrote {}, expected {}", cur, FEATURE_DIM);
}

// ------------------------------------------------------------------ //
// Slot encoding
// ------------------------------------------------------------------ //

// ------------------------------------------------------------------ //
// Cursor-based slot encoding (zero-allocation hot path)
// ------------------------------------------------------------------ //

/// Cursor-based slot encoder. Writes exactly [`SLOT_DIM`] floats starting at
/// `out[*cur]` and advances `*cur` by [`SLOT_DIM`].
///
/// `my_hand` is `Some(slice)` for the acting player's slots (enables
/// `evo_in_hand` and `evolved_this_turn` signals) and `None` for the
/// opponent's slots where hand is hidden.
///
/// Assumes `out` is already zeroed for the empty-slot case (see
/// [`encode_into`] which zeroes the full buffer before calling this).
fn encode_slot_into(
    out: &mut [f32; FEATURE_DIM],
    cur: &mut usize,
    slot: Option<&PokemonSlot>,
    cache: &[[f32; CARD_EMBED_DIM]],
    db: &CardDb,
    my_hand: Option<&[u16]>,
) {
    match slot {
        None => {
            // Buffer is already zeroed; just advance the cursor.
            *cur += SLOT_DIM;
        }
        Some(s) => {
            // Card embedding.
            let embed = cache
                .get(s.card_idx as usize)
                .copied()
                .unwrap_or([0.0; CARD_EMBED_DIM]);
            out[*cur..*cur + CARD_EMBED_DIM].copy_from_slice(&embed);
            *cur += CARD_EMBED_DIM;

            // Presence flag.
            out[*cur] = 1.0;
            *cur += 1;

            // HP ratio.
            out[*cur] = if s.max_hp > 0 {
                (s.current_hp as f32 / s.max_hp as f32).clamp(0.0, 1.0)
            } else {
                0.0
            };
            *cur += 1;

            // Energy per element (8 floats, normalised by 5).
            for el in 0..8 {
                out[*cur] = s.energy[el] as f32 / 5.0;
                *cur += 1;
            }

            // Status flags.
            out[*cur] = s.has_status(StatusEffect::Poisoned) as u8 as f32;
            *cur += 1;
            out[*cur] = s.has_status(StatusEffect::Burned) as u8 as f32;
            *cur += 1;
            out[*cur] = (s.has_status(StatusEffect::Paralyzed)
                || s.has_status(StatusEffect::Asleep)
                || s.has_status(StatusEffect::Confused)) as u8 as f32;
            *cur += 1;

            // Tool attached.
            out[*cur] = if s.tool_idx.is_some() { 1.0 } else { 0.0 };
            *cur += 1;

            // turns_in_play: how long this pokemon has been in play.
            // Normalized by 20 (games rarely last longer than ~20 turns).
            out[*cur] = (s.turns_in_play as f32 / 20.0).min(1.0);
            *cur += 1;

            // evo_in_hand: how many cards in my hand can evolve this pokemon.
            // Only meaningful for my own slots (opp hand is hidden).
            // Normalized by 2 (you can have at most 2 copies of any card).
            out[*cur] = if let Some(hand) = my_hand {
                let pokemon_name = &db.get_by_idx(s.card_idx).name;
                let count = hand.iter().filter(|&&ci| {
                    db.get_by_idx(ci)
                        .evolves_from
                        .as_deref()
                        .map_or(false, |from| from == pokemon_name)
                }).count();
                (count as f32 / 2.0).min(1.0)
            } else {
                0.0
            };
            *cur += 1;

            // evolved_this_turn: did this pokemon evolve this turn?
            // Signals "freshly powered-up" state — ability triggers, momentum.
            out[*cur] = s.evolved_this_turn as u8 as f32;
            *cur += 1;
            // Total: CARD_EMBED_DIM + 1+1+8+1+1+1+1+1+1+1 = CARD_EMBED_DIM + 17 = SLOT_DIM ✓
        }
    }
}

// ------------------------------------------------------------------ //
// Global encoding (cursor-based, zero-allocation)
// ------------------------------------------------------------------ //

/// Writes exactly [`GLOBAL_DIM`]
/// floats starting at `out[*cur]` and advances `*cur` by [`GLOBAL_DIM`].
///
/// Assumes `out` is already zeroed (energy one-hot and absent flags are
/// left as zeros rather than explicitly written).
fn encode_global_into(
    out: &mut [f32; FEATURE_DIM],
    cur: &mut usize,
    state: &GameState,
    db: &CardDb,
    me: usize,
    embed_cache: &[[f32; CARD_EMBED_DIM]],
) {
    let start = *cur;
    let opp = 1 - me;
    let player = &state.players[me];
    let opp_player = &state.players[opp];

    // 6 scalar globals.
    out[*cur] = (state.turn_number.max(0) as f32 / 30.0).min(1.5);
    *cur += 1;
    out[*cur] = player.points as f32 / 3.0;
    *cur += 1;
    out[*cur] = opp_player.points as f32 / 3.0;
    *cur += 1;
    out[*cur] = if state.first_player == me { 1.0 } else { 0.0 };
    *cur += 1;
    out[*cur] = if state.current_player == me { 1.0 } else { 0.0 };
    *cur += 1;
    out[*cur] = if state.phase == GamePhase::AwaitingBenchPromotion { 1.0 } else { 0.0 };
    *cur += 1;

    // Energy one-hot (8 floats). Buffer is pre-zeroed; only set the live slot.
    if let Some(el) = player.energy_available {
        out[*cur + el.idx()] = 1.0;
    }
    *cur += 8;

    // My hand composition (7 floats).
    let hand_counts = hand_composition(&player.hand, db);
    out[*cur..*cur + 7].copy_from_slice(&hand_counts);
    *cur += 7;

    // Pile sizes (6 floats).
    out[*cur] = player.hand.len() as f32 / 20.0;
    *cur += 1;
    out[*cur] = player.deck.len() as f32 / 20.0;
    *cur += 1;
    out[*cur] = player.discard.len() as f32 / 20.0;
    *cur += 1;
    out[*cur] = opp_player.hand.len() as f32 / 20.0;
    *cur += 1;
    out[*cur] = opp_player.deck.len() as f32 / 20.0;
    *cur += 1;
    out[*cur] = opp_player.discard.len() as f32 / 20.0;
    *cur += 1;

    // Opponent discard composition (7 floats).
    let opp_discard_counts = hand_composition(&opp_player.discard, db);
    out[*cur..*cur + 7].copy_from_slice(&opp_discard_counts);
    *cur += 7;

    // Per-turn flags (3 floats).
    out[*cur] = if player.has_attached_energy { 1.0 } else { 0.0 };
    *cur += 1;
    out[*cur] = if player.has_played_supporter { 1.0 } else { 0.0 };
    *cur += 1;
    out[*cur] = if player.has_retreated { 1.0 } else { 0.0 };
    *cur += 1;

    // Ban flags (3 floats).
    out[*cur] = if player.cant_play_supporter_this_turn { 1.0 } else { 0.0 };
    *cur += 1;
    out[*cur] = if player.cant_play_items_this_turn { 1.0 } else { 0.0 };
    *cur += 1;
    out[*cur] = if player.cant_attach_energy_this_turn { 1.0 } else { 0.0 };
    *cur += 1;

    // Damage bonus (1 float).
    out[*cur] = player.attack_damage_bonus as f32 / 3.0;
    *cur += 1;

    // Tactical features (8 floats).
    let tactical = tactical_features(state, db, me);
    out[*cur..*cur + 8].copy_from_slice(&tactical);
    *cur += 8;

    // Supporter features (11 floats).
    let supporter = supporter_features(state, db, me);
    out[*cur..*cur + 11].copy_from_slice(&supporter);
    *cur += 11;

    // Hand embed mean (15 floats, v3).
    // Mean of card_embed over all cards in my hand — richer than composition
    // counts because it captures actual card attributes (HP, element, damage).
    // If hand is empty, leaves these as zeros (buffer pre-zeroed by encode_into).
    let hand = &player.hand;
    if !hand.is_empty() {
        let mut mean = [0.0f32; CARD_EMBED_DIM];
        for &ci in hand.iter() {
            let emb = embed_cache.get(ci as usize).copied().unwrap_or([0.0; CARD_EMBED_DIM]);
            for k in 0..CARD_EMBED_DIM {
                mean[k] += emb[k];
            }
        }
        let n = hand.len() as f32;
        for k in 0..CARD_EMBED_DIM {
            out[*cur + k] = mean[k] / n;
        }
    }
    *cur += CARD_EMBED_DIM; // CARD_EMBED_DIM = 15

    // Strategic tempo + type + bench features (9 floats, v4).
    let strategic = strategic_features_v4(state, db, me);
    out[*cur..*cur + 9].copy_from_slice(&strategic);
    *cur += 9;

    debug_assert_eq!(
        *cur - start,
        GLOBAL_DIM,
        "global dim mismatch: wrote {}, expected {}",
        *cur - start,
        GLOBAL_DIM,
    );
}

// ------------------------------------------------------------------ //
// Tactical active-vs-active features (v2)
// ------------------------------------------------------------------ //

/// Compute 8 tactical floats describing the active-vs-active matchup.
///
/// Layout:
/// ```text
///   [0]  prize_lead              (me.points − opp.points) / 3.0
///   [1]  my_deficit_cheapest     energy still needed for cheapest attack / 4.0
///   [2]  my_deficit_best         energy still needed for best-damage attack / 4.0
///   [3]  my_max_damage_now       max damage I can deal with current energy / 200.0
///   [4]  opp_max_damage_now      max damage opp can deal (their cur. energy) / 200.0
///   [5]  i_can_ko_opp            1.0 if my_max × weakness ≥ opp.current_hp
///   [6]  opp_can_ko_me           1.0 if opp_max × weakness ≥ my.current_hp
///   [7]  my_attacks_ready        count of attacks I can use right now / 2.0
/// ```
fn tactical_features(state: &GameState, db: &CardDb, me: usize) -> [f32; 8] {
    let opp = 1 - me;
    let my_active = state.players[me].active.as_ref();
    let opp_active = state.players[opp].active.as_ref();

    // Prize lead.
    let prize_lead = (state.players[me].points as f32 - state.players[opp].points as f32) / 3.0;

    // If either active is absent, only prize_lead is meaningful.
    let (my_slot, opp_slot) = match (my_active, opp_active) {
        (Some(m), Some(o)) => (m, o),
        _ => return [prize_lead, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    };

    let my_card = db.get_by_idx(my_slot.card_idx);
    let opp_card = db.get_by_idx(opp_slot.card_idx);

    // --- My attack readiness ---
    let (my_deficit_cheapest, my_deficit_best, my_max_now, my_ready_count) =
        attack_readiness(my_slot, &my_card.attacks);

    // --- Opp attack readiness (from their current energy) ---
    let (_, _, opp_max_now, _) = attack_readiness(opp_slot, &opp_card.attacks);

    // --- KO threat: can I KO opp this turn? ---
    let my_weakness_mult = if opp_card.weakness == my_card.element { 2 } else { 1 };
    let i_can_ko_opp = (my_max_now * my_weakness_mult as i16) >= opp_slot.current_hp;

    // --- KO threat: can opp KO me this turn? ---
    let opp_weakness_mult = if my_card.weakness == opp_card.element { 2 } else { 1 };
    let opp_can_ko_me = (opp_max_now * opp_weakness_mult as i16) >= my_slot.current_hp;

    [
        prize_lead,
        (my_deficit_cheapest as f32 / 4.0).min(1.0),
        (my_deficit_best as f32 / 4.0).min(1.0),
        my_max_now as f32 / 200.0,
        opp_max_now as f32 / 200.0,
        i_can_ko_opp as u8 as f32,
        opp_can_ko_me as u8 as f32,
        (my_ready_count as f32 / 2.0).min(1.0),
    ]
}

/// Returns `(deficit_cheapest, deficit_best, max_damage_ready, ready_count)` for
/// a slot's attack list given its current energy.
///
/// - `deficit_cheapest`: extra energy needed for the lowest-cost attack.
/// - `deficit_best`: extra energy needed for the highest-damage attack.
/// - `max_damage_ready`: max base damage among attacks we can already afford.
/// - `ready_count`: how many attacks we can afford right now.
fn attack_readiness(slot: &PokemonSlot, attacks: &[Attack]) -> (u32, u32, i16, usize) {
    if attacks.is_empty() {
        return (0, 0, 0, 0);
    }

    let mut deficit_cheapest = u32::MAX;
    let mut deficit_best = 0u32;
    let mut max_damage_ready: i16 = 0;
    let mut ready_count = 0usize;
    let mut best_dmg_overall: i16 = 0;

    for atk in attacks {
        let d = energy_deficit(slot, atk);
        // Track cheapest-to-use attack (fewest energy needed).
        if d < deficit_cheapest {
            deficit_cheapest = d;
        }
        // Track best-damage attack regardless of cost.
        if atk.damage > best_dmg_overall {
            best_dmg_overall = atk.damage;
            deficit_best = d;
        }
        if d == 0 {
            ready_count += 1;
            if atk.damage > max_damage_ready {
                max_damage_ready = atk.damage;
            }
        }
    }

    if deficit_cheapest == u32::MAX {
        deficit_cheapest = 0;
    }

    (deficit_cheapest, deficit_best, max_damage_ready, ready_count)
}

/// How many more energy tokens are needed to afford `atk` given `slot`'s
/// current attached energy. Returns 0 if the attack can already be used.
fn energy_deficit(slot: &PokemonSlot, atk: &Attack) -> u32 {
    let mut avail = slot.energy; // [u8; 8]
    let mut colorless_needed: u32 = 0;
    let mut typed_deficit: u32 = 0;

    for &sym in &atk.cost {
        match sym.to_element() {
            Some(el) => {
                let idx = el.idx();
                if avail[idx] > 0 {
                    avail[idx] -= 1;
                } else {
                    typed_deficit += 1;
                }
            }
            None => {
                // Colorless — any energy satisfies this.
                colorless_needed += 1;
            }
        }
    }

    // Use any remaining energy to cover colorless requirements.
    let total_remaining: u32 = avail.iter().map(|&x| x as u32).sum();
    let colorless_deficit = colorless_needed.saturating_sub(total_remaining);

    typed_deficit + colorless_deficit
}

// ------------------------------------------------------------------ //
// Strategic tempo + type + bench features (v4)
// ------------------------------------------------------------------ //

/// Compute 9 floats covering opponent tempo, type matchup, and bench threats.
///
/// Layout:
/// ```text
///   [0]  opp_deficit_cheapest    energy opp needs for cheapest attack / 4.0
///   [1]  opp_attacks_ready       count of opp attacks usable now / 2.0
///   [2]  i_am_weak_to_opp        1.0 if my active is weak to opp's element
///   [3]  opp_is_weak_to_me       1.0 if opp active is weak to my element
///   [4]  my_bench_max_damage     max damage from my best powered bench pokemon / 200.0
///   [5]  opp_bench_max_damage    max damage from opp's best powered bench pokemon / 200.0
///   [6]  opp_bench_any_ready     1.0 if opp has any bench pokemon that can attack now
///   [7]  i_can_ko_opp_next_turn  1.0 if one more energy would let me KO opp active
///   [8]  opp_can_ko_me_next_turn 1.0 if one more energy would let opp KO my active
/// ```
fn strategic_features_v4(state: &GameState, db: &CardDb, me: usize) -> [f32; 9] {
    let opp = 1 - me;
    let my_active = state.players[me].active.as_ref();
    let opp_active = state.players[opp].active.as_ref();

    // --- Bench threats (independent of whether actives are present) ---
    let my_bench_max_damage = state.players[me].bench.iter()
        .filter_map(|s| s.as_ref())
        .map(|slot| {
            let card = db.get_by_idx(slot.card_idx);
            let (_, _, max_now, _) = attack_readiness(slot, &card.attacks);
            max_now
        })
        .max()
        .unwrap_or(0);

    let opp_bench_max_damage = state.players[opp].bench.iter()
        .filter_map(|s| s.as_ref())
        .map(|slot| {
            let card = db.get_by_idx(slot.card_idx);
            let (_, _, max_now, _) = attack_readiness(slot, &card.attacks);
            max_now
        })
        .max()
        .unwrap_or(0);

    let opp_bench_any_ready = opp_bench_max_damage > 0;

    // If either active is absent, return what we have so far with zeros for active-dependent features.
    let (my_slot, opp_slot) = match (my_active, opp_active) {
        (Some(m), Some(o)) => (m, o),
        _ => return [
            0.0, 0.0, 0.0, 0.0,
            my_bench_max_damage as f32 / 200.0,
            opp_bench_max_damage as f32 / 200.0,
            opp_bench_any_ready as u8 as f32,
            0.0, 0.0,
        ],
    };

    let my_card = db.get_by_idx(my_slot.card_idx);
    let opp_card = db.get_by_idx(opp_slot.card_idx);

    // --- Opponent attack tempo ---
    let (opp_deficit_cheapest, _, _, opp_ready_count) =
        attack_readiness(opp_slot, &opp_card.attacks);

    // --- Type weakness flags ---
    let i_am_weak_to_opp = my_card.weakness == opp_card.element;
    let opp_is_weak_to_me = opp_card.weakness == my_card.element;

    // --- Next-turn KO threats (deficit == 1 for best-damage attack) ---
    // "Could I KO them if I had exactly 1 more energy right now?"
    let my_weakness_mult = if opp_is_weak_to_me { 2i16 } else { 1i16 };
    let i_can_ko_next_turn = my_card.attacks.iter().any(|atk| {
        energy_deficit(my_slot, atk) == 1
            && (atk.damage * my_weakness_mult) >= opp_slot.current_hp
    });

    let opp_weakness_mult = if i_am_weak_to_opp { 2i16 } else { 1i16 };
    let opp_can_ko_next_turn = opp_card.attacks.iter().any(|atk| {
        energy_deficit(opp_slot, atk) == 1
            && (atk.damage * opp_weakness_mult) >= my_slot.current_hp
    });

    [
        (opp_deficit_cheapest as f32 / 4.0).min(1.0),
        (opp_ready_count as f32 / 2.0).min(1.0),
        i_am_weak_to_opp as u8 as f32,
        opp_is_weak_to_me as u8 as f32,
        my_bench_max_damage as f32 / 200.0,
        opp_bench_max_damage as f32 / 200.0,
        opp_bench_any_ready as u8 as f32,
        i_can_ko_next_turn as u8 as f32,
        opp_can_ko_next_turn as u8 as f32,
    ]
}

// ------------------------------------------------------------------ //
// Supporter-category + board-context features (v2)
// ------------------------------------------------------------------ //

/// Compute 11 floats covering supporter-type availability and contextual
/// board signals that make each supporter type more or less valuable.
///
/// Layout:
/// ```text
///   [0]  has_pivot           pivot supporter in hand (Sabrina/Leaf/Cyrus/…)
///   [1]  has_energy_accel    energy-acceleration supporter in hand (Dawn/Misty/Brock/…)
///   [2]  has_damage_mod      damage-modifier supporter in hand (Giovanni/Red/Blue/…)
///   [3]  has_healing         healing supporter in hand (Erika/PCL/Acerola/…)
///   [4]  has_disruption      disruption supporter in hand (Mars/Iono/…)
///   [5]  has_draw            draw/cycle supporter in hand (Prof Research/Pokéfan/…)
///   [6]  damage_mod_ko       damage_mod in hand AND +10 damage would KO opp active
///   [7]  pivot_useful        pivot in hand AND opp actually has bench pokemon
///   [8]  healing_useful      healing in hand AND at least one own pokemon < 66% HP
///   [9]  opp_bench_any_energy  opp has energy on any bench slot (Sabrina value signal)
///  [10]  my_bench_any_ready  my bench has a pokemon that can attack right now
/// ```
fn supporter_features(state: &GameState, db: &CardDb, me: usize) -> [f32; 11] {
    let opp = 1 - me;
    let player = &state.players[me];
    let opp_player = &state.players[opp];

    // --- Scan hand for supporter categories ---
    let mut has_pivot = false;
    let mut has_energy_accel = false;
    let mut has_damage_mod = false;
    let mut has_healing = false;
    let mut has_disruption = false;
    let mut has_draw = false;

    for &ci in &player.hand {
        let card = db.get_by_idx(ci);
        if card.kind != CardKind::Supporter {
            continue;
        }
        for effect in &card.trainer_effects {
            match effect {
                // Pivot: force opponent switch
                EffectKind::SwitchOpponentActive
                | EffectKind::SwitchOpponentDamagedToActive => {
                    has_pivot = true;
                }
                // Energy acceleration: attach extra energy to own pokemon
                EffectKind::AttachEnergyZoneBench { .. }
                | EffectKind::AttachEnergyZoneBenchBracket { .. }
                | EffectKind::AttachEnergyZoneBenchAnyBracket { .. }
                | EffectKind::AttachEnergyZoneSelf
                | EffectKind::AttachEnergyZoneSelfN { .. }
                | EffectKind::AttachEnergyZoneNamed { .. }
                | EffectKind::AttachEnergyZoneToGrass
                | EffectKind::AttachEnergyZoneSelfBracket { .. }
                | EffectKind::AttachEnergyNamedEndTurn { .. }
                | EffectKind::CoinFlipUntilTailsAttachEnergy
                | EffectKind::MoveBenchEnergyToActive => {
                    has_energy_accel = true;
                }
                // Damage modifier: boost or reduce damage
                EffectKind::SupporterDamageAura { .. }
                | EffectKind::SupporterDamageAuraVsEx { .. }
                | EffectKind::NextTurnAllDamageReduction { .. } => {
                    has_damage_mod = true;
                }
                // Healing
                EffectKind::HealGrassTarget { .. }
                | EffectKind::HealTarget { .. }
                | EffectKind::HealActive { .. }
                | EffectKind::HealAllOwn { .. }
                | EffectKind::HealAndCureStatus { .. }
                | EffectKind::HealWaterPokemon { .. }
                | EffectKind::HealStage2Target { .. } => {
                    has_healing = true;
                }
                // Disruption: force opponent to lose hand/cards
                EffectKind::DiscardRandomCardOpponent
                | EffectKind::IonoHandShuffle => {
                    has_disruption = true;
                }
                // Draw / cycle
                EffectKind::DrawCards { .. } => {
                    has_draw = true;
                }
                _ => {}
            }
        }
    }

    // --- Contextual flags: is the supporter worth playing RIGHT NOW? ---

    // damage_mod_ko: +10 damage would push my best current attack into a KO.
    let damage_mod_ko = if has_damage_mod {
        if let (Some(my_active), Some(opp_active)) =
            (&player.active, &opp_player.active)
        {
            let my_card = db.get_by_idx(my_active.card_idx);
            let opp_card = db.get_by_idx(opp_active.card_idx);
            let (_, _, my_max_now, _) = attack_readiness(my_active, &my_card.attacks);
            let weakness_mult = if opp_card.weakness == my_card.element { 2 } else { 1 };
            // Would adding +10 (Giovanni/Red) or -10 to opp's reduction cause a KO?
            (my_max_now + 10) * weakness_mult as i16 >= opp_active.current_hp
        } else {
            false
        }
    } else {
        false
    };

    // pivot_useful: opp has bench pokemon to switch into.
    let pivot_useful = has_pivot
        && opp_player.bench.iter().any(|s| s.is_some());

    // healing_useful: I have a pokemon at < 2/3 HP.
    let healing_useful = has_healing && {
        let check = |slot: Option<&PokemonSlot>| {
            slot.map_or(false, |s| {
                s.max_hp > 0 && (s.current_hp as f32 / s.max_hp as f32) < 0.67
            })
        };
        check(player.active.as_ref())
            || player.bench.iter().any(|s| check(s.as_ref()))
    };

    // opp_bench_any_energy: opponent has energy on any bench pokemon
    // (tells net whether pivoting opp active exposes an energized threat).
    let opp_bench_any_energy = opp_player.bench.iter().any(|s| {
        s.as_ref().map_or(false, |slot| slot.energy.iter().any(|&e| e > 0))
    });

    // my_bench_any_ready: I have a bench pokemon that can attack right now
    // (tells net whether retreating to it is immediately useful).
    let my_bench_any_ready = player.bench.iter().any(|s| {
        s.as_ref().map_or(false, |slot| {
            let card = db.get_by_idx(slot.card_idx);
            let (_, _, max_now, _) = attack_readiness(slot, &card.attacks);
            max_now > 0
        })
    });

    [
        has_pivot as u8 as f32,
        has_energy_accel as u8 as f32,
        has_damage_mod as u8 as f32,
        has_healing as u8 as f32,
        has_disruption as u8 as f32,
        has_draw as u8 as f32,
        damage_mod_ko as u8 as f32,
        pivot_useful as u8 as f32,
        healing_useful as u8 as f32,
        opp_bench_any_energy as u8 as f32,
        my_bench_any_ready as u8 as f32,
    ]
}

// ------------------------------------------------------------------ //
// Hand composition helper
// ------------------------------------------------------------------ //

/// Count cards by (kind, stage bucket). Returns a 7-wide vector:
///   [basic_pokemon, stage1_pokemon, stage2_pokemon, item, supporter, tool, ex_pokemon]
/// Values are normalized by 10 (rough hand ceiling).
fn hand_composition(hand: &[u16], db: &CardDb) -> [f32; 7] {
    let mut counts = [0u16; 7];
    for &ci in hand {
        let card = db.get_by_idx(ci);
        match (card.kind, card.stage) {
            (CardKind::Pokemon, Some(Stage::Basic)) => counts[0] += 1,
            (CardKind::Pokemon, Some(Stage::Stage1)) => counts[1] += 1,
            (CardKind::Pokemon, Some(Stage::Stage2)) => counts[2] += 1,
            (CardKind::Item, _) => counts[3] += 1,
            (CardKind::Supporter, _) => counts[4] += 1,
            (CardKind::Tool, _) => counts[5] += 1,
            _ => {}
        }
        if card.is_ex {
            counts[6] += 1;
        }
    }
    let mut out = [0.0f32; 7];
    for i in 0..7 {
        out[i] = counts[i] as f32 / 10.0;
    }
    out
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    #[test]
    fn feature_dim_constants_consistent() {
        // Catches drift between SLOT_DIM, NUM_SLOTS, GLOBAL_DIM and FEATURE_DIM.
        assert_eq!(FEATURE_DIM, SLOT_DIM * NUM_SLOTS + GLOBAL_DIM);
    }

    #[test]
    fn encode_empty_state_returns_correct_length() {
        let db = CardDb::load_from_dir(&assets_dir());
        let state = GameState::new(0);
        let v = encode(&state, &db, 0);
        assert_eq!(v.len(), FEATURE_DIM);
        // All slot features should be zero (no pokemon placed yet).
        for i in 0..(SLOT_DIM * NUM_SLOTS) {
            assert_eq!(v[i], 0.0, "slot feature {} should be zero", i);
        }
    }

    #[test]
    fn encode_deterministic_for_fixed_state() {
        let db = CardDb::load_from_dir(&assets_dir());
        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 5;
        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        state.players[0].active =
            Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[1].active =
            Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[0].hand = smallvec::smallvec![bulb.idx, bulb.idx];

        let v1 = encode(&state, &db, 0);
        let v2 = encode(&state, &db, 0);
        assert_eq!(v1, v2, "encode should be deterministic for fixed state");
    }

    #[test]
    fn encode_pov_symmetry() {
        // Encoding the same mirror state for player 0 vs player 1 should be
        // byte-equal: both see themselves in the first half, opponent in the
        // second — and the state is symmetric so the halves should match.
        let db = CardDb::load_from_dir(&assets_dir());
        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 3;
        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        // Perfectly symmetric state, including first_player.
        state.first_player = 0;
        state.current_player = 0;
        state.players[0].active =
            Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[1].active =
            Some(PokemonSlot::new(bulb.idx, bulb.hp));

        let v0 = encode(&state, &db, 0);
        // Make it symmetric for player 1 by swapping current_player and first_player.
        let mut mirror = state.clone();
        mirror.first_player = 1;
        mirror.current_player = 1;
        let v1 = encode(&mirror, &db, 1);

        // The slot halves should match. Global may differ slightly due to
        // "is it my turn" + "am I first" flags being symmetric here, so the
        // whole vector should be identical.
        assert_eq!(v0.len(), v1.len());
        // Slot half (indices 0 .. SLOT_DIM*NUM_SLOTS) should match because
        // POV-normalisation puts "me" first for both.
        let slot_end = SLOT_DIM * NUM_SLOTS;
        assert_eq!(&v0[..slot_end], &v1[..slot_end]);
    }
}
