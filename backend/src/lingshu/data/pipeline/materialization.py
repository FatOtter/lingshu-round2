"""Virtual Expression materialization into Doris computed columns."""

from typing import Any

from lingshu.data.connectors.doris import DorisConnector


class MaterializationService:
    """Materialize virtual/computed columns in Doris tables."""

    async def materialize_virtual_column(
        self,
        doris: DorisConnector,
        table_name: str,
        column_name: str,
        expression: str,
    ) -> str:
        """Add a generated (materialized) column to a Doris table.

        Args:
            doris: Active Doris connector.
            table_name: Target table name.
            column_name: Name for the materialized column.
            expression: SQL expression that computes the column value.

        Returns:
            The ALTER TABLE statement that was executed.
        """
        stmt = (
            f"ALTER TABLE `{table_name}` "
            f"ADD COLUMN `{column_name}` VARCHAR(512) "
            f"AS ({expression});"
        )

        pool = await doris._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(stmt)

        return stmt

    async def list_materialized_columns(
        self,
        doris: DorisConnector,
        table_name: str,
    ) -> list[dict[str, Any]]:
        """List materialized/generated columns for a Doris table.

        Returns:
            List of dicts with 'name', 'type', and 'expression' keys.
        """
        pool = await doris._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COLUMN_NAME, COLUMN_TYPE, GENERATION_EXPRESSION "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = %s AND GENERATION_EXPRESSION IS NOT NULL "
                    "AND GENERATION_EXPRESSION != ''",
                    (table_name,),
                )
                rows = await cur.fetchall()

        return [
            {
                "name": row[0],
                "type": row[1],
                "expression": row[2],
            }
            for row in rows
        ]
