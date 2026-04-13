//! Terminal board renderer — in-place, card-outline UI.
//!
//! Layout mirrors the real PTCGP board:
//!   opponent bench (3)
//!   opponent active (centred)
//!   ── turn divider ──
//!   your active (centred)
//!   your bench (3)
//!   your hand (card names)

use colored::Colorize;
use crate::card::CardDb;
use crate::state::{GameState, PokemonSlot};
use crate::types::{CostSymbol, Element, StatusEffect};

// ------------------------------------------------------------------ //
// Rolling event log (opponent narration)
// ------------------------------------------------------------------ //

use std::sync::Mutex;
static EVENT_LOG: Mutex<Vec<String>> = Mutex::new(Vec::new());
const LOG_SIZE: usize = 6;

pub fn push_event(msg: String) {
    if let Ok(mut log) = EVENT_LOG.lock() {
        log.push(msg);
        if log.len() > LOG_SIZE {
            log.remove(0);
        }
    }
}

// ------------------------------------------------------------------ //
// Card dimensions
// ------------------------------------------------------------------ //

/// Inner width of a bench card (between the │ borders).
const BENCH_W: usize = 18;

/// Inner width of the active card (between the │ borders).
const ACTIVE_W: usize = 32;

// ------------------------------------------------------------------ //
// Public API
// ------------------------------------------------------------------ //

pub fn render_state(state: &GameState, db: &CardDb, human_player: usize) {
    // Clear and redraw from top.
    print!("\x1B[2J\x1B[H");

    let opp         = 1 - human_player;
    let turn_num    = state.turn_number.max(0) as u32 / 2 + 1;
    let is_your_turn = state.current_player == human_player;

    // ── Opponent header ──────────────────────────────────────────────
    let opp_p = &state.players[opp];
    let opp_header = format!(
        " OPPONENT  ·  Points: {}/3  ·  Deck: {}  ·  Hand: {} cards",
        opp_p.points, opp_p.deck.len(), opp_p.hand.len()
    );
    if !is_your_turn {
        println!("{}", opp_header.red().bold());
    } else {
        println!("{}", opp_header.dimmed());
    }
    println!();

    // ── Opponent bench ───────────────────────────────────────────────
    print_bench_row(state, db, opp);
    println!();

    // ── Opponent active ──────────────────────────────────────────────
    print_active_centred(state, db, opp, false);
    println!();

    // ── Turn divider ─────────────────────────────────────────────────
    let divider = "═".repeat(62);
    if is_your_turn {
        println!("{}", format!(" {}", divider).dimmed());
        println!("{}", "         ▲  YOUR TURN  ▲  (turn {})".replace("{}", &turn_num.to_string()).green().bold());
        println!("{}", format!(" {}", divider).dimmed());
    } else {
        println!("{}", format!(" {}", divider).dimmed());
        println!("{}", "         ▼  OPPONENT'S TURN  ▼".red().bold());
        println!("{}", format!(" {}", divider).dimmed());
    }
    println!();

    // ── Your active ──────────────────────────────────────────────────
    print_active_centred(state, db, human_player, true);
    println!();

    // ── Your bench ───────────────────────────────────────────────────
    let your_p = &state.players[human_player];
    let energy_tag = your_p.energy_available
        .map(|e| format!("  ·  Energy ready: {}", element_emoji(e)))
        .unwrap_or_default();
    let your_header = format!(" YOU  ·  Points: {}/3  ·  Deck: {}{}", your_p.points, your_p.deck.len(), energy_tag);
    if is_your_turn {
        println!("{}", your_header.green().bold());
    } else {
        println!("{}", your_header.dimmed());
    }
    println!();

    print_bench_row(state, db, human_player);
    println!();

    // ── Hand ─────────────────────────────────────────────────────────
    if !your_p.hand.is_empty() {
        let names: Vec<String> = your_p.hand.iter().enumerate()
            .map(|(i, &idx)| format!("[{}] {}", i + 1, db.get_by_idx(idx).name))
            .collect();
        println!(" Hand: {}", names.join("   ").cyan());
        println!();
    }

    // ── Event log ────────────────────────────────────────────────────
    if let Ok(log) = EVENT_LOG.lock() {
        if !log.is_empty() {
            println!(" {}", "Recent:".bold());
            for entry in log.iter() {
                println!("   · {}", entry.dimmed());
            }
            println!();
        }
    }
}

