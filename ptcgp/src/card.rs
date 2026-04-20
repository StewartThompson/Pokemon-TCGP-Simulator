use std::collections::HashMap;
use std::path::Path;
use serde::Deserialize;
use crate::types::{CardKind, CostSymbol, Element, Stage};
use crate::effects::{EffectKind, parse_handler_string};
use crate::effects::legality::{LegalCondition, parse_legal_array};

// -------------------------------------------------------------------------- //
// Card structs
// -------------------------------------------------------------------------- //

#[derive(Clone, Debug)]
pub struct Attack {
    pub name: String,
    pub damage: i16,
    pub cost: Vec<CostSymbol>,
    pub effect_text: String,
    pub handler: String,
    pub effects: Vec<EffectKind>,
    /// Pre-parsed `legal` predicates from JSON.  Empty = always legal
    /// (no preconditions, no target enumeration); evaluated by
    /// `effects::legality::enumerate_legal_actions` at action-emit time.
    pub legal_conditions: Vec<LegalCondition>,
}

#[derive(Clone, Debug)]
pub struct Ability {
    pub name: String,
    pub effect_text: String,
    pub is_passive: bool,
    pub handler: String,
    pub effects: Vec<EffectKind>,
    pub legal_conditions: Vec<LegalCondition>,
}

#[derive(Clone, Debug)]
pub struct Card {
    pub id: String,
    pub idx: u16,
    pub name: String,
    pub kind: CardKind,
    pub stage: Option<Stage>,
    pub element: Option<Element>,
    pub hp: i16,
    pub weakness: Option<Element>,
    pub retreat_cost: u8,
    pub is_ex: bool,
    pub is_mega_ex: bool,
    pub evolves_from: Option<String>,
    pub attacks: Vec<Attack>,
    pub ability: Option<Ability>,
    pub trainer_effect_text: String,
    pub trainer_handler: String,
    pub trainer_effects: Vec<EffectKind>,
    /// `legal` predicates for trainer cards (Item / Supporter / Tool).
    /// Empty = always legal.  See `effects::legality`.
    pub trainer_legal_conditions: Vec<LegalCondition>,
    pub ko_points: u8,
}

// -------------------------------------------------------------------------- //
// CardDb
// -------------------------------------------------------------------------- //

pub struct CardDb {
    pub cards: Vec<Card>,
    pub id_to_idx: HashMap<String, u16>,
    pub name_to_indices: HashMap<String, Vec<u16>>,
    pub basic_to_stage2: HashMap<String, Vec<String>>,
}

impl CardDb {
    /// Construct an empty CardDb (useful for tests that don't need card lookup).
    pub fn new_empty() -> Self {
        Self {
            cards: Vec::new(),
            id_to_idx: HashMap::new(),
            name_to_indices: HashMap::new(),
            basic_to_stage2: HashMap::new(),
        }
    }

    pub fn get_by_id(&self, id: &str) -> Option<&Card> {
        self.id_to_idx.get(id).map(|&i| &self.cards[i as usize])
    }

    pub fn get_by_idx(&self, idx: u16) -> &Card {
        &self.cards[idx as usize]
    }

    /// Safe variant of `get_by_idx` that returns None if out of range.
    pub fn try_get_by_idx(&self, idx: u16) -> Option<&Card> {
        self.cards.get(idx as usize)
    }

    pub fn get_idx_by_id(&self, id: &str) -> Option<u16> {
        self.id_to_idx.get(id).copied()
    }

    pub fn len(&self) -> usize {
        self.cards.len()
    }

    pub fn is_empty(&self) -> bool {
        self.cards.is_empty()
    }

    /// Load card database from a list of JSON file paths
    pub fn load(paths: &[&Path]) -> Self {
        let mut raw_cards: Vec<RawCard> = Vec::new();
        for path in paths {
            match std::fs::read_to_string(path) {
                Ok(content) => match serde_json::from_str::<Vec<RawCard>>(&content) {
                    Ok(cards) => raw_cards.extend(cards),
                    Err(err) => eprintln!("warning: failed to load {}: {}", path.display(), err),
                },
                Err(err) => eprintln!("warning: failed to load {}: {}", path.display(), err),
            }
        }
        Self::build_from_raw(raw_cards)
    }

    pub fn load_from_dir(dir: &Path) -> Self {
        let mut paths: Vec<std::path::PathBuf> = std::fs::read_dir(dir)
            .unwrap_or_else(|_| panic!("Cannot read dir {:?}", dir))
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .filter(|p| p.extension().map(|x| x == "json").unwrap_or(false))
            .collect();
        paths.sort();

        let path_refs: Vec<&Path> = paths.iter().map(|p| p.as_path()).collect();
        Self::load(&path_refs)
    }

