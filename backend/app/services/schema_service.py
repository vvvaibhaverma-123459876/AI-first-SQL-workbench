"""Schema inspection and preview services."""
from sqlalchemy import inspect, text
from app.api.schemas import ColumnSchema, SchemaResponse, TablePreviewResponse, TableSchema
from app.core.config import get_settings
from app.db.session import analytics_engine


class SchemaService:
    def get_schema(self) -> SchemaResponse:
        inspector = inspect(analytics_engine)
        tables: list[TableSchema] = []
        for table_name in inspector.get_table_names():
            pk_cols = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []) or [])
            foreign_keys = inspector.get_foreign_keys(table_name)
            fk_map = {}
            for fk in foreign_keys:
                referred_table = fk.get("referred_table")
                referred_columns = fk.get("referred_columns") or []
                for local_col, remote_col in zip(fk.get("constrained_columns", []), referred_columns):
                    fk_map[local_col] = f"{referred_table}.{remote_col}"

            columns = []
            for column in inspector.get_columns(table_name):
                name = column["name"]
                columns.append(
                    ColumnSchema(
                        name=name,
                        data_type=str(column["type"]),
                        is_primary_key=name in pk_cols,
                        is_foreign_key=name in fk_map,
                        references=fk_map.get(name),
                    )
                )
            tables.append(TableSchema(name=table_name, columns=columns))
        return SchemaResponse(tables=sorted(tables, key=lambda t: t.name))

    def preview_table(self, table_name: str, limit: int = 20) -> TablePreviewResponse:
        inspector = inspect(analytics_engine)
        if table_name not in inspector.get_table_names():
            raise ValueError(f"Unknown table: {table_name}")
        sql = text(f'SELECT * FROM "{table_name}" LIMIT :limit')
        with analytics_engine.connect() as conn:
            result = conn.execute(sql, {"limit": limit})
            rows = [dict(row._mapping) for row in result]
            columns = list(result.keys())
        return TablePreviewResponse(table_name=table_name, columns=columns, rows=rows)
