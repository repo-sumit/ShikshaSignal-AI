"""Ollama provider (local HTTP endpoint, free + offline).

Defaults to ``http://localhost:11434`` and model ``qwen2.5:7b``. No API key required.
We do NOT probe the server at construction time — that would make tests slow and
brittle. If the server is unreachable when `generate()` is called, the provider
returns a `GenerationResult` with `error` set so the orchestrator can fall back.
"""

from __future__ import annotations

import os
import time
from typing import Mapping

from app.llm._http import HttpError, post_json
from app.llm.base import BaseLLMProvider, GenerationResult, assert_supported
from app.llm.prompts import build_section_prompt


_DEFAULT_BASE_URL: str = "http://localhost:11434"
_DEFAULT_MODEL: str = "qwen2.5:7b"


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (
            base_url if base_url is not None else os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE_URL)
        ).rstrip("/")
        self.model = (
            model if model is not None else os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)
        ).strip() or _DEFAULT_MODEL
        self._timeout = timeout

    def _endpoint(self) -> str:
        return f"{self.base_url}/api/generate"

    @staticmethod
    def _extract_text(payload: Mapping[str, object]) -> str:
        # Ollama /api/generate with stream=false returns {"response": "...", "done": true, ...}.
        resp = payload.get("response")
        if isinstance(resp, str):
            return resp.strip()
        return ""

    def generate(self, section_name: str, facts: Mapping[str, object]) -> GenerationResult:
        assert_supported(section_name)
        prompt = build_section_prompt(section_name, facts)
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        t0 = time.perf_counter()
        try:
            resp = post_json(self._endpoint(), body, timeout=self._timeout)
            text = self._extract_text(resp)
            elapsed = (time.perf_counter() - t0) * 1000
            if not text:
                return GenerationResult(
                    text="",
                    provider_name=self.name,
                    model=self.model,
                    latency_ms=elapsed,
                    error="empty response from Ollama",
                )
            return GenerationResult(text=text, provider_name=self.name, model=self.model, latency_ms=elapsed)
        except HttpError as e:
            return GenerationResult(
                text="",
                provider_name=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error=str(e),
            )
        except Exception as e:
            return GenerationResult(
                text="",
                provider_name=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error=f"{type(e).__name__}: {e}",
            )
