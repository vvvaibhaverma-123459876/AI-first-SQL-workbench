"""SQL validation rules for safe read-only execution."""
import re
import sqlglot
from sqlglot import expressions as exp
from app.api.schemas import SQLValidationResponse
from app.core.config import get_settings

BANNED_PATTERN = re.compile(r"\b(insert|update|delete|drop|alter|truncate|create|attach|pragma|replace|vacuum)\b", re.IGNORECASE)


class SQLValidationService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def validate(self, sql: str, apply_default_limit: bool = True) -> SQLValidationResponse:
        sql = (sql or "").strip()
        errors: list[str] = []
        warnings: list[str] = []

        if not sql:
            return SQLValidationResponse(valid=False, errors=["SQL cannot be empty."])
        if BANNED_PATTERN.search(sql):
            return SQLValidationResponse(valid=False, errors=["Unsafe SQL detected. Only read-only SELECT/WITH queries are allowed."])

        try:
            parsed = sqlglot.parse(sql, read="sqlite")
        except Exception as exc:
            return SQLValidationResponse(valid=False, errors=[f"Malformed SQL: {exc}"])

        if len(parsed) != 1:
            return SQLValidationResponse(valid=False, errors=["Only one SQL statement is allowed."])

        statement = parsed[0]
        if not isinstance(statement, (exp.Select, exp.With, exp.Union, exp.Subquery, exp.CTE)):
            outer_select = getattr(statement, "this", None)
            if not isinstance(outer_select, exp.Select) and statement.key not in {"select", "with", "union"}:
                return SQLValidationResponse(valid=False, errors=["Only SELECT or WITH queries are allowed."])

        normalized_sql = statement.sql(dialect="sqlite", pretty=True)
        if apply_default_limit and " limit " not in normalized_sql.lower():
            normalized_sql = f"{normalized_sql}\nLIMIT {self.settings.default_sql_limit}"
            warnings.append(f"No LIMIT found. Added default LIMIT {self.settings.default_sql_limit}.")

        return SQLValidationResponse(valid=True, normalized_sql=normalized_sql, warnings=warnings, errors=errors)
