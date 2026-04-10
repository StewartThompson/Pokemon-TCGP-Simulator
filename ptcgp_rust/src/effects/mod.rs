use std::collections::HashMap;

pub mod dispatch;
pub mod status_handlers;
pub mod heal_handlers;
pub mod draw_handlers;
pub mod energy_handlers;
pub mod movement_handlers;
pub mod damage_mod_handlers;
pub mod misc_handlers;

// ------------------------------------------------------------------ //
// Effect context
// ------------------------------------------------------------------ //

#[derive(Clone, Debug)]
pub struct EffectContext {
    pub acting_player: usize,
    /// The slot that is the source of the effect (typically the attacking/acting Pokémon).
    pub source_ref: Option<crate::actions::SlotRef>,
    /// The slot that is the target of the effect (e.g. opponent active, or chosen bench slot).
    pub target_ref: Option<crate::actions::SlotRef>,
    pub extra: HashMap<String, i32>,
}

impl EffectContext {
    pub fn new(acting_player: usize) -> Self {
        Self {
            acting_player,
            source_ref: None,
            target_ref: None,
            extra: HashMap::new(),
        }
    }

    pub fn with_source(mut self, src: crate::actions::SlotRef) -> Self {
        self.source_ref = Some(src);
        self
    }

    pub fn with_target(mut self, tgt: crate::actions::SlotRef) -> Self {
        self.target_ref = Some(tgt);
        self
    }
}

// ------------------------------------------------------------------ //
// EffectKind enum — all 169+ effect variants
// ------------------------------------------------------------------ //

#[derive(Clone, Debug, PartialEq)]
pub enum EffectKind {
    // --- Status effects (12) ---
    ApplyPoison,
    ApplyBurn,
    ApplySleep,
    ApplyParalysis,
    ApplyConfusion,
    ApplyRandomStatus,
    ToxicPoison,
    CoinFlipApplyParalysis,
    CoinFlipApplySleep,
    SelfConfuse,
    SelfSleep,
    CoinFlipAttackBlockNextTurn,

    // --- Heal effects ---
    HealSelf { amount: i16 },
    HealTarget { amount: i16 },
    HealActive { amount: i16 },
    HealAllOwn { amount: i16 },
    HealGrassTarget { amount: i16 },
    HealWaterPokemon { amount: i16 },
    HealStage2Target { amount: i16 },
    HealAndCureStatus { amount: i16 },
    HealSelfEqualToDamageDealt,
    HealAllNamedDiscardEnergy { name: String, amount: i16 },
    HealAllTyped { element: String, amount: i16 },

    // --- Draw effects ---
    DrawCards { count: u8 },
    DrawOneCard,
    DrawBasicPokemon,
    IonoHandShuffle,
    MarsHandShuffle,
    ShuffleHandIntoDeck,
    ShuffleHandDrawOpponentCount,
    DiscardToDraw { count: u8 },
    OpponentShuffleHandDraw { count: u8 },
    SearchDeckNamedBasic { name: String },
    SearchDeckRandomPokemon,
    SearchDeckEvolvesFrom { name: String },
    SearchDeckNamed { name: String },
    SearchDeckGrassPokemon,
    SearchDeckRandomBasic,
    SearchDiscardRandomBasic,
    LookTopOfDeck { count: u8 },
    RevealOpponentHand,
    LookOpponentHand,
    RevealOpponentSupporters,
    FishingNet,
    PokemonCommunication,
    DiscardRandomCardOpponent,
    DiscardRandomToolFromHand,
    DiscardRandomItemFromHand,
    DiscardTopDeck,

    // --- Energy effects ---
    AttachEnergyZoneSelf,
    AttachEnergyZoneBench { count: u8 },
    AttachEnergyZoneBenchBracket { count: u8 },
    AttachEnergyZoneBenchAnyBracket { count: u8 },
    AttachEnergyZoneSelfBracket,
    AttachEnergyZoneNamed { name: String },
    AttachEnergyZoneToGrass,
    AttachNEnergyZoneBench { count: u8 },
    AttachWaterTwoBench,
    AttachColorlessEnergyZoneBench,
    AttachEnergyDiscardNamed { name: String },
    AttachEnergyNamedEndTurn { name: String },
    AbilityAttachEnergyEndTurn,
    CoinFlipUntilTailsAttachEnergy,
    MultiCoinAttachBench { count: u8 },
    LusamineAttach,
    FirstTurnEnergyAttach,
    DiscardEnergySelf,
    DiscardNEnergySelf { count: u8 },
    DiscardAllEnergySelf,
    DiscardAllTypedEnergySelf { element: String },
    CoinFlipDiscardRandomEnergyOpponent,
    DiscardRandomEnergyOpponent,
    DiscardRandomEnergyBothActive,
    DiscardRandomEnergyAllPokemon,
    CoinFlipUntilTailsDiscardEnergy,
    MoveBenchEnergyToActive,
    MoveWaterBenchToActive,
    MoveAllTypedEnergyBenchToActive { element: String },
    MoveAllElectricToActiveNamed { name: String },
    ChangeOpponentEnergyType { from: String, to: String },
    OpponentNoEnergyNextTurn,
    ReduceAttackCostNamed { name: String, amount: i16 },

