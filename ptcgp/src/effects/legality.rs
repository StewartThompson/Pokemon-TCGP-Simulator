//! Per-card legality predicates.
//!
//! Each card optionally carries a `legal` JSON array of predicate strings
//! (parallel to its `handler`).  The strings are parsed at card-load time
//! into [`LegalCondition`] values; at action-enumeration time we evaluate
//! every condition and short-circuit if any fails.  Target-enumerating
//! conditions (e.g. heal target) cross-product to produce one [`Action`]
//! per valid target.
//!
//! The whole module mirrors the layout of [`crate::effects`]:
//! string parser → enum variant → evaluator.  See the plan file
//! `~/.claude/plans/eager-tinkering-llama.md` for the full audit table.

use std::collections::HashMap;

use crate::actions::{Action, SlotRef};
use crate::card::CardDb;
use crate::state::{GameState, PokemonSlot};
use crate::types::{ActionKind, Element, Stage};

// ------------------------------------------------------------------ //
// Public types
// ------------------------------------------------------------------ //

/// Skeleton of an [`Action`] missing only its `target`.  Used to build
/// concrete actions from target enumerators inside
/// [`enumerate_legal_actions`].
#[derive(Clone, Copy, Debug)]
pub enum BaseAction {
    /// Item / Supporter / non-tool Trainer played from hand.  Target is
    /// optional (most items have no target).
    PlayItem { hand_index: usize },
    /// Tool attached to one of the player's Pokémon.  Target is required.
    AttachTool { hand_index: usize },
    /// Attack from the active Pokémon.  Target is optional sub-target
    /// (e.g. opponent bench slot for Zebstrika Thunder Spear).
    Attack { attack_index: usize },
    /// Use a Pokémon's manual ability.  The ability's source slot is
    /// fixed; target enumerators are not used for abilities (those that
    /// need a target are surfaced as Attack-style actions today).
    UseAbility { source: SlotRef },
}

impl BaseAction {
    /// Build a concrete [`Action`] with the given target slot.
    pub fn with_target(&self, target: Option<SlotRef>) -> Action {
        match *self {
            Self::PlayItem { hand_index } => Action::play_item(hand_index, target),
            Self::AttachTool { hand_index } => Action {
                kind: ActionKind::PlayCard,
                hand_index: Some(hand_index),
                target,
                attack_index: None,
                extra_hand_index: None,
                extra_target: None,
            },
            Self::Attack { attack_index } => Action::attack(attack_index, target),
            Self::UseAbility { source } => {
                // UseAbility has a fixed source; targets are typically
                // chosen later by the engine or implied by ability code.
                let _ = target;
                Action::use_ability(source)
            }
        }
    }

    /// Build an attack with two own-bench targets (Manaphy-style).
    pub fn with_two_targets(&self, a: SlotRef, b: SlotRef) -> Action {
        match *self {
            Self::Attack { attack_index } => Action::attack_two_targets(attack_index, a, b),
            _ => self.with_target(Some(a)),
        }
    }
}

/// One predicate / target enumerator parsed from a card's `legal` array.
/// Boolean variants gate playability; target variants enumerate Actions.
#[derive(Clone, Debug, PartialEq)]
pub enum LegalCondition {
    // -------- Boolean preconditions --------
    OwnBenchAtLeast { count: u8 },
    OppBenchAtLeast { count: u8 },
    OppHandAtLeast { count: u8 },
    OwnDeckHasBasic,
    OwnDeckHasPokemon,
    OwnDeckHasNamed { names: Vec<String> },
    OwnEnergyDiscardAtLeast { count: u8, element: Option<Element> },
    OppPointsAtLeast { count: u8 },
    ActiveIsElement { element: Element },
    ActiveIsNamed { names: Vec<String> },
    ActiveRetreatCostAtLeast { amount: u8 },
    ActiveIsSubtype { subtype: String },
    OwnInPlaySubtype { subtype: String },
    OwnBenchSubtype { subtype: String },
    OwnInPlayBasic,
    OwnInPlayElement { element: Element },
    OwnBenchHasEnergy,
    OwnBenchHasEmpty,
    OppHasTool,
    OppActiveHasAttack,
    OwnInPlayDamaged { element: Option<Element>, stage: Option<Stage> },

