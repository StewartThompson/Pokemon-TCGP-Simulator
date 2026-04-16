//! Built-in sample decks for the PTCGP simulator.

use crate::card::CardDb;
use crate::types::{CardKind, Element, Stage};

// ------------------------------------------------------------------ //
// Grass deck — Bulbasaur line + Petilil/Lilligant + trainers
// ------------------------------------------------------------------ //

pub const GRASS_DECK: &[&str] = &[
    "a1-001", "a1-001",   // Bulbasaur x2
    "a1-002", "a1-002",   // Ivysaur x2
    "a1-004", "a1-004",   // Venusaur ex x2
    "a1-225", "a1-225",   // Sabrina x2
    "a1-219", "a1-219",   // Erika x2
    "pa-005", "pa-005",   // Poké Ball x2
    "a1-029", "a1-029",   // Petilil x2
    "a1-030", "a1-030",   // Lilligant x2
    "pa-001", "pa-001",   // Potion x2
    "pa-007", "pa-007",   // Professor's Research x2
];
pub const GRASS_ENERGY: &[Element] = &[Element::Grass];

// ------------------------------------------------------------------ //
// Fire deck — Charmander/Charizard ex + Vulpix/Ninetales
// ------------------------------------------------------------------ //

pub const FIRE_DECK: &[&str] = &[
    "a1-230", "a1-230",     // Charmander x2
    "a2b-010", "a2b-010",   // Charizard ex x2
    "a1-037", "a1-037",     // Vulpix x2
    "a1-038", "a1-038",     // Ninetales x2
    "a3-144", "a3-144",     // Rare Candy x2
    "a2-154", "a2-154",     // Dawn x2
    "a2-148", "a2-148",     // Rocky Helmet x2
    "pa-005", "pa-005",     // Poké Ball x2
    "pa-001", "pa-001",     // Potion x2
    "a2-147", "a2-147",     // Giant Cape x2
];
pub const FIRE_ENERGY: &[Element] = &[Element::Fire];

// ------------------------------------------------------------------ //
// Mewtwo ex deck — Psychic powerhouse
// Gardevoir's Psy Shadow ability accelerates energy each turn;
// Psydrive hits 150 dmg at full steam
// ------------------------------------------------------------------ //

pub const MEWTWO_EX_DECK: &[&str] = &[
    "a1-129", "a1-129",   // Mewtwo ex x2   (Psydrive 150 dmg)
    "a1-130", "a1-130",   // Ralts x2       (Gardevoir base)
    "a1-131", "a1-131",   // Kirlia x2      (Gardevoir mid-stage)
    "a1-132", "a1-132",   // Gardevoir x2   (Psy Shadow: attach Psychic energy each turn)
    "a1-225", "a1-225",   // Sabrina x2     (switch opponent's active)
    "a1-223", "a1-223",   // Giovanni x2    (+10 damage this turn)
    "a3-144", "a3-144",   // Rare Candy x2  (skip Kirlia; Ralts → Gardevoir)
    "pa-007", "pa-007",   // Professor's Research x2
    "pa-005", "pa-005",   // Poké Ball x2
    "pa-001", "pa-001",   // Potion x2
];
pub const MEWTWO_EX_ENERGY: &[Element] = &[Element::Psychic];

// ------------------------------------------------------------------ //
// Nihilego deck — Darkness/Poison control
//
// Strategy: poison the opponent early, activate Nihilego's "More Poison"
// ability to add +20 extra poison damage per turn, then sweep with
// Paldean Clodsire ex (Venoshock: 60+60=120 when poisoned) and Absol
// (Unseen Claw: 20+60=80 when any status condition).
//
// Paldean Wooper poisons cheaply (Poison Jab: 10+poison, 1 Darkness).
// Nihilego's New Wave also poisons (30+poison, 2 energy).
// Sabrina pulls a benched target into the active slot to keep the
// poison pressure on the highest-value target.
// ------------------------------------------------------------------ //