    // --- Damage modifier effects ---
    CoinFlipBonusDamage { amount: i16 },
    CoinFlipNothing,
    BothCoinsBonus { amount: i16 },
    MultiCoinDamage { count: u8, per: i16 },
    FlipUntilTailsDamage { per: i16 },
    CoinFlipBonusOrSelfDamage { bonus: i16, self_damage: i16 },
    MultiCoinPerEnergyDamage { per: i16 },
    MultiCoinPerTypedEnergyDamage { per: i16, energy_type: String },
    MultiCoinPerPokemonDamage { per: i16 },
    FlipUntilTailsBonus { per: i16 },
    MultiCoinBonus { count: u8, per: i16 },
    BonusPerBench { per: i16 },
    BonusPerBenchElement { per: i16, element: String },
    BonusPerBenchNamed { per: i16, name: String },
    BonusPerOpponentEnergy { per: i16 },
    BonusIfExtraWaterEnergy { threshold: i16, bonus: i16 },
    BonusIfOpponentDamaged { bonus: i16 },
    BonusIfSelfDamaged { bonus: i16 },
    BonusIfOpponentPoisoned { bonus: i16 },
    BonusPerOpponentBench { per: i16 },
    BonusIfToolAttached { bonus: i16 },
    BonusIfOpponentHasTool { bonus: i16 },
    BonusIfOpponentEx { bonus: i16 },
    BonusIfOpponentBasic { bonus: i16 },
    BonusIfOpponentElement { bonus: i16, element: String },
    BonusIfOpponentHasAbility { bonus: i16 },
    BonusIfBenchDamaged { bonus: i16 },
    BonusIfKoLastTurn { bonus: i16 },
    BonusIfPlayedSupporter { bonus: i16 },
    BonusIfJustPromoted { bonus: i16 },
    BonusIfOpponentMoreHp { bonus: i16 },
    BonusIfOpponentHasStatus { bonus: i16 },
    BonusEqualToDamageTaken,
    BonusIfExtraEnergy { threshold: i16, bonus: i16, energy_type: String },
    BonusIfNamedInPlay { bonus: i16, names: Vec<String> },
    HalveOpponentHp,
    DoubleHeadsInstantKo,

    // --- Movement effects ---
    SwitchOpponentActive,
    SwitchSelfToBench,
    SwitchSelfToBenchTyped { element: String },
    SwitchOpponentBasicToActive,
    SwitchOpponentDamagedToActive,
    SwitchUltraBeast,
    AbilityBenchToActive,
    CoinFlipBounceOpponent,
    ReturnActiveToHandNamed { name: String },
    ReturnColorlessToHand,
    PlaceOpponentBasicFromDiscard,
    ShuffleOpponentActiveIntoDeck,

    // --- Damage effects ---
    SplashBenchOpponent { amount: i16 },
    SplashBenchOwn { amount: i16 },
    SplashAllOpponent { amount: i16 },
    RandomHitOne { amount: i16 },
    RandomMultiHit { count: u8, amount: i16 },
    SelfDamage { amount: i16 },
    SelfDamageOnCoinFlipResult { amount: i16 },
    DiscardOpponentToolsBeforeDamage,
    DiscardAllOpponentTools,
    BenchHitOpponent { amount: i16 },
    MoveDamageToOpponent { amount: i16 },

    // --- Misc effects ---
    CantRetreatNextTurn,
    PreventDamageNextTurn,
    TakeLessDamageNextTurn { amount: i16 },
    DefenderAttacksDoLessDamage { amount: i16 },
    OpponentNoSupporterNextTurn,
    SupporterDamageAura { amount: i16, names: Vec<String> },
    SupporterDamageAuraVsEx { amount: i16 },
    ReduceRetreatCost { amount: i16 },
    CopyOpponentAttack,
    CoinFlipShuffleOpponentCard,
    MultiCoinShuffleOpponentCards { count: u8 },
    CantAttackNextTurn,
    SelfCantAttackNextTurn,
    CoinFlipSelfCantAttackNextTurn,
    SelfCantUseSpecificAttack { name: String },
    SelfAttackBuffNextTurn { amount: i16 },
    TakeMoreDamageNextTurn { amount: i16 },
    NextTurnAllDamageReduction { amount: i16 },
    NextTurnMetalDamageReduction { amount: i16 },
    OpponentCostIncreaseNextTurn { amount: i16 },
    OpponentNoItemsNextTurn,
    BigMalasada,
    MythicalSlab,
    BeastWallProtection,
    RareCandyEvolve,
    HpBonus { amount: i16 },

