from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any
from .base import MemoryItem


class JSONStorage:
    """Simple JSON file storage for memories. Each module has its own file.

    Note: not optimized for large scale. Designed for local testing and prototyping.
    """

    def __init__(self, dirpath: str):
        self.dir = Path(dirpath)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file_for(self, module_name: str) -> Path:
        return self.dir / f"{module_name}.json"

    def load(self, module_name: str) -> List[Dict[str, Any]]:
        p = self._file_for(module_name)
        if not p.exists():
            return []
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, module_name: str, items: List[Dict[str, Any]]) -> None:
        p = self._file_for(module_name)
        with p.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def append(self, module_name: str, item: Dict[str, Any]) -> None:
        items = self.load(module_name)
        items.append(item)
        self.save(module_name, items)
