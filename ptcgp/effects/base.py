"""Effect dataclass hierarchy — base classes for all parsed card effects."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Effect:
    """Base class for all parsed card effects."""
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnknownEffect(Effect):
    """Placeholder for unrecognized effect text."""
    raw_text: str = ""
