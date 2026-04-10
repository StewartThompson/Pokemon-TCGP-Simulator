"""High-level helpers for dispatching card effects.

Two dispatch paths:

1. **Handler string** (preferred) — a compact ``"name(k=v)"`` string stored
   directly in the card JSON.  Parsed by ``parse_handler_string`` (simple
   string splitting, no regex).
2. **Effect text** (fallback) — free-form card text parsed by the regex-based
   ``parse_effect_text`` in ``parser.py``.  Used only when no handler string
   is present.
"""
from __future__ import annotations

from typing import Optional

from ptcgp.effects.base import Effect
from ptcgp.effects.registry import EffectContext, resolve_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.state import GameState


# ------------------------------------------------------------------ #
# Handler-string parser (tiny, no regex)
# ------------------------------------------------------------------ #

def parse_handler_string(handler_str: str) -> list[Effect]:
    """Parse ``"name(k=v, k2=v2) | name2(k3=v3)"`` into Effect tokens.

    Format:
        name                        → Effect("name", {})
        name(val)                   → Effect("name", {"amount": <val>})
        name(k=v)                   → Effect("name", {"k": <v>})
        name(k1=v1, k2=v2)         → Effect("name", {"k1": <v1>, "k2": <v2>})
        a | b(x=1)                  → [Effect("a", {}), Effect("b", {"x": 1})]

    Values are auto-coerced: integers become int, everything else stays str.
    Pipe-delimited ``|`` inside a *value* (e.g. ``names=Ninetales|Rapidash``)
    is handled by keeping values as single strings — the caller splits if needed.
    """
    if not handler_str or not handler_str.strip():
        return []

    effects: list[Effect] = []
    # Split on top-level " | " (space-pipe-space) to separate chained effects.
    # A bare "|" inside parentheses (e.g. names=A|B) is NOT a delimiter because
    # we only split OUTSIDE parens.
    parts = _split_top_level(handler_str.strip())

    for part in parts:
        part = part.strip()
        if not part:
            continue
        paren = part.find("(")
        if paren == -1:
            effects.append(Effect(name=part, params={}))
            continue
        name = part[:paren].strip()
        args_str = part[paren + 1 :].rstrip(")")
        params = _parse_args(args_str)
        effects.append(Effect(name=name, params=params))

    return effects


def _split_top_level(s: str) -> list[str]:
    """Split on `` | `` only when outside parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "|" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    if current:
        parts.append("".join(current))
    return parts


def _parse_args(args_str: str) -> dict:
    """Parse ``"k1=v1, k2=v2"`` or ``"30"`` (positional → amount)."""
    args_str = args_str.strip()
    if not args_str:
        return {}

    params: dict = {}
    # Split on commas that are outside parentheses (for nested tuples — rare)
    tokens = [t.strip() for t in args_str.split(",")]

    for idx, token in enumerate(tokens):
        if "=" in token:
            key, val = token.split("=", 1)
            params[key.strip()] = _coerce(val.strip())
        else:
            # Positional: first positional → "amount", second → "count", etc.
            positional_names = ("amount", "count", "per", "bonus", "threshold")
            key = positional_names[idx] if idx < len(positional_names) else f"arg{idx}"
            params[key] = _coerce(token)
    return params


def _coerce(val: str):
    """Coerce string → int if it looks numeric, else leave as str.

    Handles tuples like ``(Ninetales, Rapidash, Magmar)`` by converting to a
    Python tuple of strings.
    """
    if val.startswith("(") and val.endswith(")"):
        inner = val[1:-1]
        return tuple(v.strip() for v in inner.split(",") if v.strip())
    try:
        return int(val)
    except ValueError:
        return val


# ------------------------------------------------------------------ #
# Primary dispatch: handler string preferred, effect text fallback
# ------------------------------------------------------------------ #

def apply_effects(
    state: GameState,
    effect_text: str,
    acting_player: int,
    source_ref: Optional[SlotRef] = None,
    target_ref: Optional[SlotRef] = None,
    extra: Optional[dict] = None,
    handler_str: str = "",
    cached_effects: tuple = (),
) -> GameState:
    """Dispatch card effects.

    Priority: ``cached_effects`` (pre-parsed tuple) → ``handler_str`` (parse
    now) → ``effect_text`` (regex fallback). Pass ``cached_effects`` from the
    Attack/Ability object to avoid re-parsing on every call.
    """
    if cached_effects:
        effects = cached_effects
    elif handler_str:
        effects = parse_handler_string(handler_str)
    elif effect_text:
        from ptcgp.effects.parser import parse_effect_text
        effects = parse_effect_text(effect_text)
    else:
        return state

    for effect in effects:
        ctx = EffectContext(
            state=state,
            acting_player=acting_player,
            source_ref=source_ref,
            target_ref=target_ref,
            extra=dict(extra) if extra else {},
        )
        state = resolve_effect(ctx, effect)
    return state
