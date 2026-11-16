"""Compatibility imports for callers using the original core module."""

from .errors import GameplayError as GameplayError
from .files import (
    now as now,
    identifier as identifier,
    atomic_json as atomic_json,
    read_json as read_json,
    file_lock as file_lock,
)
from .validation import number as number
from .library import Library as Library
from .transport import Bridge as Bridge