    // -------- Target enumerators --------
    /// One Action per damaged own Pokémon (active + bench), optionally
    /// filtered by element and/or stage.  Used by Potion, Erika, Leaf
    /// supporters, Pokémon Center Lady, Lillie.
    HealOwnTarget { element: Option<Element>, stage: Option<Stage> },
    /// One Action per own Pokémon **without a tool already attached**,
    /// optionally filtered by element (Inflatable Boat → Water).
    ToolTarget { element: Option<Element> },
    /// One Action per unordered pair of own benched Pokémon.  Used by
    /// Manaphy AttachWaterTwoBench.
    OwnBenchPair,
    /// One Action per opponent bench slot, optionally filtered to damaged.
    OppBenchTarget { damaged_only: bool },
    /// One Action per opponent in-play Pokémon (active + bench).
    OppAnyTarget,
    /// One Action per own in-play Pokémon, optionally filtered by element.
    OwnPokemonTarget { element: Option<Element> },
}

// ------------------------------------------------------------------ //
// Parser — mirrors effects::parse_handler_string syntax
// ------------------------------------------------------------------ //

/// Parse the `legal` JSON array (each entry a `name(arg=val,...)` string)
/// into a Vec of [`LegalCondition`].  Unknown names are silently skipped
/// so older JSON keeps loading; callers check the resulting vec length to
/// detect typos in newly-authored cards.
pub fn parse_legal_array(items: &[String]) -> Vec<LegalCondition> {
    items
        .iter()
        .filter_map(|s| parse_legal_string(s.trim()))
        .collect()
}

fn parse_legal_string(s: &str) -> Option<LegalCondition> {
    if s.is_empty() {
        return None;
    }
    let paren = s.find('(');
    let name = if let Some(p) = paren { s[..p].trim() } else { s };
    let args = if let Some(p) = paren { &s[p + 1..] } else { "" };
    let params = parse_args(args);

    Some(match name {
        // boolean
        "own_bench_at_least" => LegalCondition::OwnBenchAtLeast {
            count: get_u8(&params, "count", 1),
        },
        "opp_bench_at_least" => LegalCondition::OppBenchAtLeast {
            count: get_u8(&params, "count", 1),
        },
        "opp_hand_at_least" => LegalCondition::OppHandAtLeast {
            count: get_u8(&params, "count", 1),
        },
        "own_deck_has_basic" => LegalCondition::OwnDeckHasBasic,
        "own_deck_has_pokemon" => LegalCondition::OwnDeckHasPokemon,
        "own_deck_has_named" => LegalCondition::OwnDeckHasNamed {
            names: get_names(&params, "names"),
        },
        "own_energy_discard_at_least" => LegalCondition::OwnEnergyDiscardAtLeast {
            count: get_u8(&params, "count", 1),
            element: get_element(&params, "element"),
        },
        "opp_points_at_least" => LegalCondition::OppPointsAtLeast {
            count: get_u8(&params, "count", 1),
        },
        "active_is_element" => LegalCondition::ActiveIsElement {
            element: get_element(&params, "element").unwrap_or(Element::Grass),
        },
        "active_is_named" => LegalCondition::ActiveIsNamed {
            names: get_names(&params, "names"),
        },
        "active_retreat_cost_at_least" => LegalCondition::ActiveRetreatCostAtLeast {
            amount: get_u8(&params, "amount", 1),
        },
        "active_is_subtype" => LegalCondition::ActiveIsSubtype {
            subtype: get_str(&params, "subtype"),
        },
        "own_in_play_subtype" => LegalCondition::OwnInPlaySubtype {
            subtype: get_str(&params, "subtype"),
        },
        "own_bench_subtype" => LegalCondition::OwnBenchSubtype {
            subtype: get_str(&params, "subtype"),
        },
        "own_in_play_basic" => LegalCondition::OwnInPlayBasic,
        "own_in_play_element" => LegalCondition::OwnInPlayElement {
            element: get_element(&params, "element").unwrap_or(Element::Grass),
        },
        "own_bench_has_energy" => LegalCondition::OwnBenchHasEnergy,
        "own_bench_has_empty" => LegalCondition::OwnBenchHasEmpty,
        "opp_has_tool" => LegalCondition::OppHasTool,
        "opp_active_has_attack" => LegalCondition::OppActiveHasAttack,
        "own_in_play_damaged" => LegalCondition::OwnInPlayDamaged {
            element: get_element(&params, "element"),
            stage: get_stage(&params, "stage"),
        },

        // target enumerators
        "heal_own_target" => LegalCondition::HealOwnTarget {
            element: get_element(&params, "element"),
            stage: get_stage(&params, "stage"),
        },
        "tool_target" => LegalCondition::ToolTarget {
            element: get_element(&params, "element"),
        },
        "own_bench_pair" => LegalCondition::OwnBenchPair,
        "opp_bench_target" => LegalCondition::OppBenchTarget {
            damaged_only: get_bool(&params, "damaged_only", false),
        },
        "opp_any_target" => LegalCondition::OppAnyTarget,
        "own_pokemon_target" => LegalCondition::OwnPokemonTarget {
            element: get_element(&params, "element"),
        },

        _ => return None,
    })
}

