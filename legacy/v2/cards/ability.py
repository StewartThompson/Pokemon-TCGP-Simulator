# These are the attacks that a pokemon can use
class Ability:
    def __init__(self, id, name, effect):
        self.id = id
        self.name = name
        self.effect = effect

    def __str__(self):
        return f"{self.name} ({self.effect})"