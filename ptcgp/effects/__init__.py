# Import all effect modules to trigger @register_effect decorators
from ptcgp.effects import registry
from ptcgp.effects import heal
from ptcgp.effects import draw
from ptcgp.effects import energy_effects
from ptcgp.effects import coin_flip
from ptcgp.effects import movement
from ptcgp.effects import tool_effects
from ptcgp.effects import items
from ptcgp.effects import status_apply
from ptcgp.effects import damage_effects
from ptcgp.effects import damage_modifiers  # noqa: F401 — registers post-damage no-ops
from ptcgp.effects import misc_effects
from ptcgp.effects.apply import apply_effects  # noqa: F401 — public helper
