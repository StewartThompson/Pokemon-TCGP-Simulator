use crate::types::ActionKind;

/// Reference to a Pokemon slot on the board.
/// player: 0 or 1
/// slot: -1 = active slot, 0-2 = bench index
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct SlotRef {
    pub player: u8,
    pub slot: i8,  // -1 = active, 0-2 = bench
}

impl SlotRef {
    pub fn active(player: usize) -> Self {
        Self { player: player as u8, slot: -1 }
    }

    pub fn bench(player: usize, index: usize) -> Self {
        assert!(index <= 2, "Bench index must be 0-2");
        Self { player: player as u8, slot: index as i8 }
    }

    pub fn is_active(self) -> bool {
        self.slot == -1
    }

    pub fn is_bench(self) -> bool {
        self.slot >= 0
    }

    pub fn bench_index(self) -> usize {
        debug_assert!(self.is_bench());
        self.slot as usize
    }
}

impl std::fmt::Display for SlotRef {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if self.is_active() {
            write!(f, "p{}:active", self.player)
        } else {
            write!(f, "p{}:bench[{}]", self.player, self.slot)
        }
    }
}

/// A game action taken by a player.
#[derive(Clone, Debug, PartialEq)]
pub struct Action {
    pub kind: ActionKind,
    /// PLAY_CARD, EVOLVE: index in hand
    pub hand_index: Option<usize>,
    /// PLAY_CARD target slot, ATTACH_ENERGY, EVOLVE, USE_ABILITY, RETREAT dest, PROMOTE slot
    pub target: Option<SlotRef>,
    /// ATTACK: index into card's attacks vec
    pub attack_index: Option<usize>,
    /// Secondary hand index — used by Rare Candy
    pub extra_hand_index: Option<usize>,
    /// Secondary target slot — used by effects that pick two slots (e.g.
    /// Manaphy "Choose 2 of your Benched Pokémon" attach_water_two_bench).
    pub extra_target: Option<SlotRef>,
}

impl Action {
    pub fn end_turn() -> Self {
        Self { kind: ActionKind::EndTurn, hand_index: None, target: None, attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn attack(attack_index: usize, sub_target: Option<SlotRef>) -> Self {
        Self { kind: ActionKind::Attack, hand_index: None, target: sub_target, attack_index: Some(attack_index), extra_hand_index: None, extra_target: None }
    }

    pub fn play_basic(hand_index: usize, bench_slot: SlotRef) -> Self {
        Self { kind: ActionKind::PlayCard, hand_index: Some(hand_index), target: Some(bench_slot), attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn attach_energy(target: SlotRef) -> Self {
        Self { kind: ActionKind::AttachEnergy, hand_index: None, target: Some(target), attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn evolve(hand_index: usize, target: SlotRef) -> Self {
        Self { kind: ActionKind::Evolve, hand_index: Some(hand_index), target: Some(target), attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn use_ability(target: SlotRef) -> Self {
        Self { kind: ActionKind::UseAbility, hand_index: None, target: Some(target), attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn retreat(bench_target: SlotRef) -> Self {
        Self { kind: ActionKind::Retreat, hand_index: None, target: Some(bench_target), attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn promote(slot: SlotRef) -> Self {
        Self { kind: ActionKind::Promote, hand_index: None, target: Some(slot), attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn play_item(hand_index: usize, target: Option<SlotRef>) -> Self {
        Self { kind: ActionKind::PlayCard, hand_index: Some(hand_index), target, attack_index: None, extra_hand_index: None, extra_target: None }
    }

    pub fn play_rare_candy(hand_index: usize, target: SlotRef, evo_hand_index: usize) -> Self {
        Self { kind: ActionKind::PlayCard, hand_index: Some(hand_index), target: Some(target), attack_index: None, extra_hand_index: Some(evo_hand_index), extra_target: None }
    }

    /// Attack picking 2 own bench targets (e.g. Manaphy `attach_water_two_bench`).
    pub fn attack_two_targets(attack_index: usize, target_a: SlotRef, target_b: SlotRef) -> Self {
        Self { kind: ActionKind::Attack, hand_index: None, target: Some(target_a), attack_index: Some(attack_index), extra_hand_index: None, extra_target: Some(target_b) }
    }
}

impl std::fmt::Display for Action {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Action({:?}", self.kind)?;
        if let Some(h) = self.hand_index { write!(f, " hand={}", h)?; }
        if let Some(ref t) = self.target { write!(f, " target={}", t)?; }
        if let Some(i) = self.attack_index { write!(f, " atk={}", i)?; }
        if let Some(e) = self.extra_hand_index { write!(f, " extra_hand={}", e)?; }
        if let Some(ref t) = self.extra_target { write!(f, " extra_target={}", t)?; }
        write!(f, ")")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slot_ref_constructors() {
        let active = SlotRef::active(0);
        assert!(active.is_active());
        assert!(!active.is_bench());
        assert_eq!(active.player, 0);

        let bench = SlotRef::bench(1, 2);
        assert!(bench.is_bench());
        assert_eq!(bench.bench_index(), 2);
        assert_eq!(bench.player, 1);
    }

    #[test]
    fn action_display() {
        let a = Action::attack(0, None);
        let s = format!("{}", a);
        assert!(s.contains("Attack"));
    }

    #[test]
    fn action_end_turn() {
        let a = Action::end_turn();
        assert_eq!(a.kind, ActionKind::EndTurn);
        assert!(a.hand_index.is_none());
        assert!(a.target.is_none());
    }
}
