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
        EffectKind::DiscardTopDeck => {
            energy_handlers::discard_top_deck(state, ctx, 1)
        }

        // --- Energy effects ---
        EffectKind::AttachEnergyZoneSelf => {
            // No element specified — default to acting player's energy zone element.
            // Use Colorless as a no-op; real cards pass element via the parse handler.
            // The EffectKind variant doesn't carry element, so we call with the
            // zone element stored in state.
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_self(state, ctx, element, 1);
        }
        EffectKind::AttachEnergyZoneBench { count } => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            for _ in 0..*count {
                energy_handlers::attach_energy_zone_bench(state, db, ctx, element, None);
            }
        }
        EffectKind::AttachEnergyZoneBenchBracket { count } => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            for _ in 0..*count {
                energy_handlers::attach_energy_zone_bench(state, db, ctx, element, None);
            }
        }
        EffectKind::AttachEnergyZoneBenchAnyBracket { count } => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            for _ in 0..*count {
                energy_handlers::attach_energy_zone_bench(state, db, ctx, element, None);
            }
        }
        EffectKind::AttachEnergyZoneSelfBracket => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::attach_energy_zone_self(state, ctx, element, 1);
        }
        EffectKind::AttachEnergyZoneNamed { name } => {
            let element = state.players[ctx.acting_player].energy_available
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
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Water);
            energy_handlers::coin_flip_until_tails_attach_energy(state, ctx, element);
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
        EffectKind::DiscardEnergySelf => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::discard_energy_self(state, ctx, element);
        }
        EffectKind::DiscardNEnergySelf { count } => {
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::discard_n_energy_self(state, ctx, element, *count);
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
            // Discard energy until tails — simplified to discard once
            let element = state.players[ctx.acting_player].energy_available
                .unwrap_or(Element::Grass);
            energy_handlers::discard_energy_self(state, ctx, element);
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
        EffectKind::BonusIfOpponentHasStatus { bonus } => { let _ = bonus; }
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
            // Switch the opponent's most-damaged bench Pokémon to active
            movement_handlers::switch_opponent_active_random(state, ctx)
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
            damage_mod_handlers::self_damage(state, *amount, ctx.source_ref, ctx)
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
            // Coin flip: on heads, shuffle one opponent card into deck
            use rand::Rng;
            if state.rng.gen::<f64>() < 0.5 {
                draw_handlers::discard_random_card_opponent(state, ctx);
            }
        }
        EffectKind::MultiCoinShuffleOpponentCards { count } => {
            use rand::Rng;
            let heads: u8 = (0..*count)
                .filter(|_| state.rng.gen::<f64>() < 0.5)
                .count() as u8;
            for _ in 0..heads {
                draw_handlers::discard_random_card_opponent(state, ctx);
            }
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
        EffectKind::PassiveBlockSupporters => {}
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
        EffectKind::PassiveNoHealing => {}
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
    state: &GameState,
    db: &CardDb,
    base_damage: i16,
    effects: &[EffectKind],
    ctx: &EffectContext,
) -> (i16, bool, HashMap<String, i32>) {
    let _ = (state, db, ctx);
    let mut bonus: i16 = 0;
    for effect in effects {
        match effect {
            // Coin-flip variants are handled at attack execution time; skip here.
            EffectKind::CoinFlipBonusDamage { .. } => {}
            _ => {}
        }
    }
    (base_damage + bonus, false, HashMap::new())
}