fn parse_args(args: &str) -> HashMap<String, String> {
    let mut out = HashMap::new();
    let args = args.trim().trim_end_matches(')');
    if args.is_empty() {
        return out;
    }
    for token in args.split(',') {
        let t = token.trim();
        if let Some(eq) = t.find('=') {
            let k = t[..eq].trim().to_string();
            let v = t[eq + 1..].trim().to_string();
            out.insert(k, v);
        }
    }
    out
}

fn get_u8(p: &HashMap<String, String>, k: &str, d: u8) -> u8 {
    p.get(k).and_then(|v| v.parse().ok()).unwrap_or(d)
}

fn get_bool(p: &HashMap<String, String>, k: &str, d: bool) -> bool {
    p.get(k).and_then(|v| v.parse().ok()).unwrap_or(d)
}

fn get_str(p: &HashMap<String, String>, k: &str) -> String {
    p.get(k).cloned().unwrap_or_default()
}

fn get_element(p: &HashMap<String, String>, k: &str) -> Option<Element> {
    p.get(k).and_then(|v| Element::from_str(v))
}

fn get_stage(p: &HashMap<String, String>, k: &str) -> Option<Stage> {
    p.get(k).and_then(|v| match v.to_lowercase().as_str() {
        "basic" => Some(Stage::Basic),
        "stage1" | "stage 1" => Some(Stage::Stage1),
        "stage2" | "stage 2" => Some(Stage::Stage2),
        _ => None,
    })
}

fn get_names(p: &HashMap<String, String>, k: &str) -> Vec<String> {
    p.get(k)
        .map(|v| {
            let v = v.trim().trim_start_matches('(').trim_end_matches(')');
            v.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect()
        })
        .unwrap_or_default()
}

// ------------------------------------------------------------------ //
// Evaluator
// ------------------------------------------------------------------ //

/// Evaluate `conditions` against the game state and return the list of
/// concrete [`Action`] values that should be surfaced.  Empty Vec means
/// the card is not legal in this state.
///
/// Boolean conditions short-circuit (returns empty as soon as one fails).
/// Target enumerators are cross-producted; if multiple enumerators are
/// present the caller gets one Action per element of each enumerator's
/// target list (in practice cards almost always have at most one
/// enumerator).  If no enumerator is present, a single Action is produced
/// with `target = None`.
pub fn enumerate_legal_actions(
    conditions: &[LegalCondition],
    state: &GameState,
    db: &CardDb,
    cp: usize,
    base: BaseAction,
) -> Vec<Action> {
    // 1. Check all boolean preconditions.
    for c in conditions {
        if is_boolean(c) && !eval_bool(c, state, db, cp) {
            return Vec::new();
        }
    }

    // 2. Collect target lists from enumerators.
    let mut enum_targets: Vec<Vec<Option<SlotRef>>> = Vec::new();
    let mut bench_pair_emitted = false;
    let mut pair_actions: Vec<Action> = Vec::new();

    for c in conditions {
        match c {
            LegalCondition::HealOwnTarget { element, stage } => {
                enum_targets.push(heal_own_targets(state, db, cp, *element, *stage));
            }
            LegalCondition::ToolTarget { element } => {
                enum_targets.push(tool_targets(state, db, cp, *element));
            }
            LegalCondition::OppBenchTarget { damaged_only } => {
                enum_targets.push(opp_bench_targets(state, cp, *damaged_only));
            }
            LegalCondition::OppAnyTarget => {
                enum_targets.push(opp_any_targets(state, cp));
            }
            LegalCondition::OwnPokemonTarget { element } => {
                enum_targets.push(own_pokemon_targets(state, db, cp, *element));
            }
            LegalCondition::OwnBenchPair => {
                bench_pair_emitted = true;
                pair_actions = own_bench_pair_actions(state, cp, base);
            }
            _ => {}
        }
    }

    // 3. Combine.  The bench-pair enumerator owns its own action shape;
    //    if present, return its actions directly (other enumerators can't
    //    meaningfully cross-product with pair actions).
    if bench_pair_emitted {
        return pair_actions;
    }

    if enum_targets.is_empty() {
        // No enumerator → single targetless action.
        return vec![base.with_target(None)];
    }

    // Cross-product (almost always size 1 in practice).
    let mut out: Vec<Vec<Option<SlotRef>>> = vec![vec![]];
    for list in &enum_targets {
        if list.is_empty() {
            return Vec::new();
        }
        let mut next = Vec::with_capacity(out.len() * list.len());
        for prefix in &out {
            for &t in list {
                let mut p = prefix.clone();
                p.push(t);
                next.push(p);
            }
        }
        out = next;
    }
    // Each combination → one Action with the FIRST target (multi-target
    // attacks beyond pairs are not yet expressible here).
    out.into_iter()
        .map(|combo| base.with_target(combo.into_iter().next().flatten()))
        .collect()
}

