"""Builds a SQLAlchemy engine for each connector type.

Postgres, MySQL, and SQLite are exercised against real infrastructure in
this project's own test suite. Snowflake, BigQuery, and Databricks are
implemented against their standard SQLAlchemy dialects but have not been
verified against a live account -- no credentials for any of the three exist
in this environment. Their driver packages are imported lazily, inside the
branch that needs them, so a deployment that never uses (say) Databricks
never needs that package installed, and a missing package fails with one
clear error at connection-creation time instead of crashing the app at boot.
"""
from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.connections.schemas import (
    BigQueryConfig,
    ConnectionConfig,
    DatabricksConfig,
    MySQLConfig,
    PostgresConfig,
    SnowflakeConfig,
    SQLiteConfig,
)

# sqlglot dialect names line up with connector_type for every type except
# databricks, which sqlglot spells "databricks" too, so this is an identity
# map today -- kept explicit so a future rename on either side doesn't
# silently break statement-type classification in service.py.
SQLGLOT_DIALECT_BY_TYPE = {
    "postgres": "postgres",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "databricks": "databricks",
}


class ConnectorNotInstalledError(Exception):
    def __init__(self, package: str):
        super().__init__(f"This connector needs the '{package}' package, which is not installed on this server.")
        self.package = package


def build_engine(config: ConnectionConfig) -> Engine:
    if isinstance(config, PostgresConfig):
        url = f"postgresql+psycopg2://{quote_plus(config.username)}:{quote_plus(config.password)}@{config.host}:{config.port}/{config.database}"
        return create_engine(url, pool_pre_ping=True)

    if isinstance(config, MySQLConfig):
        try:
            import pymysql  # noqa: F401
        except ImportError as exc:
            raise ConnectorNotInstalledError("pymysql") from exc
        url = f"mysql+pymysql://{quote_plus(config.username)}:{quote_plus(config.password)}@{config.host}:{config.port}/{config.database}"
        return create_engine(url, pool_pre_ping=True)

    if isinstance(config, SQLiteConfig):
        return create_engine(f"sqlite:///{config.path}")

    if isinstance(config, SnowflakeConfig):
        try:
            from snowflake.sqlalchemy import URL as snowflake_url
        except ImportError as exc:
            raise ConnectorNotInstalledError("snowflake-sqlalchemy") from exc
        # snowflake.sqlalchemy.URL handles encoding of special characters in
        # the password/account -- building this string by hand is exactly
        # what Snowflake's own docs warn against.
        url = snowflake_url(
            account=config.account,
            user=config.user,
            password=config.password,
            database=config.database,
            schema=config.schema_name,
            warehouse=config.warehouse,
            role=config.role,
        )
        return create_engine(url)

    if isinstance(config, BigQueryConfig):
        try:
            import sqlalchemy_bigquery  # noqa: F401
        except ImportError as exc:
            raise ConnectorNotInstalledError("sqlalchemy-bigquery") from exc
        import json

        # credentials_info takes the parsed key dict directly -- passing it
        # this way (vs. credentials_path) means the service-account key is
        # never written to disk, where it would otherwise accumulate as a
        # new plaintext-credential file on every single test/schema/query call.
        dataset_part = f"/{config.dataset}" if config.dataset else ""
        url = f"bigquery://{config.project_id}{dataset_part}"
        return create_engine(url, credentials_info=json.loads(config.service_account_json))

    if isinstance(config, DatabricksConfig):
        try:
            import databricks.sqlalchemy  # noqa: F401
        except ImportError as exc:
            raise ConnectorNotInstalledError("databricks-sqlalchemy") from exc
        url = f"databricks://token:{quote_plus(config.access_token)}@{config.server_hostname}?http_path={quote_plus(config.http_path)}"
        if config.catalog:
            url += f"&catalog={quote_plus(config.catalog)}"
        if config.schema_name:
            url += f"&schema={quote_plus(config.schema_name)}"
        return create_engine(url)

    raise ValueError(f"Unhandled connector config type: {type(config)!r}")