    fn build_from_raw(raw_cards: Vec<RawCard>) -> Self {
        let mut cards: Vec<Card> = Vec::new();
        let mut id_to_idx: HashMap<String, u16> = HashMap::new();

        for raw in raw_cards {
            let card = parse_card(raw);
            let existing_idx = id_to_idx.get(&card.id).copied();
            if let Some(idx) = existing_idx {
                // Keep richer version
                let existing = &cards[idx as usize];
                if card_info_score(&card) > card_info_score(existing) {
                    let idx_val = idx;
                    let mut replacement = card;
                    replacement.idx = idx_val;
                    cards[idx_val as usize] = replacement;
                }
            } else {
                let idx = cards.len() as u16;
                id_to_idx.insert(card.id.clone(), idx);
                let mut c = card;
                c.idx = idx;
                cards.push(c);
            }
        }

        let mut name_to_indices: HashMap<String, Vec<u16>> = HashMap::new();
        for card in &cards {
            name_to_indices.entry(card.name.clone()).or_default().push(card.idx);
        }

        let basic_to_stage2 = build_evo_cache(&cards);

        Self { cards, id_to_idx, name_to_indices, basic_to_stage2 }
    }
}

fn card_info_score(card: &Card) -> i32 {
    let mut score = 0i32;
    if card.ability.is_some() { score += 2; }
    score += card.attacks.iter().filter(|a| !a.effect_text.is_empty()).count() as i32;
    if !card.trainer_effect_text.is_empty() { score += 3; }
    score
}

fn build_evo_cache(cards: &[Card]) -> HashMap<String, Vec<String>> {
    // stage1_name -> vec of basic names that evolve into it
    let mut stage1_evolves_from: HashMap<String, Vec<String>> = HashMap::new();
    for card in cards {
        if card.stage == Some(Stage::Stage1) {
            if let Some(ref basic) = card.evolves_from {
                stage1_evolves_from.entry(card.name.clone()).or_default().push(basic.clone());
            }
        }
    }

    let mut basic_to_stage2: HashMap<String, Vec<String>> = HashMap::new();
    for card in cards {
        if card.stage == Some(Stage::Stage2) {
            if let Some(ref s1_name) = card.evolves_from {
                if let Some(basics) = stage1_evolves_from.get(s1_name) {
                    for basic in basics {
                        basic_to_stage2.entry(basic.clone()).or_default().push(card.name.clone());
                    }
                }
            }
        }
    }
    basic_to_stage2
}

// -------------------------------------------------------------------------- //
// JSON deserialization (raw structs matching the JSON format)
// -------------------------------------------------------------------------- //

#[derive(Deserialize, Debug)]
struct RawCard {
    id: String,
    name: Option<String>,
    #[serde(rename = "type")]
    card_type: Option<String>,
    subtype: Option<String>,
    element: Option<String>,
    health: Option<serde_json::Value>,
    #[serde(rename = "retreatCost")]
    retreat_cost: Option<serde_json::Value>,
    weakness: Option<String>,
    attacks: Option<Vec<RawAttack>>,
    abilities: Option<Vec<RawAbility>>,
    #[serde(rename = "evolvesFrom")]
    evolves_from: Option<String>,
    #[allow(dead_code)] // present in JSON; reserved for future ex/rarity-based logic
    rarity: Option<String>,
}

#[derive(Deserialize, Debug)]
struct RawAttack {
    name: Option<String>,
    damage: Option<serde_json::Value>,
    cost: Option<Vec<String>>,
    effect: Option<String>,
    handler: Option<String>,
    /// Optional legality predicates (parallel to handler).  See
    /// `effects::legality` for the predicate language.
    #[serde(default)]
    legal: Option<Vec<String>>,
}

#[derive(Deserialize, Debug)]
struct RawAbility {
    name: Option<String>,
    effect: Option<String>,
    handler: Option<String>,
    #[serde(default)]
    legal: Option<Vec<String>>,
}

fn parse_damage(v: &serde_json::Value) -> i16 {
    match v {
        serde_json::Value::Number(n) => n.as_i64().unwrap_or(0) as i16,
        serde_json::Value::String(s) => {
            // Strip trailing +, x, × then parse
            let cleaned: String = s.chars()
                .filter(|c| c.is_ascii_digit())
                .collect();
            cleaned.parse().unwrap_or(0)
        }
        _ => 0,
    }
}

fn parse_cost(cost_list: &[String]) -> Vec<CostSymbol> {
    cost_list.iter()
        .filter_map(|s| CostSymbol::from_str(s))
        .collect()
}


