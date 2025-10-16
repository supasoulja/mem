# Simple JSON-backed Memory Store

This is a local prototype of a memory system for an AI agent. It stores memories per-module as JSON files and provides a simple rule-based memory manager that categorizes and stores chat logs.

Files created:
- `memstore/` - package containing manager, modules, storage.
- `examples/run_example.py` - small script demonstrating ingestion and queries.

Design notes:
- Local JSON storage for simplicity.
- Pluggable `ModelAdapter` to integrate Ollama later.
- Simple keyword-based categorization by default. Replace `ModelAdapter.categorize` with a call to a memory-model for advanced behavior.

Next steps:
- Integrate Ollama for the memory model and chat model separation.
- Add embedding-based semantic search (e.g., sentence-transformers) and/or vector DB.
- Add TTL / pruning policies and more specialized modules.

(This code was mainly made with AI.)