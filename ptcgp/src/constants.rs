use crate::types::Element;

pub const DECK_SIZE: usize = 20;
pub const BENCH_SIZE: usize = 3;
pub const INITIAL_HAND_SIZE: usize = 5;
pub const POINTS_TO_WIN: u8 = 3;
pub const MAX_COPIES_PER_CARD: usize = 2;

pub const POINTS_PER_KO: u8 = 1;
pub const POINTS_PER_EX_KO: u8 = 2;
pub const POINTS_PER_MEGA_EX_KO: u8 = 3;

pub const WEAKNESS_BONUS: i16 = 20;
pub const POISON_DAMAGE: i16 = 10;
pub const BURN_DAMAGE: i16 = 20;
pub const MAX_TURNS: i16 = 60;

/// Weakness chart: (defending_type, attacking_type_that_deals_bonus)
pub const WEAKNESS_CHART: &[(Element, Element)] = &[
    (Element::Grass,     Element::Fire),
    (Element::Fire,      Element::Water),
    (Element::Water,     Element::Lightning),
    (Element::Lightning, Element::Fighting),
    (Element::Psychic,   Element::Darkness),
    (Element::Fighting,  Element::Psychic),
    (Element::Darkness,  Element::Fighting),
    (Element::Metal,     Element::Fire),
];

/// Returns true if attacker_element is super-effective against defender_weakness
pub fn is_weak_to(defender_weakness: Option<Element>, attacker_element: Option<Element>) -> bool {
    match (defender_weakness, attacker_element) {
        (Some(def), Some(atk)) => def == atk,
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn weakness_fire_beats_grass() {
        assert!(is_weak_to(Some(Element::Fire), Some(Element::Fire)));
        assert!(!is_weak_to(Some(Element::Fire), Some(Element::Water)));
    }
}