fn detect_is_passive(name: &str, effect_text: &str, handler: &str) -> bool {
    // Primary indicator: the handler string.
    // Auto-triggered abilities (passive, on-evolve, end-of-turn, etc.) cannot
    // be activated by a player click — they fire on their own from the engine
    // hook for the relevant event.  Identify them by handler-name prefix so
    // legal_actions doesn't surface them as USE_ABILITY actions.
    if handler.split('|').any(|part| {
        let p = part.trim();
        p.starts_with("passive_")
            || p.starts_with("on_evolve_")
            || p.starts_with("end_of_turn_")
            // Nihilego More Poison: technically a passive aura ("takes +10
            // damage from being Poisoned") that fires from the checkup
            // pipeline.  Treat the bare `toxic_poison` handler as passive
            // so it never surfaces as USE_ABILITY.
            || p == "toxic_poison"
    }) {
        return true;
    }
    // Secondary: well-known passive effect-text patterns.
    let low = effect_text.to_lowercase();
    // "As long as…" → always-on passive condition (e.g. Goomy Sticky Membrane).
    if low.contains("as long as") {
        return true;
    }
    // "At the end of [your/each] turn" → auto-triggers, not a player choice.
    if low.contains("at the end of") {
        return true;
    }
    // "When you play this Pokemon … to evolve" → on-evolve trigger
    // (e.g. Charmeleon B2b-008 Ignition).  Fires once at evolution time only.
    if low.contains("when you play this") && low.contains("to evolve") {
        return true;
    }
    // Legacy Poké-Body naming convention.
    if name.to_lowercase().contains("body") {
        return true;
    }
    false
}

