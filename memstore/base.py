from __future__ import annotations
"""Core data structures for memory items and module interfaces.

This module defines MemoryItem (a serializable record) and MemoryModule
which is the abstract base class for concrete memory module implementations.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import time


@dataclass
class MemoryItem:
    """A single memory record stored by modules.

    Fields:
    - id: unique identifier for the memory
    - type: memory module/type name (e.g., 'conversations')
    - content: short textual content or reference
    - metadata: arbitrary key/value metadata
    - created_at: POSIX timestamp when the item was created
    """
    id: str
    type: str
    content: str
    metadata: Dict[str, Any]
    created_at: Optional[float] = None

    def __post_init__(self):
        # set a timestamp if missing
        if self.created_at is None:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary of the memory item."""
        return asdict(self)


class MemoryModule:
    """Abstract base class for memory modules.

    Implementations must provide `add(...)` and `query(...)` methods. Modules
    are lightweight adapters over the storage layer and handle type-specific
    logic (e.g., conversations vs. documents).
    """

    def __init__(self, name: str):
        self.name = name

    def add(self, *args, **kwargs):
        """Add a memory item. Concrete modules should override this."""
        raise NotImplementedError()

    def query(self, q: str, limit: int = 10):
        """Query memory items. Concrete modules should override this."""
        raise NotImplementedError()

    def serialize(self):
        """Return a serializable representation (optional)."""
        raise NotImplementedError()
