"""Status effects module"""
from .status_effect import StatusEffect
from .asleep import Asleep
from .poisoned import Poisoned
from .burned import Burned
from .paralyzed import Paralyzed
from .confused import Confused

__all__ = ['StatusEffect', 'Asleep', 'Poisoned', 'Burned', 'Paralyzed', 'Confused']

