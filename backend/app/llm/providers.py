"""Local-first AI providers.

Provider calls are intentionally local by default. Ollama is called over localhost,
while the mock provider keeps the app usable when no model runtime is installed.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

import requests

from app.core.config import get_settings


class BaseLLMProvider:
    provider_name = "base"

    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": "not_configured",
            "active_model": None,
            "base_url": None,
            "available_models": [],
            "message": "Provider is not configured.",
            "local_only": True,
        }


class MockProvider(BaseLLMProvider):
    provider_name = "mock"

    def generate(self, prompt: str) -> str:
        prompt_l = prompt.lower()
        if "explain the query result" in prompt_l or "result summary" in prompt_l:
            return "The result set has been generated successfully. Review the row counts, groupings, and totals before making a business decision."
        if "explain" in prompt_l:
            return "This query reads data from the referenced tables, applies filters and aggregations if present, and returns a read-only result set."
        if "repair" in prompt_l:
            m = re.search(r"```sql\n(.*?)```", prompt, re.S | re.I)
            candidate = m.group(1).strip() if m else "SELECT * FROM users LIMIT 50"
            return candidate if "limit" in candidate.lower() else candidate + "\nLIMIT 50"
        if "suggest relevant tables" in prompt_l or "respond as json" in prompt_l:
            return json.dumps({
                "suggestions": [
                    {"table_name": "users", "reason": "Contains core user profile and signup fields.", "suggested_columns": ["user_id", "signup_date", "country"]},
                    {"table_name": "transactions", "reason": "Useful for activity, monetary value, and status analysis.", "suggested_columns": ["transaction_id", "user_id", "amount", "status"]},
                ],
                "join_suggestions": ["users.user_id = transactions.user_id"],
            })
        if "join path" in prompt_l:
            return "users.user_id = cards.user_id; users.user_id = transactions.user_id"
        return "SELECT u.user_id, u.full_name, SUM(t.amount) AS total_amount\nFROM users u\nJOIN transactions t ON u.user_id = t.user_id\nGROUP BY u.user_id, u.full_name\nORDER BY total_amount DESC\nLIMIT 20"

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": "mock",
            "active_model": "mock-local-fallback",
            "base_url": None,
            "available_models": ["mock-local-fallback"],
            "message": "Using mock provider. Install/run Ollama for real local AI.",
            "local_only": True,
        }


class OllamaProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model

    def generate(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    def status(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            payload = response.json()
            models = [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
            has_model = self.model in models or any(model.startswith(self.model.split(":")[0]) for model in models)
            return {
                "provider": self.provider_name,
                "status": "connected" if has_model else "error",
                "active_model": self.model,
                "base_url": self.base_url,
                "available_models": models,
                "message": "Ollama is running and the active model is available." if has_model else f"Ollama is running, but model '{self.model}' was not found. Pull it with: ollama pull {self.model}",
                "local_only": True,
            }
        except Exception as exc:
            return {
                "provider": self.provider_name,
                "status": "error",
                "active_model": self.model,
                "base_url": self.base_url,
                "available_models": [],
                "message": f"Could not reach Ollama locally: {exc}",
                "local_only": True,
            }


class HuggingFaceProvider(BaseLLMProvider):
    provider_name = "huggingface-local"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._generator = None

    @property
    def generator(self):
        if self._generator is None:
            from transformers import pipeline  # imported lazily so Ollama installs do not need transformers at startup

            self._generator = pipeline("text2text-generation", model=self.settings.hf_model)
        return self._generator

    def generate(self, prompt: str) -> str:
        output = self.generator(prompt, max_new_tokens=512, do_sample=False)
        return output[0]["generated_text"].strip()

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": "not_configured",
            "active_model": self.settings.hf_model,
            "base_url": None,
            "available_models": [self.settings.hf_model],
            "message": "Hugging Face local mode is configured. Model loads lazily on first use.",
            "local_only": True,
        }


@lru_cache
def get_provider() -> BaseLLMProvider:
    provider = get_settings().ai_provider.lower()
    if provider == "ollama":
        return OllamaProvider()
    if provider in {"hf", "huggingface", "huggingface-local"}:
        return HuggingFaceProvider()
    return MockProvider()
