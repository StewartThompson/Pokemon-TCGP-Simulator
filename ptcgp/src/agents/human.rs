//! Human terminal agent — two-level menu UI.
//!
//! Level 1: every actionable item listed directly
//!   - Each playable card shown by name
//!   - Attach Energy (one entry)
//!   - Each usable ability
//!   - Each available attack
//!   - Retreat (one entry)
//!   - End turn
//!
//! Level 2 (target picker): only shown when a card/action needs a target
//!   e.g. Potion → pick which Pokémon; Retreat → pick which bench slot
//!   Typing 0 goes back to level 1.

use std::io::{self, BufRead, Write};
use crate::agents::Agent;
use crate::actions::Action;
use crate::card::CardDb;
use crate::state::{GameState, get_slot};
use crate::types::{ActionKind, CardKind, GamePhase};
use crate::engine::legal_actions::{
    get_legal_actions, get_legal_promotions,
    get_legal_setup_placements, get_legal_setup_bench_placements,
};
use crate::ui::{render_state, element_emoji, format_cost};
use crate::effects::EffectKind;

// ------------------------------------------------------------------ //
// HumanAgent
// ------------------------------------------------------------------ //

pub struct HumanAgent {
    pub player_index: usize,
}

impl HumanAgent {
    pub fn new(player_index: usize) -> Self { Self { player_index } }
}

impl Agent for HumanAgent {
    fn select_action(&self, state: &GameState, db: &CardDb, player_idx: usize) -> Action {
        let (actions, flat) = match state.phase {
            GamePhase::Setup => {
                if state.players[player_idx].active.is_some() {
                    (get_legal_setup_bench_placements(state, db, player_idx), true)
                } else {
                    (get_legal_setup_placements(state, db, player_idx), true)
                }
            }
            GamePhase::AwaitingBenchPromotion => {
                (get_legal_promotions(state, player_idx), true)
            }
            _ => (get_legal_actions(state, db), false),
        };

        let in_initial_setup =
            state.phase == GamePhase::Setup && state.players[player_idx].active.is_none();
        if !in_initial_setup {
            render_state(state, db, self.player_index);
        }

        if flat {
            return flat_menu(&actions, state, db, player_idx);
        }

        two_level_menu(state, db, &actions, player_idx)
    }
}

// ------------------------------------------------------------------ //
// Flat menu (setup / promotion phases)
// ------------------------------------------------------------------ //

fn flat_menu(actions: &[Action], state: &GameState, db: &CardDb, player_idx: usize) -> Action {
    loop {
        println!("\nChoose:");
        for (i, action) in actions.iter().enumerate() {
            println!("  {:>2}. {}", i + 1, describe_setup_action(action, state, db, player_idx));
        }
        if let Some(n) = read_choice(actions.len()) {
            return actions[n].clone();
        }
    }
}

fn describe_setup_action(
    action: &Action,
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
) -> String {
    match action.kind {
        ActionKind::EndTurn => "Done (end setup)".to_string(),
        ActionKind::Promote => {
            let name = action.target
                .and_then(|t| get_slot(state, t))
                .map(|s| db.get_by_idx(s.card_idx).name.clone())
                .unwrap_or_else(|| "?".to_string());
            format!("Promote {} to Active", name)
        }
        ActionKind::PlayCard => {
            let player = &state.players[player_idx];
            if let Some(hidx) = action.hand_index {
                if let Some(&ci) = player.hand.get(hidx) {
                    let card = db.get_by_idx(ci);
                    if let Some(target) = action.target {
                        let pos = if target.is_active() { "active".to_string() }
                                  else { format!("bench {}", target.slot) };
                        return format!("Place {} on {}", card.name, pos);
                    }
                    return format!("Place {}", card.name);
                }
            }
            "Play card".to_string()
        }
        _ => format!("{:?}", action.kind),
    }
}

// ------------------------------------------------------------------ //
// Two-level menu
// ------------------------------------------------------------------ //

/// A first-level menu entry. May represent 1 action (execute immediately)
/// or several (show target submenu).
struct MenuItem {
    label: String,
    /// Indices into the full `actions` slice.
    action_indices: Vec<usize>,
}

