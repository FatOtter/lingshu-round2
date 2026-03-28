"""Flink CDC configuration generator for data pipeline jobs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FlinkJobConfig:
    """Immutable Flink SQL job configuration."""

    job_name: str
    sql_statements: list[str]
    properties: dict[str, str]


class CdcConfigGenerator:
    """Generate Flink CDC SQL job configurations.

    These are config generators only — actual Flink execution requires
    a running Flink cluster with the appropriate CDC connectors deployed.
    """

    def __init__(
        self,
        *,
        fdb_connection_string: str = "fdb.cluster",
        iceberg_catalog: str = "nessie_catalog",
        iceberg_warehouse: str = "s3://warehouse/iceberg",
        doris_fe_host: str = "doris-fe",
        doris_fe_port: int = 8030,
        doris_user: str = "root",
        doris_password: str = "",
    ) -> None:
        self._fdb_conn = fdb_connection_string
        self._iceberg_catalog = iceberg_catalog
        self._iceberg_warehouse = iceberg_warehouse
        self._doris_host = doris_fe_host
        self._doris_port = doris_fe_port
        self._doris_user = doris_user
        self._doris_password = doris_password

    def generate_fdb_to_iceberg_job(
        self,
        table_path: str,
        nessie_ref: str = "main",
    ) -> FlinkJobConfig:
        """Generate Flink SQL config to CDC from FoundationDB to Iceberg.

        Args:
            table_path: Logical table path (e.g. 'tenant1.orders').
            nessie_ref: Nessie branch reference for Iceberg catalog.

        Returns:
            FlinkJobConfig with SQL statements for the CDC pipeline.
        """
        safe_name = table_path.replace(".", "_")
        source_table = f"fdb_source_{safe_name}"
        sink_table = f"iceberg_sink_{safe_name}"

        source_ddl = (
            f"CREATE TABLE {source_table} (\n"
            f"  `key` BYTES,\n"
            f"  `value` BYTES,\n"
            f"  `version` BIGINT,\n"
            f"  PRIMARY KEY (`key`) NOT ENFORCED\n"
            f") WITH (\n"
            f"  'connector' = 'foundationdb-cdc',\n"
            f"  'cluster-file' = '{self._fdb_conn}',\n"
            f"  'table-path' = '{table_path}'\n"
            f");"
        )

        sink_ddl = (
            f"CREATE TABLE {sink_table} (\n"
            f"  `key` BYTES,\n"
            f"  `value` BYTES,\n"
            f"  `version` BIGINT,\n"
            f"  PRIMARY KEY (`key`) NOT ENFORCED\n"
            f") WITH (\n"
            f"  'connector' = 'iceberg',\n"
            f"  'catalog-name' = '{self._iceberg_catalog}',\n"
            f"  'catalog-type' = 'nessie',\n"
            f"  'warehouse' = '{self._iceberg_warehouse}',\n"
            f"  'ref' = '{nessie_ref}',\n"
            f"  'table-path' = '{table_path}'\n"
            f");"
        )

        insert_sql = f"INSERT INTO {sink_table} SELECT * FROM {source_table};"

        return FlinkJobConfig(
            job_name=f"fdb-to-iceberg-{safe_name}",
            sql_statements=[source_ddl, sink_ddl, insert_sql],
            properties={
                "execution.checkpointing.interval": "30s",
                "execution.checkpointing.mode": "EXACTLY_ONCE",
                "state.backend": "rocksdb",
                "nessie.ref": nessie_ref,
            },
        )

    def generate_iceberg_to_doris_job(
        self,
        table_path: str,
        doris_table: str,
    ) -> FlinkJobConfig:
        """Generate Flink SQL config to sync Iceberg table into Doris.

        Args:
            table_path: Source Iceberg table path (e.g. 'tenant1.orders').
            doris_table: Target Doris table name (e.g. 'ods_orders').

        Returns:
            FlinkJobConfig with SQL statements for the sync pipeline.
        """
        safe_name = table_path.replace(".", "_")
        source_table = f"iceberg_source_{safe_name}"
        sink_table = f"doris_sink_{doris_table}"

        source_ddl = (
            f"CREATE TABLE {source_table} (\n"
            f"  `key` BYTES,\n"
            f"  `value` BYTES,\n"
            f"  `version` BIGINT\n"
            f") WITH (\n"
            f"  'connector' = 'iceberg',\n"
            f"  'catalog-name' = '{self._iceberg_catalog}',\n"
            f"  'catalog-type' = 'nessie',\n"
            f"  'warehouse' = '{self._iceberg_warehouse}',\n"
            f"  'table-path' = '{table_path}'\n"
            f");"
        )

        sink_ddl = (
            f"CREATE TABLE {sink_table} (\n"
            f"  `key` BYTES,\n"
            f"  `value` BYTES,\n"
            f"  `version` BIGINT\n"
            f") WITH (\n"
            f"  'connector' = 'doris',\n"
            f"  'fenodes' = '{self._doris_host}:{self._doris_port}',\n"
            f"  'table.identifier' = '{doris_table}',\n"
            f"  'username' = '{self._doris_user}',\n"
            f"  'password' = '{self._doris_password}',\n"
            f"  'sink.properties.format' = 'json',\n"
            f"  'sink.properties.read_json_by_line' = 'true'\n"
            f");"
        )

        insert_sql = f"INSERT INTO {sink_table} SELECT * FROM {source_table};"

        return FlinkJobConfig(
            job_name=f"iceberg-to-doris-{safe_name}",
            sql_statements=[source_ddl, sink_ddl, insert_sql],
            properties={
                "execution.checkpointing.interval": "60s",
                "execution.checkpointing.mode": "EXACTLY_ONCE",
                "state.backend": "rocksdb",
            },
        )