pub const NIHILEGO_DECK: &[&str] = &[
    "a3a-103", "a3a-103", // Nihilego x2           (More Poison: +20 poison/turn; New Wave 30+poison)
    "a2b-047", "a2b-047", // Paldean Wooper x2     (Poison Jab: 10+poison for 1 Darkness — cheap poison)
    "a2b-048", "a2b-048", // Paldean Clodsire ex x2 (Venoshock: 60+60=120 when poisoned, 2 Darkness)
    "a3-112",  "a3-112",  // Absol x2              (Unseen Claw: 20+60=80 when any status, D+C)
    "a1-223",  "a1-223",  // Giovanni x2           (+10 damage this turn)
    "a1-225",  "a1-225",  // Sabrina x2            (pull opponent's bench Pokémon to active)
    "a3-146",  "a3-146",  // Poison Barb x2        (Tool: may poison attacker on hit)
    "pa-005",  "pa-005",  // Poké Ball x2
    "pa-007",  "pa-007",  // Professor's Research x2
    "pa-001",  "pa-001",  // Potion x2
];
pub const NIHILEGO_ENERGY: &[Element] = &[Element::Darkness];

// ------------------------------------------------------------------ //
// Celebi ex deck — Grass energy burst
//
// Strategy: Celebi ex "Powerful Bloom" flips a coin per energy — 50
// damage per heads.  Exeggcute (Growth Spurt) self-attaches an extra
// Grass energy each turn, then evolves into Alolan Exeggutor (150 dmg
// coin-flip powerhouse).  Dhelmise provides a reliable 90-damage backup
// once 3+ Grass are loaded.  Erika heals to extend Celebi ex's life.
// ------------------------------------------------------------------ //

pub const CELEBI_EX_DECK: &[&str] = &[
    "a3a-099", "a3a-099", // Celebi ex x2           (Powerful Bloom 50× per heads per energy)
    "a1a-001", "a1a-001", // Exeggcute x2           (Growth Spurt: attach extra Grass to self → evolves to Alolan Exeggutor)
    "a3-002",  "a3-002",  // Alolan Exeggutor x2    (150HP Stage 1; Tropical Hammer 150 — coin-flip nuke)
    "a1a-009", "a1a-009", // Dhelmise x2            (Energy Whip 20 + 70 bonus with 3+ Grass = 90)
    "a1-219",  "a1-219",  // Erika x2               (heal 50 HP to a Grass Pokémon)
    "a1-223",  "a1-223",  // Giovanni x2            (+10 damage this turn)
    "a1-225",  "a1-225",  // Sabrina x2             (pull target to active)
    "pa-005",  "pa-005",  // Poké Ball x2
    "pa-007",  "pa-007",  // Professor's Research x2
    "pa-001",  "pa-001",  // Potion x2
];
pub const CELEBI_EX_ENERGY: &[Element] = &[Element::Grass];

// ------------------------------------------------------------------ //
// Mew ex deck — Psychic copy engine
// Mew ex "Genome Hacking" copies any of the opponent's attacks for 3
// Colorless.  Gardevoir's "Psy Shadow" ability attaches a Psychic
// energy from the energy zone each turn, ramping to Psyshot spam or
// Genome Hacking quickly.
// ------------------------------------------------------------------ //

pub const MEW_EX_DECK: &[&str] = &[
    "a1a-077", "a1a-077", // Mew ex x2        (Psyshot 20; Genome Hacking copies opponent)
    "a1-130",  "a1-130",  // Ralts x2         (Gardevoir base)
    "a1-131",  "a1-131",  // Kirlia x2        (Gardevoir mid-stage)
    "a1-132",  "a1-132",  // Gardevoir x2     (Psy Shadow: attach Psychic energy each turn)
    "a3-144",  "a3-144",  // Rare Candy x2    (Ralts → Gardevoir, skip Kirlia)
    "a1-225",  "a1-225",  // Sabrina x2
    "a1-223",  "a1-223",  // Giovanni x2
    "pa-007",  "pa-007",  // Professor's Research x2
    "pa-005",  "pa-005",  // Poké Ball x2
    "pa-001",  "pa-001",  // Potion x2
];
pub const MEW_EX_ENERGY: &[Element] = &[Element::Psychic];