fn two_level_menu(
    state: &GameState,
    db: &CardDb,
    actions: &[Action],
    player_idx: usize,
) -> Action {
    loop {
        let items = build_menu_items(actions, state, db, player_idx);

        println!("\nWhat would you like to do?");
        for (i, item) in items.iter().enumerate() {
            println!("  {:>2}. {}", i + 1, item.label);
        }

        let choice = match read_choice(items.len()) {
            Some(n) => n,
            None    => continue,
        };
        let item = &items[choice];

        // Single underlying action — execute immediately.
        if item.action_indices.len() == 1 {
            return actions[item.action_indices[0]].clone();
        }

        // Multiple targets — show submenu.
        let sub: Vec<&Action> = item.action_indices.iter().map(|&j| &actions[j]).collect();
        println!("\nChoose target:");
        for (i, action) in sub.iter().enumerate() {
            println!("  {:>2}. {}", i + 1, describe_target(action, state, db, player_idx));
        }
        println!("   0. ← Back");

        match read_choice_with_back(sub.len()) {
            Some(n) => return sub[n].clone(),
            None    => {
                render_state(state, db, player_idx);
                continue;
            }
        }
    }
}

// ------------------------------------------------------------------ //
// Build level-1 menu items
// ------------------------------------------------------------------ //

fn build_menu_items(
    actions: &[Action],
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
) -> Vec<MenuItem> {
    let mut items: Vec<MenuItem> = Vec::new();
    let player = &state.players[player_idx];

    // ── Cards (PlayCard + Evolve) grouped by hand_index ───────────────
    let mut seen_hand: std::collections::HashSet<usize> = std::collections::HashSet::new();

    for action in actions.iter() {
        if !matches!(action.kind, ActionKind::PlayCard | ActionKind::Evolve) {
            continue;
        }
        let hidx = match action.hand_index { Some(h) => h, None => continue };
        if seen_hand.contains(&hidx) { continue; }
        seen_hand.insert(hidx);

        // Collect every action that uses this hand index.
        let group: Vec<usize> = actions.iter().enumerate()
            .filter(|(_, a)| {
                matches!(a.kind, ActionKind::PlayCard | ActionKind::Evolve)
                    && a.hand_index == Some(hidx)
            })
            .map(|(j, _)| j)
            .collect();

        let label = card_level1_label(action, &group, actions, state, db, player_idx);

        // Basic Pokémon played to bench: auto-pick the first available slot — no
        // need to ask the player which bench slot number to use.
        let is_basic_bench_play = {
            let player = &state.players[player_idx];
            if action.kind == ActionKind::PlayCard {
                if let Some(&ci) = player.hand.get(hidx) {
                    let card = db.get_by_idx(ci);
                    card.kind == CardKind::Pokemon
                        && card.stage == Some(crate::types::Stage::Basic)
                        && group.len() > 1
                } else { false }
            } else { false }
        };
        let effective_indices = if is_basic_bench_play {
            vec![group[0]]
        } else {
            group
        };

        items.push(MenuItem { label, action_indices: effective_indices });
    }

    // ── Attach Energy ─────────────────────────────────────────────────
    let attach: Vec<usize> = actions.iter().enumerate()
        .filter(|(_, a)| a.kind == ActionKind::AttachEnergy)
        .map(|(j, _)| j)
        .collect();
    if !attach.is_empty() {
        let emoji = player.energy_available
            .map(|e| element_emoji(e).to_string())
            .unwrap_or_else(|| "?".to_string());
        let label = if attach.len() == 1 {
            let a = &actions[attach[0]];
            let name = a.target.and_then(|t| get_slot(state, t))
                .map(|s| db.get_by_idx(s.card_idx).name.clone())
                .unwrap_or_else(|| "?".to_string());
            let pos = a.target.map(slot_pos_label).unwrap_or_default();
            format!("Attach {} energy → {} ({})", emoji, name, pos)
        } else {
            format!("Attach {} energy", emoji)
        };
        items.push(MenuItem { label, action_indices: attach });
    }

    // ── Use Ability (one entry per Pokémon with a usable ability) ─────
    for (i, action) in actions.iter().enumerate() {
        if action.kind != ActionKind::UseAbility { continue; }
        let slot = action.target.and_then(|t| get_slot(state, t));
        let pokemon = slot.map(|s| db.get_by_idx(s.card_idx).name.clone())
            .unwrap_or_else(|| "?".to_string());
        let ability = slot.and_then(|s| db.get_by_idx(s.card_idx).ability.as_ref())
            .map(|ab| ab.name.as_str().to_owned())
            .unwrap_or_else(|| "ability".to_string());
        let pos = action.target.map(slot_pos_label).unwrap_or_default();
        let label = format!("Use {}'s {} ({})", pokemon, ability, pos);
        items.push(MenuItem { label, action_indices: vec![i] });
    }

    // ── Attacks (one entry per attack) ────────────────────────────────
    for (i, action) in actions.iter().enumerate() {
        if action.kind != ActionKind::Attack { continue; }
        let label = if let Some(ref active) = player.active {
            let card = db.get_by_idx(active.card_idx);
            let atk_idx = action.attack_index.unwrap_or(0);
            if let Some(atk) = card.attacks.get(atk_idx) {
                format!("Attack: {} ({}dmg)  [{}]", atk.name, atk.damage, format_cost(&atk.cost))
            } else { "Attack".to_string() }
        } else { "Attack".to_string() };
        items.push(MenuItem { label, action_indices: vec![i] });
    }

    // ── Retreat ───────────────────────────────────────────────────────
    let retreat: Vec<usize> = actions.iter().enumerate()
        .filter(|(_, a)| a.kind == ActionKind::Retreat)
        .map(|(j, _)| j)
        .collect();
    if !retreat.is_empty() {
        let label = if retreat.len() == 1 {
            let a = &actions[retreat[0]];
            let name = a.target.and_then(|t| get_slot(state, t))
                .map(|s| db.get_by_idx(s.card_idx).name.clone())
                .unwrap_or_else(|| "?".to_string());
            let pos = a.target.map(slot_pos_label).unwrap_or_default();
            format!("Retreat → switch in {} ({})", name, pos)
        } else {
            "Retreat".to_string()
        };
        items.push(MenuItem { label, action_indices: retreat });
    }

    // ── End Turn ──────────────────────────────────────────────────────
    if let Some((i, _)) = actions.iter().enumerate().find(|(_, a)| a.kind == ActionKind::EndTurn) {
        items.push(MenuItem { label: "End turn".to_string(), action_indices: vec![i] });
    }

    items
}

