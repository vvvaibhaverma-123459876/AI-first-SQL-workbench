"""Schema-aware local AI services for generation, explanation, repair, and suggestions."""
from __future__ import annotations

import json
import re

from app.api.schemas import ExplainSQLResponse, RepairSQLResponse, SQLExecutionResponse, SuggestTablesResponse, TableSuggestion
from app.llm.providers import MockProvider, get_provider
from app.services.schema_service import SchemaService
from app.utils.schema_text import schema_to_prompt_text


class AIService:
    def __init__(self) -> None:
        self.provider = get_provider()
        self.fallback = MockProvider()
        self.schema_service = SchemaService()

    def status(self) -> dict:
        return self.provider.status()

    def _generate(self, prompt_text: str) -> str:
        try:
            return self.provider.generate(prompt_text)
        except Exception as exc:
            # Do not break the whole workbench if Ollama is not running. The UI will
            # still show provider status, while mock keeps demos/tests functional.
            return self.fallback.generate(f"{prompt_text}\n\nProvider failure fallback reason: {exc}")

    def _schema_text(self) -> str:
        return schema_to_prompt_text(self.schema_service.get_schema())

    def generate_sql(self, prompt: str) -> str:
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
        return self._strip_code_fences(self._generate(prompt_text))

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
        return ExplainSQLResponse(explanation=self._generate(prompt_text))

    def explain_result(self, question: str, sql: str, result: SQLExecutionResponse) -> str:
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
        return self._generate(prompt_text).strip()

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
        repaired = self._strip_code_fences(self._generate(prompt_text))
        return RepairSQLResponse(repaired_sql=repaired, rationale="Generated a safer or syntactically corrected read-only SQL statement.")

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
        raw = self._generate(prompt_text)
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
                return SuggestTablesResponse(suggestions=filtered[:6], join_suggestions=joins[:6])
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
