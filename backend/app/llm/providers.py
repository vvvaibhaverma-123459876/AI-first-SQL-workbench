"""Local-first AI providers.

Provider calls are intentionally local by default. Ollama is called over localhost,
while the mock provider keeps the app usable when no model runtime is installed.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import requests

from app.core.config import get_settings


class BaseLLMProvider:
    provider_name = "base"

    def generate(self, prompt: str, model: str | None = None) -> str:
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

    def generate(self, prompt: str, model: str | None = None) -> str:
        # The mock provider has no real models to route between -- accepts
        # the parameter only so it satisfies the same interface as the real
        # providers and callers don't need to special-case it.
        prompt_l = prompt.lower()
        if "investigation report" in prompt_l:
            return (
                "**Summary:** The primary question and its automatic follow-up were both answered "
                "from the live query results above -- see each step for the exact SQL and row counts. "
                "Nothing in the sample rows stands out as an anomaly beyond what the numbers already show.\n\n"
                "**Suggested next step:** Drill into whichever segment from the follow-up step has the "
                "largest share of rows, to see whether it explains the primary result."
            )
        if "explain the query result" in prompt_l or "result summary" in prompt_l:
            return "The result set has been generated successfully. Review the row counts, groupings, and totals before making a business decision."
        if "explain" in prompt_l:
            return "This query reads data from the referenced tables, applies filters and aggregations if present, and returns a read-only result set."
        if "repair" in prompt_l:
            m = re.search(r"```sql\n(.*?)```", prompt, re.S | re.I)
            candidate = m.group(1).strip() if m else "SELECT * FROM users LIMIT 50"
            return candidate if "limit" in candidate.lower() else candidate + "\nLIMIT 50"
        if "suggest relevant tables" in prompt_l or "respond as json" in prompt_l:
            # Mock has no real semantic understanding of table relevance for an
            # arbitrary question. Deliberately return non-JSON so
            # AIService.suggest_tables() falls through to its honest
            # keyword/schema-based fallback instead of a fabricated, always-
            # identical answer regardless of what was actually asked.
            return "mock provider cannot semantically rank table relevance for this request"
        if "join path" in prompt_l:
            return "users.user_id = cards.user_id; users.user_id = transactions.user_id"
        return self._mock_sql_for(self._business_question(prompt))

    @staticmethod
    def _business_question(prompt: str) -> str:
        """generate_sql's prompt template embeds the *entire* schema ahead of
        the actual question, under a "Business question:" marker — matching
        keywords against the raw prompt would spuriously hit every table/column
        name in the schema dump on every call. Isolate just the question."""
        marker = "business question:"
        idx = prompt.lower().rfind(marker)
        return prompt[idx + len(marker):].lower() if idx != -1 else prompt.lower()

    # Keyword-matched canned SQL for generate-sql / ask prompts. Deliberately
    # covers the README's 5 suggested demo queries (and near-paraphrases) with
    # distinct, schema-accurate SQL each — a single generic fallback here would
    # make every demo question return the same chart, which looks broken rather
    # than "mock". Falls through to the original top-users-by-spend query for
    # anything else, same as before.
    def _mock_sql_for(self, prompt_l: str) -> str:
        if "referral" in prompt_l and ("activation" in prompt_l or "card" in prompt_l):
            return (
                "SELECT r.channel,\n"
                "       COUNT(DISTINCT r.referred_user_id) AS referred_users,\n"
                "       COUNT(DISTINCT CASE WHEN c.status = 'active' THEN c.user_id END) AS activated_users,\n"
                "       ROUND(100.0 * COUNT(DISTINCT CASE WHEN c.status = 'active' THEN c.user_id END)\n"
                "             / NULLIF(COUNT(DISTINCT r.referred_user_id), 0), 1) AS activation_rate_pct\n"
                "FROM referrals r\n"
                "LEFT JOIN cards c ON c.user_id = r.referred_user_id\n"
                "GROUP BY r.channel\n"
                "ORDER BY activation_rate_pct DESC\n"
                "LIMIT 20"
            )
        if "monthly" in prompt_l and "revenue" in prompt_l:
            return (
                "SELECT strftime('%Y-%m', transaction_at) AS month, SUM(amount) AS revenue\n"
                "FROM transactions\n"
                "WHERE status = 'success'\n"
                "GROUP BY month\n"
                "ORDER BY month DESC\n"
                "LIMIT 6"
            )
        if "support ticket" in prompt_l:
            return (
                "SELECT u.user_id, u.full_name,\n"
                "       COUNT(DISTINCT st.ticket_id) AS open_tickets,\n"
                "       COALESCE(SUM(t.amount), 0) AS total_spend\n"
                "FROM users u\n"
                "JOIN support_tickets st ON st.user_id = u.user_id AND st.status = 'open'\n"
                "LEFT JOIN transactions t ON t.user_id = u.user_id AND t.status = 'success'\n"
                "GROUP BY u.user_id, u.full_name\n"
                "ORDER BY total_spend DESC\n"
                "LIMIT 20"
            )
        if "days to first transaction" in prompt_l or ("days" in prompt_l and "first transaction" in prompt_l):
            return (
                "SELECT u.country,\n"
                "       ROUND(AVG(julianday(ft.first_transaction_at) - julianday(u.signup_date)), 1) AS avg_days_to_first_transaction\n"
                "FROM users u\n"
                "JOIN (\n"
                "    SELECT user_id, MIN(transaction_at) AS first_transaction_at\n"
                "    FROM transactions\n"
                "    GROUP BY user_id\n"
                ") ft ON ft.user_id = u.user_id\n"
                "GROUP BY u.country\n"
                "ORDER BY avg_days_to_first_transaction ASC\n"
                "LIMIT 20"
            )
        return (
            "SELECT u.user_id, u.full_name, SUM(t.amount) AS total_amount\n"
            "FROM users u\n"
            "JOIN transactions t ON u.user_id = t.user_id\n"
            "GROUP BY u.user_id, u.full_name\n"
            "ORDER BY total_amount DESC\n"
            "LIMIT 20"
        )

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

    def generate(self, prompt: str, model: str | None = None) -> str:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": model or self.model, "prompt": prompt, "stream": False},
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

    def generate(self, prompt: str, model: str | None = None) -> str:
        # Single fixed pipeline model (self.settings.hf_model) -- no
        # per-task routing support in this provider, unlike Ollama.
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
    provider = get_settings().effective_ai_mode
    if provider == "ollama":
        return OllamaProvider()
    if provider in {"hf", "huggingface", "huggingface-local"}:
        return HuggingFaceProvider()
    return MockProvider()