    // --- Passive ability effects ---
    PassiveDamageReduction { amount: i16 },
    PassiveRetaliate { amount: i16 },
    PassiveBlockSupporters,
    PassiveDittoImpostor { hp: i16 },
    PassiveDoubleGrassEnergy,
    PassiveImmuneStatus,
    PassiveKoEnergyTransfer,
    PassiveSurviveKoCoinFlip,
    PassiveTypeDamageBoost { element: String, amount: i16 },
    PassiveTypeDamageReduction { element: String, amount: i16 },
    PassiveBenchRetreatReduction { amount: i16 },
    PassiveBlockEvolution,
    PassiveCheckupDamage { amount: i16 },
    PassiveCoinFlipDamageReduction { amount: i16 },
    PassiveDarkEnergyPing { amount: i16 },
    PassiveElectricalCord,
    PassiveEnergySleep,
    PassiveFirstTurnNoRetreat,
    PassiveFreeRetreatWithEnergy,
    PassiveKoRetaliate { amount: i16 },
    PassiveLumBerry,
    PassiveMoveDamageToSelf,
    PassiveNamedNoRetreat { name: String },
    PassiveNoHealing,
    PassiveOpponentAttackCostIncrease { amount: i16 },
    PassiveOpponentDamageReduction { amount: i16 },
    PassivePreventAttackEffects,
    PassivePreventExDamage,
    PassivePsychicCleanse,
    PassiveRetaliatePoison,
    PassiveArceusCostReduction,
    PassiveArceusDamageReduction { amount: i16 },
    PassiveArceusNoRetreat,
    PassiveBeastiteDamage { amount: i16 },
}

// ------------------------------------------------------------------ //
// Parser
// ------------------------------------------------------------------ //

pub fn parse_handler_string(s: &str) -> Vec<EffectKind> {
    if s.is_empty() {
        return vec![];
    }

    split_top_level(s)
        .into_iter()
        .filter_map(|part| parse_single_effect(part.trim()))
        .collect()
}

fn split_top_level(s: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut current = String::new();
    let mut depth = 0usize;
    for ch in s.chars() {
        match ch {
            '(' => {
                depth += 1;
                current.push(ch);
            }
            ')' => {
                depth = depth.saturating_sub(1);
                current.push(ch);
            }
            '|' if depth == 0 => {
                parts.push(current.trim().to_string());
                current = String::new();
            }
            _ => current.push(ch),
        }
    }
    if !current.trim().is_empty() {
        parts.push(current.trim().to_string());
    }
    parts
}

fn parse_args(args_str: &str) -> HashMap<String, String> {
    let mut params = HashMap::new();
    let args_str = args_str.trim().trim_end_matches(')');
    if args_str.is_empty() {
        return params;
    }

    for (idx, token) in args_str.split(',').enumerate() {
        let token = token.trim();
        if let Some(eq) = token.find('=') {
            let k = token[..eq].trim().to_string();
            let v = token[eq + 1..].trim().to_string();
            params.insert(k, v);
        } else if !token.is_empty() {
            let keys = ["amount", "count", "per", "bonus", "threshold"];
            let key = keys.get(idx).unwrap_or(&"arg").to_string();
            params.insert(key, token.to_string());
        }
    }
    params
}

fn get_i16(params: &HashMap<String, String>, key: &str, default: i16) -> i16 {
    params.get(key).and_then(|v| v.parse().ok()).unwrap_or(default)
}

fn get_u8(params: &HashMap<String, String>, key: &str, default: u8) -> u8 {
    params.get(key).and_then(|v| v.parse().ok()).unwrap_or(default)
}

fn get_str(params: &HashMap<String, String>, key: &str) -> String {
    params.get(key).cloned().unwrap_or_default()
}

fn get_names(params: &HashMap<String, String>, key: &str) -> Vec<String> {
    params
        .get(key)
        .map(|v| {
            let v = v.trim_matches('(').trim_matches(')');
            v.split(',').map(|s| s.trim().to_string()).collect()
        })
        .unwrap_or_default()
}

