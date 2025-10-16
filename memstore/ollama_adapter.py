from __future__ import annotations
"""Minimal Ollama adapter with HTTP and CLI fallbacks.

This module provides methods to list available models and generate text using a local
Ollama runtime. It prefers HTTP API at the configured endpoint, and if that fails,
falls back to calling the `ollama` CLI if available on PATH.
"""

import json
import subprocess
import shutil
from typing import List, Dict, Any, Optional

try:
    # use urllib to avoid extra deps
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except Exception:
    Request = None
    urlopen = None
    URLError = Exception


class OllamaAdapter:
    """Adapter to call a local Ollama model.

    Methods:
    - list_models(): return a list of available model names
    - generate(): generate raw text output from a model
    - chat_generate(): helper for simple chat-like prompts
    """

    def __init__(self, endpoint: str = "http://localhost:11434"):
        # HTTP endpoint for Ollama local server (if running)
        self.endpoint = endpoint.rstrip("/")

    def list_models(self) -> List[str]:
        """Return list of model names from HTTP endpoint or CLI.

        Tries HTTP /api/models first, then falls back to `ollama ls --json`.
        Returns an empty list if neither method works.
        """
        models: List[str] = []
        # try HTTP
        try:
            if Request is not None:
                url = f"{self.endpoint}/api/models"
                req = Request(url, method="GET")
                with urlopen(req, timeout=5) as resp:
                    body = resp.read().decode("utf-8")
                    try:
                        parsed = json.loads(body)
                        # parsed may be a list of objects or a dict
                        if isinstance(parsed, list):
                            for it in parsed:
                                if isinstance(it, dict) and "model" in it:
                                    models.append(it.get("model"))
                                elif isinstance(it, str):
                                    models.append(it)
                        elif isinstance(parsed, dict):
                            # some endpoints return {models:[...]}
                            for k in ("models", "data"):
                                if k in parsed and isinstance(parsed[k], list):
                                    for it in parsed[k]:
                                        if isinstance(it, dict) and "model" in it:
                                            models.append(it.get("model"))
                                        elif isinstance(it, str):
                                            models.append(it)
                    except Exception:
                        pass
        except Exception:
            pass

        # fallback to CLI
        if not models and shutil.which("ollama"):
            try:
                proc = subprocess.run(["ollama", "ls", "--json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                out = proc.stdout.decode("utf-8")
                parsed = json.loads(out)
                if isinstance(parsed, list):
                    for it in parsed:
                        if isinstance(it, dict) and "name" in it:
                            models.append(it["name"])
                        elif isinstance(it, str):
                            models.append(it)
            except Exception:
                # Older Ollama may not support --json; try simple `ollama ls`
                try:
                    proc = subprocess.run(["ollama", "ls"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                    out = proc.stdout.decode("utf-8")
                    for line in out.splitlines():
                        line = line.strip()
                        if line:
                            models.append(line.split()[0])
                except Exception:
                    pass

        return models

    def _http_generate(self, model: str, prompt: str, max_tokens: int = 1024) -> Optional[str]:
        """Call Ollama HTTP generate endpoint. Returns raw body or None on failure."""
        if Request is None:
            return None
        url = f"{self.endpoint}/api/generate"
        payload = {"model": model, "prompt": prompt, "max_tokens": max_tokens}
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                # try to parse JSON response, else return raw
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        # common fields might be 'text', 'response', or 'result'
                        return parsed.get("text") or parsed.get("response") or json.dumps(parsed)
                    return json.dumps(parsed)
                except Exception:
                    return body
        except URLError:
            return None

    def _cli_generate(self, model: str, prompt: str, max_tokens: int = 1024) -> Optional[str]:
        """Fallback to calling `ollama generate` CLI and returning stdout."""
        if not shutil.which("ollama"):
            return None
        try:
            proc = subprocess.run(["ollama", "generate", model, "--no-stream"], input=prompt.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            out = proc.stdout.decode("utf-8")
            return out if out else None
        except Exception:
            return None

    def generate(self, model: str, prompt: str, max_tokens: int = 1024) -> str:
        """Generate text from model. Tries HTTP, then CLI. Raises RuntimeError if both fail."""
        http_res = self._http_generate(model, prompt, max_tokens=max_tokens)
        if http_res:
            return http_res
        cli_res = self._cli_generate(model, prompt, max_tokens=max_tokens)
        if cli_res:
            return cli_res
        raise RuntimeError("Could not call Ollama via HTTP or CLI. Ensure Ollama is running or 'ollama' is on PATH.")

    def chat_generate(self, model: str, system: str, messages: List[Dict[str, Any]], max_tokens: int = 1024) -> str:
        """Helper that composes a simple prompt from system and messages and calls generate."""
        parts = []
        if system:
            parts.append("[SYSTEM]\n" + system)
        for m in messages:
            role = m.get("role", "user")
            parts.append(f"[{role.upper()}]\n" + m.get("content", ""))
        prompt = "\n\n".join(parts)
        return self.generate(model, prompt, max_tokens=max_tokens)
