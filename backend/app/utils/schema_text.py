"""Helpers for rendering schema into prompt-friendly text."""
from app.api.schemas import SchemaResponse


def schema_to_prompt_text(schema: SchemaResponse) -> str:
    lines: list[str] = []
    for table in schema.tables:
        lines.append(f"Table: {table.name}")
        for col in table.columns:
            annotations = []
            if col.is_primary_key:
                annotations.append("PK")
            if col.is_foreign_key and col.references:
                annotations.append(f"FK->{col.references}")
            suffix = f" [{' | '.join(annotations)}]" if annotations else ""
            lines.append(f"  - {col.name}: {col.data_type}{suffix}")
    return "\n".join(lines)
