"""Bounded gameplay input validation."""

from __future__ import annotations

import math

from .errors import GameplayError


def number(value, minimum, maximum, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise GameplayError(
            f"{name} must be finite and between {minimum} and {maximum}"
        )
    return float(value)