// ------------------------------------------------------------------ //
// Dragonite deck — Dragon spread sweeper
//
// Strategy: Draco Meteor hits 4 random targets for 50 each (200 total
// spread) and wins by accumulating damage across the bench.  Drampa is
// a hard-hitting Basic (Berserk 70 base; 120 when any bench Pokémon is
// damaged) that pairs perfectly since Draco Meteor's splash keeps the
// bench in the "damaged" zone.  Misty accelerates Water energy so
// Dragonite can attack as early as turn 4.  Rare Candy lets Dratini
// skip Dragonair entirely.
// ------------------------------------------------------------------ //

pub const DRAGONITE_DECK: &[&str] = &[
    "a1-183",  "a1-183",  // Dratini x2       (60 HP basic; Dragon path)
    "a1-184",  "a1-184",  // Dragonair x2     (Stage 1 bridge)
    "a1-185",  "a1-185",  // Dragonite x2     (Draco Meteor: 4× 50 random = 200 total spread)
    "a3-124",  "a3-124",  // Drampa x2        (Berserk: 20+50=[70] or 120 when bench damaged)
    "a3-144",  "a3-144",  // Rare Candy x2    (Dratini → Dragonite, skip Dragonair)
    "a1-220",  "a1-220",  // Misty x2         (may attach up to 3 Water energy at once)
    "a1-225",  "a1-225",  // Sabrina x2       (pull damaged bench target to active)
    "a1-223",  "a1-223",  // Giovanni x2      (+10 damage this turn)
    "pa-005",  "pa-005",  // Poké Ball x2
    "pa-007",  "pa-007",  // Professor's Research x2
];
pub const DRAGONITE_ENERGY: &[Element] = &[Element::Water, Element::Lightning];

// ------------------------------------------------------------------ //
// Rampardos deck — Fighting fossil aggro + Silvally Colorless support
//
// Strategy: Skull Fossil plays Cranidos (Rampardos base) from the deck.
// Rampardos Head Smash hits 130 for 2 Fighting — one of the hardest-
// hitting Stage 1s in the game.  Type: Null evolves into Silvally
// (Brave Buddies: +50 if it shares the field with an Ultra Beast) for
// a flexible Colorless attacker.  Gladion searches for a specific card
// from the deck.  Iono + Mars disrupt the opponent's hand.
// Red boosts next attack damage.  Sabrina pulls bench targets.
// ------------------------------------------------------------------ //

pub const RAMPARDOS_DECK: &[&str] = &[
    "a2-088",             // Cranidos x1      (Rampardos base via Skull Fossil)
    "a2-089",  "a2-089",  // Rampardos x2     (Head Smash 130 for 2 Fighting)
    "a3a-060", "a3a-060", // Type: Null x2    (Silvally base; Colorless)
    "a3a-061", "a3a-061", // Silvally x2      (Brave Buddies: 50+50=100 with Ultra Beast bench)
    "pa-005",             // Poké Ball x1
    "a3-144",  "a3-144",  // Rare Candy x2    (Cranidos → Rampardos)
    "a3a-067", "a3a-067", // Gladion x2       (search any card from deck)
    "a2b-069",            // Iono x1          (shuffle both hands, draw equal counts)
    "a2-155",             // Mars x1          (opponent discards a random card)
    "pa-007",  "pa-007",  // Professor's Research x2
    "a2b-071",            // Red x1           (+20 damage next attack)
    "a1-225",             // Sabrina x1       (pull opponent bench target to active)
    "a2-144",  "a2-144",  // Skull Fossil x2  (search deck for Cranidos)
];
pub const RAMPARDOS_ENERGY: &[Element] = &[Element::Fighting];

