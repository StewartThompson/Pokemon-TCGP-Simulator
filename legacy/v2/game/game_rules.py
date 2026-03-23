from cards.pokemon import Pokemon


class GameRules:
    """Centralized game rules and constants"""
    DECK_SIZE = 20
    MAX_BENCH_SIZE = 3
    WINNING_POINTS = 3
    INITIAL_HAND_SIZE = 5
    MAX_TURNS = 50
    MAX_ACTIONS_PER_TURN = 50
    BASIC = "basic"
    STAGE1 = "stage1"
    STAGE2 = "stage2"
    
    @staticmethod
    def can_evolve(target: Pokemon, evolution: Pokemon) -> bool:
        """Check evolution rules"""
        if target.turns_in_play < 1:
            return False
        return ((target.stage == GameRules.BASIC and evolution.stage == GameRules.STAGE1) or
                (target.stage == GameRules.STAGE1 and evolution.stage == GameRules.STAGE2))
    
    @staticmethod
    def calculate_prize_value(pokemon: Pokemon) -> int:
        """Calculate prize points for knocking out Pokemon"""
        return 2 if pokemon.is_ex else 1