fn is_boolean(c: &LegalCondition) -> bool {
    !matches!(
        c,
        LegalCondition::HealOwnTarget { .. }
            | LegalCondition::ToolTarget { .. }
            | LegalCondition::OwnBenchPair
            | LegalCondition::OppBenchTarget { .. }
            | LegalCondition::OppAnyTarget
            | LegalCondition::OwnPokemonTarget { .. }
    )
}

fn eval_bool(c: &LegalCondition, state: &GameState, db: &CardDb, cp: usize) -> bool {
    let player = &state.players[cp];
    let opp = &state.players[1 - cp];
    match c {
        LegalCondition::OwnBenchAtLeast { count } => {
            count_bench(player) >= *count as usize
        }
        LegalCondition::OppBenchAtLeast { count } => {
            count_bench(opp) >= *count as usize
        }
        LegalCondition::OppHandAtLeast { count } => opp.hand.len() >= *count as usize,
        LegalCondition::OwnDeckHasBasic => player.deck.iter().any(|&idx| {
            db.try_get_by_idx(idx)
                .map(|c| c.kind == crate::types::CardKind::Pokemon
                    && c.stage == Some(Stage::Basic))
                .unwrap_or(false)
        }),
        LegalCondition::OwnDeckHasPokemon => player.deck.iter().any(|&idx| {
            db.try_get_by_idx(idx)
                .map(|c| c.kind == crate::types::CardKind::Pokemon)
                .unwrap_or(false)
        }),
        LegalCondition::OwnDeckHasNamed { names } => {
            let lc: Vec<String> = names.iter().map(|s| s.to_lowercase()).collect();
            player.deck.iter().any(|&idx| {
                db.try_get_by_idx(idx)
                    .map(|c| lc.iter().any(|n| n == &c.name.to_lowercase()))
                    .unwrap_or(false)
            })
        }
        LegalCondition::OwnEnergyDiscardAtLeast { count, element } => {
            match element {
                Some(el) => player.energy_discard[el.idx()] >= *count,
                None => player.energy_discard.iter().sum::<u8>() >= *count,
            }
        }
        LegalCondition::OppPointsAtLeast { count } => opp.points >= *count,
        LegalCondition::ActiveIsElement { element } => {
            player.active.as_ref().map(|s| {
                db.try_get_by_idx(s.card_idx).and_then(|c| c.element) == Some(*element)
            }).unwrap_or(false)
        }
        LegalCondition::ActiveIsNamed { names } => {
            let lc: Vec<String> = names.iter().map(|s| s.to_lowercase()).collect();
            player.active.as_ref().map(|s| {
                db.try_get_by_idx(s.card_idx)
                    .map(|c| lc.iter().any(|n| n == &c.name.to_lowercase()))
                    .unwrap_or(false)
            }).unwrap_or(false)
        }
        LegalCondition::ActiveRetreatCostAtLeast { amount } => {
            player.active.as_ref().map(|s| {
                db.try_get_by_idx(s.card_idx)
                    .map(|c| {
                        let base_cost = c.retreat_cost;
                        if base_cost == u8::MAX { return false; }
                        let modifier = player.retreat_cost_modifier as i16;
                        // Tool reduction (e.g. Inflatable Boat).
                        let tool_red: i16 = s.tool_idx
                            .and_then(|t| db.try_get_by_idx(t))
                            .map(|tool| {
                                tool.trainer_effects.iter().find_map(|e| {
                                    if let crate::effects::EffectKind::PassiveBenchRetreatReduction { amount }
                                        = e
                                    {
                                        Some(*amount as i16)
                                    } else {
                                        None
                                    }
                                }).unwrap_or(0)
                            })
                            .unwrap_or(0);
                        let effective = (base_cost as i16 + modifier - tool_red).max(0) as u8;
                        effective >= *amount
                    })
                    .unwrap_or(false)
            }).unwrap_or(false)
        }
        LegalCondition::ActiveIsSubtype { subtype } | LegalCondition::OwnInPlaySubtype { subtype } => {
            // PTCGP "subtype" field on cards; we approximate with name search
            // ("Ultra Beast" appears in the subtype/pack metadata).  Today
            // CardDb doesn't expose subtype, so we fall back to name-list
            // matching the known Ultra Beast roster.
            let ultra_beasts = ["Nihilego", "Celesteela", "Guzzlord ex"];
            let is_ub = |idx: u16| -> bool {
                db.try_get_by_idx(idx)
                    .map(|c| ultra_beasts.iter().any(|n| c.name == *n))
                    .unwrap_or(false)
            };
            let matches = subtype.eq_ignore_ascii_case("ultra beast");
            if !matches {
                return false;
            }
            match c {
                LegalCondition::ActiveIsSubtype { .. } => {
                    player.active.as_ref().map(|s| is_ub(s.card_idx)).unwrap_or(false)
                }
                LegalCondition::OwnInPlaySubtype { .. } => {
                    player.active.as_ref().map(|s| is_ub(s.card_idx)).unwrap_or(false)
                        || player.bench.iter().any(|b| {
                            b.as_ref().map(|s| is_ub(s.card_idx)).unwrap_or(false)
                        })
                }
                _ => false,
            }
        }
        LegalCondition::OwnBenchSubtype { subtype } => {
            let ultra_beasts = ["Nihilego", "Celesteela", "Guzzlord ex"];
            let matches = subtype.eq_ignore_ascii_case("ultra beast");
            if !matches { return false; }
            player.bench.iter().any(|b| {
                b.as_ref().and_then(|s| db.try_get_by_idx(s.card_idx))
                    .map(|c| ultra_beasts.iter().any(|n| c.name == *n))
                    .unwrap_or(false)
            })
        }
        LegalCondition::OwnInPlayBasic => {
            let is_basic = |slot: &PokemonSlot| -> bool {
                db.try_get_by_idx(slot.card_idx)
                    .map(|c| c.stage == Some(Stage::Basic))
                    .unwrap_or(false)
            };
            player.active.as_ref().map(is_basic).unwrap_or(false)
                || player.bench.iter().any(|b| b.as_ref().map(is_basic).unwrap_or(false))
        }
        LegalCondition::OwnInPlayElement { element } => {
            let is_el = |slot: &PokemonSlot| -> bool {
                db.try_get_by_idx(slot.card_idx)
                    .and_then(|c| c.element)
                    == Some(*element)
            };
            player.active.as_ref().map(is_el).unwrap_or(false)
                || player.bench.iter().any(|b| b.as_ref().map(is_el).unwrap_or(false))
        }
        LegalCondition::OwnBenchHasEnergy => {
            player.bench.iter().any(|b| {
                b.as_ref().map(|s| s.total_energy() > 0).unwrap_or(false)
            })
        }
        LegalCondition::OwnBenchHasEmpty => {
            player.bench.iter().any(|b| b.is_none())
        }
        LegalCondition::OppHasTool => {
            let any_tool = |slot: &PokemonSlot| slot.tool_idx.is_some();
            opp.active.as_ref().map(any_tool).unwrap_or(false)
                || opp.bench.iter().any(|b| b.as_ref().map(any_tool).unwrap_or(false))
        }
        LegalCondition::OppActiveHasAttack => {
            opp.active.as_ref().map(|s| {
                db.try_get_by_idx(s.card_idx)
                    .map(|c| !c.attacks.is_empty())
                    .unwrap_or(false)
            }).unwrap_or(false)
        }
        LegalCondition::OwnInPlayDamaged { element, stage } => {
            let matches = |slot: &PokemonSlot| -> bool {
                if slot.current_hp >= slot.max_hp { return false; }
                let card = match db.try_get_by_idx(slot.card_idx) { Some(c) => c, None => return false };
                if let Some(el) = element {
                    if card.element != Some(*el) { return false; }
                }
                if let Some(st) = stage {
                    if card.stage != Some(*st) { return false; }
                }
                true
            };
            player.active.as_ref().map(matches).unwrap_or(false)
                || player.bench.iter().any(|b| b.as_ref().map(matches).unwrap_or(false))
        }

        // Target enumerators are not boolean — should not be reached.
        _ => true,
    }
}