fn parse_card(raw: RawCard) -> Card {
    let name = raw.name.unwrap_or_default();
    let card_type = raw.card_type.as_deref().unwrap_or("Pokemon");
    let subtype = raw.subtype.as_deref().unwrap_or("");
    let is_pokemon = card_type.eq_ignore_ascii_case("pokemon");

    // Strict suffix-only check (case-insensitive) to avoid false positives from
    // names like "Hex Maniac" or rarities containing the letters "ex".
    let trimmed_lower = name.trim().to_lowercase();
    let is_ex = trimmed_lower.ends_with(" ex") || trimmed_lower.ends_with("-ex");
    let is_mega_ex = trimmed_lower.contains("mega") && is_ex;

    let (kind, stage, element, weakness, hp, retreat_cost, attacks, ability,
         trainer_effect_text, trainer_handler, trainer_effects,
         trainer_legal_conditions) = if is_pokemon {
        let kind = CardKind::Pokemon;
        let stage = Stage::from_str(subtype);
        let element = raw.element.as_deref().and_then(Element::from_str);
        let weakness = raw.weakness.as_deref().and_then(Element::from_str);
        let hp = raw.health.as_ref().map(|v| match v {
            serde_json::Value::Number(n) => n.as_i64().unwrap_or(0) as i16,
            serde_json::Value::String(s) => s.parse().unwrap_or(0),
            _ => 0,
        }).unwrap_or(0);
        let retreat_cost = match raw.retreat_cost.as_ref() {
            Some(serde_json::Value::Number(n)) => {
                let v = n.as_u64().unwrap_or(0);
                // Sentinel: 999 (or any value > 4) means "cannot retreat".
                // Use u8::MAX so the engine can treat MAX as "no retreat allowed"
                // rather than silently making the cost 0 (free retreat).
                if v > 4 { u8::MAX } else { v as u8 }
            }
            Some(serde_json::Value::String(s)) => match s.parse::<u64>() {
                Ok(v) if v > 4 => u8::MAX,
                Ok(v) => v as u8,
                Err(_) => 0,
            },
            _ => 0,
        };

        // Parse attacks, dedup by (name, cost, damage)
        let mut seen: std::collections::HashSet<(String, Vec<String>, i16)> = std::collections::HashSet::new();
        let mut attacks: Vec<Attack> = Vec::new();
        for ra in raw.attacks.unwrap_or_default() {
            let atk_name = ra.name.unwrap_or_default();
            let damage = ra.damage.as_ref().map(parse_damage).unwrap_or(0);
            let cost_raw: Vec<String> = ra.cost.unwrap_or_default();
            let key = (atk_name.clone(), cost_raw.clone(), damage);
            if seen.contains(&key) { continue; }
            seen.insert(key);
            let handler = ra.handler.unwrap_or_default();
            let effects = parse_handler_string(&handler);
            let legal_conditions = ra.legal.as_ref()
                .map(|v| parse_legal_array(v))
                .unwrap_or_default();
            attacks.push(Attack {
                name: atk_name,
                damage,
                cost: parse_cost(&cost_raw),
                effect_text: ra.effect.unwrap_or_default(),
                handler,
                effects,
                legal_conditions,
            });
        }

        // Parse ability
        let ability = raw.abilities.as_ref().and_then(|abs| {
            abs.iter().find(|a| a.name.is_some() && a.effect.is_some()).map(|a| {
                let handler = a.handler.clone().unwrap_or_default();
                let effects = parse_handler_string(&handler);
                let legal_conditions = a.legal.as_ref()
                    .map(|v| parse_legal_array(v))
                    .unwrap_or_default();
                let ab_name = a.name.clone().unwrap_or_default();
                let effect_text = a.effect.clone().unwrap_or_default();
                let is_passive = detect_is_passive(&ab_name, &effect_text, &handler);
                Ability { name: ab_name, effect_text, is_passive, handler, effects, legal_conditions }
            })
        });

        (kind, stage, element, weakness, hp, retreat_cost, attacks, ability,
         String::new(), String::new(), vec![], vec![])
    } else {
        let kind = match subtype.to_lowercase().as_str() {
            "supporter" => CardKind::Supporter,
            "tool" => CardKind::Tool,
            _ => CardKind::Item,
        };
        let trainer_effect_text = raw.abilities.as_ref()
            .and_then(|abs| abs.first())
            .and_then(|a| a.effect.clone())
            .unwrap_or_default();
        let trainer_handler = raw.abilities.as_ref()
            .and_then(|abs| abs.first())
            .and_then(|a| a.handler.clone())
            .unwrap_or_default();
        let trainer_effects = parse_handler_string(&trainer_handler);
        let trainer_legal_conditions = raw.abilities.as_ref()
            .and_then(|abs| abs.first())
            .and_then(|a| a.legal.as_ref())
            .map(|v| parse_legal_array(v))
            .unwrap_or_default();

        // Fossil cards (e.g. Skull Fossil) have passive_ditto_impostor and are played
        // directly to the bench as a Basic Pokémon. Reclassify them so the engine
        // treats them correctly: legal_actions, play_basic, and the evolve system
        // can then work with them as-is.
        let fossil_hp = trainer_effects.iter().find_map(|e| {
            if let EffectKind::PassiveDittoImpostor { hp } = e { Some(*hp) } else { None }
        });
        if let Some(hp) = fossil_hp {
            // Treat as a Basic Pokémon with the given HP and cannot retreat (cost=4).
            (CardKind::Pokemon, Some(crate::types::Stage::Basic), None, None,
             hp, 4u8, vec![], None, String::new(), String::new(), vec![], vec![])
        } else {
            (kind, None, None, None, 0, 0, vec![], None,
             trainer_effect_text, trainer_handler, trainer_effects, trainer_legal_conditions)
        }
    };

    let ko_points = if is_mega_ex { 3 } else if is_ex { 2 } else { 1 };

    Card {
        id: raw.id,
        idx: 0, // set by CardDb
        name,
        kind,
        stage,
        element,
        hp,
        weakness,
        retreat_cost,
        is_ex: is_ex || is_mega_ex,
        is_mega_ex,
        evolves_from: raw.evolves_from,
        attacks,
        ability,
        trainer_effect_text,
        trainer_handler,
        trainer_effects,
        trainer_legal_conditions,
        ko_points,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop(); // go up from ptcgp/  to project root
        d.push("assets/cards");
        d
    }

    #[test]
    fn load_all_cards() {
        let db = CardDb::load_from_dir(&assets_dir());
        assert!(db.len() > 100, "Expected >100 cards, got {}", db.len());
    }

    #[test]
    fn bulbasaur_parsed_correctly() {
        let db = CardDb::load_from_dir(&assets_dir());
        let card = db.get_by_id("a1-001").expect("a1-001 not found");
        assert_eq!(card.name, "Bulbasaur");
        assert_eq!(card.kind, CardKind::Pokemon);
        assert_eq!(card.stage, Some(Stage::Basic));
        assert_eq!(card.element, Some(Element::Grass));
        assert_eq!(card.hp, 70);
        assert_eq!(card.weakness, Some(Element::Fire));
        assert_eq!(card.retreat_cost, 1);
        assert_eq!(card.attacks.len(), 1);
        assert_eq!(card.attacks[0].name, "Vine Whip");
        assert_eq!(card.attacks[0].damage, 40);
        assert_eq!(card.attacks[0].cost, vec![CostSymbol::Grass, CostSymbol::Colorless]);
    }

    #[test]
    fn ko_points_correct() {
        let db = CardDb::load_from_dir(&assets_dir());
        // Bulbasaur: 1 point
        let bulb = db.get_by_id("a1-001").unwrap();
        assert_eq!(bulb.ko_points, 1);
    }
}