// ------------------------------------------------------------------ //
// Level-1 label for a card
// ------------------------------------------------------------------ //

fn card_level1_label(
    first: &Action,
    group: &[usize],
    all_actions: &[Action],
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
) -> String {
    let player = &state.players[player_idx];
    let hidx = match first.hand_index { Some(h) => h, None => return "Play card".to_string() };
    let ci = match player.hand.get(hidx) { Some(&c) => c, None => return "Play card".to_string() };
    let card = db.get_by_idx(ci);

    match first.kind {
        // ── Evolve ────────────────────────────────────────────────────
        ActionKind::Evolve => {
            let evo_name = &card.name;
            let base_name = card.evolves_from.as_deref().unwrap_or("?");
            if group.len() == 1 {
                let pos = first.target.map(slot_pos_label).unwrap_or_default();
                let base = first.target.and_then(|t| get_slot(state, t))
                    .map(|s| db.get_by_idx(s.card_idx).name.clone())
                    .unwrap_or_else(|| base_name.to_string());
                format!("Evolve {} → {}  ({})", base, evo_name, pos)
            } else {
                format!("Evolve {} → {} (choose target)", base_name, evo_name)
            }
        }

        // ── PlayCard ──────────────────────────────────────────────────
        ActionKind::PlayCard => {
            // Rare Candy
            if first.extra_hand_index.is_some() {
                let mut evo_names: Vec<String> = Vec::new();
                let mut seen_evo: std::collections::HashSet<String> = std::collections::HashSet::new();
                for &j in group {
                    if let Some(ehidx) = all_actions[j].extra_hand_index {
                        if let Some(&eci) = player.hand.get(ehidx) {
                            let name = db.get_by_idx(eci).name.clone();
                            if seen_evo.insert(name.clone()) { evo_names.push(name); }
                        }
                    }
                }
                let targets: Vec<String> = {
                    let mut bases: Vec<String> = Vec::new();
                    let mut seen_base: std::collections::HashSet<String> = std::collections::HashSet::new();
                    for &j in group {
                        let base = all_actions[j].target
                            .and_then(|t| get_slot(state, t))
                            .map(|s| db.get_by_idx(s.card_idx).name.clone())
                            .unwrap_or_else(|| "?".to_string());
                        if seen_base.insert(base.clone()) { bases.push(base); }
                    }
                    bases
                };
                let base_str = targets.join(" / ");
                let evo_str = evo_names.join(" / ");
                if group.len() == 1 {
                    let pos = first.target.map(slot_pos_label).unwrap_or_default();
                    return format!("Rare Candy: {} → {}  ({})", base_str, evo_str, pos);
                }
                return format!("Rare Candy: {} → {}", base_str, evo_str);
            }

            match card.kind {
                CardKind::Pokemon => {
                    // Always show a simple label — bench slot selection is handled
                    // automatically (first free slot), no need to expose the slot index.
                    format!("Play {} to bench", card.name)
                }
                CardKind::Tool => {
                    if group.len() == 1 {
                        let poke = first.target.and_then(|t| get_slot(state, t))
                            .map(|s| db.get_by_idx(s.card_idx).name.clone())
                            .unwrap_or_else(|| "?".to_string());
                        let pos = first.target.map(slot_pos_label).unwrap_or_default();
                        format!("Attach {} to {} ({})", card.name, poke, pos)
                    } else {
                        format!("Attach {} (choose target)", card.name)
                    }
                }
                CardKind::Item => {
                    let has_heal = card.trainer_effects.iter().any(|e| matches!(
                        e,
                        EffectKind::HealTarget { .. } | EffectKind::HealAndCureStatus { .. }
                    ));
                    if has_heal && group.len() == 1 {
                        let slot = first.target.and_then(|t| get_slot(state, t));
                        let name = slot.map(|s| db.get_by_idx(s.card_idx).name.clone())
                            .unwrap_or_else(|| "?".to_string());
                        let hp = slot.map(|s| format!(" ({}/{}HP)", s.current_hp, s.max_hp))
                            .unwrap_or_default();
                        format!("Play {} → heal {}{}", card.name, name, hp)
                    } else {
                        format!("Play {}", card.name)
                    }
                }
                CardKind::Supporter => format!("Play {}", card.name),
            }
        }

        _ => "Play card".to_string(),
    }
}

