import sys
import threading
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memstore import MemoryManager
from memstore.ollama_adapter import OllamaAdapter


class MemGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Memory Manager Tester")
        self.geometry("900x700")
        self.mgr = MemoryManager(storage_dir=str(ROOT / "memstore" / "data"))
        # try to auto-detect and configure Ollama models on startup
        self.auto_configure_models()

        self.create_widgets()

    def auto_configure_models(self):
        """Try to detect local Ollama models and attach an adapter automatically.

        This makes the program usable for non-technical users: if Gemini/Gemma and
        Qwen models are present, we attach them automatically. Otherwise we proceed
        without an LLM and fallback to local ingestion.
        """
        try:
            adapter = OllamaAdapter()
            models = adapter.list_models()
            if not models:
                # no models found; leave manager unconfigured
                return
            # heuristics to find Gemma and Qwen models
            gemma = None
            qwen = None
            for m in models:
                ml = m.lower()
                if "gemma" in ml or "gemma3" in ml:
                    gemma = m
                if "qwen" in ml:
                    qwen = m
            # fallback: if only one model available, use it for both roles
            if not gemma and models:
                # try to pick a large model for chat heuristically
                gemma = next((m for m in models if "12" in m or "12b" in m), models[0])
            if not qwen and models:
                qwen = next((m for m in models if "qwen" in m), models[0])

            # attach adapter and set model names
            self.mgr.set_llm_adapter(adapter, chat_model=gemma, mem_model=qwen)
            self._detected_models = {"chat": gemma, "memory": qwen}
        except Exception:
            # ignore detection errors; app stays usable without models
            self._detected_models = {}

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Chat input
        ttk.Label(frm, text="Chat / Text to ingest:").pack(anchor=tk.W)
        self.chat_text = scrolledtext.ScrolledText(frm, height=10)
        self.chat_text.pack(fill=tk.X)

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X, pady=6)
        # Single primary action: Process / Ingest
        ttk.Button(btn_row, text="Process / Ingest", command=self._thread(self.ingest_chat)).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Show Modules", command=self._thread(self.show_modules)).pack(side=tk.LEFT, padx=6)
        # status label to inform non-technical users
        # set initial status based on model detection performed at startup
        default_status = "Ready"
        detected = getattr(self, "_detected_models", None)
        if detected and isinstance(detected, dict):
            chat = detected.get("chat") or "(none)"
            memory = detected.get("memory") or "(none)"
            default_status = f"Detected: chat={chat} mem={memory}"
        else:
            default_status = "Ollama not detected or preferred models missing (local ingest only)"
        self.status_var = tk.StringVar(value=default_status)
        ttk.Label(btn_row, textvariable=self.status_var).pack(side=tk.RIGHT)

        # Query section
        qfrm = ttk.LabelFrame(frm, text="Query / Find")
        qfrm.pack(fill=tk.X, pady=6)
        ttk.Label(qfrm, text="Query:").grid(row=0, column=0, sticky=tk.W)
        self.query_entry = ttk.Entry(qfrm, width=80)
        self.query_entry.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(qfrm, text="Target types (comma separated):").grid(row=1, column=0, sticky=tk.W)
        self.types_entry = ttk.Entry(qfrm, width=80)
        self.types_entry.grid(row=1, column=1, padx=6, pady=4)

        ttk.Button(qfrm, text="Find Relevant", command=self._thread(self.find_relevant)).grid(row=2, column=1, sticky=tk.W, pady=6)

        # Module viewer
        mfrm = ttk.LabelFrame(frm, text="Module Viewer")
        mfrm.pack(fill=tk.BOTH, expand=True, pady=6)
        ttk.Label(mfrm, text="Module name:").pack(anchor=tk.W)
        self.module_combo = ttk.Combobox(mfrm, values=list(self.mgr.modules.keys()))
        self.module_combo.pack(fill=tk.X)
        ttk.Button(mfrm, text="Show Module Contents", command=self._thread(self.show_module_contents)).pack(pady=4)

        # Output
        ttk.Label(frm, text="Output:").pack(anchor=tk.W)
        self.output = scrolledtext.ScrolledText(frm, height=18)
        self.output.pack(fill=tk.BOTH, expand=True)

    def _thread(self, func):
        def wrapped():
            t = threading.Thread(target=self._run_with_catch, args=(func,))
            t.daemon = True
            t.start()

        return wrapped

    def _run_with_catch(self, func):
        try:
            func()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def ingest_chat(self):
        text = self.chat_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Info", "No text to ingest.")
            return
        self._log("Processing text...\n")
        self.status_var.set("Processing...")
        try:
            # If a memory model is attached, invoke it and ingest its JSON output automatically
            if getattr(self.mgr, "llm_adapter", None) and getattr(self.mgr, "mem_model_name", None):
                system_prompt = """<memory manager system prompt: produce strict JSON IngestChunk output>"""
                messages = [{"role":"user","content": text}]
                raw = self.mgr.memory_generate(system_prompt, messages, max_tokens=1024)
                # try to ingest structured JSON; fallback to naive ingest if parsing fails
                try:
                    counts = self.mgr.ingest_qwen_json(raw)
                except Exception:
                    # fallback: store by splitting lines
                    counts = self.mgr.ingest_chat_log(text)
            else:
                # no memory model available: use local naive ingestion
                counts = self.mgr.ingest_chat_log(text)
            self._log("Done. Ingest results:\n")
            self._log(json.dumps(counts, indent=2) + "\n")
            self.status_var.set("Idle")
        except Exception as e:
            self.status_var.set("Error")
            messagebox.showerror("Error", str(e))

    def show_modules(self):
        mods = list(self.mgr.modules.keys())
        self._log("Available modules:\n")
        self._log(json.dumps(mods, indent=2) + "\n")

    def find_relevant(self):
        q = self.query_entry.get().strip()
        if not q:
            messagebox.showinfo("Info", "Enter a query.")
            return
        types_raw = self.types_entry.get().strip()
        types = [t.strip() for t in types_raw.split(",") if t.strip()] if types_raw else None
        self._log(f"Finding relevant for query: {q} types={types}\n")
        results = self.mgr.find_relevant(q, mem_types=types, limit=10)
        self._log(json.dumps(results, indent=2) + "\n")

    def detect_models(self):
        """Call the attached Ollama adapter to list available models and display them."""
        try:
            adapter = getattr(self.mgr, "llm_adapter", None)
            if not adapter:
                messagebox.showinfo("Info", "No LLM adapter configured. Attach one using the code or GUI.")
                return
            models = adapter.list_models()
            self._log("Detected models:\n")
            self._log(json.dumps(models, indent=2) + "\n")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def run_memory_model(self):
        """Run the memory model (Qwen) on the current chat text, ingest returned JSON into store.

        This expects the memory model to return the IngestChunk JSON format. We attempt
        to parse and ingest the returned JSON automatically.
        """
        try:
            if not self.mgr.llm_adapter or not self.mgr.mem_model_name:
                messagebox.showinfo("Info", "Configure the LLM adapter and mem model name first.")
                return
            text = self.chat_text.get("1.0", tk.END).strip()
            if not text:
                messagebox.showinfo("Info", "No text to send to memory model.")
                return
            system_prompt = """<memory manager system prompt: produce strict JSON IngestChunk output>"""
            messages = [{"role":"user","content": text}]
            # call memory model
            self._log("Calling memory model...\n")
            raw = self.mgr.memory_generate(system_prompt, messages, max_tokens=1024)
            self._log("Memory model returned:\n")
            self._log(raw + "\n")
            # try to ingest parsed JSON
            counts = self.mgr.ingest_qwen_json(raw)
            self._log("Ingest counts after memory model:\n")
            self._log(json.dumps(counts, indent=2) + "\n")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_module_contents(self):
        mod = self.module_combo.get().strip()
        if not mod:
            messagebox.showinfo("Info", "Select a module.")
            return
        module = self.mgr.modules.get(mod)
        if not module:
            messagebox.showerror("Error", f"Unknown module {mod}")
            return
        items = []
        try:
            items = module.all()
        except Exception:
            # fallback: try to query empty string to fetch all
            items = module.query("", limit=1000)
        self._log(f"Contents of module {mod}:\n")
        self._log(json.dumps(items, indent=2) + "\n")

    def _log(self, text: str):
        self.output.insert(tk.END, text)
        self.output.see(tk.END)


def main():
    app = MemGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
