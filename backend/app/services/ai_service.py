"""Schema-aware AI services for generation, explanation, repair, and suggestions."""
from __future__ import annotations
import json
import re
from app.api.schemas import ExplainSQLResponse, RepairSQLResponse, SuggestTablesResponse, TableSuggestion
from app.llm.providers import get_provider
from app.services.schema_service import SchemaService
from app.utils.schema_text import schema_to_prompt_text


class AIService:
    def __init__(self) -> None:
        self.provider = get_provider()
        self.schema_service = SchemaService()

    def _schema_text(self) -> str:
        return schema_to_prompt_text(self.schema_service.get_schema())

    def generate_sql(self, prompt: str) -> str:
        prompt_text = f"""
You are an expert SQLite assistant.
Use only the schema below.
Never invent tables or columns.
Return SQL only, no markdown.
Prefer concise valid SELECT queries.
Schema:
{self._schema_text()}

Question: {prompt}
"""
        return self._strip_code_fences(self.provider.generate(prompt_text))

    def explain_sql(self, sql: str) -> ExplainSQLResponse:
        prompt_text = f"""
Explain this SQLite query in plain English for an analyst.
Focus on tables used, joins, filters, grouping, sorting, and returned fields.

SQL:
```sql
{sql}
```
"""
        return ExplainSQLResponse(explanation=self.provider.generate(prompt_text))

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
        repaired = self._strip_code_fences(self.provider.generate(prompt_text))
        return RepairSQLResponse(repaired_sql=repaired, rationale="Generated a safer or syntactically corrected read-only SQL statement.")

    def suggest_tables(self, prompt: str) -> SuggestTablesResponse:
        schema = self.schema_service.get_schema()
        prompt_text = f"""
Suggest relevant tables for this analyst request.
Respond as JSON with keys suggestions and join_suggestions.
Each suggestion should contain table_name, reason, and suggested_columns.
Schema:
{schema_to_prompt_text(schema)}
Request: {prompt}
"""
        raw = self.provider.generate(prompt_text)
        try:
            payload = json.loads(self._extract_json(raw))
            suggestions = [TableSuggestion(**item) for item in payload.get("suggestions", [])]
            joins = payload.get("join_suggestions", [])
            return SuggestTablesResponse(suggestions=suggestions, join_suggestions=joins)
        except Exception:
            keywords = {word.strip("?,.").lower() for word in prompt.split() if len(word) > 3}
            fallback = []
            for table in schema.tables:
                col_names = [c.name for c in table.columns]
                if any(k in table.name.lower() or any(k in c.lower() for c in col_names) for k in keywords):
                    fallback.append(TableSuggestion(table_name=table.name, reason="Matched prompt keywords.", suggested_columns=col_names[:5]))
            joins = self._heuristic_join_suggestions(schema)
            return SuggestTablesResponse(suggestions=fallback[:5], join_suggestions=joins[:5])

    def ask(self, mode: str, prompt: str | None = None, sql: str | None = None, error_message: str | None = None):
        if mode == "generate":
            return {"sql": self.generate_sql(prompt or "")}
        if mode == "explain":
            return self.explain_sql(sql or "").model_dump()
        if mode == "repair":
            return self.repair_sql(sql or "", error_message or "").model_dump()
        if mode == "suggest":
            return self.suggest_tables(prompt or "").model_dump()
        raise ValueError(f"Unsupported mode: {mode}")

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```sql\s*", "", text, flags=re.I)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text)
        return text.strip()

    @staticmethod
    def _extract_json(text: str) -> str:
        match = re.search(r"\{.*\}", text, re.S)
        return match.group(0) if match else text

    @staticmethod
    def _heuristic_join_suggestions(schema) -> list[str]:
        joins: list[str] = []
        for table in schema.tables:
            for col in table.columns:
                if col.is_foreign_key and col.references:
                    joins.append(f"{table.name}.{col.name} = {col.references}")
        return joins
