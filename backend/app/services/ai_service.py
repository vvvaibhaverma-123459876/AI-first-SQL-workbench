"""Schema-aware local AI services for generation, explanation, repair, and suggestions."""
from __future__ import annotations

import json
import logging
import re

from app.api.schemas import ExplainSQLResponse, RepairSQLResponse, SQLExecutionResponse, SuggestTablesResponse, TableSuggestion
from app.core.config import get_settings
from app.llm.providers import MockProvider, get_provider
from app.services.schema_service import SchemaService
from app.utils.schema_text import schema_to_prompt_text

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self) -> None:
        self.provider = get_provider()
        self.fallback = MockProvider()
        self.schema_service = SchemaService()

    def status(self) -> dict:
        return self.provider.status()

    def _generate(self, prompt_text: str, *, task: str) -> tuple[str, str | None]:
        """Returns (text, fallback_reason). fallback_reason is None on the
        happy path and a human-readable explanation whenever the real
        provider failed and mock output was substituted instead — callers
        must surface this to the user rather than silently swallowing it.

        task is one of generate|explain|repair|suggest|investigate --
        resolved to a concrete model via Settings.model_for_task(), so every
        caller (the legacy v1 endpoints included) gets task-appropriate
        model routing without needing to know or pass a model themselves."""
        model = get_settings().model_for_task(task)
        try:
            return self.provider.generate(prompt_text, model=model), None
        except Exception as exc:
            reason = f"{self.provider.provider_name} provider failed ({exc}); used local mock fallback instead."
            logger.warning("AI provider fallback: %s", reason)
            return self.fallback.generate(f"{prompt_text}\n\nProvider failure fallback reason: {exc}"), reason

    def _schema_text(self) -> str:
        return schema_to_prompt_text(self.schema_service.get_schema())

    def generate_sql(self, prompt: str) -> tuple[str, str | None]:
        prompt_text = f"""
You are an expert SQLite analyst working inside a local-only SQL workbench.
Use only the schema below. Never invent tables or columns.
Return SQL only, no markdown, no commentary.
Rules:
- Use read-only SELECT/WITH SQL only.
- Prefer explicit joins.
- Include a LIMIT unless the user asks for an aggregate-only single-row answer.
- Use SQLite-compatible syntax.

Schema:
{self._schema_text()}

Business question: {prompt}
"""
        raw, fallback_reason = self._generate(prompt_text, task="generate")
        return self._strip_code_fences(raw), fallback_reason

    def explain_sql(self, sql: str) -> ExplainSQLResponse:
        prompt_text = f"""
Explain this SQLite query in plain English for an analyst.
Focus on tables used, joins, filters, grouping, sorting, and returned fields.
Be concise.

SQL:
```sql
{sql}
```
"""
        explanation, fallback_reason = self._generate(prompt_text, task="explain")
        return ExplainSQLResponse(explanation=explanation, provider_fallback=fallback_reason)

    def explain_result(self, question: str, sql: str, result: SQLExecutionResponse) -> tuple[str, str | None]:
        sample_rows = result.rows[:10]
        prompt_text = f"""
Explain the query result for an analyst.
Do not invent facts beyond the rows shown.
Mention row count, obvious top/bottom values, caveats, and one next analysis.

Original question: {question}
SQL:
```sql
{sql}
```
Columns: {result.columns}
Row count: {result.row_count}
Sample rows JSON:
{json.dumps(sample_rows, default=str)}
"""
        text, fallback_reason = self._generate(prompt_text, task="explain")
        return text.strip(), fallback_reason

    def repair_sql(self, sql: str, error_message: str = "") -> RepairSQLResponse:
        prompt_text = f"""
Repair the following SQLite query.
Return SQL only.
Use only the schema below and keep the query read-only.

Schema:
{self._schema_text()}

Error: {error_message}
SQL:
```sql
{sql}
```
"""
        raw, fallback_reason = self._generate(prompt_text, task="repair")
        repaired = self._strip_code_fences(raw)
        if self._normalize_sql(repaired) == self._normalize_sql(sql):
            rationale = "No automatic correction could be generated; the original SQL was returned unchanged. Please review the query manually."
        else:
            rationale = "Generated a safer or syntactically corrected read-only SQL statement."
        return RepairSQLResponse(repaired_sql=repaired, rationale=rationale, provider_fallback=fallback_reason)

    def suggest_tables(self, prompt: str) -> SuggestTablesResponse:
        schema = self.schema_service.get_schema()
        prompt_text = f"""
Suggest relevant tables for this analyst request.
Respond as JSON with keys suggestions and join_suggestions.
Each suggestion should contain table_name, reason, and suggested_columns.
Use only tables and columns from the schema.

Schema:
{schema_to_prompt_text(schema)}
Request: {prompt}
"""
        raw, fallback_reason = self._generate(prompt_text, task="suggest")
        try:
            payload = json.loads(self._extract_json(raw))
            suggestions = [TableSuggestion(**item) for item in payload.get("suggestions", [])]
            joins = payload.get("join_suggestions", [])
            # Validate against actual schema so model output cannot invent names.
            table_map = {table.name: {column.name for column in table.columns} for table in schema.tables}
            filtered: list[TableSuggestion] = []
            for suggestion in suggestions:
                if suggestion.table_name in table_map:
                    suggestion.suggested_columns = [col for col in suggestion.suggested_columns if col in table_map[suggestion.table_name]][:8]
                    filtered.append(suggestion)
            if filtered:
                return SuggestTablesResponse(suggestions=filtered[:6], join_suggestions=joins[:6], provider_fallback=fallback_reason)
        except Exception:
            pass

        keywords = {word.strip("?,.").lower() for word in prompt.split() if len(word) > 3}
        fallback = []
        for table in schema.tables:
            col_names = [c.name for c in table.columns]
            if any(k in table.name.lower() or any(k in c.lower() for c in col_names) for k in keywords):
                fallback.append(TableSuggestion(table_name=table.name, reason="Matched prompt keywords.", suggested_columns=col_names[:5]))
        if not fallback:
            fallback = [TableSuggestion(table_name=table.name, reason="Included as general schema context.", suggested_columns=[c.name for c in table.columns[:5]]) for table in schema.tables[:3]]
        joins = self._heuristic_join_suggestions(schema)
        return SuggestTablesResponse(suggestions=fallback[:5], join_suggestions=joins[:5], provider_fallback=fallback_reason)

    def ask(self, mode: str, prompt: str | None = None, sql: str | None = None, error_message: str | None = None):
        if mode == "generate":
            sql_text, fallback_reason = self.generate_sql(prompt or "")
            return {"sql": sql_text, "provider_fallback": fallback_reason}
        if mode == "explain":
            return self.explain_sql(sql or "").model_dump()
        if mode == "repair":
            return self.repair_sql(sql or "", error_message or "").model_dump()
        if mode == "suggest":
            return self.suggest_tables(prompt or "").model_dump()
        raise ValueError(f"Unsupported mode: {mode}")

    @staticmethod
    def _normalize_sql(text: str) -> str:
        """Whitespace/case/trailing-semicolon-insensitive comparison, and
        also ignores a trailing LIMIT clause: appending a LIMIT does not fix
        the kind of error repair_sql is invoked for (missing table/column,
        syntax error), so it must not by itself count as a "real" repair."""
        normalized = re.sub(r"\s+", " ", (text or "").strip()).rstrip(";").strip().lower()
        return re.sub(r"\s+limit\s+\d+\s*$", "", normalized).strip()

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        text = (text or "").strip()
        match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
        if match:
            return match.group(1).strip()
        text = re.sub(r"^```sql\s*", "", text, flags=re.I)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text)
        return text.strip()

    @staticmethod
    def _extract_json(text: str) -> str:
        match = re.search(r"\{.*\}", text or "", re.S)
        return match.group(0) if match else text

    @staticmethod
    def _heuristic_join_suggestions(schema) -> list[str]:
        joins: list[str] = []
        for table in schema.tables:
            for col in table.columns:
                if col.is_foreign_key and col.references:
                    joins.append(f"{table.name}.{col.name} = {col.references}")
        return joins
