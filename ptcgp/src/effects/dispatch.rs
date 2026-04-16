use std::collections::HashMap;
use crate::card::CardDb;
use crate::effects::{EffectKind, EffectContext};
use crate::state::GameState;
use crate::types::Element;

use super::{
    status_handlers,
    heal_handlers,
    draw_handlers,
    energy_handlers,
    movement_handlers,
    damage_mod_handlers,
    misc_handlers,
};

/// Apply a list of effects to the game state.
pub fn apply_effects(
    state: &mut GameState,
    db: &CardDb,
    effects: &[EffectKind],
    ctx: &EffectContext,
) {
    for effect in effects {
        apply_effect(state, db, effect, ctx);
    }
}

/// Dispatch a single effect to the appropriate handler function.
pub fn apply_effect(
    state: &mut GameState,
    db: &CardDb,
    effect: &EffectKind,
    ctx: &EffectContext,
) {
    match effect {
        // --- Status effects ---
        EffectKind::ApplyPoison => status_handlers::apply_poison(state, ctx),
        EffectKind::ApplyBurn => status_handlers::apply_burn(state, ctx),
        EffectKind::ApplySleep => status_handlers::apply_sleep(state, ctx),
        EffectKind::ApplyParalysis => status_handlers::apply_paralysis(state, ctx),
        EffectKind::ApplyConfusion => status_handlers::apply_confusion(state, ctx),
        EffectKind::ApplyRandomStatus => status_handlers::apply_random_status(state, ctx),
        EffectKind::ToxicPoison => status_handlers::toxic_poison(state, ctx),
        EffectKind::CoinFlipApplyParalysis => status_handlers::coin_flip_apply_paralysis(state, ctx),
        EffectKind::CoinFlipApplySleep => status_handlers::coin_flip_apply_sleep(state, ctx),
        EffectKind::SelfConfuse => status_handlers::self_confuse(state, ctx),
        EffectKind::SelfSleep => status_handlers::self_sleep(state, ctx),
        EffectKind::CoinFlipAttackBlockNextTurn => {
            status_handlers::coin_flip_attack_block_next_turn(state, ctx)
        }

        // --- Heal effects ---
        EffectKind::HealSelf { amount } => heal_handlers::heal_self(state, *amount, ctx),
        EffectKind::HealTarget { amount } => heal_handlers::heal_target(state, *amount, ctx),
        EffectKind::HealActive { amount } => heal_handlers::heal_active(state, *amount, ctx),
        EffectKind::HealAllOwn { amount } => heal_handlers::heal_all_own(state, *amount, ctx),
        EffectKind::HealGrassTarget { amount } => {
            heal_handlers::heal_grass_target(state, db, *amount, ctx)
        }
        EffectKind::HealWaterPokemon { amount } => {
            heal_handlers::heal_water_pokemon(state, db, *amount, ctx)
        }
        EffectKind::HealStage2Target { amount } => {
            heal_handlers::heal_stage2_target(state, db, *amount, ctx)
        }
        EffectKind::HealAndCureStatus { amount } => {
            heal_handlers::heal_and_cure_status(state, *amount, ctx)
        }
        EffectKind::HealSelfEqualToDamageDealt => {
            heal_handlers::heal_self_equal_to_damage_dealt(state, ctx)
        }
        EffectKind::HealAllNamedDiscardEnergy { name, amount } => {
            heal_handlers::heal_all_named_discard_energy(state, db, name, *amount, ctx)
        }
        EffectKind::HealAllTyped { element, amount } => {
            heal_handlers::heal_all_typed(state, db, element, *amount, ctx)
        }

        // --- Draw effects ---
        EffectKind::DrawCards { count } => draw_handlers::draw_cards(state, *count, ctx),
        EffectKind::DrawOneCard => draw_handlers::draw_one_card(state, ctx),
        EffectKind::DrawBasicPokemon => draw_handlers::draw_basic_pokemon(state, db, ctx),
        EffectKind::IonoHandShuffle => draw_handlers::iono_hand_shuffle(state, ctx),
        EffectKind::MarsHandShuffle => draw_handlers::mars_hand_shuffle(state, ctx),
        EffectKind::ShuffleHandIntoDeck => draw_handlers::shuffle_hand_into_deck(state, ctx),
        EffectKind::ShuffleHandDrawOpponentCount => {
            draw_handlers::shuffle_hand_draw_opponent_count(state, ctx)
        }
        EffectKind::DiscardToDraw { count } => draw_handlers::discard_to_draw(state, *count, ctx),
        EffectKind::MaintenanceShuffle { shuffle_count, draw_count } => {
            draw_handlers::maintenance_shuffle(state, *shuffle_count, *draw_count, ctx)
        }
        EffectKind::OpponentShuffleHandDraw { count } => {
            draw_handlers::opponent_shuffle_hand_draw(state, *count, ctx)
        }
        EffectKind::SearchDeckNamedBasic { name } => {
            draw_handlers::search_deck_named_basic(state, db, name, ctx)
        }
        EffectKind::SearchDeckRandomPokemon => {
            draw_handlers::search_deck_random_pokemon(state, db, ctx)
        }
        EffectKind::SearchDeckEvolvesFrom { name } => {
            draw_handlers::search_deck_evolves_from(state, db, name, ctx)
        }
        EffectKind::SearchDeckNamed { name } => {
            draw_handlers::search_deck_named(state, db, name, ctx)
        }
        EffectKind::SearchDeckMultiNamed { names } => {
            draw_handlers::search_deck_multi_named(state, db, names, ctx)
        }
        EffectKind::SearchDeckGrassPokemon => {
            draw_handlers::search_deck_grass_pokemon(state, db, ctx)
        }
        EffectKind::SearchDeckRandomBasic => {
            draw_handlers::search_deck_random_basic(state, db, ctx)
        }
        EffectKind::SearchDiscardRandomBasic => {
            draw_handlers::search_discard_random_basic(state, db, ctx)
        }
        EffectKind::LookTopOfDeck { count } => {
            draw_handlers::look_top_of_deck(state, *count, ctx)
        }
        EffectKind::RevealOpponentHand => draw_handlers::reveal_opponent_hand(state, ctx),
        EffectKind::LookOpponentHand => draw_handlers::look_opponent_hand(state, ctx),
        EffectKind::RevealOpponentSupporters => {
            draw_handlers::reveal_opponent_supporters(state, ctx)
        }
        EffectKind::FishingNet => draw_handlers::fishing_net(state, db, ctx),
        EffectKind::PokemonCommunication => draw_handlers::pokemon_communication(state, db, ctx),
        EffectKind::DiscardRandomCardOpponent => {
            draw_handlers::discard_random_card_opponent(state, ctx)
        }
        EffectKind::DiscardRandomToolFromHand => {
            draw_handlers::discard_random_tool_from_hand(state, db, ctx)
        }
        EffectKind::DiscardRandomItemFromHand => {
            draw_handlers::discard_random_item_from_hand(state, db, ctx)
        }
        EffectKind::DiscardTopDeck { count } => {
            energy_handlers::discard_top_deck(state, ctx, *count as usize)
        }

        // --- Energy effects ---
        EffectKind::AttachEnergyZoneSelf => {
            // Use the deck's primary energy type so ability-based attachments
            // (Gardevoir Psy Shadow, Baxcalibur Ice Maker, etc.) work even when
            // energy_available has already been consumed by the manual attachment.
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_self(state, ctx, element, 1);
        }
        EffectKind::AttachEnergyZoneSelfN { count } => {
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Grass);
            for _ in 0..*count {
                energy_handlers::attach_energy_zone_self(state, ctx, element, 1);
            }
        }
        EffectKind::AttachEnergyZoneBench { count } => {
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Grass);
            for _ in 0..*count {
                energy_handlers::attach_energy_zone_bench(state, db, ctx, element, None);
            }
        }
        EffectKind::AttachEnergyZoneBenchBracket { count } => {
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Grass);
            for _ in 0..*count {
                energy_handlers::attach_energy_zone_bench(state, db, ctx, element, None);
            }
        }
        EffectKind::AttachEnergyZoneBenchAnyBracket { count } => {
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Grass);
            for _ in 0..*count {
                energy_handlers::attach_energy_zone_bench(state, db, ctx, element, None);
            }
        }
        EffectKind::AttachEnergyZoneSelfBracket => {
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_self(state, ctx, element, 1);
        }
        EffectKind::AttachEnergyZoneNamed { name } => {
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_named(state, db, ctx, element, &[name.as_str()]);
        }
        EffectKind::AttachEnergyZoneToGrass => {
            energy_handlers::attach_energy_zone_to_grass(state, db, ctx)
        }
        EffectKind::AttachNEnergyZoneBench { count } => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::attach_n_energy_zone_bench(state, db, ctx, element, *count);
        }
        EffectKind::AttachWaterTwoBench => energy_handlers::attach_water_two_bench(state, ctx),
        EffectKind::AttachColorlessEnergyZoneBench => {
            energy_handlers::attach_colorless_energy_zone_bench(state, ctx)
        }
        EffectKind::AttachEnergyDiscardNamed { name: _ } => {
            // Attach energy then discard a named card — simplified to attach only
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_self(state, ctx, element, 1);
        }
        EffectKind::AttachEnergyNamedEndTurn { name } => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_named(state, db, ctx, element, &[name.as_str()]);
        }
        EffectKind::AbilityAttachEnergyEndTurn => {
            energy_handlers::ability_attach_energy_end_turn(state, ctx)
        }
        EffectKind::CoinFlipUntilTailsAttachEnergy => {
            // Use the deck's primary energy type (same fix as AttachEnergyZoneSelf).
            let element = state.players[ctx.acting_player].energy_types
                .first().copied()
                .or_else(|| state.players[ctx.acting_player].energy_available)
                .unwrap_or(Element::Water);
            energy_handlers::coin_flip_until_tails_attach_energy(state, db, ctx, element);
        }
        EffectKind::MultiCoinAttachBench { count } => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Fire);
            energy_handlers::multi_coin_attach_bench(state, db, ctx, *count, element, None);
        }
        EffectKind::LusamineAttach => {
            // Lusamine: attach energy to any bench — treated as AttachEnergyZoneBench(1)
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_bench(state, db, ctx, element, None);
        }
        EffectKind::FirstTurnEnergyAttach => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::first_turn_energy_attach(state, ctx, element);
        }
        EffectKind::DiscardEnergySelf { energy_type } => {
            // "Random" (or unrecognised) → discard a random energy from self.
            // Otherwise parse the element name and discard that specific type.
            match Element::from_str(energy_type) {
                Some(el) => energy_handlers::discard_energy_self(state, ctx, el),
                None     => energy_handlers::discard_random_energy_self(state, ctx),
            }
        }
        EffectKind::DiscardNEnergySelf { count, energy_type } => {
            match Element::from_str(energy_type) {
                Some(el) => energy_handlers::discard_n_energy_self(state, ctx, el, *count),
                None     => {
                    for _ in 0..*count {
                        energy_handlers::discard_random_energy_self(state, ctx);
                    }
                }
            }
        }
        EffectKind::DiscardAllEnergySelf => {
            energy_handlers::discard_all_energy_self(state, ctx)
        }
        EffectKind::DiscardAllTypedEnergySelf { element } => {
            if let Some(el) = Element::from_str(element) {
                energy_handlers::discard_all_typed_energy_self(state, ctx, el);
            }
        }
        EffectKind::CoinFlipDiscardRandomEnergyOpponent => {
            energy_handlers::coin_flip_discard_random_energy_opponent(state, ctx)
        }
        EffectKind::DiscardRandomEnergyOpponent => {
            energy_handlers::discard_random_energy_opponent(state, ctx)
        }
        EffectKind::DiscardRandomEnergyBothActive => {
            energy_handlers::discard_random_energy_both_active(state, ctx)
        }
        EffectKind::DiscardRandomEnergyAllPokemon => {
            energy_handlers::discard_random_energy_all_pokemon(state, ctx)
        }
        EffectKind::CoinFlipUntilTailsDiscardEnergy => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::coin_flip_until_tails_discard_energy(state, ctx, element);
        }
        EffectKind::CoinFlipUntilTailsDiscardRandomEnergyOpponent => {
            energy_handlers::coin_flip_until_tails_discard_random_energy_opponent(state, ctx);
        }
        EffectKind::MoveBenchEnergyToActive => {
            energy_handlers::move_bench_energy_to_active(state, ctx)
        }
        EffectKind::MoveWaterBenchToActive => {
            energy_handlers::move_water_bench_to_active(state, db, ctx)
        }
        EffectKind::MoveAllTypedEnergyBenchToActive { element } => {
            if let Some(el) = Element::from_str(element) {
                energy_handlers::move_all_typed_energy_bench_to_active(state, db, ctx, el, None);
            }
        }
        EffectKind::MoveAllElectricToActiveNamed { name } => {
            energy_handlers::move_all_electric_to_active_named(state, db, ctx, &[name.as_str()]);
        }
        EffectKind::ChangeOpponentEnergyType { from: _, to: _ } => {
            // Complex energy type change — no-op (not supported structurally)
        }
        EffectKind::OpponentNoEnergyNextTurn => {
            misc_handlers::opponent_no_energy_next_turn(state, ctx)
        }
        EffectKind::ReduceAttackCostNamed { name: _, amount: _ } => {
            // Attack cost reduction — handled structurally; no-op here
        }

        // --- Damage modifier effects (applied at attack time via compute_damage_modifier) ---
        EffectKind::CoinFlipBonusDamage { amount } => {
            // Coin-flip damage — handled at attack dispatch time
            let _ = amount;
        }
        EffectKind::CoinFlipNothing => {}
        EffectKind::BothCoinsBonus { amount } => { let _ = amount; }
        EffectKind::MultiCoinDamage { count, per } => { let _ = (count, per); }
        EffectKind::FlipUntilTailsDamage { per } => { let _ = per; }
        EffectKind::CoinFlipBonusOrSelfDamage { bonus, self_damage } => {
            let _ = (bonus, self_damage);
        }
        EffectKind::MultiCoinPerEnergyDamage { per } => { let _ = per; }
        EffectKind::MultiCoinPerTypedEnergyDamage { per, energy_type } => {
            let _ = (per, energy_type);
        }
        EffectKind::MultiCoinPerPokemonDamage { per } => { let _ = per; }
        EffectKind::FlipUntilTailsBonus { per } => { let _ = per; }
        EffectKind::MultiCoinBonus { count, per } => { let _ = (count, per); }
        EffectKind::BonusPerBench { per } => { let _ = per; }
        EffectKind::BonusPerBenchElement { per, element } => { let _ = (per, element); }
        EffectKind::BonusPerBenchNamed { per, name } => { let _ = (per, name); }
        EffectKind::BonusPerOpponentEnergy { per } => { let _ = per; }
        EffectKind::BonusIfExtraWaterEnergy { threshold, bonus } => {
            let _ = (threshold, bonus);
        }
        EffectKind::BonusIfOpponentDamaged { bonus } => { let _ = bonus; }
        EffectKind::BonusIfSelfDamaged { bonus } => { let _ = bonus; }
        EffectKind::BonusIfOpponentPoisoned { bonus } => { let _ = bonus; }
        EffectKind::BonusPerOpponentBench { per } => { let _ = per; }
        EffectKind::BonusIfToolAttached { bonus } => { let _ = bonus; }
        EffectKind::BonusIfOpponentHasTool { bonus } => { let _ = bonus; }
        EffectKind::BonusIfOpponentEx { bonus } => { let _ = bonus; }
        EffectKind::BonusIfOpponentBasic { bonus } => { let _ = bonus; }
        EffectKind::BonusIfOpponentElement { bonus, element } => { let _ = (bonus, element); }
        EffectKind::BonusIfOpponentHasAbility { bonus } => { let _ = bonus; }
        EffectKind::BonusIfBenchDamaged { bonus } => { let _ = bonus; }
        EffectKind::BonusIfKoLastTurn { bonus } => { let _ = bonus; }
        EffectKind::BonusIfPlayedSupporter { bonus } => { let _ = bonus; }
        EffectKind::BonusIfJustPromoted { bonus } => { let _ = bonus; }
        EffectKind::BonusIfOpponentMoreHp { bonus } => { let _ = bonus; }
        EffectKind::BonusIfOpponentHasStatus { bonus } => { let _ = bonus;
        }
        EffectKind::BonusEqualToDamageTaken => {}
        EffectKind::BonusIfExtraEnergy { threshold, bonus, energy_type } => {
            let _ = (threshold, bonus, energy_type);
        }
        EffectKind::BonusIfNamedInPlay { bonus, names } => { let _ = (bonus, names); }
        EffectKind::HalveOpponentHp => {
            let opp = 1 - ctx.acting_player;
            if let Some(slot) = state.players[opp].active.as_mut() {
                slot.current_hp = (slot.current_hp / 2).max(0);
            }
        }
        EffectKind::DoubleHeadsInstantKo => {
            // Handled at attack time — no-op here
        }

        // --- Movement effects ---
        EffectKind::SwitchOpponentActive => {
            movement_handlers::switch_opponent_active_random(state, ctx)
        }
        EffectKind::SwitchSelfToBench => movement_handlers::switch_self_active(state, ctx),
        EffectKind::SwitchSelfToBenchTyped { element } => {
            let el = Element::from_str(element);
            movement_handlers::switch_self_to_bench_typed(state, ctx, db, el);
        }
        EffectKind::SwitchOpponentBasicToActive => {
            movement_handlers::switch_opponent_basic_to_active(state, ctx, db)
        }
        EffectKind::SwitchOpponentDamagedToActive => {
            movement_handlers::switch_opponent_damaged_to_active(state, ctx)
        }
        EffectKind::SwitchUltraBeast => movement_handlers::switch_ultra_beast(state, ctx),
        EffectKind::AbilityBenchToActive => movement_handlers::ability_bench_to_active(state, ctx),
        EffectKind::CoinFlipBounceOpponent => {
            movement_handlers::coin_flip_bounce_opponent(state, ctx)
        }
        EffectKind::ReturnActiveToHandNamed { name } => {
            movement_handlers::return_active_to_hand_named(state, ctx, db, &[name.as_str()])
        }
        EffectKind::ReturnColorlessToHand => {
            // Return any Colorless-type active to hand — use empty name filter
            movement_handlers::return_active_to_hand_named(state, ctx, db, &[])
        }
        EffectKind::PlaceOpponentBasicFromDiscard => {
            // No-op: complex interaction not yet fully modelled
        }
        EffectKind::ShuffleOpponentActiveIntoDeck => {
            movement_handlers::shuffle_opponent_active_into_deck(state, ctx)
        }

        // --- Splash / bench damage effects ---
        EffectKind::SplashBenchOpponent { amount } => {
            damage_mod_handlers::damage_all_opponent_bench(state, *amount, ctx)
        }
        EffectKind::SplashBenchOwn { amount } => {
            // Damage own bench
            let p = ctx.acting_player;
            for i in 0..state.players[p].bench.len() {
                if state.players[p].bench[i].is_some() {
                    let sr = crate::actions::SlotRef::bench(p, i);
                    if let Some(slot) = crate::state::get_slot_mut(state, sr) {
                        slot.current_hp = (slot.current_hp - *amount).max(0);
                    }
                }
            }
        }
        EffectKind::SplashAllOpponent { amount } => {
            damage_mod_handlers::damage_all_opponent(state, *amount, ctx)
        }
        EffectKind::RandomHitOne { amount } => {
            // Hit a random opponent Pokémon (active or bench)
            use rand::Rng;
            let opp = 1 - ctx.acting_player;
            let mut targets = Vec::new();
            if state.players[opp].active.is_some() {
                targets.push(crate::actions::SlotRef::active(opp));
            }
            for i in 0..3 {
                if state.players[opp].bench[i].is_some() {
                    targets.push(crate::actions::SlotRef::bench(opp, i));
                }
            }
            if !targets.is_empty() {
                let idx = state.rng.gen_range(0..targets.len());
                let sr = targets[idx];
                if let Some(slot) = crate::state::get_slot_mut(state, sr) {
                    slot.current_hp = (slot.current_hp - *amount).max(0);
                }
            }
        }
        EffectKind::RandomMultiHit { count, amount } => {
            use rand::Rng;
            let opp = 1 - ctx.acting_player;
            for _ in 0..*count {
                let mut targets = Vec::new();
                if state.players[opp].active.is_some() {
                    targets.push(crate::actions::SlotRef::active(opp));
                }
                for i in 0..3 {
                    if state.players[opp].bench[i].is_some() {
                        targets.push(crate::actions::SlotRef::bench(opp, i));
                    }
                }
                if !targets.is_empty() {
                    let idx = state.rng.gen_range(0..targets.len());
                    let sr = targets[idx];
                    if let Some(slot) = crate::state::get_slot_mut(state, sr) {
                        slot.current_hp = (slot.current_hp - *amount).max(0);
                    }
                }
            }
        }
        EffectKind::SelfDamage { amount } => {
            // Head Smash and similar: self-damage only triggers when the attack KO'd the opponent.
            // "opponent_ko" is 1 if the attack KO'd the defender, 0 otherwise. If not set (non-attack
            // context), default to 0 (don't self-damage without a KO condition).
            let did_ko = ctx.extra.get("opponent_ko").copied().unwrap_or(0) != 0;
            if did_ko {
                damage_mod_handlers::self_damage(state, *amount, ctx.source_ref, ctx)
            }
        }
        EffectKind::SelfDamageOnCoinFlipResult { amount } => {
            use rand::Rng;
            if state.rng.gen::<f64>() >= 0.5 {
                damage_mod_handlers::self_damage(state, *amount, ctx.source_ref, ctx);
            }
        }
        EffectKind::DiscardOpponentToolsBeforeDamage => {
            // Discard attached tool from opponent's active
            let opp = 1 - ctx.acting_player;
            if let Some(slot) = state.players[opp].active.as_mut() {
                if let Some(tool_idx) = slot.tool_idx.take() {
                    state.players[opp].discard.push(tool_idx);
                }
            }
        }
        EffectKind::DiscardAllOpponentTools => {
            let opp = 1 - ctx.acting_player;
            // Active
            if let Some(slot) = state.players[opp].active.as_mut() {
                if let Some(tool_idx) = slot.tool_idx.take() {
                    state.players[opp].discard.push(tool_idx);
                }
            }
            // Bench
            for i in 0..3 {
                if let Some(slot) = state.players[opp].bench[i].as_mut() {
                    if let Some(tool_idx) = slot.tool_idx.take() {
                        state.players[opp].discard.push(tool_idx);
                    }
                }
            }
        }
        EffectKind::BenchHitOpponent { amount } => {
            damage_mod_handlers::damage_specific_bench(state, *amount, ctx.target_ref, ctx)
        }
        EffectKind::MoveDamageToOpponent { amount } => {
            // Transfer damage counters from self to opponent
            let p = ctx.acting_player;
            let opp = 1 - p;
            let damage_on_self = state.players[p].active
                .as_ref()
                .map(|s| s.max_hp - s.current_hp)
                .unwrap_or(0)
                .min(*amount);
            // Heal self
            if let Some(slot) = state.players[p].active.as_mut() {
                slot.current_hp = (slot.current_hp + damage_on_self).min(slot.max_hp);
            }
            // Damage opponent
            if let Some(slot) = state.players[opp].active.as_mut() {
                slot.current_hp = (slot.current_hp - damage_on_self).max(0);
            }
        }

        // --- Misc effects ---
        EffectKind::CantRetreatNextTurn => misc_handlers::cant_retreat_next_turn(state, ctx),
        EffectKind::PreventDamageNextTurn => misc_handlers::prevent_damage_next_turn(state, ctx),
        EffectKind::TakeLessDamageNextTurn { amount } => {
            misc_handlers::take_less_damage_next_turn(state, *amount as i8, ctx)
        }
        EffectKind::DefenderAttacksDoLessDamage { amount } => {
            misc_handlers::defender_attacks_do_less_damage(state, *amount as i8, ctx)
        }
        EffectKind::OpponentNoSupporterNextTurn => {
            misc_handlers::opponent_no_supporter_next_turn(state, ctx)
        }
        EffectKind::SupporterDamageAura { amount, names } => {
            misc_handlers::supporter_damage_aura(state, *amount as i8, names, ctx)
        }
        EffectKind::SupporterDamageAuraVsEx { amount } => {
            misc_handlers::supporter_damage_aura_vs_ex(state, *amount as i8, ctx)
        }
        EffectKind::ReduceRetreatCost { amount } => {
            misc_handlers::reduce_retreat_cost(state, *amount as i8, ctx)
        }
        EffectKind::CopyOpponentAttack => misc_handlers::copy_opponent_attack(state, db, ctx),
        EffectKind::CoinFlipShuffleOpponentCard => {
            misc_handlers::coin_flip_shuffle_opponent_card(state, ctx)
        }
        EffectKind::MultiCoinShuffleOpponentCards { count } => {
            misc_handlers::multi_coin_shuffle_opponent_cards(state, *count, ctx)
        }
        EffectKind::CantAttackNextTurn => misc_handlers::cant_attack_next_turn(state, ctx),
        EffectKind::SelfCantAttackNextTurn => misc_handlers::self_cant_attack_next_turn(state, ctx),
        EffectKind::CoinFlipSelfCantAttackNextTurn => {
            misc_handlers::coin_flip_self_cant_attack_next_turn(state, ctx)
        }
        EffectKind::SelfCantUseSpecificAttack { name: _ } => {
            misc_handlers::self_cant_use_specific_attack(state, ctx)
        }
        EffectKind::SelfAttackBuffNextTurn { amount } => {
            misc_handlers::self_attack_buff_next_turn(state, *amount as i8, ctx)
        }
        EffectKind::TakeMoreDamageNextTurn { amount } => {
            misc_handlers::take_more_damage_next_turn(state, *amount as i8, ctx)
        }
        EffectKind::NextTurnAllDamageReduction { amount } => {
            misc_handlers::next_turn_all_damage_reduction(state, *amount as i8, ctx)
        }
        EffectKind::NextTurnMetalDamageReduction { amount } => {
            misc_handlers::next_turn_metal_damage_reduction(state, *amount as i8, ctx)
        }
        EffectKind::OpponentCostIncreaseNextTurn { amount: _ } => {
            misc_handlers::opponent_cost_increase_next_turn(state, ctx)
        }
        EffectKind::OpponentNoItemsNextTurn => {
            misc_handlers::opponent_no_items_next_turn(state, ctx)
        }
        EffectKind::BigMalasada => misc_handlers::big_malasada(state, ctx),
        EffectKind::MythicalSlab => misc_handlers::mythical_slab(state, db, ctx),
        EffectKind::BeastWallProtection => misc_handlers::beast_wall_protection(state, ctx),
        EffectKind::RareCandyEvolve => misc_handlers::rare_candy_evolve(state, db, ctx),
        EffectKind::HpBonus { amount } => misc_handlers::hp_bonus(state, *amount, ctx),

        // --- Passive ability effects (structural; no runtime state mutation needed) ---
        EffectKind::PassiveDamageReduction { amount: _ } => {}
        EffectKind::PassiveRetaliate { amount: _ } => {}
        EffectKind::PassiveBlockSupporters => {
            misc_handlers::passive_block_supporters(state, ctx);
        }
        EffectKind::PassiveDittoImpostor { hp: _ } => {}
        EffectKind::PassiveDoubleGrassEnergy => {}
        EffectKind::PassiveImmuneStatus => {}
        EffectKind::PassiveKoEnergyTransfer => {}
        EffectKind::PassiveSurviveKoCoinFlip => {}
        EffectKind::PassiveTypeDamageBoost { element: _, amount: _ } => {}
        EffectKind::PassiveTypeDamageReduction { element: _, amount: _ } => {}
        EffectKind::PassiveBenchRetreatReduction { amount: _ } => {}
        EffectKind::PassiveBlockEvolution => {}
        EffectKind::PassiveCheckupDamage { amount: _ } => {}
        EffectKind::PassiveCoinFlipDamageReduction { amount: _ } => {}
        EffectKind::PassiveDarkEnergyPing { amount: _ } => {}
        EffectKind::PassiveElectricalCord => {}
        EffectKind::PassiveEnergySleep => {}
        EffectKind::PassiveFirstTurnNoRetreat => {}
        EffectKind::PassiveFreeRetreatWithEnergy => {}
        EffectKind::PassiveKoRetaliate { amount: _ } => {}
        EffectKind::PassiveLumBerry => {}
        EffectKind::PassiveMoveDamageToSelf => {}
        EffectKind::PassiveNamedNoRetreat { name: _ } => {}
        EffectKind::PassiveNoHealing => {
            // Card text: "Pokémon (both yours and your opponent's) can't be healed."
            // Set the flag for both players; reset each start_turn and re-applied
            // by passive dispatch.  If a future card has "opponent can't heal" only,
            // a new EffectKind variant should be introduced.
            state.players[0].cant_heal_this_turn = true;
            state.players[1].cant_heal_this_turn = true;
            let _ = ctx;
        }
        EffectKind::PassiveOpponentAttackCostIncrease { amount: _ } => {}
        EffectKind::PassiveOpponentDamageReduction { amount: _ } => {}
        EffectKind::PassivePreventAttackEffects => {}
        EffectKind::PassivePreventExDamage => {}
        EffectKind::PassivePsychicCleanse => {}
        EffectKind::PassiveRetaliatePoison => {}
        EffectKind::PassiveArceusCostReduction => {}
        EffectKind::PassiveArceusDamageReduction { amount: _ } => {}
        EffectKind::PassiveArceusNoRetreat => {}
        EffectKind::PassiveBeastiteDamage { amount: _ } => {}
    }
}