fn parse_single_effect(s: &str) -> Option<EffectKind> {
    let paren = s.find('(');
    let name = if let Some(p) = paren {
        s[..p].trim()
    } else {
        s
    };
    let args_str = if let Some(p) = paren { &s[p + 1..] } else { "" };
    let params = parse_args(args_str);

    Some(match name {
        // Status
        "apply_poison" => EffectKind::ApplyPoison,
        "apply_burn" => EffectKind::ApplyBurn,
        "apply_sleep" => EffectKind::ApplySleep,
        "apply_paralysis" => EffectKind::ApplyParalysis,
        "apply_confusion" => EffectKind::ApplyConfusion,
        "apply_random_status" => EffectKind::ApplyRandomStatus,
        "toxic_poison" => EffectKind::ToxicPoison,
        "coin_flip_apply_paralysis" => EffectKind::CoinFlipApplyParalysis,
        "coin_flip_apply_sleep" => EffectKind::CoinFlipApplySleep,
        "self_confuse" => EffectKind::SelfConfuse,
        "self_sleep" => EffectKind::SelfSleep,
        "coin_flip_attack_block_next_turn" => EffectKind::CoinFlipAttackBlockNextTurn,

        // Heal
        "heal_self" => EffectKind::HealSelf {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_target" => EffectKind::HealTarget {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_active" => EffectKind::HealActive {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_all_own" => EffectKind::HealAllOwn {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_grass_target" => EffectKind::HealGrassTarget {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_water_pokemon" => EffectKind::HealWaterPokemon {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_stage2_target" => EffectKind::HealStage2Target {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_and_cure_status" => EffectKind::HealAndCureStatus {
            amount: get_i16(&params, "amount", 0),
        },
        "heal_self_equal_to_damage_dealt" => EffectKind::HealSelfEqualToDamageDealt,
        "heal_all_named_discard_energy" => EffectKind::HealAllNamedDiscardEnergy {
            name: get_str(&params, "name"),
            amount: get_i16(&params, "amount", 0),
        },
        "heal_all_typed" => EffectKind::HealAllTyped {
            element: get_str(&params, "element"),
            amount: get_i16(&params, "amount", 0),
        },

        // Draw
        "draw_cards" => EffectKind::DrawCards {
            count: get_u8(&params, "count", 2),
        },
        "draw_one_card" => EffectKind::DrawOneCard,
        "draw_basic_pokemon" => EffectKind::DrawBasicPokemon,
        "iono_hand_shuffle" => EffectKind::IonoHandShuffle,
        "mars_hand_shuffle" => EffectKind::MarsHandShuffle,
        "shuffle_hand_into_deck" => EffectKind::ShuffleHandIntoDeck,
        "shuffle_hand_draw_opponent_count" => EffectKind::ShuffleHandDrawOpponentCount,
        "discard_to_draw" => EffectKind::DiscardToDraw {
            count: get_u8(&params, "count", 1),
        },
        "opponent_shuffle_hand_draw" => EffectKind::OpponentShuffleHandDraw {
            count: get_u8(&params, "count", 3),
        },
        "search_deck_named_basic" => EffectKind::SearchDeckNamedBasic {
            name: get_str(&params, "name"),
        },
        "search_deck_random_pokemon" => EffectKind::SearchDeckRandomPokemon,
        "search_deck_evolves_from" => EffectKind::SearchDeckEvolvesFrom {
            name: get_str(&params, "name"),
        },
        "search_deck_named" => EffectKind::SearchDeckNamed {
            name: get_str(&params, "name"),
        },
        "search_deck_grass_pokemon" => EffectKind::SearchDeckGrassPokemon,
        "search_deck_random_basic" => EffectKind::SearchDeckRandomBasic,
        "search_discard_random_basic" => EffectKind::SearchDiscardRandomBasic,
        "look_top_of_deck" => EffectKind::LookTopOfDeck {
            count: get_u8(&params, "count", 1),
        },
        "reveal_opponent_hand" => EffectKind::RevealOpponentHand,
        "look_opponent_hand" => EffectKind::LookOpponentHand,
        "reveal_opponent_supporters" => EffectKind::RevealOpponentSupporters,
        "fishing_net" => EffectKind::FishingNet,
        "pokemon_communication" => EffectKind::PokemonCommunication,
        "discard_random_card_opponent" => EffectKind::DiscardRandomCardOpponent,
        "discard_random_tool_from_hand" => EffectKind::DiscardRandomToolFromHand,
        "discard_random_item_from_hand" => EffectKind::DiscardRandomItemFromHand,
        "discard_top_deck" => EffectKind::DiscardTopDeck,

        // Energy
        "attach_energy_zone_self" => EffectKind::AttachEnergyZoneSelf,
        "attach_energy_zone_bench" => EffectKind::AttachEnergyZoneBench {
            count: get_u8(&params, "count", 1),
        },
        "attach_energy_zone_bench_bracket" => EffectKind::AttachEnergyZoneBenchBracket {
            count: get_u8(&params, "count", 1),
        },
        "attach_energy_zone_bench_any_bracket" => EffectKind::AttachEnergyZoneBenchAnyBracket {
            count: get_u8(&params, "count", 1),
        },
        "attach_energy_zone_self_bracket" => EffectKind::AttachEnergyZoneSelfBracket,
        "attach_energy_zone_named" => EffectKind::AttachEnergyZoneNamed {
            name: get_str(&params, "name"),
        },
        "attach_energy_zone_to_grass" => EffectKind::AttachEnergyZoneToGrass,
        "attach_n_energy_zone_bench" => EffectKind::AttachNEnergyZoneBench {
            count: get_u8(&params, "count", 1),
        },
        "attach_water_two_bench" => EffectKind::AttachWaterTwoBench,
        "attach_colorless_energy_zone_bench" => EffectKind::AttachColorlessEnergyZoneBench,
        "attach_energy_discard_named" => EffectKind::AttachEnergyDiscardNamed {
            name: get_str(&params, "name"),
        },
        "attach_energy_named_end_turn" => EffectKind::AttachEnergyNamedEndTurn {
            name: get_str(&params, "name"),
        },
        "ability_attach_energy_end_turn" => EffectKind::AbilityAttachEnergyEndTurn,
        "coin_flip_until_tails_attach_energy" => EffectKind::CoinFlipUntilTailsAttachEnergy,
        "multi_coin_attach_bench" => EffectKind::MultiCoinAttachBench {
            count: get_u8(&params, "count", 3),
        },
        "lusamine_attach" => EffectKind::LusamineAttach,
        "first_turn_energy_attach" => EffectKind::FirstTurnEnergyAttach,
        "discard_energy_self" => EffectKind::DiscardEnergySelf,
        "discard_n_energy_self" => EffectKind::DiscardNEnergySelf {
            count: get_u8(&params, "count", 1),
        },
        "discard_all_energy_self" => EffectKind::DiscardAllEnergySelf,
        "discard_all_typed_energy_self" => EffectKind::DiscardAllTypedEnergySelf {
            element: get_str(&params, "element"),
        },
        "coin_flip_discard_random_energy_opponent" => {
            EffectKind::CoinFlipDiscardRandomEnergyOpponent
        }
        "discard_random_energy_opponent" => EffectKind::DiscardRandomEnergyOpponent,
        "discard_random_energy_both_active" => EffectKind::DiscardRandomEnergyBothActive,
        "discard_random_energy_all_pokemon" => EffectKind::DiscardRandomEnergyAllPokemon,
        "coin_flip_until_tails_discard_energy" => EffectKind::CoinFlipUntilTailsDiscardEnergy,
        "move_bench_energy_to_active" => EffectKind::MoveBenchEnergyToActive,
        "move_water_bench_to_active" => EffectKind::MoveWaterBenchToActive,
        "move_all_typed_energy_bench_to_active" => EffectKind::MoveAllTypedEnergyBenchToActive {
            element: get_str(&params, "element"),
        },
        "move_all_electric_to_active_named" => EffectKind::MoveAllElectricToActiveNamed {
            name: get_str(&params, "name"),
        },
        "change_opponent_energy_type" => EffectKind::ChangeOpponentEnergyType {
            from: get_str(&params, "from"),
            to: get_str(&params, "to"),
        },
        "opponent_no_energy_next_turn" => EffectKind::OpponentNoEnergyNextTurn,
        "reduce_attack_cost_named" => EffectKind::ReduceAttackCostNamed {
            name: get_str(&params, "name"),
            amount: get_i16(&params, "amount", 1),
        },

        // Damage modifiers
        "coin_flip_bonus_damage" => EffectKind::CoinFlipBonusDamage {
            amount: get_i16(&params, "amount", 0),
        },
        "coin_flip_nothing" => EffectKind::CoinFlipNothing,
        "both_coins_bonus" => EffectKind::BothCoinsBonus {
            amount: get_i16(&params, "amount", 0),
        },
        "multi_coin_damage" => EffectKind::MultiCoinDamage {
            count: get_u8(&params, "count", 1),
            per: get_i16(&params, "per", 0),
        },
        "flip_until_tails_damage" => EffectKind::FlipUntilTailsDamage {
            per: get_i16(&params, "per", 0),
        },
        "coin_flip_bonus_or_self_damage" => EffectKind::CoinFlipBonusOrSelfDamage {
            bonus: get_i16(&params, "bonus", 0),
            self_damage: get_i16(&params, "self_damage", 0),
        },
        "multi_coin_per_energy_damage" => EffectKind::MultiCoinPerEnergyDamage {
            per: get_i16(&params, "per", 0),
        },
        "multi_coin_per_typed_energy_damage" => EffectKind::MultiCoinPerTypedEnergyDamage {
            per: get_i16(&params, "per", 0),
            energy_type: get_str(&params, "energy_type"),
        },
        "multi_coin_per_pokemon_damage" => EffectKind::MultiCoinPerPokemonDamage {
            per: get_i16(&params, "per", 0),
        },
        "flip_until_tails_bonus" => EffectKind::FlipUntilTailsBonus {
            per: get_i16(&params, "per", 0),
        },
        "multi_coin_bonus" => EffectKind::MultiCoinBonus {
            count: get_u8(&params, "count", 1),
            per: get_i16(&params, "per", 0),
        },
        "bonus_per_bench" => EffectKind::BonusPerBench {
            per: get_i16(&params, "per", 0),
        },
        "bonus_per_bench_element" => EffectKind::BonusPerBenchElement {
            per: get_i16(&params, "per", 0),
            element: get_str(&params, "element"),
        },
        "bonus_per_bench_named" => EffectKind::BonusPerBenchNamed {
            per: get_i16(&params, "per", 0),
            name: get_str(&params, "name"),
        },
        "bonus_per_opponent_energy" => EffectKind::BonusPerOpponentEnergy {
            per: get_i16(&params, "per", 0),
        },
        "bonus_if_extra_water_energy" => EffectKind::BonusIfExtraWaterEnergy {
            threshold: get_i16(&params, "threshold", 2),
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_damaged" => EffectKind::BonusIfOpponentDamaged {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_self_damaged" => EffectKind::BonusIfSelfDamaged {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_poisoned" => EffectKind::BonusIfOpponentPoisoned {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_per_opponent_bench" => EffectKind::BonusPerOpponentBench {
            per: get_i16(&params, "per", 0),
        },
        "bonus_if_tool_attached" => EffectKind::BonusIfToolAttached {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_has_tool" => EffectKind::BonusIfOpponentHasTool {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_ex" => EffectKind::BonusIfOpponentEx {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_basic" => EffectKind::BonusIfOpponentBasic {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_element" => EffectKind::BonusIfOpponentElement {
            bonus: get_i16(&params, "bonus", 0),
            element: get_str(&params, "element"),
        },
        "bonus_if_opponent_has_ability" => EffectKind::BonusIfOpponentHasAbility {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_bench_damaged" => EffectKind::BonusIfBenchDamaged {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_ko_last_turn" => EffectKind::BonusIfKoLastTurn {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_played_supporter" => EffectKind::BonusIfPlayedSupporter {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_just_promoted" => EffectKind::BonusIfJustPromoted {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_more_hp" => EffectKind::BonusIfOpponentMoreHp {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_if_opponent_has_status" => EffectKind::BonusIfOpponentHasStatus {
            bonus: get_i16(&params, "bonus", 0),
        },
        "bonus_equal_to_damage_taken" => EffectKind::BonusEqualToDamageTaken,
        "bonus_if_extra_energy" => EffectKind::BonusIfExtraEnergy {
            threshold: get_i16(&params, "threshold", 2),
            bonus: get_i16(&params, "bonus", 0),
            energy_type: get_str(&params, "energy_type"),
        },
        "bonus_if_named_in_play" => EffectKind::BonusIfNamedInPlay {
            bonus: get_i16(&params, "bonus", 0),
            names: get_names(&params, "names"),
        },
        "halve_opponent_hp" => EffectKind::HalveOpponentHp,
        "double_heads_instant_ko" => EffectKind::DoubleHeadsInstantKo,

        // Movement
        "switch_opponent_active" => EffectKind::SwitchOpponentActive,
        "switch_self_to_bench" => EffectKind::SwitchSelfToBench,
        "switch_self_to_bench_typed" => EffectKind::SwitchSelfToBenchTyped {
            element: get_str(&params, "element"),
        },
        "switch_opponent_basic_to_active" => EffectKind::SwitchOpponentBasicToActive,
        "switch_opponent_damaged_to_active" => EffectKind::SwitchOpponentDamagedToActive,
        "switch_ultra_beast" => EffectKind::SwitchUltraBeast,
        "ability_bench_to_active" => EffectKind::AbilityBenchToActive,
        "coin_flip_bounce_opponent" => EffectKind::CoinFlipBounceOpponent,
        "return_active_to_hand_named" => EffectKind::ReturnActiveToHandNamed {
            name: get_str(&params, "name"),
        },
        "return_colorless_to_hand" => EffectKind::ReturnColorlessToHand,
        "place_opponent_basic_from_discard" => EffectKind::PlaceOpponentBasicFromDiscard,
        "shuffle_opponent_active_into_deck" => EffectKind::ShuffleOpponentActiveIntoDeck,

        // Damage effects
        "splash_bench_opponent" => EffectKind::SplashBenchOpponent {
            amount: get_i16(&params, "amount", 0),
        },
        "splash_bench_own" => EffectKind::SplashBenchOwn {
            amount: get_i16(&params, "amount", 0),
        },
        "splash_all_opponent" => EffectKind::SplashAllOpponent {
            amount: get_i16(&params, "amount", 0),
        },
        "random_hit_one" => EffectKind::RandomHitOne {
            amount: get_i16(&params, "amount", 0),
        },
        "random_multi_hit" => EffectKind::RandomMultiHit {
            count: get_u8(&params, "count", 1),
            amount: get_i16(&params, "amount", 0),
        },
        "self_damage" => EffectKind::SelfDamage {
            amount: get_i16(&params, "amount", 0),
        },
        "self_damage_on_coin_flip_result" => EffectKind::SelfDamageOnCoinFlipResult {
            amount: get_i16(&params, "amount", 0),
        },
        "discard_opponent_tools_before_damage" => EffectKind::DiscardOpponentToolsBeforeDamage,
        "discard_all_opponent_tools" => EffectKind::DiscardAllOpponentTools,
        "bench_hit_opponent" => EffectKind::BenchHitOpponent {
            amount: get_i16(&params, "amount", 0),
        },
        "move_damage_to_opponent" => EffectKind::MoveDamageToOpponent {
            amount: get_i16(&params, "amount", 0),
        },

        // Misc
        "cant_retreat_next_turn" => EffectKind::CantRetreatNextTurn,
        "prevent_damage_next_turn" => EffectKind::PreventDamageNextTurn,
        "take_less_damage_next_turn" => EffectKind::TakeLessDamageNextTurn {
            amount: get_i16(&params, "amount", 0),
        },
        "defender_attacks_do_less_damage" => EffectKind::DefenderAttacksDoLessDamage {
            amount: get_i16(&params, "amount", 0),
        },
        "opponent_no_supporter_next_turn" => EffectKind::OpponentNoSupporterNextTurn,
        "supporter_damage_aura" => EffectKind::SupporterDamageAura {
            amount: get_i16(&params, "amount", 0),
            names: get_names(&params, "names"),
        },
        "supporter_damage_aura_vs_ex" => EffectKind::SupporterDamageAuraVsEx {
            amount: get_i16(&params, "amount", 0),
        },
        "reduce_retreat_cost" => EffectKind::ReduceRetreatCost {
            amount: get_i16(&params, "amount", 1),
        },
        "copy_opponent_attack" => EffectKind::CopyOpponentAttack,
        "coin_flip_shuffle_opponent_card" => EffectKind::CoinFlipShuffleOpponentCard,
        "multi_coin_shuffle_opponent_cards" => EffectKind::MultiCoinShuffleOpponentCards {
            count: get_u8(&params, "count", 3),
        },
        "cant_attack_next_turn" => EffectKind::CantAttackNextTurn,
        "self_cant_attack_next_turn" => EffectKind::SelfCantAttackNextTurn,
        "coin_flip_self_cant_attack_next_turn" => EffectKind::CoinFlipSelfCantAttackNextTurn,
        "self_cant_use_specific_attack" => EffectKind::SelfCantUseSpecificAttack {
            name: get_str(&params, "name"),
        },
        "self_attack_buff_next_turn" => EffectKind::SelfAttackBuffNextTurn {
            amount: get_i16(&params, "amount", 0),
        },
        "take_more_damage_next_turn" => EffectKind::TakeMoreDamageNextTurn {
            amount: get_i16(&params, "amount", 0),
        },
        "next_turn_all_damage_reduction" => EffectKind::NextTurnAllDamageReduction {
            amount: get_i16(&params, "amount", 0),
        },
        "next_turn_metal_damage_reduction" => EffectKind::NextTurnMetalDamageReduction {
            amount: get_i16(&params, "amount", 0),
        },
        "opponent_cost_increase_next_turn" => EffectKind::OpponentCostIncreaseNextTurn {
            amount: get_i16(&params, "amount", 0),
        },
        "opponent_no_items_next_turn" => EffectKind::OpponentNoItemsNextTurn,
        "big_malasada" => EffectKind::BigMalasada,
        "mythical_slab" => EffectKind::MythicalSlab,
        "beast_wall_protection" => EffectKind::BeastWallProtection,
        "rare_candy_evolve" => EffectKind::RareCandyEvolve,
        "hp_bonus" => EffectKind::HpBonus {
            amount: get_i16(&params, "amount", 0),
        },

        // Passives
        "passive_damage_reduction" => EffectKind::PassiveDamageReduction {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_retaliate" => EffectKind::PassiveRetaliate {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_block_supporters" => EffectKind::PassiveBlockSupporters,
        "passive_ditto_impostor" => EffectKind::PassiveDittoImpostor {
            hp: get_i16(&params, "hp", 0),
        },
        "passive_double_grass_energy" => EffectKind::PassiveDoubleGrassEnergy,
        "passive_immune_status" => EffectKind::PassiveImmuneStatus,
        "passive_ko_energy_transfer" => EffectKind::PassiveKoEnergyTransfer,
        "passive_survive_ko_coin_flip" => EffectKind::PassiveSurviveKoCoinFlip,
        "passive_type_damage_boost" => EffectKind::PassiveTypeDamageBoost {
            element: get_str(&params, "element"),
            amount: get_i16(&params, "amount", 0),
        },
        "passive_type_damage_reduction" => EffectKind::PassiveTypeDamageReduction {
            element: get_str(&params, "element"),
            amount: get_i16(&params, "amount", 0),
        },
        "passive_bench_retreat_reduction" => EffectKind::PassiveBenchRetreatReduction {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_block_evolution" => EffectKind::PassiveBlockEvolution,
        "passive_checkup_damage" => EffectKind::PassiveCheckupDamage {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_coin_flip_damage_reduction" => EffectKind::PassiveCoinFlipDamageReduction {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_dark_energy_ping" => EffectKind::PassiveDarkEnergyPing {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_electrical_cord" => EffectKind::PassiveElectricalCord,
        "passive_energy_sleep" => EffectKind::PassiveEnergySleep,
        "passive_first_turn_no_retreat" => EffectKind::PassiveFirstTurnNoRetreat,
        "passive_free_retreat_with_energy" => EffectKind::PassiveFreeRetreatWithEnergy,
        "passive_ko_retaliate" => EffectKind::PassiveKoRetaliate {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_lum_berry" => EffectKind::PassiveLumBerry,
        "passive_move_damage_to_self" => EffectKind::PassiveMoveDamageToSelf,
        "passive_named_no_retreat" => EffectKind::PassiveNamedNoRetreat {
            name: get_str(&params, "name"),
        },
        "passive_no_healing" => EffectKind::PassiveNoHealing,
        "passive_opponent_attack_cost_increase" => EffectKind::PassiveOpponentAttackCostIncrease {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_opponent_damage_reduction" => EffectKind::PassiveOpponentDamageReduction {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_prevent_attack_effects" => EffectKind::PassivePreventAttackEffects,
        "passive_prevent_ex_damage" => EffectKind::PassivePreventExDamage,
        "passive_psychic_cleanse" => EffectKind::PassivePsychicCleanse,
        "passive_retaliate_poison" => EffectKind::PassiveRetaliatePoison,
        "passive_arceus_cost_reduction" => EffectKind::PassiveArceusCostReduction,
        "passive_arceus_damage_reduction" => EffectKind::PassiveArceusDamageReduction {
            amount: get_i16(&params, "amount", 0),
        },
        "passive_arceus_no_retreat" => EffectKind::PassiveArceusNoRetreat,
        "passive_beastite_damage" => EffectKind::PassiveBeastiteDamage {
            amount: get_i16(&params, "amount", 0),
        },

        _ => return None, // Unknown effect — skip
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_simple_handler() {
        let effects = parse_handler_string("heal_self(amount=30)");
        assert_eq!(effects.len(), 1);
        assert_eq!(effects[0], EffectKind::HealSelf { amount: 30 });
    }

    #[test]
    fn parse_chained_handler() {
        let effects = parse_handler_string("apply_poison | self_damage(amount=20)");
        assert_eq!(effects.len(), 2);
        assert_eq!(effects[0], EffectKind::ApplyPoison);
        assert_eq!(effects[1], EffectKind::SelfDamage { amount: 20 });
    }

    #[test]
    fn parse_draw_cards() {
        let effects = parse_handler_string("draw_cards(count=2)");
        assert_eq!(effects[0], EffectKind::DrawCards { count: 2 });
    }

    #[test]
    fn parse_unknown_is_skipped() {
        let effects = parse_handler_string("some_future_effect(x=1)");
        assert!(effects.is_empty());
    }

    #[test]
    fn parse_multi_coin() {
        let effects = parse_handler_string("multi_coin_damage(count=4, per=50)");
        assert_eq!(
            effects[0],
            EffectKind::MultiCoinDamage { count: 4, per: 50 }
        );
    }
}
