use rand::SeedableRng;
use rand::rngs::SmallRng;
use crate::types::{EnergyArray, Element, GamePhase, StatusEffect, energy_get, energy_add, energy_sub, energy_total};
use crate::actions::SlotRef;

// ------------------------------------------------------------------ //
// PokemonSlot
// ------------------------------------------------------------------ //

#[derive(Clone, Debug)]
pub struct PokemonSlot {
    pub card_idx: u16,
    pub current_hp: i16,
    pub max_hp: i16,
    pub energy: EnergyArray,
    pub status: u8,                       // bitfield of StatusEffect bits
    pub turns_in_play: u8,
    pub tool_idx: Option<u16>,
    pub evolved_this_turn: bool,
    pub ability_used_this_turn: bool,
    pub cant_attack_next_turn: bool,
    pub cant_retreat_next_turn: bool,
    pub prevent_damage_next_turn: bool,
    pub incoming_damage_reduction: i8,
    pub attack_bonus_next_turn_self: i8,
}

impl PokemonSlot {
    pub fn new(card_idx: u16, hp: i16) -> Self {
        Self {
            card_idx,
            current_hp: hp,
            max_hp: hp,
            energy: [0; 8],
            status: 0,
            turns_in_play: 0,
            tool_idx: None,
            evolved_this_turn: false,
            ability_used_this_turn: false,
            cant_attack_next_turn: false,
            cant_retreat_next_turn: false,
            prevent_damage_next_turn: false,
            incoming_damage_reduction: 0,
            attack_bonus_next_turn_self: 0,
        }
    }

    #[inline]
    pub fn total_energy(&self) -> u8 {
        energy_total(&self.energy)
    }

    #[inline]
    pub fn energy_count(&self, el: Element) -> u8 {
        energy_get(&self.energy, el)
    }

    #[inline]
    pub fn add_energy(&mut self, el: Element, n: u8) {
        energy_add(&mut self.energy, el, n);
    }

    #[inline]
    pub fn remove_energy(&mut self, el: Element, n: u8) {
        energy_sub(&mut self.energy, el, n);
    }

    #[inline]
    pub fn has_status(&self, s: StatusEffect) -> bool {
        self.status & s.bit() != 0
    }

    #[inline]
    pub fn add_status(&mut self, s: StatusEffect) {
        self.status |= s.bit();
    }

    #[inline]
    pub fn remove_status(&mut self, s: StatusEffect) {
        self.status &= !s.bit();
    }

    #[inline]
    pub fn clear_status(&mut self) {
        self.status = 0;
    }

    #[inline]
    pub fn has_any_status(&self) -> bool {
        self.status != 0
    }
}

// ------------------------------------------------------------------ //
// PlayerState
// ------------------------------------------------------------------ //

#[derive(Clone, Debug)]
pub struct PlayerState {
    pub active: Option<PokemonSlot>,
    pub bench: [Option<PokemonSlot>; 3],
    pub hand: Vec<u16>,
    pub deck: Vec<u16>,
    pub discard: Vec<u16>,
    pub points: u8,
    pub energy_types: Vec<Element>,
    pub energy_available: Option<Element>,
    // Per-turn flags
    pub has_attached_energy: bool,
    pub has_played_supporter: bool,
    pub has_retreated: bool,
    // Turn-scoped buffs
    pub attack_damage_bonus: i8,
    pub attack_damage_bonus_names: Vec<String>,
    pub retreat_cost_modifier: i8,
    pub cant_play_supporter_this_turn: bool,
    pub cant_play_supporter_incoming: bool,
}

impl Default for PlayerState {
    fn default() -> Self {
        Self {
            active: None,
            bench: [None, None, None],
            hand: Vec::new(),
            deck: Vec::new(),
            discard: Vec::new(),
            points: 0,
            energy_types: Vec::new(),
            energy_available: None,
            has_attached_energy: false,
            has_played_supporter: false,
            has_retreated: false,
            attack_damage_bonus: 0,
            attack_damage_bonus_names: Vec::new(),
            retreat_cost_modifier: 0,
            cant_play_supporter_this_turn: false,
            cant_play_supporter_incoming: false,
        }
    }
}

impl PlayerState {
    /// Returns references to all non-None Pokemon in play
    pub fn all_pokemon(&self) -> Vec<&PokemonSlot> {
        let mut result = Vec::new();
        if let Some(ref a) = self.active {
            result.push(a);
        }
        for slot in &self.bench {
            if let Some(ref s) = slot {
                result.push(s);
            }
        }
        result
    }

    /// Returns mutable references to all non-None Pokemon in play
    pub fn all_pokemon_mut(&mut self) -> Vec<&mut PokemonSlot> {
        let mut result = Vec::new();
        if let Some(ref mut a) = self.active {
            result.push(a);
        }
        for slot in &mut self.bench {
            if let Some(ref mut s) = slot {
                result.push(s);
            }
        }
        result
    }

    pub fn bench_count(&self) -> usize {
        self.bench.iter().filter(|s| s.is_some()).count()
    }

