class BattleEngineError(Exception):
    """Base exception for battle engine errors"""
    pass

class InvalidActionError(BattleEngineError):
    """Action is invalid for current game state"""
    def __init__(self, action: str, reason: str):
        self.action = action
        self.reason = reason
        super().__init__(f"Invalid action '{action}': {reason}")

class RuleViolationError(BattleEngineError):
    """Action violates game rules"""
    def __init__(self, rule: str, details: str = ""):
        self.rule = rule
        self.details = details
        super().__init__(f"Rule violation: {rule}. {details}")

class StateError(BattleEngineError):
    """Game state is inconsistent"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"State error: {message}")