// ------------------------------------------------------------------ //
// Bench row (3 cards side-by-side)
// ------------------------------------------------------------------ //

fn print_bench_row(state: &GameState, db: &CardDb, player_idx: usize) {
    let player = &state.players[player_idx];
    let cards: Vec<Vec<String>> = (0..3).map(|j| {
        match &player.bench[j] {
            Some(slot) => bench_card_lines(slot, db),
            None       => empty_bench_lines(),
        }
    }).collect();

    let rows = cards[0].len();
    for r in 0..rows {
        print!(" ");
        for (i, card) in cards.iter().enumerate() {
            print!("{}", card[r]);
            if i < 2 { print!("   "); }
        }
        println!();
    }
}

// ------------------------------------------------------------------ //
// Active card (centred, wider)
// ------------------------------------------------------------------ //

fn print_active_centred(state: &GameState, db: &CardDb, player_idx: usize, is_you: bool) {
    let player = &state.players[player_idx];
    let lines = match &player.active {
        Some(slot) => active_card_lines(slot, db, is_you),
        None       => active_empty_lines(is_you),
    };

    // Total width of a bench row = 3*(BENCH_W+2) + 3*3 = 3*20+9 = 69
    // Centre the active card (ACTIVE_W+2 wide) within that.
    let bench_row_w: usize = 3 * (BENCH_W + 2) + 3 * 3;  // 69
    let active_total_w = ACTIVE_W + 2;
    let left_pad = (bench_row_w.saturating_sub(active_total_w)) / 2;
    let indent = " ".repeat(left_pad + 1); // +1 for the leading space in bench rows

    for line in &lines {
        println!("{}{}", indent, line);
    }
}

// ------------------------------------------------------------------ //
// Bench card box  (BENCH_W + 2 wide)
// ------------------------------------------------------------------ //

fn bench_card_lines(slot: &PokemonSlot, db: &CardDb) -> Vec<String> {
    let w = BENCH_W;
    let card = db.get_by_idx(slot.card_idx);

    let ex_tag   = if card.is_ex { " ex" } else { "" };
    let elem_tag = card.element.map(element_emoji).unwrap_or("");
    let name     = format!("{}{}{}", elem_tag, card.name, ex_tag);

    let hp_str   = format!("HP {}/{}", slot.current_hp, slot.max_hp);
    let energy   = format_energy_str(slot);
    let status   = format_status_str(slot.status);
    let tool     = slot.tool_idx
        .map(|t| format!("🔧 {}", db.get_by_idx(t).name))
        .unwrap_or_default();

    let mut lines: Vec<String> = Vec::new();
    lines.push(box_top(w));
    lines.push(box_line(&name, w));
    lines.push(box_line(&hp_str, w));
    if !energy.is_empty() {
        lines.push(box_line(&energy, w));
    } else {
        lines.push(box_line("No energy", w));
    }
    if !status.is_empty() {
        lines.push(box_line_colored(&status, w));
    } else {
        lines.push(box_line("", w));
    }
    if !tool.is_empty() {
        lines.push(box_line(&tool, w));
    } else {
        lines.push(box_line("", w));
    }
    lines.push(box_bot(w));
    lines
}

fn empty_bench_lines() -> Vec<String> {
    let w = BENCH_W;
    let rows = 7; // top + 5 content + bot
    let mut lines = vec![box_top(w).dimmed().to_string()];
    let mid = rows / 2;
    for i in 1..(rows - 1) {
        if i == mid {
            lines.push(box_line("(empty)", w).dimmed().to_string());
        } else {
            lines.push(box_line("", w).dimmed().to_string());
        }
    }
    lines.push(box_bot(w).dimmed().to_string());
    lines
}

// ------------------------------------------------------------------ //
// Active card box  (ACTIVE_W + 2 wide, includes attack descriptions)
// ------------------------------------------------------------------ //

