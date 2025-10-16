from __future__ import annotations
from typing import Dict, Any, List
from .storage import JSONStorage
from .modules import ConversationMemory, DocumentMemory, GenericMemory
from .ollama_adapter import OllamaAdapter
from .base import MemoryItem
import os
import json


class ModelAdapter:
    """Pluggable adapter for LLM/embeddings. For now a simple stub that can be replaced with an Ollama client."""

    def categorize(self, text: str) -> List[str]:
        """Return list of mem types this text belongs to.

        This is a stub that uses simple keyword rules. Replace with a model call for better accuracy.
        """
        text_l = text.lower()
        tags = []
        rules = {
            "conversations": ["said", "asked", "reply", "conversation", "chat"],
            "documents": ["document", "report", "article", "paper", "notes"],
            "crashreport": ["error", "traceback", "crash", "exception"],
            "reminders": ["remind", "reminder", "remember to"],
        }
        for tag, kws in rules.items():
            for kw in kws:
                if kw in text_l:
                    tags.append(tag)
                    break
        if not tags:
            tags = ["generic"]
        return tags


class MemoryManager:
    def __init__(self, storage_dir: str = None, model_adapter: ModelAdapter = None):
        storage_dir = storage_dir or os.path.join(os.path.dirname(__file__), "data")
        self.storage = JSONStorage(str(storage_dir))
        self.model = model_adapter or ModelAdapter()
        # optional external LLM adapter (e.g., Ollama)
        self.llm_adapter: OllamaAdapter | None = None
        self.chat_model_name: str | None = None
        self.mem_model_name: str | None = None
        # create modules mapped to mem types
        self.modules: Dict[str, GenericMemory] = {
            "conversations": ConversationMemory("conversations", self.storage),
            "documents": DocumentMemory("documents", self.storage),
            "generic": GenericMemory("generic", self.storage),
            "crashreport": GenericMemory("crashreport", self.storage),
            "reminders": GenericMemory("reminders", self.storage),
        }

    def ingest_chat_log(self, chat_text: str) -> Dict[str, int]:
        """Take a long chat log and split into lines/turns and categorize and store them.

        Returns a dict mapping module name to number of items stored.
        """
        counts: Dict[str, int] = {k: 0 for k in self.modules.keys()}
        # naive split: lines separated by newlines
        lines = [ln.strip() for ln in chat_text.splitlines() if ln.strip()]
        for ln in lines:
            tags = self.model.categorize(ln)
            for tag in tags:
                mod = self.modules.get(tag) or self.modules.get("generic")
                # if conversation-like, try to parse speaker
                if tag == "conversations":
                    # simple parse: "Alice: hello"
                    if hasattr(mod, "add_turn"):
                        if ":" in ln:
                            sp, txt = ln.split(":", 1)
                            mod.add_turn(sp.strip(), txt.strip())
                        else:
                            mod.add_turn("user", ln)
                    else:
                        mod.add(content=ln)
                elif tag == "documents":
                    if hasattr(mod, "add_document"):
                        mod.add_document(title="ingested", text=ln)
                    else:
                        mod.add(content=ln)
                else:
                    if hasattr(mod, "add"):
                        mod.add(content=ln)
                if mod is not None:
                    counts[mod.name] = counts.get(mod.name, 0) + 1
        return counts

    def query(self, mem_type: str, q: str, limit: int = 10) -> List[Dict[str, Any]]:
        mod = self.modules.get(mem_type)
        if not mod:
            return []
        return mod.query(q, limit=limit)

    def set_llm_adapter(self, adapter: OllamaAdapter, chat_model: str = None, mem_model: str = None):
        self.llm_adapter = adapter
        self.chat_model_name = chat_model
        self.mem_model_name = mem_model

    def ingest_qwen_json(self, json_text: str) -> Dict[str, int]:
        """Given JSON text from the memory model (Qwen) that follows the IngestChunk output
        format, parse it and store items into the appropriate modules. Returns counts per module.
        """
        try:
            parsed = json.loads(json_text)
        except Exception as e:
            raise ValueError(f"Invalid JSON from memory model: {e}")
        items = parsed.get("items") or parsed.get("results") or []
        counts = {k: 0 for k in self.modules.keys()}
        for it in items:
            typ = it.get("type") or it.get("mem_type") or "generic"
            content = it.get("content") or it.get("summary") or ""
            metadata = it.get("metadata") or {}
            mod = self.modules.get(typ) or self.modules.get("generic")
            if typ == "conversations" and hasattr(mod, "add_turn"):
                speaker = metadata.get("speaker", "user")
                # add_turn returns a MemoryItem
                mod.add_turn(speaker, content, metadata=metadata)
            elif typ == "documents" and hasattr(mod, "add_document"):
                title = metadata.get("title", "ingested")
                mod.add_document(title=title, text=content, metadata=metadata)
            else:
                mod.add(content=content, metadata=metadata)
            counts[mod.name] = counts.get(mod.name, 0) + 1
        return counts

    def chat_generate(self, system_prompt: str, messages: list, max_tokens: int = 1024) -> str:
        if not self.llm_adapter or not self.chat_model_name:
            raise RuntimeError("LLM adapter or chat model name not configured")
        return self.llm_adapter.chat_generate(self.chat_model_name, system_prompt, messages, max_tokens=max_tokens)

    def memory_generate(self, system_prompt: str, messages: list, max_tokens: int = 1024) -> str:
        if not self.llm_adapter or not self.mem_model_name:
            raise RuntimeError("LLM adapter or memory model name not configured")
        return self.llm_adapter.chat_generate(self.mem_model_name, system_prompt, messages, max_tokens=max_tokens)

    def find_relevant(self, query_text: str, mem_types: 'List[str] | None' = None, limit: int = 10):
        """Find relevant memories across given mem_types. For now, a simple substring search over selected modules."""
        mem_types = mem_types or list(self.modules.keys())
        results = []
        for mt in mem_types:
            mod = self.modules.get(mt)
            if not mod:
                continue
            results.extend(mod.query(query_text, limit=limit))
        # naive ranking: by created_at descending
        results_sorted = sorted(results, key=lambda r: r.get("created_at", 0), reverse=True)
        return results_sorted[:limit]
