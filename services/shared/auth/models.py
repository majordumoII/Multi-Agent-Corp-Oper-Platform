"""User identity shared across services.

Mirrors `rag_guardrails.auth.models` in Project 2 by convention, not by
import — Project 3 composes with its siblings over HTTP/DB, the same way
Project 2 composes with Project 1, so there is no cross-repo Python
dependency. Keeping the shape identical means requests can be forwarded to
Project 2 without translation, and this same struct is what later phases
will serialize onto Pub/Sub as plain JSON.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class ClearanceLevel(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3

    @classmethod
    def from_str(cls, name: str) -> "ClearanceLevel":
        try:
            return cls[name.strip().upper()]
        except KeyError:
            raise ValueError(
                f"Unknown clearance level {name!r}; expected one of "
                f"{[m.name.lower() for m in cls]}"
            ) from None


@dataclass
class UserContext:
    user_id: str
    clearance: ClearanceLevel
    roles: list[str] = field(default_factory=list)
