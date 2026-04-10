//! Terminal board renderer — read-only, never mutates state.

use colored::Colorize;
use crate::card::CardDb;
use crate::state::{GameState, PokemonSlot};
use crate::types::{Element, StatusEffect};

// ------------------------------------------------------------------ //
// Public API
// ------------------------------------------------------------------ //

/// Print the full board state to stdout.
///
/// `human_player` controls which player's hand is shown in full
/// and which side of the turn indicator is highlighted.
pub fn render_state(state: &GameState, db: &CardDb, human_player: usize) {
    let separator = "─".repeat(60);
    println!("{}", separator);
    println!("{}", "Pokemon TCG Pocket".bold());
    println!("{}", separator);

    let opponent_idx = 1 - human_player;
    render_player_section(state, db, opponent_idx, "OPPONENT", false);
    println!();

    if state.current_player == human_player {
        println!("{}", ">>> YOUR TURN <<<".green().bold());
    } else {
        println!("{}", ">>> OPPONENT'S TURN <<<".red().bold());
    }
    println!();

    render_player_section(state, db, human_player, "YOU", true);
    println!("{}", separator);
}

// ------------------------------------------------------------------ //
// Internal helpers
// ------------------------------------------------------------------ //

fn render_player_section(
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
    label: &str,
    show_hand: bool,
) {
    let player = &state.players[player_idx];
    let turn_display = (state.turn_number.max(0) as u32 + 1) / 2;

    let header = format!(
        "[ {} ]  Points: {}/3  |  Deck: {}  |  Hand: {}  |  Turn: {}",
        label,
        player.points,
        player.deck.len(),
        player.hand.len(),
        turn_display,
    );
    if player_idx == state.current_player {
        println!("{}", header.bold());
    } else {
        println!("{}", header.dimmed());
    }

    // Energy available
    if let Some(el) = player.energy_available {
        if player_idx == state.current_player {
            println!("  Energy available: {}", element_symbol(el).yellow());
        }
    }

    // Active pokemon
    if let Some(ref active) = player.active {
        println!("  ACTIVE: {}", format_slot_full(active, db).green());
        // Show attacks
        let card = db.get_by_idx(active.card_idx);
        for (i, atk) in card.attacks.iter().enumerate() {
            let cost_str = atk.cost.iter()
                .map(|c| format!("{:?}", c))
                .collect::<Vec<_>>()
                .join(",");
            println!(
                "    ATK{}: {} ({}dmg) [{}]",
                i + 1, atk.name, atk.damage, cost_str
            );
        }
    } else {
        println!("  ACTIVE: {}", "[empty]".dimmed());
    }

    // Bench
    let bench_str: Vec<String> = player.bench.iter().map(|slot| {
        match slot {
            Some(s) => format_slot_short(s, db),
            None    => "---".dimmed().to_string(),
        }
    }).collect();
    println!("  BENCH:  {}", bench_str.join("  "));

    // Hand (only shown for the human player)
    if show_hand && !player.hand.is_empty() {
        let hand_names: Vec<String> = player.hand.iter()
            .map(|&idx| db.get_by_idx(idx).name.clone())
            .collect();
        println!("  HAND:   {}", hand_names.join(", ").cyan());
    }
}

fn format_slot_full(slot: &PokemonSlot, db: &CardDb) -> String {
    let card = db.get_by_idx(slot.card_idx);
    let ex_tag = if card.is_ex { " EX" } else { "" };
    let hp_str = format!("{}/{}", slot.current_hp, slot.max_hp);
    let energy_str = format_energy(slot);
    let status_str = format_status(slot.status);
    let energy_tag = if energy_str.is_empty() {
        String::new()
    } else {
        format!("  [{} energy]", energy_str)
    };
    let status_tag = if status_str.is_empty() {
        String::new()
    } else {
        format!("  {}", status_str)
    };
    let tool_tag = if slot.tool_idx.is_some() { "  [Tool]" } else { "" };
    format!("{}{} ({}){}{}{}", card.name, ex_tag, hp_str, energy_tag, status_tag, tool_tag)
}

fn format_slot_short(slot: &PokemonSlot, db: &CardDb) -> String {
    let card = db.get_by_idx(slot.card_idx);
    let ex_tag = if card.is_ex { "*" } else { "" };
    let energy_str = format_energy(slot);
    let energy_tag = if energy_str.is_empty() {
        String::new()
    } else {
        format!(" {}", energy_str)
    };
    let tool_tag = if slot.tool_idx.is_some() { " T" } else { "" };
    format!("[{}{} {}/{}{}{}]", card.name, ex_tag, slot.current_hp, slot.max_hp, energy_tag, tool_tag)
}

fn format_energy(slot: &PokemonSlot) -> String {
    let elements = [
        Element::Grass, Element::Fire, Element::Water, Element::Lightning,
        Element::Psychic, Element::Fighting, Element::Darkness, Element::Metal,
    ];
    let parts: Vec<String> = elements.iter()
        .filter_map(|&el| {
            let n = slot.energy[el.idx()];
            if n > 0 { Some(format!("{}{}", n, element_symbol(el))) } else { None }
        })
        .collect();
    parts.join(" ")
}

fn format_status(status: u8) -> String {
    let mut parts: Vec<&str> = Vec::new();
    if status & StatusEffect::Poisoned.bit()  != 0 { parts.push("PSN"); }
    if status & StatusEffect::Burned.bit()    != 0 { parts.push("BRN"); }
    if status & StatusEffect::Paralyzed.bit() != 0 { parts.push("PAR"); }
    if status & StatusEffect::Asleep.bit()    != 0 { parts.push("SLP"); }
    if status & StatusEffect::Confused.bit()  != 0 { parts.push("CNF"); }
    if parts.is_empty() {
        String::new()
    } else {
        format!("[{}]", parts.join(",")).yellow().to_string()
    }
}

fn element_symbol(el: Element) -> &'static str {
    match el {
        Element::Grass     => "G",
        Element::Fire      => "R",
        Element::Water     => "W",
        Element::Lightning => "L",
        Element::Psychic   => "P",
        Element::Fighting  => "F",
        Element::Darkness  => "D",
        Element::Metal     => "M",
    }
}