fn active_card_lines(slot: &PokemonSlot, db: &CardDb, is_you: bool) -> Vec<String> {
    let w = ACTIVE_W;
    let card = db.get_by_idx(slot.card_idx);

    let ex_tag   = if card.is_ex { " ex" } else { "" };
    let elem_tag = card.element.map(element_emoji).unwrap_or("");
    let name     = format!("★ {}{}{}", elem_tag, card.name, ex_tag);
    let hp_str   = format!("HP {}/{}", slot.current_hp, slot.max_hp);
    let energy   = format_energy_str(slot);
    let status   = format_status_str(slot.status);
    let tool     = slot.tool_idx
        .map(|t| format!("🔧 {}", db.get_by_idx(t).name))
        .unwrap_or_default();

    let mut lines: Vec<String> = Vec::new();
    lines.push(box_top(w));
    lines.push(box_line(&name, w));
    lines.push(box_line(&hp_str, w));

    // Energy + status on same line if both present, else separate
    let energy_display = if energy.is_empty() { "No energy".to_string() } else { energy };
    if !status.is_empty() {
        // Two-segment line: energy left, status right
        let status_plain = strip_ansi(&status);
        let gap = w.saturating_sub(visible_len(&energy_display) + visible_len(&status_plain) + 1);
        let combined = format!("{}{}{}",
            energy_display,
            " ".repeat(gap + 1),
            status
        );
        lines.push(box_line_raw(&combined, w));
    } else {
        lines.push(box_line(&energy_display, w));
    }

    if !tool.is_empty() {
        lines.push(box_line(&tool, w));
    }

    // Separator
    lines.push(box_separator(w));

    // Attacks
    for atk in &card.attacks {
        let cost_str  = format_cost_emojis(&atk.cost);
        let dmg_str   = if atk.damage > 0 { format!("{}dmg", atk.damage) } else { String::new() };

        // Header line: "  Vine Whip  40dmg  [🌿○]"
        let atk_header = if dmg_str.is_empty() {
            format!("{} [{}]", atk.name, cost_str)
        } else {
            format!("{} — {} [{}]", atk.name, dmg_str, cost_str)
        };
        lines.push(box_line(&atk_header, w));

        // Effect text (word-wrapped to fit)
        if !atk.effect_text.is_empty() {
            for chunk in word_wrap(&atk.effect_text, w - 2) {
                lines.push(box_line(&format!("  {}", chunk), w));
            }
        }
    }

    lines.push(box_bot(w));

    // Highlight active Pokemon with a colour border
    if is_you {
        lines.iter().map(|l| l.green().to_string()).collect()
    } else {
        lines.iter().map(|l| l.red().to_string()).collect()
    }
}

fn active_empty_lines(is_you: bool) -> Vec<String> {
    let w = ACTIVE_W;
    let inner = if is_you { "(no active — choose a Pokémon)" } else { "(no active)" };
    let mut lines = vec![
        box_top(w),
        box_line("", w),
        box_line(inner, w),
        box_line("", w),
        box_bot(w),
    ];
    if is_you {
        lines = lines.iter().map(|l| l.green().to_string()).collect();
    } else {
        lines = lines.iter().map(|l| l.dimmed().to_string()).collect();
    }
    lines
}

// ------------------------------------------------------------------ //
// Box drawing primitives
// ------------------------------------------------------------------ //

fn box_top(w: usize) -> String {
    format!("╔{}╗", "═".repeat(w))
}

fn box_bot(w: usize) -> String {
    format!("╚{}╝", "═".repeat(w))
}

fn box_separator(w: usize) -> String {
    format!("╠{}╣", "─".repeat(w))
}

/// Pad plain text to fill the box interior.
fn box_line(text: &str, w: usize) -> String {
    let vlen = visible_len(text);
    let pad  = if vlen < w { w - vlen } else { 0 };
    format!("║{}{}║", text, " ".repeat(pad))
}

/// Like box_line but `text` may contain ANSI codes (coloured status badges).
fn box_line_colored(text: &str, w: usize) -> String {
    // text may include ANSI escapes; use visible_len for padding.
    let vlen = visible_len(text);
    let pad  = if vlen < w { w - vlen } else { 0 };
    format!("║{}{}║", text, " ".repeat(pad))
}

