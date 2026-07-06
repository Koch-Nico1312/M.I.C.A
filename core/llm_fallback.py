"""
Local LLM Fallback System using Ollama
Provides offline capability when Gemini API is unavailable
"""

import asyncio
import json
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from config.config_loader import get_config


class OllamaFallback:
    """Ollama-based local LLM fallback"""

    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get("ollama.enabled", False)
        self.base_url = self.config.get("ollama.base_url", "http://localhost:11434")
        self.model = self.config.get("ollama.model", "llama3")
        self.fallback_only = self.config.get("ollama.fallback_only", False)
        self.auto_start = self.config.get("ollama.auto_start", True)
        self.client = None
        self.ollama_process = None

        if self.enabled and OLLAMA_AVAILABLE:
            # Try to start Ollama server if not running
            if self.auto_start:
                self._start_ollama_server()

            try:
                self.client = ollama.Client(host=self.base_url)
                # Test connection
                self.client.list()
                print(f"[Ollama] ✅ Connected to {self.base_url} with model {self.model}")
            except Exception as e:
                print(f"[Ollama] ⚠️ Could not connect: {e}")
                self.enabled = False

    def _start_ollama_server(self) -> None:
        """Start Ollama server if not already running."""
        if not REQUESTS_AVAILABLE:
            print("[Ollama] ⚠️ Requests library not available, cannot check/start server")
            return

        try:
            # Check if Ollama is already running by testing connection
            try:
                response = requests.get(f"{self.base_url}/api/tags", timeout=2)
                if response.status_code == 200:
                    print("[Ollama] ✅ Server already running")
                    return
            except requests.RequestException:
                pass

            # Start Ollama server
            print("[Ollama] 🚀 Starting Ollama server...")

            if sys.platform == "win32":
                # Windows
                self.ollama_process = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                # Linux/Mac
                self.ollama_process = subprocess.Popen(
                    ["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

            # Wait for server to start
            max_wait = 10
            for i in range(max_wait):
                time.sleep(1)
                try:
                    response = requests.get(f"{self.base_url}/api/tags", timeout=1)
                    if response.status_code == 200:
                        print("[Ollama] ✅ Server started successfully")
                        return
                except requests.RequestException:
                    if i < max_wait - 1:
                        print(f"[Ollama] ⏳ Waiting for server to start... ({i+1}/{max_wait})")

            print("[Ollama] ⚠️ Server started but connection test failed")

        except FileNotFoundError:
            print(
                "[Ollama] ❌ Ollama executable not found. Please install Ollama from https://ollama.com"
            )
        except Exception as e:
            print(f"[Ollama] ⚠️ Failed to start server: {e}")

    def shutdown(self) -> None:
        """Shutdown Ollama server if we started it."""
        if self.ollama_process:
            try:
                self.ollama_process.terminate()
                self.ollama_process.wait(timeout=5)
                print("[Ollama] 🔒 Server stopped")
            except Exception as e:
                print(f"[Ollama] ⚠️ Error stopping server: {e}")
            self.ollama_process = None

    def is_available(self) -> bool:
        """Check if Ollama is available"""
        return self.enabled and OLLAMA_AVAILABLE and self.client is not None

    def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        """Generate text using Ollama"""
        if not self.is_available():
            raise RuntimeError("Ollama is not available")

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat(model=self.model, messages=messages)

            return response["message"]["content"]
        except Exception as e:
            print(f"[Ollama] ❌ Generation error: {e}")
            raise

    def generate_tool_call(
        self, prompt: str, available_tools: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Generate a tool call decision using Ollama"""
        if not self.is_available():
            return None

        tools_desc = "\n".join(
            [f"- {tool['name']}: {tool['description']}" for tool in available_tools]
        )

        system_prompt = (
            "You are M.I.C.A (Modular Intern Computer Assistant), a calm, personal, local-first assistant. "
            "You have access to the following tools. "
            "When the user asks for something, decide if a tool is needed. "
            "If so, respond with a JSON object containing 'name' and 'parameters'. "
            "If no tool is needed, respond with a natural text response.\n\n"
            f"Available tools:\n{tools_desc}"
        )

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            response = self.client.chat(model=self.model, messages=messages, format="json")

            result = response["message"]["content"]

            # Try to parse as JSON
            try:
                tool_call = json.loads(result)
                if "name" in tool_call and "parameters" in tool_call:
                    return tool_call
            except json.JSONDecodeError:
                pass

            # Return as text response
            return {"text": result}

        except Exception as e:
            print(f"[Ollama] ❌ Tool call error: {e}")
            return None

    def simple_command(self, command: str) -> str:
        """Execute a simple command using Ollama (for basic system tasks)"""
        if not self.is_available():
            raise RuntimeError("Ollama is not available")

        system_prompt = (
            "You are a helpful assistant for basic computer tasks. "
            "Keep responses very short and direct. "
            "For commands like 'open Chrome', 'turn up volume', etc., "
            "just acknowledge the request briefly."
        )

        return self.generate_text(command, system_prompt)

    async def async_generate_text(self, prompt: str, system_prompt: str = "") -> str:
        """Async version of generate_text"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_text, prompt, system_prompt)

    def __del__(self):
        """Cleanup when instance is destroyed."""
        self.shutdown()


class HybridLLM:
    """Hybrid LLM that uses Gemini by default and falls back to Ollama"""

    def __init__(self):
        self.config = get_config()
        self.ollama = OllamaFallback()
        self.use_ollama = False

    def set_fallback_mode(self, use_fallback: bool):
        """Force use of fallback mode"""
        if use_fallback and self.ollama.is_available():
            self.use_ollama = True
            print("[HybridLLM] Switched to Ollama fallback")
        else:
            self.use_ollama = False
            print("[HybridLLM] Using primary LLM (Gemini)")

    def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        """Generate text using available LLM"""
        if self.use_ollama or (self.ollama.fallback_only and self.ollama.is_available()):
            try:
                return self.ollama.generate_text(prompt, system_prompt)
            except Exception as e:
                print(f"[HybridLLM] Ollama failed: {e}")

        from core.model_runner import get_model_runner

        return get_model_runner().generate_text(
            prompt,
            intent="chat",
            system_instruction=system_prompt,
            use_cache=False,
        )

    def should_use_fallback(self, error: Exception) -> bool:
        """Determine if we should switch to fallback based on error"""
        if not self.ollama.is_available():
            return False

        error_str = str(error).lower()
        fallback_triggers = [
            "api key",
            "quota",
            "rate limit",
            "timeout",
            "connection",
            "network",
            "unavailable",
        ]

        return any(trigger in error_str for trigger in fallback_triggers)


# Global instances
_ollama_fallback: Optional[OllamaFallback] = None
_hybrid_llm: Optional[HybridLLM] = None


def get_ollama_fallback() -> OllamaFallback:
    """Get the global Ollama fallback instance"""
    global _ollama_fallback
    if _ollama_fallback is None:
        _ollama_fallback = OllamaFallback()
    return _ollama_fallback


def get_hybrid_llm() -> HybridLLM:
    """Get the global hybrid LLM instance"""
    global _hybrid_llm
    if _hybrid_llm is None:
        _hybrid_llm = HybridLLM()
    return _hybrid_llm
