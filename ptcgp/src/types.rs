use serde::{Deserialize, Serialize};

/// The 8 real energy types. Colorless is NOT an energy type — it's a cost symbol only.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Element {
    Grass = 0,
    Fire = 1,
    Water = 2,
    Lightning = 3,
    Psychic = 4,
    Fighting = 5,
    Darkness = 6,
    Metal = 7,
}

impl Element {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "grass" => Some(Self::Grass),
            "fire" => Some(Self::Fire),
            "water" => Some(Self::Water),
            "lightning" => Some(Self::Lightning),
            "psychic" => Some(Self::Psychic),
            "fighting" => Some(Self::Fighting),
            "darkness" | "dark" => Some(Self::Darkness),
            "metal" | "steel" => Some(Self::Metal),
            _ => None,
        }
    }

    /// Index 0-7 for use in EnergyArray indexing
    #[inline]
    pub fn idx(self) -> usize {
        self as usize
    }
}

/// All cost symbols that can appear in an attack's energy cost list.
/// Includes all 8 Elements plus COLORLESS (any energy type).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CostSymbol {
    Grass,
    Fire,
    Water,
    Lightning,
    Psychic,
    Fighting,
    Darkness,
    Metal,
    Colorless,
}

impl CostSymbol {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "grass" => Some(Self::Grass),
            "fire" => Some(Self::Fire),
            "water" => Some(Self::Water),
            "lightning" => Some(Self::Lightning),
            "psychic" => Some(Self::Psychic),
            "fighting" => Some(Self::Fighting),
            "darkness" | "dark" => Some(Self::Darkness),
            "metal" | "steel" => Some(Self::Metal),
            "colorless" => Some(Self::Colorless),
            _ => None,
        }
    }

    /// Convert to Element. Returns None for Colorless.
    #[inline]
    pub fn to_element(self) -> Option<Element> {
        match self {
            Self::Grass => Some(Element::Grass),
            Self::Fire => Some(Element::Fire),
            Self::Water => Some(Element::Water),
            Self::Lightning => Some(Element::Lightning),
            Self::Psychic => Some(Element::Psychic),
            Self::Fighting => Some(Element::Fighting),
            Self::Darkness => Some(Element::Darkness),
            Self::Metal => Some(Element::Metal),
            Self::Colorless => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Stage {
    Basic,
    Stage1,
    Stage2,
}

impl Stage {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().replace(' ', "").as_str() {
            "basic" => Some(Self::Basic),
            "stage1" => Some(Self::Stage1),
            "stage2" => Some(Self::Stage2),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CardKind {
    Pokemon,
    Item,
    Supporter,
    Tool,
}

impl CardKind {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "pokemon" => Some(Self::Pokemon),
            "item" => Some(Self::Item),
            "supporter" => Some(Self::Supporter),
            "tool" => Some(Self::Tool),
            _ => None,
        }
    }
}

/// Status effects encoded as bit flags for the u8 bitfield in PokemonSlot.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum StatusEffect {
    Poisoned  = 0b00001,
    Burned    = 0b00010,
    Paralyzed = 0b00100,
    Asleep    = 0b01000,
    Confused  = 0b10000,
}

impl StatusEffect {
    #[inline]
    pub fn bit(self) -> u8 {
        self as u8
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum GamePhase {
    Setup,
    Main,
    AwaitingBenchPromotion,
    GameOver,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum ActionKind {
    PlayCard,
    AttachEnergy,
    Evolve,
    UseAbility,
    Retreat,
    Attack,
    EndTurn,
    Promote,
}

/// Fixed-size energy array indexed by Element::idx()
pub type EnergyArray = [u8; 8];

#[inline]
pub fn energy_total(e: &EnergyArray) -> u8 {
    e.iter().sum()
}

#[inline]
pub fn energy_get(e: &EnergyArray, el: Element) -> u8 {
    e[el.idx()]
}

#[inline]
pub fn energy_add(e: &mut EnergyArray, el: Element, n: u8) {
    e[el.idx()] = e[el.idx()].saturating_add(n);
}

#[inline]
pub fn energy_sub(e: &mut EnergyArray, el: Element, n: u8) {
    e[el.idx()] = e[el.idx()].saturating_sub(n);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn element_from_str() {
        assert_eq!(Element::from_str("Grass"), Some(Element::Grass));
        assert_eq!(Element::from_str("fire"), Some(Element::Fire));
        assert_eq!(Element::from_str("metal"), Some(Element::Metal));
        assert_eq!(Element::from_str("steel"), Some(Element::Metal));
        assert_eq!(Element::from_str("unknown"), None);
    }

    #[test]
    fn cost_symbol_to_element() {
        assert_eq!(CostSymbol::Water.to_element(), Some(Element::Water));
        assert_eq!(CostSymbol::Colorless.to_element(), None);
    }

    #[test]
    fn status_effect_bits_unique() {
        let bits = [
            StatusEffect::Poisoned.bit(),
            StatusEffect::Burned.bit(),
            StatusEffect::Paralyzed.bit(),
            StatusEffect::Asleep.bit(),
            StatusEffect::Confused.bit(),
        ];
        // All bits must be unique powers of 2
        for (i, &b1) in bits.iter().enumerate() {
            for (j, &b2) in bits.iter().enumerate() {
                if i != j {
                    assert_eq!(b1 & b2, 0, "Status bits overlap: {:b} & {:b}", b1, b2);
                }
            }
        }
    }

    #[test]
    fn energy_array_ops() {
        let mut e: EnergyArray = [0; 8];
        energy_add(&mut e, Element::Fire, 2);
        energy_add(&mut e, Element::Water, 1);
        assert_eq!(energy_get(&e, Element::Fire), 2);
        assert_eq!(energy_get(&e, Element::Water), 1);
        assert_eq!(energy_total(&e), 3);
        energy_sub(&mut e, Element::Fire, 1);
        assert_eq!(energy_get(&e, Element::Fire), 1);
        assert_eq!(energy_total(&e), 2);
    }
}