// ------------------------------------------------------------------ //
// Greninja / Gyarados ex deck — Water aggro + passive damage
//
// Strategy: Gyarados ex is the main attacker (150 HP ex, powerful Water
// attacks).  Magikarp evolves into Gyarados ex via Rare Candy.  Greninja
// pings 20 to a bench Pokémon each turn for free.  Druddigon retaliates
// 20 to the attacker whenever it takes damage (passive Dragon Tail).
// Cyrus swaps an opponent's bench Pokémon into the active slot.
// Leaf heals 30 HP to a Pokémon.  Misty accelerates Water energy.
// ------------------------------------------------------------------ //

pub const GRENINJA_DECK: &[&str] = &[
    "a1a-017", "a1a-017", // Magikarp x2      (Gyarados ex base)
    "a1a-018", "a1a-018", // Gyarados ex x2   (main attacker — Water powerhouse)
    "a1a-056", "a1a-056", // Druddigon x2     (Dragon Tail: retaliate 20 on hit)
    "a3a-091", "a3a-091", // Froakie x2       (Greninja base)
    "a3a-093", "a3a-093", // Greninja x2      (Water Shuriken: 20 to any bench free each turn)
    "a3-144",  "a3-144",  // Rare Candy x2    (Magikarp → Gyarados ex, skip Magikarp)
    "a1-220",  "a1-220",  // Misty x2         (accelerate Water energy)
    "a2-150",             // Cyrus x1         (switch opponent's bench Pokémon to active)
    "a1a-068",            // Leaf x1          (heal 30 HP to a Pokémon)
    "pa-005",  "pa-005",  // Poké Ball x2
    "pa-007",  "pa-007",  // Professor's Research x2
];
pub const GRENINJA_ENERGY: &[Element] = &[Element::Water];

// ------------------------------------------------------------------ //
// Guzzlord ex deck — Ultra Beast control/poison
//
// Strategy: Nihilego's "More Poison" ability adds +20 extra poison damage
// per turn.  Celesteela (Metal) acts as a bulky pivot.  Guzzlord ex is
// the main damage dealer.  Lusamine can recycle Ultra Beast supporters.
// Cyrus / Guzma pull bench targets into active.  Mars disrupts the
// opponent's hand.  Poison Barb inflicts poison when the holder is hit.
// Rocky Helmet retaliates damage to the attacker.  Pokémon Center Lady
// heals 60 HP to a Pokémon.  Sabrina pulls the opponent's bench target.
// ------------------------------------------------------------------ //

pub const GUZZLORD_DECK: &[&str] = &[
    "a3a-103", "a3a-103", // Nihilego x2           (More Poison: +20 poison/turn)
    "a3a-062", "a3a-062", // Celesteela x2         (bulky Metal Ultra Beast pivot)
    "a3a-043", "a3a-043", // Guzzlord ex x2        (main attacker)
    "pa-005",  "pa-005",  // Poké Ball x2
    "a2-150",             // Cyrus x1              (switch opponent bench → active)
    "a3-151",             // Guzma x1              (switch opponent bench → active)
    "a3a-069", "a3a-069", // Lusamine x2           (recycle Ultra Beast trainers)
    "a2-155",             // Mars x1               (opponent discards a card)
    "a3-146",  "a3-146",  // Poison Barb x2        (tool: may poison attacker on hit)
    "a2b-070",            // Pokémon Center Lady x1 (heal 60 HP)
    "pa-007",  "pa-007",  // Professor's Research x2
    "a2-148",             // Rocky Helmet x1       (retaliate 20 on hit)
    "a1-225",             // Sabrina x1            (pull opponent bench to active)
];
pub const GUZZLORD_ENERGY: &[Element] = &[Element::Darkness];

// ------------------------------------------------------------------ //
// Lookup
// ------------------------------------------------------------------ //

