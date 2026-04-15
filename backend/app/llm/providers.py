"""AI providers for local LLM integration."""
from __future__ import annotations
import json
import re
from functools import lru_cache
import requests
from transformers import pipeline
from app.core.config import get_settings


class BaseLLMProvider:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class MockProvider(BaseLLMProvider):
    def generate(self, prompt: str) -> str:
        prompt_l = prompt.lower()
        if "explain" in prompt_l:
            return "This query reads data from the referenced tables, applies filters and aggregations if present, and returns a read-only result set."
        if "repair" in prompt_l:
            m = re.search(r"```sql\n(.*?)```", prompt, re.S)
            candidate = m.group(1).strip() if m else "SELECT * FROM users LIMIT 50"
            return candidate if "limit" in candidate.lower() else candidate + "\nLIMIT 50"
        if "suggest relevant tables" in prompt_l:
            return json.dumps({
                "suggestions": [
                    {"table_name": "users", "reason": "Contains core user profile and signup fields.", "suggested_columns": ["user_id", "signup_date", "country"]},
                    {"table_name": "transactions", "reason": "Useful for activity and amount analysis.", "suggested_columns": ["transaction_id", "user_id", "amount", "status"]},
                ],
                "join_suggestions": ["users.user_id = transactions.user_id"]
            })
        if "join path" in prompt_l:
            return "users.user_id = cards.user_id; users.user_id = transactions.user_id"
        return "SELECT u.user_id, u.full_name, SUM(t.amount) AS total_amount\nFROM users u\nJOIN transactions t ON u.user_id = t.user_id\nGROUP BY u.user_id, u.full_name\nORDER BY total_amount DESC\nLIMIT 20"


class OllamaProvider(BaseLLMProvider):
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


class HuggingFaceProvider(BaseLLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.generator = pipeline("text2text-generation", model=settings.hf_model)

    def generate(self, prompt: str) -> str:
        output = self.generator(prompt, max_new_tokens=256, do_sample=False)
        return output[0]["generated_text"].strip()


@lru_cache
def get_provider() -> BaseLLMProvider:
    provider = get_settings().ai_provider.lower()
    if provider == "ollama":
        return OllamaProvider()
    if provider in {"hf", "huggingface"}:
        return HuggingFaceProvider()
    return MockProvider()
