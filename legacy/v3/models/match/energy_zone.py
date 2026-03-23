import random
from typing import Optional, List
from v3.models.cards.energy import Energy

class EnergyZone:
    """Manages Energy Zone state and generation"""
    
    def __init__(self, chosen_energies: List[Energy.Type]):
        if not chosen_energies or len(chosen_energies) < 1:
            raise ValueError("Must choose at least 1 energy type")
        self.chosen_energies = chosen_energies
        self.current: Optional[Energy.Type] = None
        self.next: Optional[Energy.Type] = None
    
    def generate_energy(self) -> None:
        """Generate energy at start of turn"""
        if self.current is None:
            self.current = self._random_energy()
        if self.next is None:
            self.next = self._random_energy()
    
    def consume_current(self) -> Optional[Energy.Type]:
        """Consume current energy and shift"""
        energy = self.current
        self.current = self.next
        self.next = None
        self.generate_energy()  # Refill if needed
        return energy
    
    def _random_energy(self) -> Energy.Type:
        return random.choice(self.chosen_energies)
    
    def has_energy(self) -> bool:
        return self.current is not None
    
    @property
    def current_energy(self) -> Optional[Energy.Type]:
        return self.current
    
    @property
    def next_energy(self) -> Optional[Energy.Type]:
        return self.next