    pub fn has_any_pokemon(&self) -> bool {
        self.active.is_some() || self.bench.iter().any(|s| s.is_some())
    }

    pub fn total_pokemon_count(&self) -> usize {
        (if self.active.is_some() { 1 } else { 0 }) + self.bench_count()
    }
}

// ------------------------------------------------------------------ //
// GameState
// ------------------------------------------------------------------ //

#[derive(Clone)]
pub struct GameState {
    pub players: [PlayerState; 2],
    pub turn_number: i16,
    pub current_player: usize,
    pub first_player: usize,
    pub phase: GamePhase,
    pub winner: Option<i8>,
    pub rng: SmallRng,
}

impl GameState {
    pub fn new(seed: u64) -> Self {
        Self {
            players: [PlayerState::default(), PlayerState::default()],
            turn_number: -1,
            current_player: 0,
            first_player: 0,
            phase: GamePhase::Setup,
            winner: None,
            rng: SmallRng::seed_from_u64(seed),
        }
    }

    #[inline]
    pub fn current(&self) -> &PlayerState {
        &self.players[self.current_player]
    }

    #[inline]
    pub fn current_mut(&mut self) -> &mut PlayerState {
        &mut self.players[self.current_player]
    }

    #[inline]
    pub fn opponent(&self) -> &PlayerState {
        &self.players[1 - self.current_player]
    }

    #[inline]
    pub fn opponent_mut(&mut self) -> &mut PlayerState {
        &mut self.players[1 - self.current_player]
    }

    #[inline]
    pub fn opponent_index(&self) -> usize {
        1 - self.current_player
    }

    #[inline]
    pub fn is_first_turn(&self) -> bool {
        self.turn_number == 0
            || (self.turn_number == 1 && self.current_player != self.first_player)
    }

    #[inline]
    pub fn player_turn_number(&self) -> u16 {
        (self.turn_number.max(0) as u16) / 2
    }
}

// ------------------------------------------------------------------ //
// Slot accessors (equivalent to slot_utils.py)
// ------------------------------------------------------------------ //

#[inline]
pub fn get_slot<'a>(state: &'a GameState, slot_ref: SlotRef) -> Option<&'a PokemonSlot> {
    let player = &state.players[slot_ref.player as usize];
    if slot_ref.slot == -1 {
        player.active.as_ref()
    } else {
        player.bench[slot_ref.slot as usize].as_ref()
    }
}

#[inline]
pub fn get_slot_mut<'a>(state: &'a mut GameState, slot_ref: SlotRef) -> Option<&'a mut PokemonSlot> {
    let player = &mut state.players[slot_ref.player as usize];
    if slot_ref.slot == -1 {
        player.active.as_mut()
    } else {
        player.bench[slot_ref.slot as usize].as_mut()
    }
}

pub fn set_slot(state: &mut GameState, slot_ref: SlotRef, new_slot: Option<PokemonSlot>) {
    let player = &mut state.players[slot_ref.player as usize];
    if slot_ref.slot == -1 {
        player.active = new_slot;
    } else {
        player.bench[slot_ref.slot as usize] = new_slot;
    }
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::StatusEffect;

    #[test]
    fn pokemon_slot_status_flags() {
        let mut slot = PokemonSlot::new(0, 100);
        assert!(!slot.has_status(StatusEffect::Poisoned));
        slot.add_status(StatusEffect::Poisoned);
        assert!(slot.has_status(StatusEffect::Poisoned));
        assert!(!slot.has_status(StatusEffect::Burned));
        slot.add_status(StatusEffect::Burned);
        assert!(slot.has_status(StatusEffect::Burned));
        slot.remove_status(StatusEffect::Poisoned);
        assert!(!slot.has_status(StatusEffect::Poisoned));
        assert!(slot.has_status(StatusEffect::Burned));
    }

    #[test]
    fn pokemon_slot_energy() {
        let mut slot = PokemonSlot::new(0, 80);
        assert_eq!(slot.total_energy(), 0);
        slot.add_energy(Element::Fire, 2);
        slot.add_energy(Element::Water, 1);
        assert_eq!(slot.total_energy(), 3);
        assert_eq!(slot.energy_count(Element::Fire), 2);
        slot.remove_energy(Element::Fire, 1);
        assert_eq!(slot.total_energy(), 2);
    }

    #[test]
    fn game_state_clone_is_independent() {
        let mut state = GameState::new(42);
        state.players[0].points = 1;
        let mut clone = state.clone();
        clone.players[0].points = 2;
        assert_eq!(state.players[0].points, 1);
        assert_eq!(clone.players[0].points, 2);
    }

    #[test]
    fn slot_accessors() {
        let mut state = GameState::new(0);
        let slot = PokemonSlot::new(5, 70);
        state.players[0].active = Some(slot);

        let ref_ = SlotRef::active(0);
        assert!(get_slot(&state, ref_).is_some());
        assert_eq!(get_slot(&state, ref_).unwrap().card_idx, 5);

        let bench_ref = SlotRef::bench(0, 1);
        assert!(get_slot(&state, bench_ref).is_none());
    }
}
