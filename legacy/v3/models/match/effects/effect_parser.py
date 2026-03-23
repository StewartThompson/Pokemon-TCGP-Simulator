"""Effect parser - parses effect text into executable Effect objects"""
from typing import Optional, List
from .effect import Effect
from .heal_effect import HealEffect
from .draw_effect import DrawEffect
from .search_effect import SearchEffect
from .status_effect_effect import StatusEffectEffect
from .switch_effect import SwitchEffect
from .discard_effect import DiscardEffect
from .energy_effect import EnergyEffect
from .heal_all_effect import HealAllEffect
from .rare_candy_effect import RareCandyEffect
from .coin_flip_effect import CoinFlipEffect

class EffectParser:
    """Parse effect text into executable Effect objects"""
    
    EFFECT_CLASSES = [
        RareCandyEffect,  # Check this early (specific pattern)
        CoinFlipEffect,  # Check coin flips early (specific pattern)
        HealAllEffect,  # Check this first (more specific)
        HealEffect,
        DrawEffect,
        SearchEffect,
        StatusEffectEffect,
        SwitchEffect,
        DiscardEffect,
        EnergyEffect,
    ]
    
    @classmethod
    def parse_ability_effect(cls, effect_text: str) -> Optional[Effect]:
        """Parse ability effect text (may have different patterns than attack effects)"""
        # Abilities often start with "Once during your turn" or "As long as"
        text_lower = effect_text.lower()
        
        # Remove common prefixes
        if "once during your turn" in text_lower:
            text_lower = text_lower.replace("once during your turn, you may", "").strip()
        if "as long as" in text_lower:
            # Passive ability - handle differently
            return None
        
        # Try standard parsing
        return cls.parse(effect_text)
    
    @classmethod
    def parse(cls, effect_text: str) -> Optional[Effect]:
        """Parse effect text into Effect object"""
        if not effect_text:
            return None
        
        # Debug: Try to parse and log which class matches
        for effect_class in cls.EFFECT_CLASSES:
            effect = effect_class.from_text(effect_text)
            if effect:
                # Debug logging can be added here if needed
                return effect
        
        return None  # Unknown effect
    
    @classmethod
    def parse_multiple(cls, effect_text: str) -> List[Effect]:
        """Parse effect text that may contain multiple effects"""
        effects = []
        # First try parsing the whole text (some effects span multiple sentences)
        effect = cls.parse(effect_text)
        if effect:
            effects.append(effect)
            return effects
        
        # If that fails, split by common separators
        parts = effect_text.split('.')
        for part in parts:
            part = part.strip()
            if part:
                effect = cls.parse(part)
                if effect:
                    effects.append(effect)
        return effects