/// Returns `(card_id_slice, energy_type_slice)` for a named deck.
///
/// Recognised names (case-insensitive):
///   `"grass"`, `"fire"`, `"mewtwo"`, `"nihilego"`, `"celebi"`,
///   `"mew"`, `"dragonite"`, `"rampardos"`, `"greninja"`,
///   `"guzzlord"`.
/// Returns `None` for unknown names.
pub fn get_sample_deck(name: &str) -> Option<(&'static [&'static str], &'static [Element])> {
    match name.trim().to_lowercase().as_str() {
        "grass"                                => Some((GRASS_DECK,      GRASS_ENERGY)),
        "fire"                                 => Some((FIRE_DECK,       FIRE_ENERGY)),
        "mewtwo" | "psychic"                   => Some((MEWTWO_EX_DECK,  MEWTWO_EX_ENERGY)),
        "nihilego" | "poison"                  => Some((NIHILEGO_DECK,   NIHILEGO_ENERGY)),
        "celebi"                               => Some((CELEBI_EX_DECK,  CELEBI_EX_ENERGY)),
        "mew"                                  => Some((MEW_EX_DECK,     MEW_EX_ENERGY)),
        "dragonite" | "dragon"                 => Some((DRAGONITE_DECK,  DRAGONITE_ENERGY)),
        "rampardos" | "fighting" | "fossil"    => Some((RAMPARDOS_DECK,  RAMPARDOS_ENERGY)),
        "greninja" | "water" | "gyarados"      => Some((GRENINJA_DECK,   GRENINJA_ENERGY)),
        "guzzlord" | "darkness" | "ultrabeast" => Some((GUZZLORD_DECK,   GUZZLORD_ENERGY)),
        _                                      => None,
    }
}

// ------------------------------------------------------------------ //
// Deck validation
// ------------------------------------------------------------------ //