// ------------------------------------------------------------------ //
// Level-2 target description
// ------------------------------------------------------------------ //

fn describe_target(
    action: &Action,
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
) -> String {
    let player = &state.players[player_idx];

    match action.kind {
        // PlayCard targets
        ActionKind::PlayCard => {
            let hidx = match action.hand_index { Some(h) => h, None => return "?".to_string() };
            let ci = match player.hand.get(hidx) { Some(&c) => c, None => return "?".to_string() };
            let card = db.get_by_idx(ci);

            // Rare Candy
            if let Some(ehidx) = action.extra_hand_index {
                let evo_name = player.hand.get(ehidx)
                    .map(|&ei| db.get_by_idx(ei).name.clone())
                    .unwrap_or_else(|| "?".to_string());
                let base_name = action.target.and_then(|t| get_slot(state, t))
                    .map(|s| db.get_by_idx(s.card_idx).name.clone())
                    .unwrap_or_else(|| "?".to_string());
                let pos = action.target.map(slot_pos_label).unwrap_or_default();
                return format!("{} ({}) → {}", base_name, pos, evo_name);
            }

            if let Some(target) = action.target {
                let slot = get_slot(state, target);
                let name = slot.map(|s| db.get_by_idx(s.card_idx).name.clone())
                    .unwrap_or_else(|| "?".to_string());
                let pos = slot_pos_label(target);

                match card.kind {
                    CardKind::Item => {
                        let hp = slot.map(|s| format!(", {}/{} HP", s.current_hp, s.max_hp))
                            .unwrap_or_default();
                        format!("{} ({}{})", name, pos, hp)
                    }
                    CardKind::Tool => format!("{} ({})", name, pos),
                    CardKind::Pokemon => format!("bench slot {}", target.slot),
                    _ => format!("{} ({})", name, pos),
                }
            } else {
                "?".to_string()
            }
        }

        // Evolve targets
        ActionKind::Evolve => {
            let name = action.target.and_then(|t| get_slot(state, t))
                .map(|s| db.get_by_idx(s.card_idx).name.clone())
                .unwrap_or_else(|| "?".to_string());
            let pos = action.target.map(slot_pos_label).unwrap_or_default();
            format!("{} ({})", name, pos)
        }

        // Attach energy targets
        ActionKind::AttachEnergy => {
            let slot = action.target.and_then(|t| get_slot(state, t));
            let name = slot.map(|s| db.get_by_idx(s.card_idx).name.clone())
                .unwrap_or_else(|| "?".to_string());
            let energy = slot.map(|s| {
                let total: u8 = s.energy.iter().sum();
                format!(", {} energy attached", total)
            }).unwrap_or_default();
            let pos = action.target.map(slot_pos_label).unwrap_or_default();
            format!("{} ({}{})", name, pos, energy)
        }

        // Retreat targets
        ActionKind::Retreat => {
            let slot = action.target.and_then(|t| get_slot(state, t));
            let name = slot.map(|s| db.get_by_idx(s.card_idx).name.clone())
                .unwrap_or_else(|| "?".to_string());
            let hp = slot.map(|s| format!(", {}/{} HP", s.current_hp, s.max_hp))
                .unwrap_or_default();
            let pos = action.target.map(slot_pos_label).unwrap_or_default();
            format!("{} ({}{})", name, pos, hp)
        }

        _ => format!("{:?}", action.kind),
    }
}

