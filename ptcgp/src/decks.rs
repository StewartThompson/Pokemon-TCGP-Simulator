//! Built-in sample decks for the PTCGP simulator.

use crate::types::Element;

// ------------------------------------------------------------------ //
// Grass deck — Bulbasaur line + Caterpie/Petilil + trainers
// ------------------------------------------------------------------ //

pub const GRASS_DECK: &[&str] = &[
    "a1-001", "a1-001",   // Bulbasaur x2
    "a1-002", "a1-002",   // Ivysaur x2
    "a1-004", "a1-004",   // Venusaur ex x2
    "a1-225", "a1-225",   // Sabrina x2
    "a1-219", "a1-219",   // Erika x2
    "pa-005", "pa-005",   // Pokeball x2
    "a1-029", "a1-029",   // Petilil x2
    "a1-030", "a1-030",   // Lilligant x2
    "pa-001", "pa-001",   // Potion x2
    "pa-007", "pa-007",   // Professor's Research x2
];
pub const GRASS_ENERGY: &[Element] = &[Element::Grass];

// ------------------------------------------------------------------ //
// Fire deck — Charmander/Charizard ex + Vulpix/Ninetales + Weedle line
// ------------------------------------------------------------------ //

pub const FIRE_DECK: &[&str] = &[
    "a1-230", "a1-230",     // Charmander x2
    "a2b-010", "a2b-010",   // Charizard ex x2
    "a1-037", "a1-037",     // Vulpix x2
    "a1-038", "a1-038",     // Ninetales x2
    "a3-144", "a3-144",     // Rare Candy x2
    "a2-154", "a2-154",     // Dawn x2
    "a2-148", "a2-148",     // Beedrill x2
    "pa-005", "pa-005",     // Poke Ball x2
    "pa-001", "pa-001",     // Potion x2
    "a2-147", "a2-147",     // Giant Cape x2
];
pub const FIRE_ENERGY: &[Element] = &[Element::Fire];

// ------------------------------------------------------------------ //
// Lookup
// ------------------------------------------------------------------ //

/// Returns `(card_id_slice, energy_type_slice)` for a named deck.
///
/// Recognised names: `"grass"`, `"fire"` (case-insensitive).
/// Returns `None` for unknown names.
pub fn get_sample_deck(name: &str) -> Option<(&'static [&'static str], &'static [Element])> {
    match name.trim().to_lowercase().as_str() {
        "grass" => Some((GRASS_DECK, GRASS_ENERGY)),
        "fire"  => Some((FIRE_DECK, FIRE_ENERGY)),
        _       => None,
    }
}