// ------------------------------------------------------------------ //
// Target enumerators
// ------------------------------------------------------------------ //

fn count_bench(p: &crate::state::PlayerState) -> usize {
    p.bench.iter().filter(|s| s.is_some()).count()
}

fn heal_own_targets(
    state: &GameState,
    db: &CardDb,
    cp: usize,
    element: Option<Element>,
    stage: Option<Stage>,
) -> Vec<Option<SlotRef>> {
    let player = &state.players[cp];
    let mut out = Vec::new();
    let matches = |slot: &PokemonSlot| -> bool {
        if slot.current_hp >= slot.max_hp { return false; }
        let card = match db.try_get_by_idx(slot.card_idx) { Some(c) => c, None => return false };
        if let Some(el) = element {
            if card.element != Some(el) { return false; }
        }
        if let Some(st) = stage {
            if card.stage != Some(st) { return false; }
        }
        true
    };
    if let Some(a) = player.active.as_ref() {
        if matches(a) { out.push(Some(SlotRef::active(cp))); }
    }
    for j in 0..3 {
        if let Some(b) = player.bench[j].as_ref() {
            if matches(b) { out.push(Some(SlotRef::bench(cp, j))); }
        }
    }
    out
}

fn tool_targets(
    state: &GameState,
    db: &CardDb,
    cp: usize,
    element: Option<Element>,
) -> Vec<Option<SlotRef>> {
    let player = &state.players[cp];
    let mut out = Vec::new();
    let matches = |slot: &PokemonSlot| -> bool {
        if slot.tool_idx.is_some() { return false; }
        if let Some(el) = element {
            let card = match db.try_get_by_idx(slot.card_idx) { Some(c) => c, None => return false };
            if card.element != Some(el) { return false; }
        }
        true
    };
    if let Some(a) = player.active.as_ref() {
        if matches(a) { out.push(Some(SlotRef::active(cp))); }
    }
    for j in 0..3 {
        if let Some(b) = player.bench[j].as_ref() {
            if matches(b) { out.push(Some(SlotRef::bench(cp, j))); }
        }
    }
    out
}