/// Compute the damage modifier for an attack's effects.
/// Returns (final_damage, skip_damage, extra_map).
/// Coin-flip damage variants are resolved here; other bonuses accumulate.
pub fn compute_damage_modifier(
    state: &mut GameState,
    db: &CardDb,
    base_damage: i16,
    effects: &[EffectKind],
    ctx: &EffectContext,
) -> (i16, bool, HashMap<String, i32>) {
    use rand::Rng;
    let _ = db;
    let mut bonus: i16 = 0;
    let mut base_replaced: Option<i16> = None;

    for effect in effects {
        match effect {
            EffectKind::CoinFlipBonusDamage { amount } => {
                let heads = state.rng.gen::<bool>();
                if heads { bonus += *amount; }
                state.coin_flip_log.push(
                    if heads { format!("🪙 Heads! +{}dmg", amount) }
                    else     { "🪙 Tails! No bonus damage".to_string() }
                );
            }
            EffectKind::MultiCoinPerEnergyDamage { per } => {
                let energy_count = state.players[ctx.acting_player].active
                    .as_ref()
                    .map(|s| s.total_energy())
                    .unwrap_or(0);
                let mut total: i16 = 0;
                let mut results: Vec<&str> = Vec::new();
                for _ in 0..energy_count {
                    let h = state.rng.gen::<bool>();
                    if h { total += *per; results.push("H"); } else { results.push("T"); }
                }
                if !results.is_empty() {
                    state.coin_flip_log.push(format!(
                        "🪙 {} flip{}: {}  → {}dmg",
                        energy_count, if energy_count == 1 { "" } else { "s" },
                        results.join(" "), total
                    ));
                }
                base_replaced = Some(total);
            }
            EffectKind::BonusIfOpponentPoisoned { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref active) = state.players[opp].active {
                    if active.has_status(crate::types::StatusEffect::Poisoned) {
                        bonus += *b;
                    }
                }
            }
            EffectKind::BonusIfOpponentHasStatus { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref active) = state.players[opp].active {
                    if active.has_any_status() { bonus += *b; }
                }
            }
            EffectKind::BonusPerBench { per } => {
                // Count acting player's own bench (not active).
                let p = ctx.acting_player;
                let count = state.players[p].bench.iter().filter(|s| s.is_some()).count() as i16;
                bonus += per * count;
            }
            EffectKind::BonusPerOpponentBench { per } => {
                let opp = 1 - ctx.acting_player;
                let count = state.players[opp].bench.iter().filter(|s| s.is_some()).count() as i16;
                bonus += per * count;
            }
            EffectKind::BonusIfOpponentDamaged { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref active) = state.players[opp].active {
                    if active.current_hp < active.max_hp { bonus += *b; }
                }
            }
            EffectKind::BonusIfOpponentEx { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref active) = state.players[opp].active {
                    if db.get_by_idx(active.card_idx).is_ex { bonus += *b; }
                }
            }
            EffectKind::BonusIfOpponentBasic { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref active) = state.players[opp].active {
                    if db.get_by_idx(active.card_idx).stage == Some(crate::types::Stage::Basic) {
                        bonus += *b;
                    }
                }
            }
            EffectKind::BonusIfOpponentElement { bonus: b, element } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref active) = state.players[opp].active {
                    if let Some(el) = crate::types::Element::from_str(element) {
                        if db.get_by_idx(active.card_idx).element == Some(el) { bonus += *b; }
                    }
                }
            }
            EffectKind::BonusIfBenchDamaged { bonus: b } => {
                // Drampa Berserk: +bonus if any of acting player's bench Pokémon are damaged.
                let p = ctx.acting_player;
                let bench_damaged = state.players[p].bench.iter().any(|bs| {
                    bs.as_ref().map(|s| s.current_hp < s.max_hp).unwrap_or(false)
                });
                if bench_damaged {
                    bonus += *b;
                }
            }
            EffectKind::BonusIfExtraEnergy { threshold, bonus: b, energy_type } => {
                let count = if energy_type.is_empty() {
                    state.players[ctx.acting_player].active
                        .as_ref()
                        .map(|s| s.total_energy() as i16)
                        .unwrap_or(0)
                } else {
                    crate::types::Element::from_str(energy_type)
                        .map(|el| {
                            state.players[ctx.acting_player].active
                                .as_ref()
                                .map(|s| s.energy[el.idx()] as i16)
                                .unwrap_or(0)
                        })
                        .unwrap_or(0)
                };
                if count >= *threshold {
                    bonus += *b;
                }
            }
            EffectKind::BonusIfExtraWaterEnergy { threshold, bonus: b } => {
                let count = state.players[ctx.acting_player].active
                    .as_ref()
                    .map(|s| s.energy[crate::types::Element::Water.idx()] as i16)
                    .unwrap_or(0);
                if count >= *threshold {
                    bonus += *b;
                }
            }

            // --- Multi-coin damage variants (replace base damage) ---
            EffectKind::MultiCoinDamage { count, per } => {
                let mut heads = 0u16;
                let mut results: Vec<&str> = Vec::new();
                for _ in 0..*count {
                    let h = state.rng.gen::<bool>();
                    if h { heads += 1; results.push("H"); } else { results.push("T"); }
                }
                let total = (heads as i16) * *per;
                state.coin_flip_log.push(format!(
                    "🪙 {} flip{}: {} → {}dmg",
                    count, if *count == 1 { "" } else { "s" },
                    results.join(" "), total
                ));
                base_replaced = Some(total);
            }
            EffectKind::FlipUntilTailsDamage { per } => {
                let mut heads = 0u16;
                let mut results: Vec<&str> = Vec::new();
                loop {
                    let h = state.rng.gen::<bool>();
                    if h {
                        heads += 1;
                        results.push("H");
                    } else {
                        results.push("T");
                        break;
                    }
                }
                let total = (heads as i16) * *per;
                state.coin_flip_log.push(format!(
                    "🪙 Flip until tails: {} → {}dmg",
                    results.join(" "), total
                ));
                base_replaced = Some(total);
            }
            EffectKind::MultiCoinPerTypedEnergyDamage { per, energy_type } => {
                // Flip 1 coin per typed energy attached to self; total = per × heads.
                let energy_count = if let Some(el) = crate::types::Element::from_str(energy_type) {
                    state.players[ctx.acting_player].active
                        .as_ref()
                        .map(|s| s.energy[el.idx()])
                        .unwrap_or(0)
                } else {
                    0
                };
                let mut heads = 0u16;
                let mut results: Vec<&str> = Vec::new();
                for _ in 0..energy_count {
                    let h = state.rng.gen::<bool>();
                    if h { heads += 1; results.push("H"); } else { results.push("T"); }
                }
                let total = (heads as i16) * *per;
                if !results.is_empty() {
                    state.coin_flip_log.push(format!(
                        "🪙 {} flip{}: {} → {}dmg",
                        energy_count, if energy_count == 1 { "" } else { "s" },
                        results.join(" "), total
                    ));
                }
                base_replaced = Some(total);
            }
            EffectKind::MultiCoinPerPokemonDamage { per } => {
                // Flip 1 coin per Pokemon you have in play (active + bench).
                let pcount = state.players[ctx.acting_player].total_pokemon_count();
                let mut heads = 0u16;
                let mut results: Vec<&str> = Vec::new();
                for _ in 0..pcount {
                    let h = state.rng.gen::<bool>();
                    if h { heads += 1; results.push("H"); } else { results.push("T"); }
                }
                let total = (heads as i16) * *per;
                if !results.is_empty() {
                    state.coin_flip_log.push(format!(
                        "🪙 {} flip{}: {} → {}dmg",
                        pcount, if pcount == 1 { "" } else { "s" },
                        results.join(" "), total
                    ));
                }
                base_replaced = Some(total);
            }

            // --- Coin-flip bonus variants (add to base damage) ---
            EffectKind::BothCoinsBonus { amount } => {
                let h1 = state.rng.gen::<bool>();
                let h2 = state.rng.gen::<bool>();
                if h1 && h2 {
                    bonus += *amount;
                    state.coin_flip_log.push(format!("🪙 H H! +{}dmg", amount));
                } else {
                    state.coin_flip_log.push(format!(
                        "🪙 {} {} — no bonus",
                        if h1 { "H" } else { "T" },
                        if h2 { "H" } else { "T" }
                    ));
                }
            }
            EffectKind::MultiCoinBonus { count, per } => {
                let mut heads = 0u16;
                let mut results: Vec<&str> = Vec::new();
                for _ in 0..*count {
                    let h = state.rng.gen::<bool>();
                    if h { heads += 1; results.push("H"); } else { results.push("T"); }
                }
                let add = (heads as i16) * *per;
                bonus += add;
                state.coin_flip_log.push(format!(
                    "🪙 {} flip{}: {} → +{}dmg",
                    count, if *count == 1 { "" } else { "s" },
                    results.join(" "), add
                ));
            }
            EffectKind::FlipUntilTailsBonus { per } => {
                let mut heads = 0u16;
                let mut results: Vec<&str> = Vec::new();
                loop {
                    let h = state.rng.gen::<bool>();
                    if h {
                        heads += 1;
                        results.push("H");
                    } else {
                        results.push("T");
                        break;
                    }
                }
                let add = (heads as i16) * *per;
                bonus += add;
                state.coin_flip_log.push(format!(
                    "🪙 Flip until tails: {} → +{}dmg",
                    results.join(" "), add
                ));
            }
            EffectKind::CoinFlipBonusOrSelfDamage { bonus: b, self_damage } => {
                let h = state.rng.gen::<bool>();
                if h {
                    bonus += *b;
                    state.coin_flip_log.push(format!("🪙 Heads! +{}dmg", b));
                } else {
                    state.coin_flip_log.push(format!("🪙 Tails! Self-damage {}", self_damage));
                    if let Some(slot) = state.players[ctx.acting_player].active.as_mut() {
                        slot.current_hp = (slot.current_hp - *self_damage).max(0);
                    }
                }
            }

            // --- Conditional bonuses based on opponent / self / board state ---
            EffectKind::BonusPerOpponentEnergy { per } => {
                let opp = 1 - ctx.acting_player;
                let energy_count = state.players[opp].active
                    .as_ref()
                    .map(|s| s.total_energy() as i16)
                    .unwrap_or(0);
                bonus += per * energy_count;
            }
            EffectKind::BonusPerBenchElement { per, element } => {
                let p = ctx.acting_player;
                if let Some(el) = crate::types::Element::from_str(element) {
                    let count = state.players[p].bench.iter().filter_map(|bs| {
                        bs.as_ref().and_then(|s| {
                            db.try_get_by_idx(s.card_idx).and_then(|c| c.element)
                                .map(|e| e == el)
                        })
                    }).filter(|&b| b).count() as i16;
                    bonus += per * count;
                }
            }
            EffectKind::BonusPerBenchNamed { per, name } => {
                let p = ctx.acting_player;
                let target = name.to_ascii_lowercase();
                let count = state.players[p].bench.iter().filter_map(|bs| {
                    bs.as_ref().and_then(|s| {
                        db.try_get_by_idx(s.card_idx)
                            .map(|c| c.name.to_ascii_lowercase() == target)
                    })
                }).filter(|&b| b).count() as i16;
                bonus += per * count;
            }
            EffectKind::BonusIfSelfDamaged { bonus: b } => {
                if let Some(ref slot) = state.players[ctx.acting_player].active {
                    if slot.current_hp < slot.max_hp {
                        bonus += *b;
                    }
                }
            }
            EffectKind::BonusIfToolAttached { bonus: b } => {
                if let Some(ref slot) = state.players[ctx.acting_player].active {
                    if slot.tool_idx.is_some() {
                        bonus += *b;
                    }
                }
            }
            EffectKind::BonusIfOpponentHasTool { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref slot) = state.players[opp].active {
                    if slot.tool_idx.is_some() {
                        bonus += *b;
                    }
                }
            }
            EffectKind::BonusIfOpponentHasAbility { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                if let Some(ref slot) = state.players[opp].active {
                    if let Some(card) = db.try_get_by_idx(slot.card_idx) {
                        if card.ability.is_some() {
                            bonus += *b;
                        }
                    }
                }
            }
            EffectKind::BonusIfKoLastTurn { bonus: b } => {
                // TODO: needs state field `ko_last_turn` on PlayerState.
                // No such field exists yet; skip without modifying damage.
                let _ = b;
            }
            EffectKind::BonusIfPlayedSupporter { bonus: b } => {
                if state.players[ctx.acting_player].has_played_supporter {
                    bonus += *b;
                }
            }
            EffectKind::BonusIfJustPromoted { bonus: b } => {
                // TODO: needs state field `was_promoted_this_turn` on PokemonSlot.
                // No such field exists yet; skip without modifying damage.
                let _ = b;
            }
            EffectKind::BonusIfOpponentMoreHp { bonus: b } => {
                let opp = 1 - ctx.acting_player;
                let opp_hp = state.players[opp].active.as_ref().map(|s| s.current_hp).unwrap_or(0);
                let self_hp = state.players[ctx.acting_player].active
                    .as_ref().map(|s| s.current_hp).unwrap_or(0);
                if opp_hp > self_hp {
                    bonus += *b;
                }
            }
            EffectKind::BonusIfNamedInPlay { bonus: b, names } => {
                let p = ctx.acting_player;
                let lc_names: Vec<String> = names.iter().map(|n| n.to_ascii_lowercase()).collect();
                let mut found = false;
                // Check active
                if let Some(ref slot) = state.players[p].active {
                    if let Some(card) = db.try_get_by_idx(slot.card_idx) {
                        let lcn = card.name.to_ascii_lowercase();
                        if lc_names.iter().any(|n| *n == lcn) {
                            found = true;
                        }
                    }
                }
                // Check bench
                if !found {
                    for bs in &state.players[p].bench {
                        if let Some(slot) = bs {
                            if let Some(card) = db.try_get_by_idx(slot.card_idx) {
                                let lcn = card.name.to_ascii_lowercase();
                                if lc_names.iter().any(|n| *n == lcn) {
                                    found = true;
                                    break;
                                }
                            }
                        }
                    }
                }
                if found {
                    bonus += *b;
                }
            }
            EffectKind::BonusEqualToDamageTaken => {
                if let Some(ref slot) = state.players[ctx.acting_player].active {
                    let dmg = slot.max_hp - slot.current_hp;
                    bonus += dmg;
                }
            }
            EffectKind::DoubleHeadsInstantKo => {
                let h1 = state.rng.gen::<bool>();
                let h2 = state.rng.gen::<bool>();
                if h1 && h2 {
                    let opp = 1 - ctx.acting_player;
                    let target_hp = state.players[opp].active.as_ref()
                        .map(|s| s.current_hp).unwrap_or(0);
                    state.coin_flip_log.push("🪙 H H! Instant KO".to_string());
                    base_replaced = Some(target_hp);
                } else {
                    state.coin_flip_log.push(format!(
                        "🪙 {} {} — no KO",
                        if h1 { "H" } else { "T" },
                        if h2 { "H" } else { "T" }
                    ));
                }
            }
            _ => {}
        }
    }

    // Apply supporter damage aura (Giovanni, Red, etc.)
    // attack_damage_bonus is set each turn by supporter trainers and cleared at turn start.
    let aura = state.players[ctx.acting_player].attack_damage_bonus as i16;
    if aura != 0 {
        let names = state.players[ctx.acting_player].attack_damage_bonus_names.clone();
        let applies = if names.is_empty() {
            // No restriction — applies to all targets (Giovanni-style)
            true
        } else if names.iter().any(|n| n == "ex") {
            // Red-style: only applies when opponent's active is an ex Pokémon
            let opp = 1 - ctx.acting_player;
            state.players[opp].active.as_ref()
                .map(|s| db.get_by_idx(s.card_idx).is_ex)
                .unwrap_or(false)
        } else {
            // Named-attacker restriction: only applies when the attacker's name is in the list
            state.players[ctx.acting_player].active.as_ref()
                .map(|s| names.iter().any(|n| *n == db.get_by_idx(s.card_idx).name))
                .unwrap_or(false)
        };
        if applies {
            bonus += aura;
        }
    }

    let final_damage = if let Some(replaced) = base_replaced {
        replaced + bonus
    } else {
        base_damage + bonus
    };
    (final_damage, false, HashMap::new())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::{Card, CardDb};
    use crate::state::{GameState, PokemonSlot};
    use crate::types::{CardKind, Element, Stage};

    fn make_card(idx: u16, name: &str, element: Option<Element>) -> Card {
        Card {
            id: format!("test-{}", idx),
            idx,
            name: name.to_string(),
            kind: CardKind::Pokemon,
            stage: Some(Stage::Basic),
            element,
            hp: 100,
            weakness: None,
            retreat_cost: 1,
            is_ex: false,
            is_mega_ex: false,
            evolves_from: None,
            attacks: vec![],
            ability: None,
            trainer_effect_text: String::new(),
            trainer_handler: String::new(),
            trainer_effects: vec![],
            ko_points: 1,
        }
    }

    fn make_db(cards: Vec<Card>) -> CardDb {
        let mut db = CardDb::new_empty();
        for c in cards {
            let idx = c.idx;
            db.id_to_idx.insert(c.id.clone(), idx);
            db.name_to_indices.entry(c.name.clone())
                .or_insert_with(Vec::new).push(idx);
            db.cards.push(c);
        }
        db
    }

    /// Pikachu ex Circle Circuit: 30 damage per Lightning bench Pokémon.
    #[test]
    fn pikachu_ex_circle_circuit_bonus_per_bench_element() {
        let pikachu = make_card(0, "Pikachu ex", Some(Element::Lightning));
        let raichu  = make_card(1, "Raichu",     Some(Element::Lightning));
        let other   = make_card(2, "Bulbasaur",  Some(Element::Grass));
        let db = make_db(vec![pikachu, raichu, other]);

        let mut state = GameState::new(0);
        // Active = Pikachu ex
        state.players[0].active = Some(PokemonSlot::new(0, 70));
        // Bench = 2 Lightning + 1 Grass
        state.players[0].bench[0] = Some(PokemonSlot::new(1, 90));
        state.players[0].bench[1] = Some(PokemonSlot::new(1, 90));
        state.players[0].bench[2] = Some(PokemonSlot::new(2, 70));
        // Opponent active dummy
        state.players[1].active = Some(PokemonSlot::new(2, 70));

        let ctx = EffectContext::new(0);
        let effects = vec![EffectKind::BonusPerBenchElement {
            per: 30,
            element: "Lightning".to_string(),
        }];
        let (final_damage, _, _) = compute_damage_modifier(&mut state, &db, 0, &effects, &ctx);
        // 2 Lightning bench × 30 = 60
        assert_eq!(final_damage, 60);
    }

    /// Alakazam Psychic: +20 damage per energy on opponent's active.
    #[test]
    fn alakazam_psychic_bonus_per_opponent_energy() {
        let alakazam = make_card(0, "Alakazam", Some(Element::Psychic));
        let mewtwo   = make_card(1, "Mewtwo",   Some(Element::Psychic));
        let db = make_db(vec![alakazam, mewtwo]);

        let mut state = GameState::new(0);
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        let mut opp = PokemonSlot::new(1, 100);
        opp.add_energy(Element::Psychic, 2);
        opp.add_energy(Element::Water, 1);
        state.players[1].active = Some(opp);

        let ctx = EffectContext::new(0);
        let effects = vec![EffectKind::BonusPerOpponentEnergy { per: 20 }];
        let base = 60;
        let (final_damage, _, _) = compute_damage_modifier(&mut state, &db, base, &effects, &ctx);
        // base 60 + 3 energies × 20 = 60 + 60 = 120
        assert_eq!(final_damage, 120);
    }

    /// Marowak ex Bonemerang: 80 damage per heads on 2 coin flips.
    /// With deterministic seed we just check it's one of the valid outcomes (0/80/160).
    #[test]
    fn marowak_ex_bonemerang_multi_coin_damage() {
        let marowak = make_card(0, "Marowak ex", Some(Element::Fighting));
        let dummy   = make_card(1, "Dummy",      Some(Element::Grass));
        let db = make_db(vec![marowak, dummy]);

        let mut state = GameState::new(123); // fixed seed
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state.players[1].active = Some(PokemonSlot::new(1, 100));

        let ctx = EffectContext::new(0);
        let effects = vec![EffectKind::MultiCoinDamage { count: 2, per: 80 }];
        let (final_damage, _, _) = compute_damage_modifier(&mut state, &db, 0, &effects, &ctx);
        assert!(
            final_damage == 0 || final_damage == 80 || final_damage == 160,
            "expected 0/80/160 — got {}", final_damage
        );

        // Sample many flips: average should be ~80 (1 head expected on 2 flips × 80).
        let mut total: i64 = 0;
        let trials = 2000;
        for seed in 0..trials {
            let mut s = GameState::new(seed);
            s.players[0].active = Some(PokemonSlot::new(0, 100));
            s.players[1].active = Some(PokemonSlot::new(1, 100));
            let (d, _, _) = compute_damage_modifier(&mut s, &db, 0, &effects, &ctx);
            total += d as i64;
        }
        let avg = total as f64 / trials as f64;
        // Expected = 80; allow loose tolerance.
        assert!(avg > 60.0 && avg < 100.0, "avg = {}", avg);
    }
}

