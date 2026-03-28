"""Doris auto-schema: create and sync table schemas from Ontology definitions."""

from typing import Any

from lingshu.data.connectors.doris import DorisConnector

# Map Ontology property type names to Doris column types.
_TYPE_MAP: dict[str, str] = {
    "string": "VARCHAR(512)",
    "text": "STRING",
    "integer": "BIGINT",
    "float": "DOUBLE",
    "double": "DOUBLE",
    "decimal": "DECIMAL(18, 4)",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "datetime": "DATETIME",
    "timestamp": "DATETIME",
    "json": "JSON",
}


def _doris_type(ontology_type: str) -> str:
    """Resolve an Ontology property type to a Doris column type."""
    return _TYPE_MAP.get(ontology_type.lower(), "STRING")


class DorisSchemaSync:
    """Synchronise Doris table schemas with Ontology definitions."""

    async def ensure_table(
        self,
        doris: DorisConnector,
        table_name: str,
        columns: list[dict[str, Any]],
        *,
        key_columns: list[str] | None = None,
    ) -> str:
        """CREATE TABLE IF NOT EXISTS in Doris.

        Args:
            doris: Active Doris connector.
            table_name: Target table name.
            columns: List of dicts with 'name' and 'type' keys
                     (type is an Ontology property type name).
            key_columns: Optional list of key column names for the
                         Doris DUPLICATE KEY model. Defaults to the
                         first column.

        Returns:
            The DDL statement that was executed.
        """
        col_defs: list[str] = []
        for col in columns:
            col_name = col["name"]
            col_type = _doris_type(col.get("type", "string"))
            col_defs.append(f"  `{col_name}` {col_type}")

        keys = key_columns or ([columns[0]["name"]] if columns else [])
        key_clause = ", ".join(f"`{k}`" for k in keys)

        ddl = (
            f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n"
            + ",\n".join(col_defs)
            + f"\n)\n"
            f"DUPLICATE KEY({key_clause})\n"
            f"DISTRIBUTED BY HASH({key_clause}) BUCKETS 8\n"
            f"PROPERTIES ('replication_num' = '1');"
        )

        pool = await doris._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(ddl)

        return ddl

    async def sync_schema(
        self,
        doris: DorisConnector,
        table_name: str,
        expected_columns: list[dict[str, Any]],
    ) -> list[str]:
        """Add missing columns to an existing Doris table.

        Compares *expected_columns* with the current table schema and
        issues ALTER TABLE ADD COLUMN for any that are missing.

        Args:
            doris: Active Doris connector.
            table_name: Target table name.
            expected_columns: List of dicts with 'name' and 'type' keys.

        Returns:
            List of ALTER statements that were executed (empty if in sync).
        """
        pool = await doris._get_pool()

        # Fetch existing columns from INFORMATION_SCHEMA
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = %s",
                    (table_name,),
                )
                rows = await cur.fetchall()

        existing = {row[0] for row in rows}

        alter_stmts: list[str] = []
        for col in expected_columns:
            if col["name"] not in existing:
                col_type = _doris_type(col.get("type", "string"))
                stmt = (
                    f"ALTER TABLE `{table_name}` "
                    f"ADD COLUMN `{col['name']}` {col_type};"
                )
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(stmt)
                alter_stmts.append(stmt)

        return alter_stmts
