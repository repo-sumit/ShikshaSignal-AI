"""Gemini provider (Google Generative Language REST API).

Free-tier friendly: defaults to ``gemini-1.5-flash`` and reads its API key from
``GOOGLE_API_KEY``. Construction fails fast with `MissingCredentialsError` when the
key is absent so the factory can fall back to MockLLM. Call-time HTTP errors are
captured into the returned `GenerationResult` rather than raised, so the orchestrator
can do per-section fallback.
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


_DEFAULT_MODEL: str = "gemini-1.5-flash"
_ENDPOINT_TEMPLATE: str = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 20.0) -> None:
        # Accept either GOOGLE_API_KEY (the spec-canonical name) or GEMINI_API_KEY
        # (commonly used elsewhere); whichever is set first wins.
        env_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
        key = (api_key if api_key is not None else env_key).strip()
        if not key:
            raise MissingCredentialsError(
                "Neither GOOGLE_API_KEY nor GEMINI_API_KEY is set; "
                "cannot construct GeminiProvider."
            )
        self._api_key = key
        self.model = (model if model is not None else os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)).strip() or _DEFAULT_MODEL
        self._timeout = timeout

    def _endpoint(self) -> str:
        return _ENDPOINT_TEMPLATE.format(model=self.model) + f"?key={self._api_key}"

    @staticmethod
    def _extract_text(payload: Mapping[str, object]) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        first = candidates[0] or {}
        content = (first.get("content") if isinstance(first, dict) else {}) or {}
        parts = content.get("parts") or [] if isinstance(content, dict) else []
        chunks: list[str] = []
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                chunks.append(p["text"])
        return "".join(chunks).strip()

    def generate(self, section_name: str, facts: Mapping[str, object]) -> GenerationResult:
        assert_supported(section_name)
        prompt = build_section_prompt(section_name, facts)
        body = {"contents": [{"parts": [{"text": prompt}]}]}
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
                    error="empty response from Gemini",
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
        except Exception as e:  # safety net
            return GenerationResult(
                text="",
                provider_name=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error=f"{type(e).__name__}: {e}",
            )
