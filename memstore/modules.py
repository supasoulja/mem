from __future__ import annotations
"""Concrete memory module implementations.

GenericMemory is a simple JSON-backed module that keeps an in-memory cache
and persists to the `JSONStorage`. ConversationMemory and DocumentMemory
provide small convenience methods for their specific item shapes.
"""

from typing import List, Dict, Any, Optional
from .base import MemoryModule, MemoryItem
import uuid


class GenericMemory(MemoryModule):
    """A generic memory module that stores items in JSON and supports substring queries."""

    def __init__(self, name: str, storage):
        super().__init__(name)
        self.storage = storage
        # load existing items for this module into memory
        self._items: List[Dict[str, Any]] = self.storage.load(name)

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
        """Add a new MemoryItem and persist the module file."""
        metadata = metadata or {}
        mid = str(uuid.uuid4())
        item = MemoryItem(id=mid, type=self.name, content=content, metadata=metadata)
        self._items.append(item.to_dict())
        # persist the entire module file (simple approach)
        self.storage.save(self.name, self._items)
        return item

    def query(self, q: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Simple substring query over content field (case-insensitive)."""
        ql = q.lower()
        results = [it for it in self._items if ql in it.get("content", "").lower()]
        return results[:limit]

    def all(self) -> List[Dict[str, Any]]:
        """Return all stored items for inspection/debugging."""
        return self._items


class ConversationMemory(GenericMemory):
    """Convenience wrapper for conversation-like entries (speaker + text)."""

    def add_turn(self, speaker: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
        metadata = metadata or {}
        metadata.update({"speaker": speaker})
        return self.add(content=text, metadata=metadata)


class DocumentMemory(GenericMemory):
    """Convenience wrapper for document-like entries (title + text)."""

    def add_document(self, title: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
        metadata = metadata or {}
        metadata.update({"title": title})
        return self.add(content=text, metadata=metadata)