/// Validate a deck against the PTCGP rules (RULES.md §2):
///   * Exactly 20 cards.
///   * No more than 2 copies of any card (by name — alternate art counts together).
///   * At least one Basic Pokémon.
///   * Energy types: between 1 and 3 inclusive.
///
/// NOTE: `runner::run_game` should also call this (currently it does not — see
/// the Python entry in `lib.rs::run_game` which gates on this validator).
pub fn validate_deck(db: &CardDb, deck: &[u16], energy_types: &[Element]) -> Result<(), String> {
    // 1. Exactly 20 cards.
    if deck.len() != 20 {
        return Err(format!("deck must contain exactly 20 cards, got {}", deck.len()));
    }

    // 2. Max 2 copies of any card (by name — alternate art share the same name).
    let mut counts: std::collections::HashMap<&str, u8> = std::collections::HashMap::new();
    for &idx in deck {
        let card = db
            .try_get_by_idx(idx)
            .ok_or_else(|| format!("card index {idx} not found in CardDb"))?;
        let entry = counts.entry(card.name.as_str()).or_insert(0);
        *entry += 1;
        if *entry > 2 {
            return Err(format!(
                "more than 2 copies of '{}' in deck (found {})",
                card.name, *entry
            ));
        }
    }

    // 3. At least one Basic Pokémon.
    let has_basic = deck.iter().any(|&idx| {
        match db.try_get_by_idx(idx) {
            Some(c) => matches!(c.kind, CardKind::Pokemon) && c.stage == Some(Stage::Basic),
            None => false,
        }
    });
    if !has_basic {
        return Err("deck must contain at least one Basic Pokémon".to_string());
    }

    // 4. Energy types: 1..=3.
    if energy_types.is_empty() {
        return Err("deck must declare at least 1 energy type".to_string());
    }
    if energy_types.len() > 3 {
        return Err(format!(
            "deck may declare at most 3 energy types, got {}",
            energy_types.len()
        ));
    }

    Ok(())
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
        d.pop(); // up to project root
        d.push("assets/cards");
        d
    }

    /// Resolve a sample deck's card-id slice into a Vec<u16> of CardDb indices.
    fn resolve(db: &CardDb, ids: &[&str]) -> Vec<u16> {
        ids.iter()
            .filter_map(|id| db.get_idx_by_id(id))
            .collect()
    }

    #[test]
    fn valid_sample_deck_passes() {
        let db = CardDb::load_from_dir(&assets_dir());
        let (ids, energy) = get_sample_deck("grass").unwrap();
        let deck = resolve(&db, ids);
        assert_eq!(deck.len(), 20, "sample grass deck should resolve to 20 cards");
        assert!(validate_deck(&db, &deck, energy).is_ok());
    }

    #[test]
    fn deck_size_not_20_fails() {
        let db = CardDb::load_from_dir(&assets_dir());
        let (ids, energy) = get_sample_deck("grass").unwrap();
        let mut deck = resolve(&db, ids);
        deck.pop(); // 19 cards
        let err = validate_deck(&db, &deck, energy).unwrap_err();
        assert!(err.contains("20"), "expected size error, got: {err}");
    }

    #[test]
    fn more_than_two_copies_fails() {
        let db = CardDb::load_from_dir(&assets_dir());
        let bulba = db.get_idx_by_id("a1-001").unwrap();
        // 20-card deck, 3 copies of Bulbasaur, plus 17 other unique-ish cards.
        // We just take 17 non-Bulbasaur basics to fill — but easiest: 3 Bulbasaur +
        // 17 Charmander would also exceed. Use 3 Bulba + 17 single copies of varied cards.
        let mut deck = vec![bulba, bulba, bulba];
        // Pad to 20 with single copies of distinct cards (skipping Bulbasaur).
        for c in db.cards.iter() {
            if deck.len() == 20 { break; }
            if c.name == "Bulbasaur" { continue; }
            deck.push(c.idx);
        }
        let err = validate_deck(&db, &deck, &[Element::Grass]).unwrap_err();
        assert!(err.contains("more than 2 copies"), "expected copy error, got: {err}");
    }

    #[test]
    fn zero_basics_fails() {
        let db = CardDb::load_from_dir(&assets_dir());
        // Build a 20-card deck of trainer/non-Basic cards only.
        // Use Potion (pa-001) — a Trainer item — 2x, and other trainers / evolved Pokémon.
        let mut deck: Vec<u16> = Vec::new();
        let mut name_counts: std::collections::HashMap<String, u8> =
            std::collections::HashMap::new();
        for c in db.cards.iter() {
            if deck.len() == 20 { break; }
            // Skip basic Pokémon entirely.
            if matches!(c.kind, CardKind::Pokemon) && c.stage == Some(Stage::Basic) {
                continue;
            }
            let entry = name_counts.entry(c.name.clone()).or_insert(0);
            if *entry >= 2 { continue; }
            *entry += 1;
            deck.push(c.idx);
        }
        assert_eq!(deck.len(), 20, "should have constructed a 20-card non-Basic deck");
        let err = validate_deck(&db, &deck, &[Element::Grass]).unwrap_err();
        assert!(err.contains("Basic"), "expected basic error, got: {err}");
    }

    #[test]
    fn more_than_three_energy_types_fails() {
        let db = CardDb::load_from_dir(&assets_dir());
        let (ids, _) = get_sample_deck("grass").unwrap();
        let deck = resolve(&db, ids);
        let energy = vec![
            Element::Grass,
            Element::Fire,
            Element::Water,
            Element::Lightning,
        ];
        let err = validate_deck(&db, &deck, &energy).unwrap_err();
        assert!(err.contains("3 energy types"), "expected energy error, got: {err}");
    }

    #[test]
    fn zero_energy_types_fails() {
        let db = CardDb::load_from_dir(&assets_dir());
        let (ids, _) = get_sample_deck("grass").unwrap();
        let deck = resolve(&db, ids);
        let err = validate_deck(&db, &deck, &[]).unwrap_err();
        assert!(err.contains("at least 1 energy"), "expected energy error, got: {err}");
    }
}