fn opp_bench_targets(
    state: &GameState,
    cp: usize,
    damaged_only: bool,
) -> Vec<Option<SlotRef>> {
    let opp = 1 - cp;
    let mut out = Vec::new();
    for j in 0..3 {
        if let Some(slot) = state.players[opp].bench[j].as_ref() {
            if !damaged_only || slot.current_hp < slot.max_hp {
                out.push(Some(SlotRef::bench(opp, j)));
            }
        }
    }
    out
}

fn opp_any_targets(state: &GameState, cp: usize) -> Vec<Option<SlotRef>> {
    let opp = 1 - cp;
    let mut out = Vec::new();
    if state.players[opp].active.is_some() {
        out.push(Some(SlotRef::active(opp)));
    }
    for j in 0..3 {
        if state.players[opp].bench[j].is_some() {
            out.push(Some(SlotRef::bench(opp, j)));
        }
    }
    out
}

fn own_pokemon_targets(
    state: &GameState,
    db: &CardDb,
    cp: usize,
    element: Option<Element>,
) -> Vec<Option<SlotRef>> {
    let player = &state.players[cp];
    let mut out = Vec::new();
    let matches = |slot: &PokemonSlot| -> bool {
        if let Some(el) = element {
            let card = match db.try_get_by_idx(slot.card_idx) { Some(c) => c, None => return false };
            if card.element != Some(el) { return false; }
        }
        true
    };
    if let Some(a) = player.active.as_ref() {
        if matches(a) { out.push(Some(SlotRef::active(cp))); }
    }
    for j in 0..3 {
        if let Some(b) = player.bench[j].as_ref() {
            if matches(b) { out.push(Some(SlotRef::bench(cp, j))); }
        }
    }
    out
}