/// Accept a pre-built raw string that already has correct visible width.
fn box_line_raw(text: &str, w: usize) -> String {
    let vlen = visible_len(text);
    let pad  = if vlen < w { w - vlen } else { 0 };
    format!("║{}{}║", text, " ".repeat(pad))
}

// ------------------------------------------------------------------ //
// Formatting helpers
// ------------------------------------------------------------------ //

fn format_energy_str(slot: &PokemonSlot) -> String {
    let elements = [
        Element::Grass, Element::Fire, Element::Water, Element::Lightning,
        Element::Psychic, Element::Fighting, Element::Darkness, Element::Metal,
    ];
    let parts: Vec<String> = elements.iter().filter_map(|&el| {
        let n = slot.energy[el.idx()] as usize;
        if n > 0 { Some(format!("{}", element_emoji(el).repeat(n))) } else { None }
    }).collect();
    parts.join(" ")
}

fn format_status_str(status: u8) -> String {
    let mut parts: Vec<&str> = Vec::new();
    if status & StatusEffect::Poisoned.bit()  != 0 { parts.push("PSN"); }
    if status & StatusEffect::Burned.bit()    != 0 { parts.push("BRN"); }
    if status & StatusEffect::Paralyzed.bit() != 0 { parts.push("PAR"); }
    if status & StatusEffect::Asleep.bit()    != 0 { parts.push("SLP"); }
    if status & StatusEffect::Confused.bit()  != 0 { parts.push("CNF"); }
    if parts.is_empty() {
        String::new()
    } else {
        format!("[{}]", parts.join("|")).yellow().to_string()
    }
}

/// Format cost as emoji string without numbers — e.g. "🔥🔥○"
fn format_cost_emojis(cost: &[CostSymbol]) -> String {
    cost.iter().map(|c| match c.to_element() {
        Some(el) => element_emoji(el).to_string(),
        None     => "○".to_string(),
    }).collect()
}

/// Public version used by human.rs action descriptions.
pub fn format_cost(cost: &[CostSymbol]) -> String {
    format_cost_emojis(cost)
}

pub fn element_emoji(el: Element) -> &'static str {
    match el {
        Element::Grass     => "🌿",
        Element::Fire      => "🔥",
        Element::Water     => "💧",
        Element::Lightning => "⚡",
        Element::Psychic   => "🔮",
        Element::Fighting  => "👊",
        Element::Darkness  => "🌑",
        Element::Metal     => "⚙️",
    }
}

// ------------------------------------------------------------------ //
// Text utilities
// ------------------------------------------------------------------ //

/// Visible character width: emoji = 2, ASCII = 1; strips ANSI sequences.
fn visible_len(s: &str) -> usize {
    let mut len = 0usize;
    let mut in_esc = false;
    for ch in s.chars() {
        if ch == '\x1B' { in_esc = true; }
        if in_esc {
            if ch == 'm' { in_esc = false; }
            continue;
        }
        len += if (ch as u32) > 127 { 2 } else { 1 };
    }
    len
}

/// Strip all ANSI escape sequences from a string.
fn strip_ansi(s: &str) -> String {
    let mut out = String::new();
    let mut in_esc = false;
    for ch in s.chars() {
        if ch == '\x1B' { in_esc = true; }
        if in_esc {
            if ch == 'm' { in_esc = false; }
            continue;
        }
        out.push(ch);
    }
    out
}

/// Greedy word-wrap to `max_w` visible columns.
fn word_wrap(text: &str, max_w: usize) -> Vec<String> {
    let mut lines: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut current_len = 0usize;

    for word in text.split_whitespace() {
        let wlen = word.chars().map(|c| if (c as u32) > 127 { 2 } else { 1 }).sum::<usize>();
        if current_len == 0 {
            current.push_str(word);
            current_len = wlen;
        } else if current_len + 1 + wlen <= max_w {
            current.push(' ');
            current.push_str(word);
            current_len += 1 + wlen;
        } else {
            lines.push(current.clone());
            current = word.to_string();
            current_len = wlen;
        }
    }
    if !current.is_empty() { lines.push(current); }
    if lines.is_empty() { lines.push(String::new()); }
    lines
}