// ------------------------------------------------------------------ //
// Slot position label
// ------------------------------------------------------------------ //

fn slot_pos_label(slot_ref: crate::actions::SlotRef) -> String {
    if slot_ref.is_active() { "active".to_string() }
    else { format!("bench {}", slot_ref.slot) }
}

// ------------------------------------------------------------------ //
// stdin helpers
// ------------------------------------------------------------------ //

fn read_choice(max: usize) -> Option<usize> {
    print!("Choose (1-{}): ", max);
    let _ = io::stdout().flush();
    let mut line = String::new();
    match io::stdin().lock().read_line(&mut line) {
        // EOF (Ctrl-D / closed stdin) — the trait can't return None for
        // "exit cleanly", and silently returning Some(0) (= first option)
        // can cause a runaway loop or unintended action. Make the failure
        // mode loud and explicit instead.
        Ok(0) => panic!("HumanAgent: stdin closed (EOF) while reading menu choice; exiting"),
        Ok(_) => {
            let n: usize = line.trim().parse().ok()?;
            if n >= 1 && n <= max { Some(n - 1) } else { None }
        }
        Err(e) => panic!("HumanAgent: stdin read failed ({}); exiting", e),
    }
}

fn read_choice_with_back(max: usize) -> Option<usize> {
    print!("Choose (0=back, 1-{}): ", max);
    let _ = io::stdout().flush();
    let mut line = String::new();
    match io::stdin().lock().read_line(&mut line) {
        // See note in read_choice — fail loudly on EOF rather than silently
        // mapping to "back" or the first option.
        Ok(0) => panic!("HumanAgent: stdin closed (EOF) while reading menu choice; exiting"),
        Ok(_) => {
            let n: usize = line.trim().parse().ok()?;
            if n == 0 { None } else if n <= max { Some(n - 1) } else { None }
        }
        Err(e) => panic!("HumanAgent: stdin read failed ({}); exiting", e),
    }
}
