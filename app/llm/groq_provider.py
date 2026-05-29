"""Groq provider (OpenAI-compatible /chat/completions endpoint).

Free-tier friendly: defaults to ``llama-3.1-8b-instant`` and reads its API key from
``GROQ_API_KEY``. Construction fails fast with `MissingCredentialsError` when the key
is absent so the factory can fall back to MockLLM. Call-time HTTP errors are captured
into the returned `GenerationResult` rather than raised.
"""

from __future__ import annotations

import os
import time
from typing import Mapping

from app.llm._http import HttpError, post_json
from app.llm.base import (
    BaseLLMProvider,
    GenerationResult,
    MissingCredentialsError,
    assert_supported,
)
from app.llm.prompts import build_section_prompt


_DEFAULT_MODEL: str = "llama-3.1-8b-instant"
_ENDPOINT: str = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(BaseLLMProvider):
    name = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 20.0) -> None:
        key = (api_key if api_key is not None else os.getenv("GROQ_API_KEY", "")).strip()
        if not key:
            raise MissingCredentialsError(
                "GROQ_API_KEY is not set; cannot construct GroqProvider."
            )
        self._api_key = key
        self.model = (model if model is not None else os.getenv("GROQ_MODEL", _DEFAULT_MODEL)).strip() or _DEFAULT_MODEL
        self._timeout = timeout

    @staticmethod
    def _extract_text(payload: Mapping[str, object]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = (first.get("message") if isinstance(first, dict) else {}) or {}
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"].strip()
        return ""

    def generate(self, section_name: str, facts: Mapping[str, object]) -> GenerationResult:
        assert_supported(section_name)
        prompt = build_section_prompt(section_name, facts)
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a grounded technical writer for government education "
                        "programmes. Strictly obey the rules at the top of every user "
                        "message; never invent numbers."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        t0 = time.perf_counter()
        try:
            resp = post_json(_ENDPOINT, body, headers=headers, timeout=self._timeout)
            text = self._extract_text(resp)
            elapsed = (time.perf_counter() - t0) * 1000
            if not text:
                return GenerationResult(
                    text="",
                    provider_name=self.name,
                    model=self.model,
                    latency_ms=elapsed,
                    error="empty response from Groq",
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