fn own_bench_pair_actions(
    state: &GameState,
    cp: usize,
    base: BaseAction,
) -> Vec<Action> {
    let player = &state.players[cp];
    let bench_indices: Vec<usize> = (0..3).filter(|&j| player.bench[j].is_some()).collect();
    let mut out = Vec::new();
    if bench_indices.len() >= 2 {
        for a in 0..bench_indices.len() {
            for b in (a + 1)..bench_indices.len() {
                let sa = SlotRef::bench(cp, bench_indices[a]);
                let sb = SlotRef::bench(cp, bench_indices[b]);
                out.push(base.with_two_targets(sa, sb));
            }
        }
    } else if bench_indices.len() == 1 {
        let sa = SlotRef::bench(cp, bench_indices[0]);
        out.push(base.with_target(Some(sa)));
    } else {
        // No bench at all — attack still legal per rules but the attach
        // will fizzle.  Emit a no-target action.
        out.push(base.with_target(None));
    }
    out
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::{Card, CardDb};
    use crate::state::{GameState, PokemonSlot};
    use crate::types::{CardKind, Element, GamePhase, Stage};
    use std::collections::HashMap;

    fn make_card(idx: u16, name: &str, element: Option<Element>, stage: Option<Stage>) -> Card {
        Card {
            id: format!("test-{}", idx),
            idx,
            name: name.to_string(),
            kind: CardKind::Pokemon,
            stage,
            element,
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
            trainer_legal_conditions: vec![],
            ko_points: 1,
        }
    }

    fn db_with(cards: Vec<Card>) -> CardDb {
        let mut db = CardDb::new_empty();
        for c in cards {
            let idx = c.idx;
            db.id_to_idx.insert(c.id.clone(), idx);
            db.name_to_indices.entry(c.name.clone()).or_insert_with(Vec::new).push(idx);
            db.cards.push(c);
        }
        db
    }

    fn empty_state() -> GameState {
        let mut s = GameState::new(0);
        s.phase = GamePhase::Main;
        s
    }

    #[test]
    fn parse_simple_legal_array() {
        let conds = parse_legal_array(&["own_bench_at_least(count=2)".to_string()]);
        assert_eq!(conds, vec![LegalCondition::OwnBenchAtLeast { count: 2 }]);
    }

    #[test]
    fn parse_named_list() {
        let conds = parse_legal_array(&["active_is_named(names=Mew ex)".to_string()]);
        assert_eq!(
            conds,
            vec![LegalCondition::ActiveIsNamed { names: vec!["Mew ex".to_string()] }]
        );
    }

    #[test]
    fn parse_three_condition_array() {
        let conds = parse_legal_array(&[
            "opp_points_at_least(count=1)".to_string(),
            "own_in_play_subtype(subtype=Ultra Beast)".to_string(),
            "own_energy_discard_at_least(count=2)".to_string(),
        ]);
        assert_eq!(conds.len(), 3);
    }

    #[test]
    fn parse_unknown_skipped() {
        let conds = parse_legal_array(&["foo_bar(x=1)".to_string()]);
        assert!(conds.is_empty());
    }

    #[test]
    fn opp_bench_at_least_empty_fails() {
        let pikachu = make_card(0, "Pikachu", Some(Element::Lightning), Some(Stage::Basic));
        let db = db_with(vec![pikachu]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));
        s.players[1].active = Some(PokemonSlot::new(0, 100));
        let conds = vec![LegalCondition::OppBenchAtLeast { count: 1 }];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert!(out.is_empty(), "Sabrina-style precondition should reject empty opp bench");
    }

    #[test]
    fn opp_bench_at_least_one_pokemon_passes() {
        let pikachu = make_card(0, "Pikachu", Some(Element::Lightning), Some(Stage::Basic));
        let db = db_with(vec![pikachu]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));
        s.players[1].active = Some(PokemonSlot::new(0, 100));
        s.players[1].bench[0] = Some(PokemonSlot::new(0, 100));
        let conds = vec![LegalCondition::OppBenchAtLeast { count: 1 }];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert_eq!(out.len(), 1, "Sabrina-style precondition should pass when opp has bench");
    }

    #[test]
    fn dawn_no_bench_energy_fails() {
        let pikachu = make_card(0, "Pikachu", Some(Element::Lightning), Some(Stage::Basic));
        let db = db_with(vec![pikachu]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));
        s.players[0].bench[0] = Some(PokemonSlot::new(0, 100)); // no energy
        let conds = vec![LegalCondition::OwnBenchHasEnergy];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert!(out.is_empty());
    }

    #[test]
    fn dawn_with_bench_energy_passes() {
        let pikachu = make_card(0, "Pikachu", Some(Element::Lightning), Some(Stage::Basic));
        let db = db_with(vec![pikachu]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));
        let mut bench = PokemonSlot::new(0, 100);
        bench.add_energy(Element::Lightning, 1);
        s.players[0].bench[0] = Some(bench);
        let conds = vec![LegalCondition::OwnBenchHasEnergy];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert_eq!(out.len(), 1);
    }

    #[test]
    fn x_speed_active_zero_retreat_fails() {
        let mut pikachu = make_card(0, "Pikachu", Some(Element::Lightning), Some(Stage::Basic));
        pikachu.retreat_cost = 0;
        let db = db_with(vec![pikachu]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));
        let conds = vec![LegalCondition::ActiveRetreatCostAtLeast { amount: 1 }];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert!(out.is_empty());
    }

    #[test]
    fn potion_emits_one_action_per_damaged() {
        let pikachu = make_card(0, "Pikachu", Some(Element::Lightning), Some(Stage::Basic));
        let db = db_with(vec![pikachu]);
        let mut s = empty_state();
        let mut active = PokemonSlot::new(0, 100);
        active.current_hp = 60;
        s.players[0].active = Some(active);
        let mut bench0 = PokemonSlot::new(0, 100); // full HP
        bench0.current_hp = 100;
        s.players[0].bench[0] = Some(bench0);
        let mut bench1 = PokemonSlot::new(0, 100);
        bench1.current_hp = 70;
        s.players[0].bench[1] = Some(bench1);

        let conds = vec![LegalCondition::HealOwnTarget { element: None, stage: None }];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert_eq!(out.len(), 2, "expected one Action per damaged Pokémon (active + bench1)");
    }

    #[test]
    fn inflatable_boat_only_water_targets() {
        let charmander = make_card(0, "Charmander", Some(Element::Fire), Some(Stage::Basic));
        let squirtle = make_card(1, "Squirtle", Some(Element::Water), Some(Stage::Basic));
        let db = db_with(vec![charmander, squirtle]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));   // Fire active
        s.players[0].bench[0] = Some(PokemonSlot::new(1, 100)); // Water bench

        let conds = vec![LegalCondition::ToolTarget { element: Some(Element::Water) }];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::AttachTool { hand_index: 0 });
        assert_eq!(out.len(), 1, "Inflatable Boat should only attach to Water Pokémon");
    }

    #[test]
    fn lusamine_three_conditions_all_must_pass() {
        let nihilego = make_card(0, "Nihilego", Some(Element::Darkness), Some(Stage::Basic));
        let db = db_with(vec![nihilego]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));

        let conds = vec![
            LegalCondition::OppPointsAtLeast { count: 1 },
            LegalCondition::OwnInPlaySubtype { subtype: "Ultra Beast".to_string() },
            LegalCondition::OwnEnergyDiscardAtLeast { count: 2, element: None },
        ];
        // Opp has 0 points → fail.
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert!(out.is_empty(), "Lusamine should fail when opp has 0 points");

        // Opp has 1 point but discard pile empty → fail.
        s.players[1].points = 1;
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert!(out.is_empty(), "Lusamine should fail when discard pile empty");

        // Add 2 discarded energies → pass.
        s.players[0].energy_discard[Element::Darkness.idx()] = 2;
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert_eq!(out.len(), 1, "Lusamine should be legal when all 3 conditions pass");
    }

    #[test]
    fn red_card_opp_hand_below_threshold_fails() {
        let pikachu = make_card(0, "Pikachu", Some(Element::Lightning), Some(Stage::Basic));
        let db = db_with(vec![pikachu]);
        let mut s = empty_state();
        s.players[0].active = Some(PokemonSlot::new(0, 100));
        s.players[1].active = Some(PokemonSlot::new(0, 100));
        s.players[1].hand = smallvec::smallvec![0u16, 0u16]; // 2 cards
        let conds = vec![LegalCondition::OppHandAtLeast { count: 3 }];
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert!(out.is_empty());

        s.players[1].hand.push(0u16); // 3 cards
        let out = enumerate_legal_actions(&conds, &s, &db, 0, BaseAction::PlayItem { hand_index: 0 });
        assert_eq!(out.len(), 1);
    }
}
